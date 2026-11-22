"""
OpenFlow Main Application Entry
Integrates:
- Audio recording (sounddevice)
- Local speech recognition:
    * English: faster-whisper tiny.en
    * Hindi: Udgam Labs Shruti-ONNX (Devanagari script, English words preserved)
    * Hinglish: Udgam Labs Shruti-ONNX + Roman Hinglish transliteration pipeline
- Personal corrections dictionary (FreeWispr pattern with local JSON storage)
- Resilient Global hotkey listener (Win32 low-level hook + async fallback)
- Focused application text injection (pyautogui/pyperclip)
- Modern desktop UI (pywebview / Edge WebView2)
- Diagnostic local logging (%APPDATA%/OpenFlow/logs/)
"""
import os
import sys
import time
import threading
import webview
import json

def _patch_pywebview_interop():
    """
    Ensures pywebview on Windows x64 can locate required Edge Chromium / WebView2 interop DLLs
    when packaged in PyInstaller frozen environments (onedir or onefile).
    Prevents FileNotFoundError on foreign architectures (e.g. 'win-arm64') while ensuring
    the correct host architecture native runtime (win-x64) is resolved and placed on PATH.
    """
    try:
        import webview.util
        import platform

        orig_interop = webview.util.interop_dll_path

        def resilient_interop_dll_path(dll_name: str) -> str:
            # 1. Try original resolution
            try:
                return orig_interop(dll_name)
            except FileNotFoundError:
                pass

            # 2. Search PyInstaller frozen and relative bundle paths
            meipass = getattr(sys, "_MEIPASS", None)
            app_dir = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))
            search_roots = [r for r in [meipass, app_dir, os.path.join(app_dir, "_internal")] if r and os.path.isdir(r)]

            candidates = []
            for root in search_roots:
                # Direct named folder (e.g. root/win-x64, root/win-arm64)
                candidates.append(os.path.join(root, dll_name))
                # Standard webview hierarchy
                candidates.append(os.path.join(root, "webview", "lib", "runtimes", dll_name, "native"))
                candidates.append(os.path.join(root, "runtimes", dll_name, "native"))
                # Direct dll in lib or root
                candidates.append(os.path.join(root, "webview", "lib", dll_name))
                candidates.append(os.path.join(root, "lib", dll_name))
                candidates.append(os.path.join(root, dll_name))

            for candidate in candidates:
                if os.path.exists(candidate):
                    return candidate

            # 3. Architecture-aware fallback for foreign architecture directory queries:
            # edgechromium.py loops over ('win-arm64', 'win-x64', 'win-x86'). On an x64 machine,
            # if an unneeded foreign architecture directory is omitted, fall back to host architecture (win-x64).
            machine = platform.machine().lower()
            host_arch = "win-x64" if machine in ("amd64", "x86_64") else ("win-arm64" if "arm" in machine else "win-x86")
            if dll_name in ("win-arm64", "win-x64", "win-x86") and dll_name != host_arch:
                try:
                    return resilient_interop_dll_path(host_arch)
                except FileNotFoundError:
                    pass

            raise FileNotFoundError(f"Cannot find {dll_name}")

        webview.util.interop_dll_path = resilient_interop_dll_path
    except Exception as e:
        print(f"[OpenFlow] Notice setting up pywebview interop: {e}")

_patch_pywebview_interop()

from engine_audio import AudioRecorder
from engine_transcription import TranscriptionEngine
from engine_shruti import ShrutiTranscriptionEngine
from engine_transliterate import transliterate_to_hinglish
from engine_corrections import apply_corrections
from engine_injector import insert_text
from engine_hotkey import GlobalHotkeyManager
from language_config import LanguageMode, get_language_profile
from utils_paths import get_asset_path
from utils_logger import log_info, log_warning, log_error
from utils_single_instance import SingleInstanceGuard
from ui_overlay import FloatingOverlay

class OpenFlowBridge:
    """
    Dedicated JavaScript API bridge exposed to the pywebview frontend.
    Exposes only the deliberate public methods required by index.html:
    - toggle_recording()
    - clear_transcript()
    - get_language_mode()
    - set_language_mode(mode)
    - get_available_languages()
    - get_hotkey_status()

    All internal controller references are private (prefixed with '_')
    so that pywebview's recursive bridge inspection never crawls the
    underlying Whisper/Shruti models, audio streams, locks, or native window / WebView2 objects.
    """
    def __init__(self, api: "OpenFlowAPI"):
        self._api = api

    def toggle_recording(self):
        """Toggle audio recording on or off."""
        self._api.toggle_recording()

    def clear_transcript(self):
        """Clear transcription history and reset UI."""
        return self._api.clear_transcript()

    def get_language_mode(self):
        """Get currently selected dictation mode."""
        return self._api.get_language_mode()

    def set_language_mode(self, mode: str):
        """Switch dictation mode between 'en', 'hi', and 'hinglish'."""
        return self._api.set_language_mode(mode)

    def get_available_languages(self):
        """Return metadata for available dictation languages."""
        return [
            {"id": "en", "name": "English", "badge": "tiny.en"},
            {"id": "hi", "name": "Hindi (हिन्दी)", "badge": "Shruti Devanagari"},
            {"id": "hinglish", "name": "Hinglish", "badge": "Shruti Roman"},
        ]

    def get_hotkey_status(self):
        """Returns whether the global shortcut is successfully registered and active."""
        return {
            "active": self._api.is_hotkey_active(),
            "shortcut": "Ctrl+Shift+Space"
        }


class OpenFlowAPI:
    def __init__(self):
        log_info("[OpenFlow] Initializing OpenFlow application controller...")
        self.overlay = FloatingOverlay()
        self.recorder = AudioRecorder(sample_rate=16000, level_callback=self.overlay.update_audio_level)
        self.transcriber_en = TranscriptionEngine(model_size="tiny.en")
        self.transcriber_shruti = ShrutiTranscriptionEngine()
        self._current_mode = LanguageMode.ENGLISH.value
        self._window = None
        self.is_processing = False
        self.history = []
        self._current_snippet = ""
        self._target_hwnd = 0
        self._active_session_mode = self._current_mode
        self._lock = threading.Lock()
        self.hotkey_manager = None
        
        # Preload the default English Whisper model in background
        threading.Thread(target=self._preload_default_model, daemon=True).start()

    def _preload_default_model(self):
        log_info("[OpenFlow] Preloading default English whisper model in background...")
        self.transcriber_en.load()
        log_info("[OpenFlow] English whisper model loaded and ready.")

    def is_hotkey_active(self) -> bool:
        return self.hotkey_manager is not None and self.hotkey_manager.is_registered

    def get_language_mode(self) -> str:
        return self._current_mode

    def set_language_mode(self, mode: str) -> bool:
        with self._lock:
            if mode in (LanguageMode.ENGLISH.value, LanguageMode.HINDI.value, LanguageMode.HINGLISH.value):
                self._current_mode = mode
                log_info(f"[OpenFlow] Active language mode switched to: {mode}")
                # Preload Shruti in background if switching to Hindi or Hinglish
                if mode in (LanguageMode.HINDI.value, LanguageMode.HINGLISH.value) and not self.transcriber_shruti.is_loaded():
                    threading.Thread(target=self.transcriber_shruti.load, daemon=True).start()
                return True
            return False

    def set_window(self, window):
        self._window = window

    def _evaluate_js(self, script: str):
        """Safely evaluates JavaScript in the webview window with UI-thread marshaling and error handling."""
        if self._window is not None:
            try:
                self._window.evaluate_js(script)
            except Exception as e:
                log_warning(f"[OpenFlow] Warning: Failed to evaluate JavaScript on UI: {e}")

    def toggle_recording(self):
        with self._lock:
            if self.is_processing:
                log_info("[OpenFlow] Ignoring toggle_recording while processing audio.")
                return
            
            if not self.recorder.is_recording:
                # Freeze current language mode for this entire recording session
                self._active_session_mode = self._current_mode
                log_info(f"[OpenFlow] Starting dictation recording (SessionMode={self._active_session_mode})...")
                # Capture current foreground window before starting dictation
                try:
                    import ctypes
                    user32 = ctypes.windll.user32
                    self._target_hwnd = user32.GetForegroundWindow()
                except Exception:
                    self._target_hwnd = 0

                # Start recording with error handling
                try:
                    self.recorder.start()
                    self.overlay.show_listening(target_hwnd=self._target_hwnd)
                    self._evaluate_js("window.onRecordingStarted && window.onRecordingStarted();")
                    log_info(f"[OpenFlow] Recording active (target_hwnd={self._target_hwnd}, Mode={self._active_session_mode})")
                except Exception as e:
                    log_error("[OpenFlow] Failed to start microphone", e)
                    self.overlay.show_error("⚠ Mic Error")
                    err_msg = json.dumps(f"Mic error: {str(e)}")
                    self._evaluate_js(f"window.onRecordingError && window.onRecordingError({err_msg});")
            else:
                log_info(f"[OpenFlow] Stopping dictation recording (SessionMode={self._active_session_mode})...")
                self.is_processing = True
                t_stop_initiated = time.perf_counter()
                t_audio_fin_start = time.perf_counter()
                audio_data = self.recorder.stop()
                t_audio_fin = time.perf_counter() - t_audio_fin_start
                rec_duration = self.recorder.get_last_duration()
                target_hwnd = self._target_hwnd
                session_mode = self._active_session_mode
                self.overlay.show_transcribing()
                self._evaluate_js("window.onProcessingStarted && window.onProcessingStarted();")
                
                # Run transcription in worker thread with timing context
                threading.Thread(
                    target=self._process_audio,
                    args=(audio_data, t_stop_initiated, t_audio_fin, rec_duration, target_hwnd, session_mode),
                    daemon=True
                ).start()

    def _process_audio(self, audio_data, t_stop: float = 0.0, t_audio_fin: float = 0.0,
                       rec_duration: float = 0.0, target_hwnd: int = 0, mode: str = "en"):
        try:
            if audio_data is None or len(audio_data) == 0:
                log_warning("[OpenFlow] No audio frames captured, skipping transcription.")
                self._current_snippet = ""
                self.overlay.show_error("⚠ No audio")
                self._evaluate_js("window.onTranscriptionComplete && window.onTranscriptionComplete('');")
                return

            profile = get_language_profile(mode)
            engine_type = profile.get("engine", "english")
            t_stt_start = time.perf_counter()

            log_info(f"[OpenFlow STT Dispatch] Mode='{mode}' | Engine='{engine_type}' | AudioLength={len(audio_data)/16000:.2f}s")

            if engine_type == "english":
                # Mode 1: English (faster-whisper tiny.en)
                raw_text = self.transcriber_en.transcribe(audio_data, language="en")
            elif engine_type == "shruti":
                # Mode 2 & 3: Shruti ASR engine
                shruti_lang = profile.get("language")
                raw_text = self.transcriber_shruti.transcribe(
                    audio_data,
                    language=shruti_lang,
                    beams=profile.get("beams", 5)
                )
            else:
                raw_text = self.transcriber_en.transcribe(audio_data, language="en")

            t_stt_end = time.perf_counter()
            stt_duration = t_stt_end - t_stt_start

            # Step 2: Hinglish Roman transliteration (if configured for the mode)
            if profile.get("transliterate", False):
                t_trans_start = time.perf_counter()
                processed_text = transliterate_to_hinglish(raw_text)
                t_trans_duration = time.perf_counter() - t_trans_start
                log_info(f"[OpenFlow Transliterate] Converted Devanagari to Roman Hinglish ({t_trans_duration*1000:.1f}ms)")
            else:
                processed_text = raw_text
                t_trans_duration = 0.0

            # Step 3: Apply personal dictionary corrections
            final_snippet = apply_corrections(processed_text)
            if final_snippet != processed_text:
                log_info("[OpenFlow Corrections] Applied personal dictionary replacements.")

            # Store only the current recording's distinct snippet
            self._current_snippet = final_snippet or ""

            # Text injection timing - ONLY the current snippet is passed to the injector
            t_inj_duration = 0.0
            inject_ok = False
            if self._current_snippet:
                self.history.append(self._current_snippet)
                t_inj_start = time.perf_counter()
                try:
                    inject_ok = insert_text(self._current_snippet, target_hwnd=target_hwnd)
                except Exception as paste_err:
                    log_warning(f"[OpenFlow] Warning during text insertion: {paste_err}")
                t_inj_duration = time.perf_counter() - t_inj_start

            total_post_record = (time.perf_counter() - t_stop) if t_stop > 0 else 0.0
            log_info(
                f"[OpenFlow Latency Breakdown | Mode={mode}] "
                f"Audio Finalization: {t_audio_fin*1000:.1f}ms | "
                f"Rec: {rec_duration:.2f}s | "
                f"STT ({engine_type}): {stt_duration:.2f}s | "
                f"Translit: {t_trans_duration*1000:.1f}ms | "
                f"Inject: {t_inj_duration:.2f}s | "
                f"Total Post-Record Latency: {total_post_record:.2f}s"
            )

            if inject_ok:
                self.overlay.show_success("✓ Text inserted")
            elif self._current_snippet:
                self.overlay.show_error("⚠ Paste failed")
            else:
                self.overlay.show_error("⚠ No speech detected")

            safe_text = json.dumps(self._current_snippet)
            self._evaluate_js(f"window.onTranscriptionComplete && window.onTranscriptionComplete({safe_text});")
        except Exception as e:
            log_error("[OpenFlow] Error during transcription pipeline", e)
            self._current_snippet = ""
            self.overlay.show_error("⚠ Error")
            self._evaluate_js("window.onTranscriptionComplete && window.onTranscriptionComplete('');")
        finally:
            self.is_processing = False

    def clear_transcript(self):
        self.history = []
        self._current_snippet = ""
        log_info("[OpenFlow] Cleared transcription history.")
        return True


def setup_global_hotkey(api: OpenFlowAPI):
    """
    Sets up the global Ctrl+Shift+Space listener via GlobalHotkeyManager.
    """
    def on_hotkey():
        log_info("[OpenFlow] Hotkey callback invoked -> Toggling dictation")
        api.toggle_recording()

    try:
        api.hotkey_manager = GlobalHotkeyManager(on_hotkey)
        success = api.hotkey_manager.start()
        if success:
            log_info("[OpenFlow] Global hotkey Ctrl+Shift+Space is actively registered and listening.")
        else:
            log_warning("[OpenFlow] Warning: Could not register low-level global hotkey. UI fallback control is active.")
    except Exception as e:
        log_error("[OpenFlow] Exception setting up global hotkey", e)


def cleanup_resources(api: OpenFlowAPI):
    """
    Cleanly and selectively releases OpenFlow's registered hotkey listener,
    audio stream, and overlay.
    """
    log_info("[OpenFlow] Cleaning up application resources...")
    if api.hotkey_manager is not None:
        try:
            api.hotkey_manager.stop()
        except Exception as e:
            log_warning(f"[OpenFlow] Warning while stopping hotkey manager: {e}")
        finally:
            api.hotkey_manager = None

    if api.recorder.is_recording:
        try:
            api.recorder.stop()
            log_info("[OpenFlow] Stopped active recording stream.")
        except Exception as e:
            log_warning(f"[OpenFlow] Warning while stopping audio stream: {e}")

    if hasattr(api, "overlay") and api.overlay is not None:
        try:
            api.overlay.close()
            log_info("[OpenFlow] Closed system-wide status overlay.")
        except Exception as e:
            log_warning(f"[OpenFlow] Warning while closing overlay: {e}")


def main():
    # Single-instance enforcement: prevent competing processes from fighting over audio/hotkeys/CPU
    guard = SingleInstanceGuard()
    if not guard.acquire():
        # Another instance is already active and was brought to foreground
        sys.exit(0)

    log_info("=" * 60)
    log_info(f"Starting OpenFlow Desktop Application v1.1.0 (PID={os.getpid()})")
    log_info("=" * 60)
    api = OpenFlowAPI()
    bridge = OpenFlowBridge(api)
    try:
        setup_global_hotkey(api)

        html_path = get_asset_path("index.html")
        log_info(f"[OpenFlow] Loading frontend UI from: {html_path}")

        window = webview.create_window(
            title="OpenFlow",
            url=html_path,
            js_api=bridge,
            width=580,
            height=690,
            resizable=True,
            focus=False,
            min_size=(460, 520)
        )
        api.set_window(window)

        # Push *live* listener health to the UI (not just "hook installed once")
        def health_monitor():
            last = None
            while True:
                time.sleep(2.0)
                try:
                    status = api.is_hotkey_active()
                    if status != last:
                        log_info(f"[OpenFlow] Hotkey health changed -> active={status} "
                                 f"details={api.hotkey_manager.health() if api.hotkey_manager else None}")
                        last = status
                    api._evaluate_js(f"window.onHotkeyStatusChanged && window.onHotkeyStatusChanged({str(status).lower()});")
                except Exception as e:
                    log_error("[OpenFlow] health monitor error", e)

        def on_loaded():
            threading.Thread(target=health_monitor, name="HotkeyHealth", daemon=True).start()

        window.events.loaded += on_loaded

        # Start native webview application
        webview.start(debug=False)
    finally:
        cleanup_resources(api)
        guard.release()
        log_info("[OpenFlow] Application terminated.")


if __name__ == "__main__":
    main()

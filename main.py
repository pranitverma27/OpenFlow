"""
OpenFlow Main Application Entry
Integrates:
- Audio recording (sounddevice)
- Local speech recognition (faster-whisper)
- Global hotkey listener (keyboard)
- Focused application text injection (pyautogui/pyperclip)
- Modern desktop UI (pywebview / Edge WebView2)
"""
import os
import sys
import time
import threading
import keyboard
import webview
import json

from engine_audio import AudioRecorder
from engine_transcription import TranscriptionEngine
from engine_injector import insert_text
from utils_paths import get_asset_path
from ui_overlay import FloatingOverlay

class OpenFlowBridge:
    """
    Dedicated JavaScript API bridge exposed to the pywebview frontend.
    Exposes only the deliberate public methods required by index.html:
    - toggle_recording()
    - clear_transcript()

    All internal controller references are private (prefixed with '_')
    so that pywebview's recursive bridge inspection never crawls the
    underlying Whisper model, audio streams, locks, or native window / WebView2 objects.
    """
    def __init__(self, api: "OpenFlowAPI"):
        self._api = api

    def toggle_recording(self):
        """Toggle audio recording on or off."""
        self._api.toggle_recording()

    def clear_transcript(self):
        """Clear transcription history and reset UI."""
        return self._api.clear_transcript()


class OpenFlowAPI:
    def __init__(self):
        self.overlay = FloatingOverlay()
        self.recorder = AudioRecorder(sample_rate=16000, level_callback=self.overlay.update_audio_level)
        self.transcriber = TranscriptionEngine(model_size="tiny.en")
        self._window = None
        self.is_processing = False
        self.history = []
        self._current_snippet = ""
        self._target_hwnd = 0
        self._lock = threading.Lock()
        self.hotkey_handler = None
        
        # Preload the Whisper model in background
        threading.Thread(target=self._preload_model, daemon=True).start()

    def _preload_model(self):
        print("[OpenFlow] Preloading whisper model...")
        self.transcriber.load()
        print("[OpenFlow] Model loaded and ready.")

    def set_window(self, window):
        self._window = window

    def _evaluate_js(self, script: str):
        """Safely evaluates JavaScript in the webview window with UI-thread marshaling and error handling."""
        if self._window is not None:
            try:
                self._window.evaluate_js(script)
            except Exception as e:
                print(f"[OpenFlow] Warning: Failed to evaluate JavaScript on UI: {e}")

    def toggle_recording(self):
        with self._lock:
            if self.is_processing:
                return
            
            if not self.recorder.is_recording:
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
                except Exception as e:
                    print(f"[OpenFlow] Failed to start microphone: {e}")
                    self.overlay.show_error("⚠ Mic Error")
                    err_msg = json.dumps(f"Mic error: {str(e)}")
                    self._evaluate_js(f"window.onRecordingError && window.onRecordingError({err_msg});")
            else:
                # Stop recording and process
                self.is_processing = True
                t_stop_initiated = time.perf_counter()
                t_audio_fin_start = time.perf_counter()
                audio_data = self.recorder.stop()
                t_audio_fin = time.perf_counter() - t_audio_fin_start
                rec_duration = self.recorder.get_last_duration()
                target_hwnd = self._target_hwnd
                self.overlay.show_transcribing()
                self._evaluate_js("window.onProcessingStarted && window.onProcessingStarted();")
                
                # Run transcription in worker thread with timing context
                threading.Thread(
                    target=self._process_audio,
                    args=(audio_data, t_stop_initiated, t_audio_fin, rec_duration, target_hwnd),
                    daemon=True
                ).start()

    def _process_audio(self, audio_data, t_stop: float = 0.0, t_audio_fin: float = 0.0, rec_duration: float = 0.0, target_hwnd: int = 0):
        try:
            if audio_data is None or len(audio_data) == 0:
                print("[OpenFlow] No audio frames captured, skipping transcription.")
                self._current_snippet = ""
                self.overlay.show_error("⚠ No audio")
                self._evaluate_js("window.onTranscriptionComplete && window.onTranscriptionComplete('');")
                return

            t_stt_start = time.perf_counter()
            snippet = self.transcriber.transcribe(audio_data)
            t_stt_end = time.perf_counter()
            stt_duration = t_stt_end - t_stt_start

            # Store only the current recording's distinct snippet
            self._current_snippet = snippet or ""

            # Text injection timing - ONLY the current snippet is passed to the injector
            t_inj_duration = 0.0
            inject_ok = False
            if self._current_snippet:
                self.history.append(self._current_snippet)
                t_inj_start = time.perf_counter()
                try:
                    inject_ok = insert_text(self._current_snippet, target_hwnd=target_hwnd)
                except Exception as paste_err:
                    print(f"[{time.strftime('%H:%M:%S')}] [OpenFlow] Warning during text insertion: {paste_err}")
                t_inj_duration = time.perf_counter() - t_inj_start

            total_post_record = (time.perf_counter() - t_stop) if t_stop > 0 else 0.0
            print(
                f"[{time.strftime('%H:%M:%S')}] [OpenFlow Latency Breakdown] "
                f"Audio Finalization: {t_audio_fin*1000:.1f}ms | "
                f"Rec: {rec_duration:.2f}s | "
                f"STT (Whisper): {stt_duration:.2f}s | "
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
            print(f"[OpenFlow] Error during transcription: {e}")
            self._current_snippet = ""
            self.overlay.show_error("⚠ Error")
            self._evaluate_js("window.onTranscriptionComplete && window.onTranscriptionComplete('');")
        finally:
            self.is_processing = False

    def clear_transcript(self):
        self.history = []
        self._current_snippet = ""
        return True


def setup_global_hotkey(api: OpenFlowAPI):
    # Hotkey: Ctrl+Shift+Space to toggle dictation anywhere
    def on_hotkey():
        print("[OpenFlow] Hotkey triggered: Ctrl+Shift+Space")
        api.toggle_recording()

    try:
        # Retain specific hotkey handle for targeted unhooking
        api.hotkey_handler = keyboard.add_hotkey("ctrl+shift+space", on_hotkey)
        print("[OpenFlow] Registered global hotkey: Ctrl+Shift+Space")
    except Exception as e:
        print(f"[OpenFlow] Warning: Could not register global hotkey: {e}")


def cleanup_resources(api: OpenFlowAPI):
    """
    Cleanly and selectively releases only OpenFlow's registered hotkey
    and audio resources without disturbing other hotkeys or external components.
    """
    print("[OpenFlow] Cleaning up application resources...")
    if api.hotkey_handler is not None:
        try:
            keyboard.remove_hotkey(api.hotkey_handler)
            print("[OpenFlow] Unhooked OpenFlow global hotkey.")
        except Exception as e:
            print(f"[OpenFlow] Warning while unhooking hotkey: {e}")
        finally:
            api.hotkey_handler = None

    if api.recorder.is_recording:
        try:
            api.recorder.stop()
            print("[OpenFlow] Stopped active recording stream.")
        except Exception as e:
            print(f"[OpenFlow] Warning while stopping audio stream: {e}")

    if hasattr(api, "overlay") and api.overlay is not None:
        try:
            api.overlay.close()
            print("[OpenFlow] Closed system-wide status overlay.")
        except Exception as e:
            print(f"[OpenFlow] Warning while closing overlay: {e}")


def main():
    api = OpenFlowAPI()
    bridge = OpenFlowBridge(api)
    try:
        setup_global_hotkey(api)

        html_path = get_asset_path("index.html")
        print(f"[OpenFlow] Loading frontend UI from: {html_path}")

        window = webview.create_window(
            title="OpenFlow",
            url=html_path,
            js_api=bridge,
            width=580,
            height=660,
            resizable=True,
            focus=False,
            min_size=(460, 520)
        )
        api.set_window(window)

        # Start native webview application
        webview.start(debug=False)
    finally:
        # Guaranteed targeted cleanup even if webview creation or runtime throws
        cleanup_resources(api)


if __name__ == "__main__":
    main()

# OpenFlow — Privacy-First Offline Dictation for Windows

OpenFlow is an open-source, privacy-first, 100% offline desktop dictation application for Windows 10 and 11. It enables system-wide voice typing into any active application via a global keyboard shortcut (`Ctrl + Shift + Space`) with zero cloud dependencies, zero external APIs, and complete local processing.

---

## Releases & Version History

OpenFlow maintains a clear historical distinction between major development milestones:

### Version 1.0.0 — English-Only Baseline
* **Baseline Commit**: `6de5f58` (Tagged `v1.0.0-english-stable`)
* **Core Engine**: `faster-whisper` (`tiny.en` model, INT8 quantized via CTranslate2).
* **Capabilities**: System-wide English voice dictation, desktop webview UI, floating status overlay, and clipboard-preserving active window injection.

### Version 2.0.0 — Multilingual Release (English, Hindi & Hinglish)
* **Branch**: `feature/hindi-hinglish` / `v2.0.0`
* **Release Tag**: `v2.0.0`
* **Tri-Mode Speech Engine**:
  1. **English**: Optimized `faster-whisper` (`tiny.en`, INT8) with greedy decoding (`beam_size=1`, no autoregressive conditioning, multi-threaded CPU execution).
  2. **Hindi (Devanagari)**: Local `Udgam Labs Shruti-ONNX` acoustic frontend, encoder, and decoder running via ONNX Runtime CPU execution provider. Accurately transcribes Hindi speech while keeping English vocabulary in Latin script.
  3. **Hinglish (Romanized Hindi)**: Seamless combination of Shruti speech recognition and an offline phoneme-preserving Devanagari-to-Roman transliteration engine with configurable regex corrections.
* **Production Enhancements**:
  * **Global Hotkey Manager (`engine_hotkey.py`)**: Dedicated Win32 low-level keyboard hook (`WH_KEYBOARD_LL`) with a background Windows message loop, unhook watchdog, and periodic polling fallback.
  * **Single-Instance Protection (`utils_single_instance.py`)**: Windows named mutex (`Local\OpenFlow_SingleInstance_Mutex_v110`) preventing duplicate background processes from competing for audio devices or CPU threads, automatically bringing the existing window to the foreground.
  * **Per-User Windows Installer (`installer_build/setup_installer.py`)**: Standalone self-contained installer registering under `HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\OpenFlow`, appearing in Windows 11 Settings > Installed apps without requiring administrator privileges.
  * **PyWebView EdgeChromium Robustness**: Multi-architecture WebView2 loader discovery (`win-x64`, `win-arm64`, `win-x86`) and dynamic fallback preventing `FileNotFoundError` during launch.

---

## Architectural Breakdown

```
OpenFlow/
├── main.py                     # Application entry point, PyWebView bridge, hotkey binding, lifecycle management
├── index.html                  # Glassmorphic dark-mode UI with tri-mode switcher and live hotkey indicator
├── ui_overlay.py               # Top-level floating recording and processing indicator overlay
├── OpenFlow.spec               # PyInstaller multi-architecture build specification
├── OpenFlow-Setup.spec         # Standalone self-extracting installer build specification
│
├── Speech Engines
│   ├── engine_audio.py         # Thread-safe PortAudio microphone capture (16kHz mono float32)
│   ├── engine_transcription.py # Low-latency English transcription (faster-whisper / CTranslate2)
│   ├── engine_shruti.py        # Offline Hindi code-switched ASR (Udgam Labs Shruti ONNX)
│   ├── engine_transliterate.py # Devanagari-to-Roman phonetic transliterator for Hinglish
│   ├── engine_corrections.py   # Personal vocabulary and phonetic correction dictionary
│   └── language_config.py      # Language mode definitions (English, Hindi, Hinglish)
│
├── Windows System Integration
│   ├── engine_hotkey.py        # Win32 low-level keyboard hook (WH_KEYBOARD_LL) + polling watchdog
│   ├── engine_injector.py      # Active window text paste via Win32 keybd_event with clipboard restore
│   ├── utils_single_instance.py# Win32 named mutex single-instance guard
│   ├── utils_paths.py          # Offline model directory and writable %APPDATA% path resolution
│   └── utils_logger.py         # Rotating diagnostic logger (%APPDATA%/OpenFlow/logs/openflow.log)
│
├── Installer & Distribution
│   └── installer_build/
│       └── setup_installer.py  # Per-user Windows installer & uninstaller generator
│
└── Models (Local Offline)
    ├── models/tiny.en/         # CTranslate2 INT8 English Whisper model
    └── models/shruti-hi/       # Shruti ONNX acoustic, encoder, decoder models & vocabulary
```

---

## How to Run from Source

### Prerequisites
* Windows 10 or Windows 11 (64-bit x64)
* Python 3.10 to 3.13 (64-bit)

### Installation
```powershell
# Clone the repository
git clone https://github.com/pranitverma27/OpenFlow.git
cd OpenFlow

# Install dependencies
pip install -r requirements.txt # or install faster-whisper, sounddevice, pywebview, onnxruntime, keyboard, pyperclip
```

### Launch
```powershell
python main.py
```

---

## Keyboard Controls & Usage

1. Press **`Ctrl + Shift + Space`** anywhere in Windows to begin dictation.
2. Speak naturally in English, Hindi, or Hinglish (depending on selected mode).
3. Press **`Ctrl + Shift + Space`** again to end dictation.
4. OpenFlow automatically processes your voice locally and injects the text into your active window.

---

## Building Standalone Binaries

### Building Portable Executable
```powershell
pyinstaller --noconfirm --clean OpenFlow.spec
```
Outputs the portable standalone application to `dist/OpenFlow/OpenFlow.exe`.

### Building Standalone Installer
```powershell
pyinstaller --noconfirm --clean OpenFlow-Setup.spec
```
Outputs `dist/OpenFlow-Setup.exe`.

---

## Licenses & Attributions

OpenFlow is licensed under the **MIT License**.

Third-party models and libraries:
* **Udgam Labs Shruti**: Apache License 2.0 (Copyright (c) 2024 Udgam Labs)
* **faster-whisper**: MIT License (Guillaume Klein, SYSTRAN)
* **CTranslate2**: MIT License (OpenNMT / SYSTRAN)
* **ONNX Runtime**: MIT License (Microsoft Corporation)
* **FreeWispr**: MIT License (x26prakhar)

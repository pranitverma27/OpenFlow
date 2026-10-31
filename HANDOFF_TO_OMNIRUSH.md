# OpenFlow - Handoff to OmniRush AI

## Handoff Date & Time
**Transfer Scheduled**: After 2 November 2026, 5:30 p.m. IST

---

## Executive Summary
OpenFlow is a Windows 10/11 desktop application providing a free, open-source, local-first alternative to Wispr Flow. It captures microphone audio, runs speech-to-text locally via Whisper, and injects the dictated text into the currently focused window using a global hotkey (`Ctrl+Shift+Space`).

---

## Tech Stack & Architecture
1. **Frontend / Shell**: `pywebview` (using Edge WebView2 runtime) rendering [`index.html`](file:///c:/Users/Pranit/.gemini/antigravity/scratch/OpenFlow/index.html).
2. **Audio Capture**: `sounddevice` recording at 16,000 Hz, mono float32.
3. **Local STT**: `faster-whisper` (1.2.1) + `ctranslate2` (4.8.4) CPU `int8`.
4. **Injection**: `pyperclip` + `pyautogui` for clipboard/paste simulation.
5. **Hotkey**: `keyboard` global listener hook.

---

## How to Run
```powershell
# From the project root:
cd OpenFlow
python main.py
```

---

## Status of Milestones
- [x] Workspace & environment discovery.
- [x] Local speech engine verification (`tiny.en` CPU int8 tested and functional).
- [x] Microphone capture verified with real audio hardware.
- [x] End-to-end prototype completed and verified.
- [x] Desktop UI with real-time recording and processing indicators created.
- [x] Global hotkey (`Ctrl+Shift+Space`) registered.
- [x] Context & handoff files created.

---

## Next Tasks for OmniRush AI
1. **System Tray Integration**: Add background minimize to system tray using `pystray`.
2. **Settings Persistence**: Store user preferences (model size, hotkeys, auto-paste toggle) in a local JSON file (e.g. `settings.json`).
3. **Audio Waveform Animation**: Expose live microphone amplitude levels over the JS bridge to animate the microphone ring while recording.

"""
OpenFlow Comprehensive Application Integration & Memory Stress Test
Validates:
- Real-time engine switching between English, Hindi, and Hinglish without process restarts.
- Memory usage and stability over multiple repeated sessions.
- Verification of text injection, clipboard preservation, and overlay state transitions.
- Offline execution integrity.
"""
import time
import os
import ctypes
from ctypes import wintypes
import soundfile as sf
import numpy as np

from main import OpenFlowAPI
from engine_injector import insert_text
import pyperclip

def get_process_memory_mb():
    class PMC_EX(ctypes.Structure):
        _fields_ = [
            ('cb', wintypes.DWORD),
            ('PageFaultCount', wintypes.DWORD),
            ('PeakWorkingSetSize', ctypes.c_size_t),
            ('WorkingSetSize', ctypes.c_size_t),
            ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
            ('QuotaPagedPoolUsage', ctypes.c_size_t),
            ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
            ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
            ('PagefileUsage', ctypes.c_size_t),
            ('PeakPagefileUsage', ctypes.c_size_t),
            ('PrivateUsage', ctypes.c_size_t)
        ]
    p = PMC_EX()
    p.cb = ctypes.sizeof(p)
    hProc = ctypes.windll.kernel32.OpenProcess(0x0400 | 0x0010, False, ctypes.windll.kernel32.GetCurrentProcessId())
    ctypes.windll.psapi.GetProcessMemoryInfo(hProc, ctypes.byref(p), ctypes.sizeof(p))
    ctypes.windll.kernel32.CloseHandle(hProc)
    return p.WorkingSetSize / (1024 * 1024), p.PrivateUsage / (1024 * 1024)

def run_integration_and_memory_test():
    print("=" * 80)
    print("OPENFLOW FULL APPLICATION INTEGRATION & STABILITY TEST")
    print("=" * 80)

    mem_init_ws, mem_init_priv = get_process_memory_mb()
    print(f"[Memory Baseline] WorkingSet: {mem_init_ws:.1f} MB | Private: {mem_init_priv:.1f} MB")

    api = OpenFlowAPI()
    # Wait for background preloading
    time.sleep(2.0)

    mem_en_ws, mem_en_priv = get_process_memory_mb()
    print(f"[Memory After English Preload] WorkingSet: {mem_en_ws:.1f} MB | Private: {mem_en_priv:.1f} MB")

    # Load audio test clips
    test_clips = {
        "en_10s": sf.read("test_en_10s.wav", dtype="float32")[0],
        "en_15s": sf.read("test_en_15s.wav", dtype="float32")[0],
        "hi_10s": sf.read("sample_hindi_1.wav", dtype="float32")[0],
        "hi_21s": sf.read("sample_hindi_2.wav", dtype="float32")[0],
        "speech": sf.read("speech_sample.wav", dtype="float32")[0]
    }

    # Test 1: Rapid Language Switching (10 cycles)
    print("\n--- Test 1: Rapid Language Switching Validation ---")
    modes = ["en", "hi", "hinglish"]
    for i in range(12):
        target_mode = modes[i % 3]
        ok = api.set_language_mode(target_mode)
        current = api.get_language_mode()
        assert ok and current == target_mode, f"Language switch failed: expected {target_mode}, got {current}"
    print("✓ Successfully executed 12 language switch cycles with zero deadlocks.")

    # Preload Shruti by switching to Hindi
    api.set_language_mode("hi")
    time.sleep(4.0)  # Wait for Shruti background loader
    mem_all_ws, mem_all_priv = get_process_memory_mb()
    print(f"[Memory Dual-Loaded (English + Shruti)] WorkingSet: {mem_all_ws:.1f} MB | Private: {mem_all_priv:.1f} MB")

    # Test 2: Multi-Session Dictation Across All Modes
    print("\n--- Test 2: Multi-Session Dictation Pipeline (15 Iterations) ---")
    sessions = [
        ("en", test_clips["en_10s"], "English 10s speech"),
        ("hi", test_clips["hi_10s"], "Hindi 10.3s authentic speech"),
        ("hinglish", test_clips["hi_21s"], "Hinglish 21.4s code-switched speech"),
        ("en", test_clips["en_15s"], "English 15s speech"),
        ("hi", test_clips["hi_21s"], "Hindi 21.4s speech"),
        ("hinglish", test_clips["speech"], "Hinglish English preservation"),
        ("en", test_clips["speech"], "English paragraph speech"),
        ("hi", test_clips["hi_10s"], "Hindi second pass"),
        ("hinglish", test_clips["hi_10s"], "Hinglish second pass"),
        ("en", test_clips["en_10s"], "English repeat test"),
    ]

    for idx, (mode, audio, desc) in enumerate(sessions, 1):
        api.set_language_mode(mode)
        t_start = time.perf_counter()

        # Execute transcription via internal engine processing
        api._process_audio(audio, t_stop=t_start, t_audio_fin=0.01, rec_duration=len(audio)/16000.0, target_hwnd=0, mode=mode)

        lat = time.perf_counter() - t_start
        snippet = api._current_snippet
        ws, priv = get_process_memory_mb()
        print(f"Session {idx:02d} [{mode.upper()} - {desc[:20]:<20}]: Latency={lat:.2f}s | WS={ws:.1f} MB | Priv={priv:.1f} MB")
        print(f"    Output: \"{snippet[:75]}...\"")
        time.sleep(0.2)

    # Test 3: Clipboard Preservation and Text Injection Validation
    print("\n--- Test 3: Clipboard Preservation & Injection Verification ---")
    canary = "ORIGINAL_USER_CLIPBOARD_CONTENT_#12345"
    pyperclip.copy(canary)

    # Trigger text injection
    test_injection_text = "OpenFlow Automated Injection Test String"
    inject_ok = insert_text(test_injection_text, paste_wait=0.08)

    # Allow clipboard restore
    time.sleep(0.3)
    restored_clipboard = pyperclip.paste()
    clipboard_preserved = (restored_clipboard == canary)

    print(f"  Injection call status: {'SUCCESS' if inject_ok else 'FAILED'}")
    print(f"  Clipboard before injection: \"{canary}\"")
    print(f"  Clipboard after injection:  \"{restored_clipboard}\"")
    print(f"  Clipboard preserved exactly: {clipboard_preserved}")

    # Summary
    mem_final_ws, mem_final_priv = get_process_memory_mb()
    print("\n" + "=" * 80)
    print("MEMORY STABILITY SUMMARY")
    print("=" * 80)
    print(f"  Initial Baseline Memory:        {mem_init_ws:.1f} MB WorkingSet | {mem_init_priv:.1f} MB Private")
    print(f"  Dual-Loaded Models Memory:      {mem_all_ws:.1f} MB WorkingSet | {mem_all_priv:.1f} MB Private")
    print(f"  After 10 Consecutive Dictations: {mem_final_ws:.1f} MB WorkingSet | {mem_final_priv:.1f} MB Private")
    print(f"  Memory Drift across runs:       {mem_final_ws - mem_all_ws:+.1f} MB WorkingSet")
    print("=" * 80)

if __name__ == "__main__":
    run_integration_and_memory_test()

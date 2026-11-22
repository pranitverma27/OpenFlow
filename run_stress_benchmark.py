"""
OpenFlow Comprehensive Stress Test Suite (45 Trials)
Measures latency across 3 Modes x 3 Durations x 5 Trials = 45 Trials:
- Modes: English (tiny.en), Hindi (tiny multilingual 'hi'), Hinglish (tiny multilingual 'hinglish')
- Durations: 5s, 10s, 15s
- Per Trial Metrics:
  - Recording duration
  - STT time
  - Postprocessing time
  - Injection time
  - Total post-record latency
"""
import os
import sys
import time
import json
import numpy as np
import soundfile as sf
from typing import Dict, Any, List

# Add workspace to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine_transcription import TranscriptionEngine
from engine_multilingual import MultilingualTranscriptionEngine
from language_config import LanguageMode
from engine_injector import insert_text

def load_audio_as_16k(file_path: str) -> np.ndarray:
    data, sr = sf.read(file_path)
    if data.ndim > 1:
        data = data.mean(axis=1)
    if sr != 16000:
        new_len = int(round(len(data) * 16000.0 / float(sr)))
        indices = np.linspace(0, len(data) - 1, new_len)
        data = np.interp(indices, np.arange(len(data)), data)
    return data.astype(np.float32)

def run_stress_test():
    print("=" * 80)
    print("OPENFLOW STRESS TEST SUITE — 45 LIVE TRIALS")
    print("Testing English, Hindi, Hinglish at 5s, 10s, 15s (5 trials each)")
    print("Strict acceptance limit: < 5.00 seconds")
    print("=" * 80)

    # 1. Initialize Engines
    print("\n[Init] Preloading English engine (tiny.en)...")
    en_engine = TranscriptionEngine()
    en_engine.load()

    print("[Init] Preloading Multilingual engine (tiny)...")
    multi_engine = MultilingualTranscriptionEngine()
    multi_engine.load()
    print("[Init] Both engines loaded and ready.\n")

    # Define test combinations
    combinations = [
        # (mode_key, label, duration_label, filename)
        ("en", "English", "5s", "test_en_5s.wav"),
        ("en", "English", "10s", "test_en_10s.wav"),
        ("en", "English", "15s", "test_en_15s.wav"),
        ("hi", "Hindi", "5s", "test_hi_5s.wav"),
        ("hi", "Hindi", "10s", "test_hi_10s.wav"),
        ("hi", "Hindi", "15s", "test_hi_15s.wav"),
        ("hinglish", "Hinglish", "5s", "test_hgl_5s.wav"),
        ("hinglish", "Hinglish", "10s", "test_hgl_10s.wav"),
        ("hinglish", "Hinglish", "15s", "test_hgl_15s.wav"),
    ]

    results: List[Dict[str, Any]] = []

    for mode_key, label, dur_label, audio_file in combinations:
        print(f"\n--- Testing {label} ({dur_label}) from {audio_file} ---")
        audio_data = load_audio_as_16k(audio_file)
        rec_duration = len(audio_data) / 16000.0

        for trial in range(1, 6):
            t_stop_initiated = time.perf_counter()

            # 1. Preprocessing / Audio finalize simulation (audio already in memory, convert/verify)
            t_pre_start = time.perf_counter()
            audio_buffer = np.ascontiguousarray(audio_data, dtype=np.float32)
            t_pre = time.perf_counter() - t_pre_start

            # 2. STT (Whisper Inference + VAD)
            t_stt_start = time.perf_counter()
            if mode_key == "en":
                transcript = en_engine.transcribe(audio_buffer)
            else:
                transcript = multi_engine.transcribe(audio_buffer, mode=mode_key)
            t_stt = time.perf_counter() - t_stt_start

            # 3. Postprocessing (text clean, history update)
            t_post_start = time.perf_counter()
            text_snippet = transcript.strip() if transcript else ""
            t_post = time.perf_counter() - t_post_start

            # 4. Injection (Clipboard copy + Win32 SendInput Ctrl+V + clipboard restore)
            t_inj_start = time.perf_counter()
            inject_ok = False
            if text_snippet:
                inject_ok = insert_text(text_snippet, target_hwnd=0)
            t_inj = time.perf_counter() - t_inj_start

            # Total Post-Record Latency
            t_total = time.perf_counter() - t_stop_initiated
            passed = t_total < 5.00

            trial_record = {
                "mode": mode_key,
                "mode_label": label,
                "duration_target": dur_label,
                "trial": trial,
                "rec_duration": round(rec_duration, 2),
                "pre_time_ms": round(t_pre * 1000, 2),
                "stt_time_s": round(t_stt, 3),
                "post_time_ms": round(t_post * 1000, 2),
                "inj_time_s": round(t_inj, 3),
                "total_latency_s": round(t_total, 3),
                "passed": passed,
                "text_preview": text_snippet[:50] + ("..." if len(text_snippet) > 50 else ""),
            }
            results.append(trial_record)

            status_str = "PASS" if passed else "FAILED"
            print(
                f"  Trial {trial}/5 | Rec: {rec_duration:.2f}s | "
                f"STT: {t_stt:.2f}s | Inj: {t_inj:.2f}s | "
                f"Total: {t_total:.2f}s [{status_str}] | "
                f"Text: {trial_record['text_preview']}"
            )

    # Save output to JSON
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stress_test_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\nAll 45 trials completed. Results saved to: {output_path}")

if __name__ == "__main__":
    run_stress_test()


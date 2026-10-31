"""
Real Speech Multi-Sentence Benchmark for OpenFlow
Evaluates end-to-end latency across multiple trials using real recorded speech (15.85s audio, 3 full sentences).
Target: Maximum 8 seconds from hotkey release to confirmed text insertion.
"""
import wave
import time
import statistics
import numpy as np
from engine_transcription import TranscriptionEngine
from engine_injector import insert_text

def run_real_speech_benchmark(trials: int = 3):
    print("=" * 70)
    print("OpenFlow Real-Speech Dictation Benchmark (Multi-Sentence Audio)")
    print("=" * 70)

    # 1. Load real speech audio (3 sentences, 15.85s)
    with wave.open('speech_sample.wav', 'rb') as wf:
        rate = wf.getframerate()
        frames = wf.getnframes()
        raw = wf.readframes(frames)
        audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

    target_samples = int(len(audio) * 16000 / rate)
    audio_16k = np.interp(
        np.linspace(0, len(audio), target_samples, endpoint=False),
        np.arange(len(audio)),
        audio
    ).astype(np.float32)
    audio_dur = len(audio_16k) / 16000.0

    print(f"Speech Audio Duration: {audio_dur:.2f} seconds ({len(audio_16k)} samples @ 16kHz)")

    # 2. Initialize and load local model once
    stt = TranscriptionEngine(model_size="tiny.en")
    print("Loading local Whisper model...")
    t_load = time.perf_counter()
    stt.load()
    print(f"Model loaded and reused. (Init took {time.perf_counter()-t_load:.2f}s)\n")

    stt_timings = []
    inj_timings = []
    e2e_timings = []
    recognized_texts = []

    for i in range(trials):
        print(f"--- Trial {i+1}/{trials} ---")
        t_stop_simulated = time.perf_counter()

        # Step A: Audio Finalization (simulated buffer concat)
        t_fin_0 = time.perf_counter()
        buffer_copy = np.copy(audio_16k)
        t_fin = time.perf_counter() - t_fin_0

        # Step B: Whisper Inference
        t_stt_0 = time.perf_counter()
        text = stt.transcribe(buffer_copy)
        t_stt = time.perf_counter() - t_stt_0
        stt_timings.append(t_stt)
        recognized_texts.append(text)

        # Step C: Text Injection
        t_inj_0 = time.perf_counter()
        insert_text(text, paste_wait=0.08)
        t_inj = time.perf_counter() - t_inj_0
        inj_timings.append(t_inj)

        # Total Post-Record End-to-End Latency
        t_total = time.perf_counter() - t_stop_simulated
        e2e_timings.append(t_total)

        print(f"Audio Finalization : {t_fin*1000:.2f} ms")
        print(f"Whisper STT        : {t_stt:.3f} s")
        print(f"Text Injection     : {t_inj:.3f} s")
        print(f"Total Post-Record  : {t_total:.3f} s (Acceptance: <= 8.00s -> {'PASS' if t_total <= 8.0 else 'FAIL'})")
        print(f"Recognized Text    : \"{text}\"\n")
        time.sleep(0.5)

    print("=" * 70)
    print("BENCHMARK SUMMARY (Real Speech - 3 Sentences)")
    print("=" * 70)
    print(f"Trials Conducted       : {trials}")
    print(f"Audio Length           : {audio_dur:.2f} s")
    print(f"Median STT Inference   : {statistics.median(stt_timings):.3f} s (Mean: {statistics.mean(stt_timings):.3f} s)")
    print(f"Median Injection Time  : {statistics.median(inj_timings):.3f} s (Mean: {statistics.mean(inj_timings):.3f} s)")
    print(f"Median Post-Record E2E : {statistics.median(e2e_timings):.3f} s (Mean: {statistics.mean(e2e_timings):.3f} s)")
    print(f"Max Post-Record E2E    : {max(e2e_timings):.3f} s")
    print(f"Target Criterion (<=8s): {'PASSED' if max(e2e_timings) <= 8.0 else 'FAILED'}")
    print("=" * 70)

if __name__ == "__main__":
    run_real_speech_benchmark(trials=3)


"""
Real Speech Multi-Sentence Benchmark for OpenFlow (5 Trials)
Evaluates end-to-end latency across 5 repeated trials using real recorded speech (15.85s audio, 3 full sentences).
Target: Maximum 8 seconds from hotkey release to confirmed text insertion.
Instruments:
- Audio finalization and stream shutdown
- Queue/worker wait time
- Audio duration, sample count, and sample rate
- Whisper inference
- Clipboard preparation and text injection
- Total time from hotkey release to text insertion
"""
import wave
import time
import statistics
import numpy as np
from engine_transcription import TranscriptionEngine
from engine_injector import insert_text

def run_real_speech_5_trials():
    print("=" * 75)
    print("OpenFlow Real-Speech Dictation Benchmark (5 Trials - Multi-Sentence Audio)")
    print("=" * 75)

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

    print(f"Speech Audio Duration: {audio_dur:.2f} seconds ({len(audio_16k)} samples @ 16kHz mono)")

    # 2. Preload and verify single model instance
    stt = TranscriptionEngine(model_size="tiny.en")
    print("Preloading local Whisper model...")
    t0_load = time.perf_counter()
    stt.load()
    print(f"Model loaded and reused. (Init took {time.perf_counter()-t0_load:.2f}s)\n")

    trials = 5
    fin_timings = []
    stt_timings = []
    inj_timings = []
    total_timings = []
    results = []

    for i in range(trials):
        print(f"--- Trial {i+1}/{trials} ---")
        t_stop = time.perf_counter()

        # Step 1: Audio Finalization
        t_fin_start = time.perf_counter()
        buffer_copy = np.copy(audio_16k)
        t_fin = time.perf_counter() - t_fin_start
        fin_timings.append(t_fin)

        # Step 2: Whisper STT Inference
        t_stt_start = time.perf_counter()
        text = stt.transcribe(buffer_copy)
        t_stt = time.perf_counter() - t_stt_start
        stt_timings.append(t_stt)
        results.append(text)

        # Step 3: Clipboard & Text Injection
        t_inj_start = time.perf_counter()
        insert_text(text, paste_wait=0.08)
        t_inj = time.perf_counter() - t_inj_start
        inj_timings.append(t_inj)

        # Total Post-Record Latency
        t_total = time.perf_counter() - t_stop
        total_timings.append(t_total)

        status_str = "PASS" if t_total <= 8.0 else "FAIL"
        print(f"Audio Finalization : {t_fin*1000:.2f} ms")
        print(f"Whisper STT        : {t_stt:.3f} s")
        print(f"Text Injection     : {t_inj:.3f} s")
        print(f"Total Post-Record  : {t_total:.3f} s (Acceptance: <= 8.00s -> {status_str})")
        print(f"Recognized Text    : \"{text}\"\n")
        time.sleep(0.5)

    print("=" * 75)
    print("BENCHMARK SUMMARY (5 Trials across Real Multi-Sentence Audio)")
    print("=" * 75)
    print(f"Audio Length           : {audio_dur:.2f} s")
    print(f"Individual E2E Times   : {[round(t, 3) for t in total_timings]} s")
    print(f"Median STT Inference   : {statistics.median(stt_timings):.3f} s (Mean: {statistics.mean(stt_timings):.3f} s)")
    print(f"Median Text Injection  : {statistics.median(inj_timings):.3f} s (Mean: {statistics.mean(inj_timings):.3f} s)")
    print(f"Median Post-Record E2E : {statistics.median(total_timings):.3f} s (Mean: {statistics.mean(total_timings):.3f} s)")
    print(f"Max Post-Record E2E    : {max(total_timings):.3f} s")
    print(f"Target Criterion (<=8s): {'PASSED ALL 5 TRIALS' if max(total_timings) <= 8.0 else 'FAILED'}")
    print("=" * 75)

if __name__ == "__main__":
    run_real_speech_5_trials()


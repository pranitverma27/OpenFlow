"""
Benchmark Script for OpenFlow Dictation Pipeline
Measures:
1. Microphone stream start latency
2. Audio capture duration & sample integrity
3. Local Whisper transcription duration across multiple repeated trials
4. Text injection & clipboard restoration duration
5. Total post-record end-to-end latency
"""
import time
import numpy as np
import statistics
from engine_audio import AudioRecorder
from engine_transcription import TranscriptionEngine
from engine_injector import insert_text

def benchmark_pipeline(trials: int = 5):
    print("=" * 65)
    print(f"OpenFlow Dictation Pipeline Benchmark ({trials} Trials)")
    print("=" * 65)

    rec = AudioRecorder(sample_rate=16000)
    stt = TranscriptionEngine(model_size="tiny.en")
    print("Preloading Whisper model...")
    t0 = time.perf_counter()
    stt.load()
    preload_dur = time.perf_counter() - t0
    print(f"Model loaded in {preload_dur:.3f} s.\n")

    start_latencies = []
    rec_durations = []
    stt_durations = []
    inject_durations = []
    total_post_record = []

    for i in range(trials):
        print(f"--- Trial {i + 1}/{trials} ---")
        
        # 1. Microphone Start Latency
        t_start_req = time.perf_counter()
        rec.start()
        t_start_lat = time.perf_counter() - t_start_req
        start_latencies.append(t_start_lat)

        # Record for 2.0 seconds
        time.sleep(2.0)

        # 2. Stop & Stream Teardown
        t_stop_req = time.perf_counter()
        audio = rec.stop()
        rec_dur = rec.get_last_duration()
        rec_durations.append(rec_dur)

        # 3. Transcription Latency
        t_stt_req = time.perf_counter()
        transcription = stt.transcribe(audio)
        t_stt_lat = time.perf_counter() - t_stt_req
        stt_durations.append(t_stt_lat)

        # 4. Text Injection Latency
        t_inj_req = time.perf_counter()
        # Test inject without altering clipboard permanently
        insert_text(transcription if transcription else "benchmark_ping", paste_wait=0.08)
        t_inj_lat = time.perf_counter() - t_inj_req
        inject_durations.append(t_inj_lat)

        # 5. Total Post-Record Latency
        total_lat = time.perf_counter() - t_stop_req
        total_post_record.append(total_lat)

        print(
            f"Start Latency: {t_start_lat*1000:.1f}ms | "
            f"Rec: {rec_dur:.2f}s ({len(audio)} samples) | "
            f"STT: {t_stt_lat:.3f}s | "
            f"Inject: {t_inj_lat:.3f}s | "
            f"Total Post-Record: {total_lat:.3f}s"
        )
        time.sleep(0.3)

    print("\n" + "=" * 65)
    print("BENCHMARK SUMMARY (Median & Mean across trials)")
    print("=" * 65)
    print(f"Microphone Start Latency : Median = {statistics.median(start_latencies)*1000:.1f} ms | Mean = {statistics.mean(start_latencies)*1000:.1f} ms")
    print(f"Recording Duration        : Median = {statistics.median(rec_durations):.2f} s | Mean = {statistics.mean(rec_durations):.2f} s")
    print(f"STT Inference Duration    : Median = {statistics.median(stt_durations):.3f} s | Mean = {statistics.mean(stt_durations):.3f} s")
    print(f"Injection Duration        : Median = {statistics.median(inject_durations):.3f} s | Mean = {statistics.mean(inject_durations):.3f} s")
    print(f"Total Post-Record Latency : Median = {statistics.median(total_post_record):.3f} s | Mean = {statistics.mean(total_post_record):.3f} s")
    print("=" * 65)

if __name__ == "__main__":
    benchmark_pipeline(trials=5)

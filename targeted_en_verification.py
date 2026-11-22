import time
import soundfile as sf
import numpy as np
from engine_transcription import TranscriptionEngine
from engine_injector import insert_text

def run_targeted_verification():
    print("=" * 65)
    print("OPENFLOW TARGETED VERIFICATION: 10s & 15s ENGLISH AUDIO")
    print("Strict Acceptance Criterion: Total Latency < 5.00s")
    print("=" * 65)

    engine = TranscriptionEngine()
    engine.load()

    # Model warmup
    warm_audio = np.zeros(16000, dtype=np.float32)
    engine.transcribe(warm_audio)

    results = {}

    for label, filename in [('10-second Audio', 'test_en_10s.wav'), ('15-second Audio', 'test_en_15s.wav')]:
        raw_data, sr = sf.read(filename)
        new_len = int(round(len(raw_data) * 16000.0 / float(sr)))
        audio = np.interp(np.linspace(0, len(raw_data) - 1, new_len), np.arange(len(raw_data)), raw_data).astype(np.float32)
        rec_dur = len(audio) / 16000.0

        print(f"\n--- Testing {label} (Recorded Speech Duration: {rec_dur:.2f}s) ---")
        trials = []

        for trial_num in range(1, 6):
            t_stop = time.perf_counter()

            # Preprocessing
            t_pre_0 = time.perf_counter()
            # Audio is already in memory 16kHz float32
            t_pre = time.perf_counter() - t_pre_0

            # STT Inference
            t_stt_0 = time.perf_counter()
            text = engine.transcribe(audio)
            t_stt = time.perf_counter() - t_stt_0

            # Postprocessing
            t_post_0 = time.perf_counter()
            cleaned_text = text.strip()
            t_post = time.perf_counter() - t_post_0

            # Injection
            t_inj_0 = time.perf_counter()
            insert_text(cleaned_text, paste_wait=0.08)
            t_inj = time.perf_counter() - t_inj_0

            total_lat = time.perf_counter() - t_stop
            passed = total_lat < 5.00

            trial_record = {
                "trial": trial_num,
                "rec_duration": round(rec_dur, 2),
                "pre_time": round(t_pre, 4),
                "stt_time": round(t_stt, 3),
                "post_time": round(t_post, 4),
                "inj_time": round(t_inj, 3),
                "total_latency": round(total_lat, 3),
                "passed": passed,
                "text": cleaned_text
            }
            trials.append(trial_record)
            print(f"  Trial {trial_num}: STT={t_stt:.3f}s | Inj={t_inj:.3f}s | Total={total_lat:.3f}s | Status={'PASS' if passed else 'FAIL'}")
            time.sleep(0.3)

        totals = [t["total_latency"] for t in trials]
        stt_times = [t["stt_time"] for t in trials]
        results[label] = {
            "trials": trials,
            "median_total": round(float(np.median(totals)), 3),
            "max_total": round(float(max(totals)), 3),
            "min_total": round(float(min(totals)), 3),
            "p95_total": round(float(np.percentile(totals, 95)), 3),
            "median_stt": round(float(np.median(stt_times)), 3),
            "pass_rate": f"{sum(1 for t in trials if t['passed'])}/{len(trials)}",
            "sample_transcription": trials[0]["text"]
        }
        print(f"Summary {label}: Median={results[label]['median_total']}s, Max={results[label]['max_total']}s, Pass Rate={results[label]['pass_rate']}")
        print(f"Sample Text: \"{trials[0]['text']}\"")

    return results

if __name__ == "__main__":
    run_targeted_verification()

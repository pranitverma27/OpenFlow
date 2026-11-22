"""
Comprehensive Head-to-Head Benchmark Suite for OpenFlow
Evaluates English, Hindi, and Hinglish across accuracy, latency, and memory metrics.
"""
import time
import os
import gc
import soundfile as sf
import numpy as np

from engine_transcription import TranscriptionEngine
from engine_shruti import ShrutiTranscriptionEngine
from engine_transliterate import transliterate_to_hinglish
from engine_corrections import apply_corrections

def compute_wer(reference: str, hypothesis: str) -> float:
    ref_words = reference.lower().strip().split()
    hyp_words = hypothesis.lower().strip().split()
    if not ref_words:
        return 0.0 if not hyp_words else 1.0

    d = np.zeros((len(ref_words) + 1, len(hyp_words) + 1), dtype=int)
    for i in range(len(ref_words) + 1):
        d[i][0] = i
    for j in range(len(hyp_words) + 1):
        d[0][j] = j

    for i in range(1, len(ref_words) + 1):
        for j in range(1, len(hyp_words) + 1):
            if ref_words[i - 1] == hyp_words[j - 1]:
                d[i][j] = d[i - 1][j - 1]
            else:
                d[i][j] = min(
                    d[i - 1][j] + 1,      # deletion
                    d[i][j - 1] + 1,      # insertion
                    d[i - 1][j - 1] + 1   # substitution
                )
    return float(d[len(ref_words)][len(hyp_words)]) / len(ref_words)

def compute_cer(reference: str, hypothesis: str) -> float:
    ref_chars = list(reference.strip().replace(" ", ""))
    hyp_chars = list(hypothesis.strip().replace(" ", ""))
    if not ref_chars:
        return 0.0 if not hyp_chars else 1.0

    d = np.zeros((len(ref_chars) + 1, len(hyp_chars) + 1), dtype=int)
    for i in range(len(ref_chars) + 1):
        d[i][0] = i
    for j in range(len(hyp_chars) + 1):
        d[0][j] = j

    for i in range(1, len(ref_chars) + 1):
        for j in range(1, len(hyp_chars) + 1):
            if ref_chars[i - 1] == hyp_chars[j - 1]:
                d[i][j] = d[i - 1][j - 1]
            else:
                d[i][j] = min(
                    d[i - 1][j] + 1,
                    d[i][j - 1] + 1,
                    d[i - 1][j - 1] + 1
                )
    return float(d[len(ref_chars)][len(hyp_chars)]) / len(ref_chars)

def run_benchmarks():
    print("=" * 80)
    print("OPENFLOW COMPREHENSIVE TRI-MODE BENCHMARK")
    print("=" * 80)

    # Initialize engines
    print("\n[Init] Preloading English Whisper (tiny.en)...")
    t0 = time.perf_counter()
    whisper_eng = TranscriptionEngine(model_size="tiny.en")
    whisper_eng.load()
    print(f"[Init] Whisper loaded in {time.perf_counter() - t0:.2f}s")

    print("\n[Init] Preloading Shruti ONNX (shruti-hi)...")
    t0 = time.perf_counter()
    shruti_eng = ShrutiTranscriptionEngine()
    shruti_eng.load()
    print(f"[Init] Shruti loaded in {time.perf_counter() - t0:.2f}s")

    test_cases = [
        # 1. English Benchmark (Verification against regression)
        {
            "mode": "en",
            "file": "test_en_5s.wav",
            "category": "English (5s baseline)",
            "ground_truth": "OpenFlow is a high performance speech dictation system for Windows."
        },
        {
            "mode": "en",
            "file": "speech_sample.wav",
            "category": "English (15.8s paragraph)",
            "ground_truth": "OpenFlow is a high performance offline speech to text dictation system for Windows. It provides low latency transcription and seamless text injection into any target application. We are verifying the end to end performance of this pipeline."
        },
        # 2. Authentic Hindi Benchmark
        {
            "mode": "hi",
            "file": "sample_hindi_1.wav",
            "category": "Authentic Hindi (10.3s)",
            "ground_truth": "वैज्ञानिकों का मानना है कि औसतन लोमड़ गंध के द्वारा जानवरों का पीछा करते और खाते हैं यह सुनते हुए कि वे जमीन पर कहाँ रहे होंगे"
        },
        {
            "mode": "hi",
            "file": "sample_hindi.wav",
            "category": "Authentic Hindi (12.2s)",
            "ground_truth": "मेजर किन खाना भूमध्य सागर में समान क्षेत्रों की तरह रोटी सब्जियों और मांस विशेष रूप से सुअर का मांस पर आधारित है और जैतून के तेल का उपयोग करता है"
        },
        {
            "mode": "hi",
            "file": "sample_hindi_2.wav",
            "category": "Authentic Hindi (21.4s)",
            "ground_truth": "आर्मड वर्षा स्नेह कहा मैंने अपनी बहन और उनकी दोस्त को खो दिया और रास्ते में व्हीलचेयर में दो दिव्यांग लोग थे और लोग उन पर उछल रहे थे और उन्हें धक्का दे रहे थे"
        },
        # 3. Hinglish Benchmark (Shruti + Roman transliteration + corrections)
        {
            "mode": "hinglish",
            "file": "sample_hindi_2.wav",
            "category": "Hinglish Roman Output (21.4s)",
            "ground_truth": "aaramd varsha sneh kaha maine apni behen aur unki dost ko kho diya aur raaste mein wheelchair mein do divyang log the aur log un par uchhal rahe the aur unhein dhakka de rahe the"
        },
        {
            "mode": "hinglish",
            "file": "speech_sample.wav",
            "category": "Hinglish English preservation (15.8s)",
            "ground_truth": "OpenFlow is a high performance offline speech to text dictation system for windows it provides low latency transcription and seamless text injection into any target application we are verifying the end to end performance of this pipeline"
        }
    ]

    results = []

    for idx, tc in enumerate(test_cases, 1):
        audio_file = tc["file"]
        if not os.path.isfile(audio_file):
            print(f"\n[Warning] File not found: {audio_file}")
            continue

        audio, sr = sf.read(audio_file, dtype="float32")
        duration_s = len(audio) / sr

        # Warmup and measurement
        t_start = time.perf_counter()

        if tc["mode"] == "en":
            raw = whisper_eng.transcribe(audio, language="en")
            translit_time = 0.0
            final = apply_corrections(raw)
        elif tc["mode"] == "hi":
            raw = shruti_eng.transcribe(audio, language="hi", beams=5)
            translit_time = 0.0
            final = apply_corrections(raw)
        elif tc["mode"] == "hinglish":
            raw = shruti_eng.transcribe(audio, language=None, beams=5)
            t_tr0 = time.perf_counter()
            roman = transliterate_to_hinglish(raw)
            translit_time = (time.perf_counter() - t_tr0) * 1000.0
            final = apply_corrections(roman)

        total_latency = time.perf_counter() - t_start

        wer = compute_wer(tc["ground_truth"], final)
        cer = compute_cer(tc["ground_truth"], final)

        res = {
            "test_id": idx,
            "category": tc["category"],
            "mode": tc["mode"],
            "audio_file": audio_file,
            "duration_s": round(duration_s, 2),
            "latency_s": round(total_latency, 3),
            "translit_ms": round(translit_time, 2),
            "wer": round(wer * 100.0, 1),
            "cer": round(cer * 100.0, 1),
            "hypothesis": final,
            "passed": total_latency < 5.00
        }
        results.append(res)

        print(f"\n[{idx}/{len(test_cases)}] {tc['category']} ({duration_s:.1f}s audio)")
        print(f"    Mode: {tc['mode'].upper()} | Latency: {total_latency:.2f}s | Pass (<5s): {res['passed']}")
        if translit_time > 0:
            print(f"    Transliteration time: {translit_time:.2f}ms")
        print(f"    WER: {res['wer']}% | CER: {res['cer']}%")
        print(f"    Hyp: \"{final[:100]}...\"" if len(final) > 100 else f"    Hyp: \"{final}\"")

    print("\n" + "=" * 80)
    print("BENCHMARK SUMMARY TABLE")
    print("=" * 80)
    print(f"{'Category':<32} | {'Audio':<6} | {'Latency':<8} | {'WER (%)':<8} | {'CER (%)':<8} | {'Status'}")
    print("-" * 80)
    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"{r['category']:<32} | {r['duration_s']:>5}s | {r['latency_s']:>6}s | {r['wer']:>7}% | {r['cer']:>7}% | {status}")
    print("=" * 80)

if __name__ == "__main__":
    run_benchmarks()

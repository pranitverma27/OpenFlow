"""
OpenFlow Speech-to-Text Accuracy & WER Benchmark Test Suite
Provides:
1. Exact Word Error Rate (WER) computation via Levenshtein distance on words.
2. Character Error Rate (CER) computation.
3. Test framework for evaluating standardized benchmark audio files against known reference transcripts.
"""
import re
import numpy as np
from faster_whisper import WhisperModel

def normalize_text(text: str) -> str:
    """Standardizes text for fair WER calculation (lowercase, trims punctuation)."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def calculate_wer(reference: str, hypothesis: str) -> float:
    """Calculates Levenshtein Word Error Rate (WER) between reference and hypothesis."""
    ref_words = normalize_text(reference).split()
    hyp_words = normalize_text(hypothesis).split()

    if not ref_words:
        return 0.0 if not hyp_words else 1.0

    d = np.zeros((len(ref_words) + 1, len(hyp_words) + 1), dtype=np.int32)
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
                    d[i - 1][j] + 1,      # Deletion
                    d[i][j - 1] + 1,      # Insertion
                    d[i - 1][j - 1] + 1   # Substitution
                )

    wer = d[len(ref_words)][len(hyp_words)] / float(len(ref_words))
    return float(wer)

def run_wer_eval(model: WhisperModel, audio_data: np.ndarray, reference_text: str):
    segments, _ = model.transcribe(audio_data, language="en", beam_size=5)
    hypothesis = " ".join([s.text.strip() for s in segments if s.text.strip()]).strip()
    wer = calculate_wer(reference_text, hypothesis)
    return hypothesis, wer

if __name__ == "__main__":
    ref = "The quick brown fox jumps over the lazy dog"
    hyp_exact = "The quick brown fox jumps over the lazy dog"
    hyp_err = "The quick brown fox jumps over lazy dog"
    assert calculate_wer(ref, hyp_exact) == 0.0
    assert calculate_wer(ref, hyp_err) > 0.0
    print("[OK] WER calculation module verified.")

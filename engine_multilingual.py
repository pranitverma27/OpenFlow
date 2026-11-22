"""
OpenFlow Multilingual Transcription Engine
Supports Hindi and Hinglish dictation using faster-whisper.
Maintains lazy initialization to avoid slowing down startup or affecting English dictation.
"""
import os
import sys
import threading
import numpy as np
from faster_whisper import WhisperModel
from utils_paths import get_model_path
from language_config import LanguageMode, get_language_profile

class MultilingualTranscriptionEngine:
    """
    Multilingual speech recognition engine for Hindi and Hinglish.
    Lazy-loads on first use and preserves sub-5s performance optimizations:
    - cpu_threads=5, num_workers=1, compute_type="int8"
    - beam_size=1, best_of=1, temperature=0.0, condition_on_previous_text=False
    - Dynamic VAD: bypassed for <= 6.0s, enabled with min_silence_duration_ms=300 for > 6.0s
    """
    def __init__(self, model_size="base", device="cpu", compute_type="int8"):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.model = None
        self._load_lock = threading.Lock()
        self._load_failed = False
        self._load_error_msg = ""

    def is_loaded(self) -> bool:
        return self.model is not None

    def load(self):
        """Lazy load the multilingual model with lock protection."""
        if self.model is not None:
            return
        with self._load_lock:
            if self.model is not None:
                return
            try:
                target_model = get_model_path(self.model_size)
                is_local = os.path.isdir(target_model)
                print(f"[MultilingualTranscriptionEngine] Loading model '{self.model_size}' from: {target_model} (local={is_local})")

                self.model = WhisperModel(
                    target_model,
                    device=self.device,
                    compute_type=self.compute_type,
                    cpu_threads=5,
                    num_workers=1,
                    local_files_only=is_local
                )
                print("[MultilingualTranscriptionEngine] Model loaded successfully.")
            except Exception as e:
                self._load_failed = True
                self._load_error_msg = str(e)
                print(f"[MultilingualTranscriptionEngine] Error loading model: {e}")
                raise

    def transcribe(self, audio_data: np.ndarray, mode: str = "hi") -> str:
        """
        Transcribe 16kHz float32 audio data according to mode ('hi' or 'hinglish').
        """
        if len(audio_data) == 0:
            return ""

        if self.model is None:
            self.load()

        profile = get_language_profile(mode)
        whisper_lang = profile.get("whisper_language")
        initial_prompt = profile.get("initial_prompt")
        rep_penalty = profile.get("repetition_penalty", 1.0)

        # Dynamic VAD bypass: for recordings <= 6.0s (<= 96,000 samples @ 16kHz),
        # bypass Silero VAD to eliminate ~1.6s ONNX overhead on continuous speech bursts.
        # For longer recordings (> 6.0s), retain VAD with 300ms silence threshold.
        duration_s = len(audio_data) / 16000.0
        use_vad = duration_s > 6.0
        vad_params = dict(min_silence_duration_ms=300) if use_vad else None

        # Performance-critical decoding parameters matching English baseline + VAD
        segments, _ = self.model.transcribe(
            audio_data,
            language=whisper_lang,
            initial_prompt=initial_prompt,
            beam_size=1,
            best_of=1,
            temperature=0.0,
            condition_on_previous_text=False,
            repetition_penalty=rep_penalty,
            vad_filter=use_vad,
            vad_parameters=vad_params
        )
        text_segments = [s.text.strip() for s in segments if s.text.strip()]
        return " ".join(text_segments).strip()


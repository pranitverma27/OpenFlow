"""
OpenFlow Transcription Engine
Offline local speech-to-text using faster-whisper.
"""
import os
import numpy as np
from faster_whisper import WhisperModel
from utils_paths import get_model_path

class TranscriptionEngine:
    def __init__(self, model_size="tiny.en", device="cpu", compute_type="int8"):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.model = None

    def load(self):
        if self.model is None:
            # Resolve local model directory if bundled or cached
            target_model = get_model_path(self.model_size)
            is_local = os.path.isdir(target_model)
            print(f"[TranscriptionEngine] Loading Whisper model from: {target_model} (local={is_local})")
            
            self.model = WhisperModel(
                target_model,
                device=self.device,
                compute_type=self.compute_type,
                cpu_threads=4,
                num_workers=2,
                local_files_only=is_local
            )

    def transcribe(self, audio_data: np.ndarray, language: str = "en") -> str:
        """
        Transcribe 16kHz float32 audio data directly in memory.
        """
        if len(audio_data) == 0:
            return ""
        if self.model is None:
            self.load()
        
        # Optimized parameters for low-latency interactive dictation:
        # - beam_size=1 (greedy decoding): eliminates 5x beam tree overhead, 6-16x speedup on multi-sentence speech
        # - condition_on_previous_text=False: eliminates autoregressive cross-window stalling
        # - vad_filter=True with 300ms silence threshold: clips trailing pauses cleanly
        segments, _ = self.model.transcribe(
            audio_data,
            language=language if language != "auto" else None,
            beam_size=1,
            best_of=1,
            temperature=0.0,
            condition_on_previous_text=False,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=300)
        )
        text_segments = [s.text.strip() for s in segments if s.text.strip()]
        return " ".join(text_segments).strip()

"""
OpenFlow Audio Recorder Engine
Direct audio recording using sounddevice at 16kHz mono float32 for Whisper models.
"""
import threading
import time
import numpy as np
import sounddevice as sd

class AudioRecorder:
    def __init__(self, sample_rate=16000, level_callback=None):
        self.sample_rate = sample_rate
        self.level_callback = level_callback
        self.is_recording = False
        self._frames = []
        self._stream = None
        self._lock = threading.Lock()
        self._start_time = 0.0

    def _audio_callback(self, indata, frames, time_info, status):
        if self.is_recording:
            # indata shape is (frames, 1), copy to prevent buffer overwrite
            self._frames.append(indata.copy())
            if self.level_callback is not None:
                try:
                    # Inexpensive RMS level estimate on the incoming block
                    rms = float(np.sqrt(np.mean(indata**2)))
                    self.level_callback(rms)
                except Exception:
                    pass

    def start(self):
        with self._lock:
            if self.is_recording:
                return
            self._frames = []
            try:
                self._stream = sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=1,
                    dtype="float32",
                    callback=self._audio_callback
                )
                self._stream.start()
                self._start_time = time.perf_counter()
                self.is_recording = True
            except Exception as e:
                self.is_recording = False
                if self._stream is not None:
                    try:
                        self._stream.close()
                    except Exception:
                        pass
                    self._stream = None
                raise e

    def stop(self) -> np.ndarray:
        with self._lock:
            if not self.is_recording:
                return np.zeros((0,), dtype=np.float32)
            self.is_recording = False
            try:
                if self._stream is not None:
                    try:
                        self._stream.stop()
                    finally:
                        self._stream.close()
            except Exception as e:
                print(f"[AudioRecorder] Error closing stream: {e}")
            finally:
                self._stream = None

            self._last_duration = max(0.0, time.perf_counter() - self._start_time) if self._start_time > 0 else 0.0

            if not self._frames:
                return np.zeros((0,), dtype=np.float32)
            audio = np.concatenate(self._frames, axis=0).flatten()
            self._frames = []
            return audio

    def get_last_duration(self) -> float:
        """Returns the duration in seconds of the most recent recording session."""
        return getattr(self, "_last_duration", 0.0)

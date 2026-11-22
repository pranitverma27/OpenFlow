"""
OpenFlow Shruti Speech Recognition Engine Adapter
Integrates Udgam Labs Shruti-ONNX Hindi/English code-switched ASR model.
Operates 100% offline via local ONNX Runtime CPUExecutionProvider.

Attribution & License Notice:
- Powered by Udgam Labs Shruti (https://github.com/udgamlabs/shruti)
- Copyright (c) 2025 Udgam Labs
- Licensed under the Apache License, Version 2.0.
"""
import os
import json
import threading
from typing import Optional, Dict, Any, List
import numpy as np
import onnxruntime as ort

from utils_paths import get_bundle_dir

RATE = 16000

class ShrutiTranscriptionEngine:
    """
    Offline local transcription engine using Udgam Labs Shruti ONNX models.
    Supports Hindi and mixed Hindi-English speech with English words preserved in Latin script.
    """
    def __init__(self, model_dir: Optional[str] = None, threads: int = 4):
        self.model_dir = model_dir
        self.threads = threads
        self.frontend: Optional[ort.InferenceSession] = None
        self.encoder: Optional[ort.InferenceSession] = None
        self.decoder: Optional[ort.InferenceSession] = None
        self.vocab: List[str] = []
        self.cfg: Dict[str, Any] = {}
        self.text_id: int = 0
        self.bos: int = 0
        self.eos: int = 0
        self.tags: Dict[str, int] = {}
        self.languages: tuple = ("hi", "en")
        self.state_names: List[str] = []
        self.state_shapes: Dict[str, List[int]] = {}
        self._load_lock = threading.Lock()
        self._is_loaded = False

    def is_loaded(self) -> bool:
        return self._is_loaded

    def _resolve_model_dir(self) -> str:
        if self.model_dir and os.path.isdir(self.model_dir):
            return self.model_dir
        
        # Check bundled / local models directory
        candidate = os.path.join(get_bundle_dir(), "models", "shruti-hi")
        if os.path.isdir(candidate) and os.path.exists(os.path.join(candidate, "shruti.json")):
            return candidate

        # Fallback to relative models/shruti-hi
        rel_candidate = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "shruti-hi")
        if os.path.isdir(rel_candidate) and os.path.exists(os.path.join(rel_candidate, "shruti.json")):
            return rel_candidate

        raise FileNotFoundError(f"Could not find local Shruti model files in '{candidate}' or '{rel_candidate}'")

    def load(self):
        """Lazy load the ONNX inference sessions and vocabulary."""
        if self._is_loaded:
            return

        with self._load_lock:
            if self._is_loaded:
                return

            folder = self._resolve_model_dir()
            print(f"[ShrutiEngine] Loading Shruti ONNX models from: {folder} (threads={self.threads})")

            so = ort.SessionOptions()
            so.intra_op_num_threads = self.threads
            so.inter_op_num_threads = 1
            so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

            load_sess = lambda f: ort.InferenceSession(os.path.join(folder, f), so, providers=["CPUExecutionProvider"])
            self.frontend = load_sess("frontend.onnx")
            self.encoder = load_sess("encoder.onnx")
            self.decoder = load_sess("decoder.onnx")

            meta_path = os.path.join(folder, "shruti.json")
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)

            self.vocab = meta["vocab"]
            self.cfg = meta["config"]
            self.text_id = self.cfg["text"]
            self.bos = self.cfg["bos"]
            self.eos = self.cfg["eos"]
            self.tags = {lang: self.text_id + i for i, lang in enumerate(self.cfg["languages"])}
            self.languages = ("hi", "en")

            self.state_names = [i.name for i in self.decoder.get_inputs()][2:]
            shapes = {i.name: i.shape for i in self.decoder.get_inputs()}
            self.state_shapes = {n: [d if isinstance(d, int) else 0 for d in shapes[n]] for n in self.state_names}

            self._is_loaded = True
            print("[ShrutiEngine] Shruti ONNX models loaded successfully.")

    def _detok(self, ids: List[int]) -> str:
        """Sentencepiece token decoding preserving UTF-8 multibyte characters and spaces."""
        out, raw = [], bytearray()
        for i in ids:
            p = self.vocab[i]
            if len(p) == 6 and p.startswith("<0x") and p.endswith(">"):
                raw.append(int(p[3:5], 16))
                continue
            if raw:
                out.append(raw.decode("utf-8", "ignore"))
                raw.clear()
            if not (p.startswith("<") and p.endswith(">")):
                out.append(p)
        if raw:
            out.append(raw.decode("utf-8", "ignore"))
        return "".join(out).replace("▁", " ").strip()

    def _init_state(self, batch_size: int = 1) -> Dict[str, np.ndarray]:
        st = {}
        for n in self.state_names:
            shp = list(self.state_shapes[n])
            if n == "pos":
                st[n] = np.zeros(1, np.int64)
                continue
            shp[0] = batch_size
            st[n] = np.zeros(shp, np.int64 if n == "hist" else np.float32)
        return st

    def _step(self, tokens: np.ndarray, cross: np.ndarray, st: Dict[str, np.ndarray]):
        r = self.decoder.run(None, {"tokens": tokens, "cross": cross, **st})
        return r[0][:, 0], dict(zip(self.state_names, r[1:]))

    def _encode(self, wav: np.ndarray) -> np.ndarray:
        feats = self.frontend.run(None, {"audio": wav[None].astype(np.float32)})[0]
        n = np.array([len(wav) // self.cfg["hop"]], np.int64)
        return self.encoder.run(None, {"features": feats, "frames": n})[0]

    @staticmethod
    def _logsoftmax(x: np.ndarray) -> np.ndarray:
        x = x - x.max(-1, keepdims=True)
        return x - np.log(np.exp(x).sum(-1, keepdims=True))

    @staticmethod
    def _cut_loops(ids: List[int], max_period: int = 8, repeats: int = 3) -> List[int]:
        n = len(ids)
        for start in range(n):
            for k in range(1, max_period + 1):
                if start + k * repeats > n:
                    break
                pat = ids[start:start + k]
                if all(ids[start + r * k:start + (r + 1) * k] == pat for r in range(1, repeats)):
                    return ids[:start + k]
        return ids

    def _transcribe_window(self, wav: np.ndarray, language: Optional[str] = None, beams: int = 5,
                           tok_per_s: float = 12.0, length_norm: bool = True, loops: str = "cut") -> Dict[str, Any]:
        tidy = self._cut_loops if loops == "cut" else (lambda ids: ids)
        cross = self._encode(wav)
        cap = int(min(self.cfg["max_tokens"] - 2, len(wav) / RATE * tok_per_s + 8))
        st = self._init_state(1)

        if language is None:
            lg, st = self._step(np.array([[self.bos]], np.int64), cross, st)
            detected = max(self.languages, key=lambda lang: lg[0, self.tags[lang]])
            lg, st = self._step(np.array([[self.tags[detected]]], np.int64), cross, st)
            language = detected
        else:
            lg, st = self._step(np.array([[self.bos, self.tags[language]]], np.int64), cross, st)

        lg[:, self.text_id:] = -np.inf

        if beams <= 1:
            ids = []
            for _ in range(cap):
                k = int(lg[0].argmax())
                if k == self.eos:
                    break
                ids.append(k)
                lg, st = self._step(np.array([[k]], np.int64), cross, st)
                lg[:, self.text_id:] = -np.inf
            ids = tidy(ids)
            return {"text": self._detok(ids), "language": language, "tokens": ids}

        # 5-beam search
        norm = (lambda sc, s: sc / (len(s) + 1)) if length_norm else (lambda sc, s: sc)
        lp = self._logsoftmax(lg[0])
        first = np.argsort(-lp)[:beams]
        seqs = [[int(k)] for k in first]
        scores = lp[first].astype(np.float64)
        finished = [(scores[i], s[:-1]) for i, s in enumerate(seqs) if s[-1] == self.eos]
        live = [i for i, s in enumerate(seqs) if s[-1] != self.eos]
        seqs, scores = [seqs[i] for i in live], scores[live]
        st = {n: (v if n == "pos" else np.repeat(v, len(seqs), 0)) for n, v in st.items()}

        for _ in range(cap - 1):
            if not seqs:
                break
            lg, st = self._step(np.array([[s[-1]] for s in seqs], np.int64), cross, st)
            lg[:, self.text_id:] = -np.inf
            lp = self._logsoftmax(lg)
            cand_scores = scores[:, None] + lp
            flat = cand_scores.reshape(-1)
            best = np.argsort(-flat)[:beams]
            rows, cols = np.unravel_index(best, cand_scores.shape)

            new_seqs, new_scores = [], []
            keep_rows = []
            for r, c in zip(rows, cols):
                token = int(c)
                sc = float(cand_scores[r, c])
                extended = seqs[r] + [token]
                if token == self.eos:
                    finished.append((sc, seqs[r]))
                else:
                    new_seqs.append(extended)
                    new_scores.append(sc)
                    keep_rows.append(r)

            if len(finished) >= beams:
                break
            if not new_seqs:
                break

            seqs = new_seqs
            scores = np.array(new_scores, np.float64)
            st = {n: (v if n == "pos" else v[keep_rows]) for n, v in st.items()}

        all_candidates = finished + [(sc, s) for sc, s in zip(scores, seqs)]
        if not all_candidates:
            return {"text": "", "language": language, "tokens": []}

        best_tokens = max(all_candidates, key=lambda item: norm(item[0], item[1]))[1]
        best_tokens = tidy(best_tokens)
        return {"text": self._detok(best_tokens), "language": language, "tokens": best_tokens}

    def transcribe(self, audio_data: np.ndarray, language: Optional[str] = "hi", beams: int = 5, window_s: float = 30.0) -> str:
        """
        Transcribe 16kHz float32 audio data.
        Returns the recognized text string (Devanagari with Latin-preserved English words).
        """
        if len(audio_data) == 0:
            return ""

        wav = np.asarray(audio_data, dtype=np.float32)
        if np.abs(wav).max() < 1e-4:
            return ""

        if not self._is_loaded:
            self.load()

        # Split into windows <= 30s
        n = max(1, int(np.ceil(len(wav) / (window_s * RATE))))
        parts = [self._transcribe_window(w, language=language, beams=beams) for w in np.array_split(wav, n)]
        text = " ".join(p["text"] for p in parts if p["text"])
        return text.strip()

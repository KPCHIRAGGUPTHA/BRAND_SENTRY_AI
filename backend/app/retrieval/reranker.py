"""
Cross-Encoder Reranking Service for BrandSentry AI.
Performs pairwise relevance scoring between individual marketing claims and retrieved
guideline passages using a lightweight, quantized ONNX MiniLM cross-encoder.

Architecture & Safety:
- Model: Xenova/ms-marco-MiniLM-L-6-v2 (quantized ONNX, ~23MB).
- Execution: ONNXRuntime on CPU via CPUExecutionProvider.
- Thread-safe lazy singleton loading (loaded once at process startup/first-use).
- Graceful error handling: falls back to original RRF candidate order if model loading
  fails, network is unavailable, or inference encounters an error.
- Never interprets reranker scores as compliance confidence or truth probability.
- Preserves all original candidate metadata (chunk_id, document_id, page_number,
  source_filename, similarity_score, bm25_score, rrf_score).
"""
import os
import logging
import threading
from typing import List, Dict, Any, Optional, Tuple
import numpy as np

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


class CrossEncoderRerankerService:
    """
    Reranks candidate guideline passages for a marketing claim using a Cross-Encoder.
    Cross-encoders process query and passage jointly through bidirectional attention,
    measuring semantic alignment and contextual relevance far better than bi-encoders.
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        enabled: Optional[bool] = None,
        max_length: Optional[int] = None,
    ):
        self.model_name = model_name or settings.RERANKER_MODEL_NAME
        self.enabled = enabled if enabled is not None else settings.RERANKING_ENABLED
        self.max_length = max_length or getattr(settings, "RERANKER_MAX_LENGTH", 256)

        self._session = None
        self._tokenizer = None
        self._load_failed = False
        self._load_lock = threading.Lock()

    def ensure_loaded(self) -> bool:
        """Public helper to initialize and verify model availability."""
        return self._load_model()

    def _load_model(self) -> bool:
        """
        Lazily downloads (if needed) and initializes ONNX session and tokenizer.
        Returns True if successful, False if fallback should be used.
        """
        if not self.enabled:
            return False

        if self._load_failed:
            return False

        if self._session is not None and self._tokenizer is not None:
            return True

        with self._load_lock:
            if self._session is not None and self._tokenizer is not None:
                return True

            try:
                from huggingface_hub import hf_hub_download
                import onnxruntime as ort
                from tokenizers import Tokenizer

                logger.info("Initializing Cross-Encoder reranker from '%s'...", self.model_name)

                # Download or load from HF cache (local cache first for fast offline loading)
                try:
                    model_file = hf_hub_download(
                        repo_id=self.model_name,
                        filename="onnx/model_quantized.onnx",
                        local_files_only=True,
                    )
                    tokenizer_file = hf_hub_download(
                        repo_id=self.model_name,
                        filename="tokenizer.json",
                        local_files_only=True,
                    )
                except Exception:
                    model_file = hf_hub_download(
                        repo_id=self.model_name,
                        filename="onnx/model_quantized.onnx",
                    )
                    tokenizer_file = hf_hub_download(
                        repo_id=self.model_name,
                        filename="tokenizer.json",
                    )

                tokenizer = Tokenizer.from_file(tokenizer_file)
                tokenizer.enable_truncation(max_length=self.max_length)
                tokenizer.enable_padding(length=self.max_length)

                sess_options = ort.SessionOptions()
                sess_options.intra_op_num_threads = 2
                sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

                session = ort.InferenceSession(
                    model_file,
                    sess_options=sess_options,
                    providers=["CPUExecutionProvider"],
                )

                self._tokenizer = tokenizer
                self._session = session
                logger.info("Cross-Encoder reranker loaded successfully on CPU.")
                return True

            except Exception as exc:
                logger.warning(
                    "Cross-Encoder reranker model loading failed: %s. "
                    "Falling back safely to RRF candidate ranking.",
                    exc,
                )
                self._load_failed = True
                return False

    def rerank(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Reranks candidate passages by joint claim-passage cross-attention score.

        If reranking is disabled, model loading fails, or candidate list is empty,
        returns candidates in their existing order truncated to top_k.
        """
        if not candidates:
            return []

        clean_query = query.strip() if query else ""
        if not clean_query:
            return candidates[:top_k]

        # Check if model can be used; if not, return original candidate order
        if not self._load_model():
            for c in candidates:
                c.setdefault("rerank_score", None)
            return candidates[:top_k]

        try:
            pairs: List[Tuple[str, str]] = [
                (clean_query, c.get("text", "").strip())
                for c in candidates
            ]

            # Encode query-passage pairs
            encodings = self._tokenizer.encode_batch(pairs)

            input_ids = np.array([e.ids for e in encodings], dtype=np.int64)
            attention_mask = np.array([e.attention_mask for e in encodings], dtype=np.int64)
            token_type_ids = np.array([e.type_ids for e in encodings], dtype=np.int64)

            ort_inputs = {
                "input_ids": input_ids,
                "attention_mask": attention_mask,
                "token_type_ids": token_type_ids,
            }

            logits = self._session.run(None, ort_inputs)[0]
            scores = logits.squeeze(-1).tolist()
            if not isinstance(scores, list):
                scores = [float(scores)]

            # Attach rerank score and re-sort
            scored_candidates = []
            for candidate, score in zip(candidates, scores):
                item = dict(candidate)
                item["rerank_score"] = round(float(score), 4)
                scored_candidates.append(item)

            # Sort descending by cross-encoder score
            scored_candidates.sort(key=lambda x: x["rerank_score"], reverse=True)
            return scored_candidates[:top_k]

        except Exception as exc:
            logger.warning("Cross-encoder inference error: %s. Falling back to RRF ordering.", exc)
            for c in candidates:
                c.setdefault("rerank_score", None)
            return candidates[:top_k]


reranker_service = CrossEncoderRerankerService()

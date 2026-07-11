"""Text sensory embedder — Chaver's ability to perceive text as vectors.

Uses sentence-transformers with a small model. Default: all-MiniLM-L6-v2
(22MB on disk, 384-dim, comfortable on CPU). This is the "many small
specialised embedders" principle applied to the text modality.

On first use, the model is downloaded (~90MB) and cached. Subsequent
loads are instant.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer


DEFAULT_TEXT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
TEXT_EMBEDDING_DIM = 384


class TextEncoder:
    """Encodes text into a fixed-dimensional normalised vector.

    Vectors are L2-normalised so cosine similarity is just a dot product.

    sentence-transformers is imported lazily on first use so that CLI
    entry points (e.g. `python -m chaver.seed --help`) and static
    inspection do not require the heavy dependency to be resolvable.
    """

    def __init__(self, model_name: str = DEFAULT_TEXT_MODEL) -> None:
        self.model_name = model_name
        self._model: "Any | None" = None

    def _ensure_loaded(self) -> None:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)

    def encode(self, text: str) -> np.ndarray:
        """Encode a single string to a float32 normalised vector."""
        self._ensure_loaded()
        assert self._model is not None
        vec = self._model.encode(text, normalize_embeddings=True)
        return np.asarray(vec, dtype=np.float32)

    def encode_batch(self, texts: list[str], batch_size: int = 8) -> np.ndarray:
        """Encode a batch of strings. Returns shape (n, dim)."""
        self._ensure_loaded()
        assert self._model is not None
        vecs = self._model.encode(
            texts,
            normalize_embeddings=True,
            batch_size=batch_size,
        )
        return np.asarray(vecs, dtype=np.float32)

    @property
    def dimension(self) -> int:
        return TEXT_EMBEDDING_DIM

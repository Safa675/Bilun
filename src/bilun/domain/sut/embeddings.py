"""Embedding providers for SUT clause retrieval.

Two providers, one interface:

- :class:`OpenAIEmbeddingProvider` — production default. Calls an
  OpenAI-compatible ``/embeddings`` endpoint (``text-embedding-3-large`` by
  default). NOTE: OpenRouter does **not** serve ``/embeddings``; this needs a
  real OpenAI key (``EMBEDDING_API_KEY`` or ``OPENAI_API_KEY``) and base URL
  ``https://api.openai.com/v1``.
- :class:`LocalHashEmbeddingProvider` — deterministic, dependency-free,
  offline fallback (feature-hashing of Turkish tokens + char n-grams). Lower
  quality than a neural model but makes the whole feature runnable and testable
  without any API key or network.

The build step records ``embed_model`` in the embeddings parquet; query-time
retrieval calls :func:`resolve_provider` with that stored id so the query is
always embedded in the **same** vector space as the corpus.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import numpy as np

try:
    from dotenv import load_dotenv
    _f = Path(__file__).resolve()
    for _p in _f.parents:
        if (_p / ".env").exists() or (_p / "pyproject.toml").exists():
            load_dotenv(dotenv_path=_p / ".env")
            break
except ImportError:
    pass

logger = logging.getLogger("bilun.sut.embeddings")

LOCAL_HASH_MODEL_ID = "local-hash-v1"
LOCAL_HASH_DIMS = 512

DEFAULT_OPENAI_MODEL = "text-embedding-3-large"
DEFAULT_OPENAI_DIMS = 1024

_OPENAI_BASE_URL = os.getenv("EMBEDDING_BASE_URL", "https://api.openai.com/v1")
_EMBED_BATCH_SIZE = 256

# ── Turkish-aware text normalization ─────────────────────────────────────────

_TR_LOWER_MAP = str.maketrans({"İ": "i", "I": "ı", "Ş": "ş", "Ğ": "ğ", "Ü": "ü", "Ö": "ö", "Ç": "ç"})
_TOKEN_RE = re.compile(r"[0-9a-zçğıöşü]+")


def tr_lower(text: str) -> str:
    """Lowercase with Turkish dotted/dotless-I handling."""
    return text.translate(_TR_LOWER_MAP).lower()


def tokenize(text: str) -> list[str]:
    """Lowercase Turkish tokenization into alphanumeric tokens."""
    return _TOKEN_RE.findall(tr_lower(text))


# ── Provider interface ───────────────────────────────────────────────────────


@runtime_checkable
class EmbeddingProvider(Protocol):
    model_id: str
    dims: int

    def embed(self, texts: list[str]) -> np.ndarray:
        """Return an ``(len(texts), dims)`` float32 array (un-normalized)."""
        ...


def normalize(matrix: np.ndarray) -> np.ndarray:
    """L2-normalize rows; zero rows stay zero (cosine-safe)."""
    matrix = np.asarray(matrix, dtype=np.float32)
    if matrix.ndim == 1:
        matrix = matrix.reshape(1, -1)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    return (matrix / norms).astype(np.float32)


# ── Local deterministic fallback ─────────────────────────────────────────────


class LocalHashEmbeddingProvider:
    """Deterministic feature-hashing embedder (no deps, offline).

    Hashes word tokens and intra-token character trigrams into a fixed-width
    vector with signed accumulation and sublinear term weighting. Stable across
    processes (uses blake2b, not the salted builtin ``hash``).
    """

    def __init__(self, dims: int = LOCAL_HASH_DIMS) -> None:
        self.model_id = LOCAL_HASH_MODEL_ID
        self.dims = dims

    @staticmethod
    def _hash(feature: str) -> tuple[int, float]:
        digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
        value = int.from_bytes(digest, "big")
        sign = 1.0 if (value & 1) else -1.0
        return value, sign

    def _features(self, text: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for token in tokenize(text):
            counts[f"w:{token}"] = counts.get(f"w:{token}", 0) + 1
            padded = f"^{token}$"
            for i in range(len(padded) - 2):
                tri = padded[i : i + 3]
                counts[f"t:{tri}"] = counts.get(f"t:{tri}", 0) + 1
        return counts

    def embed(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dims), dtype=np.float32)
        for row, text in enumerate(texts):
            for feature, count in self._features(text or "").items():
                value, sign = self._hash(feature)
                weight = sign * (1.0 + np.log(count))
                out[row, value % self.dims] += weight
        return out


# ── OpenAI-compatible provider ───────────────────────────────────────────────


def _resolve_api_key() -> str | None:
    return (
        os.environ.get("EMBEDDING_API_KEY", "").strip()
        or os.environ.get("OPENAI_API_KEY", "").strip()
        or None
    )


class OpenAIEmbeddingProvider:
    """Calls an OpenAI-compatible ``/embeddings`` endpoint in batches."""

    def __init__(
        self,
        model: str = DEFAULT_OPENAI_MODEL,
        dims: int = DEFAULT_OPENAI_DIMS,
        *,
        api_key: str | None = None,
        base_url: str = _OPENAI_BASE_URL,
    ) -> None:
        self.model_id = model
        self.dims = dims
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key or _resolve_api_key()
        if not self._api_key:
            raise ValueError(
                "No embedding API key found. Set EMBEDDING_API_KEY or OPENAI_API_KEY "
                "(OpenRouter does not serve /embeddings)."
            )

    def _supports_dims(self) -> bool:
        return self.model_id.startswith("text-embedding-3")

    def embed(self, texts: list[str]) -> np.ndarray:
        import httpx

        batch_size = 32 if ("nvidia" in self.model_id or "nvidia.com" in self._base_url) else _EMBED_BATCH_SIZE
        vectors: list[list[float]] = []
        headers = {"Authorization": f"Bearer {self._api_key}"}
        with httpx.Client(timeout=60.0) as client:
            for start in range(0, len(texts), batch_size):
                batch = texts[start : start + batch_size]
                if "nvidia" in self.model_id or "nvidia.com" in self._base_url:
                    batch = [t[:800] for t in batch]
                payload: dict = {"model": self.model_id, "input": batch}
                if self._supports_dims():
                    payload["dimensions"] = self.dims
                input_type = os.getenv("EMBEDDING_INPUT_TYPE")
                if not input_type and ("nvidia" in self.model_id or "nvidia.com" in self._base_url):
                    input_type = "passage" if len(texts) > 1 else "query"
                if input_type:
                    payload["input_type"] = input_type
                resp = client.post(
                    f"{self._base_url}/embeddings", json=payload, headers=headers
                )
                if resp.status_code != 200:
                    logger.error("Embedding API error (%d): %s", resp.status_code, resp.text)
                    resp.raise_for_status()
                data = resp.json()["data"]
                data.sort(key=lambda item: item["index"])
                vectors.extend(item["embedding"] for item in data)
        arr = np.asarray(vectors, dtype=np.float32)
        if arr.shape[1] != self.dims:
            self.dims = arr.shape[1]
        return arr


# ── Factories ────────────────────────────────────────────────────────────────


def resolve_provider(model_id: str, dims: int) -> EmbeddingProvider:
    """Return the provider matching a stored ``embed_model`` id.

    Used at query time so the query embeds into the same space as the corpus.
    """
    if model_id == LOCAL_HASH_MODEL_ID:
        return LocalHashEmbeddingProvider(dims=dims)
    return OpenAIEmbeddingProvider(model=model_id, dims=dims)


def default_build_provider() -> EmbeddingProvider:
    """Pick a provider for the offline build from env.

    ``EMBEDDING_PROVIDER`` = ``auto`` (default) | ``openai`` | ``local``.
    ``auto`` uses OpenAI when a key is present, else the local fallback.
    """
    choice = os.getenv("EMBEDDING_PROVIDER", "auto").strip().lower()
    model = os.getenv("EMBEDDING_MODEL", DEFAULT_OPENAI_MODEL)
    dims = int(os.getenv("EMBEDDING_DIMS", str(DEFAULT_OPENAI_DIMS)))

    if choice == "local":
        return LocalHashEmbeddingProvider(dims=int(os.getenv("EMBEDDING_DIMS", str(LOCAL_HASH_DIMS))))
    if choice == "openai":
        return OpenAIEmbeddingProvider(model=model, dims=dims)

    # auto
    if _resolve_api_key():
        try:
            return OpenAIEmbeddingProvider(model=model, dims=dims)
        except ValueError:
            pass
    logger.warning(
        "No embedding API key found; falling back to %s (lower quality). "
        "Set EMBEDDING_API_KEY/OPENAI_API_KEY for %s.",
        LOCAL_HASH_MODEL_ID,
        model,
    )
    return LocalHashEmbeddingProvider()

from typing import List

import httpx
import numpy as np

from app.config import get_settings


class EmbeddingService:
    """Hugging Face Inference API — sentence-transformers/all-MiniLM-L6-v2"""

    def __init__(self):
        settings = get_settings()
        self.model = settings.hf_embedding_model
        self.token = settings.hf_token
        self.api_url = f"https://api-inference.huggingface.co/pipeline/feature-extraction/{self.model}"

    def embed_text(self, text: str) -> List[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if not self.token:
            # Fallback: simple hash-based pseudo-embedding for dev (384 dims)
            return [self._fallback_embed(t) for t in texts]

        headers = {"Authorization": f"Bearer {self.token}"}
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                self.api_url,
                headers=headers,
                json={"inputs": texts, "options": {"wait_for_model": True}},
            )
            response.raise_for_status()
            data = response.json()

        if isinstance(data, list) and len(data) > 0:
            if isinstance(data[0], list) and isinstance(data[0][0], list):
                return [self._mean_pool(row) for row in data]
            if isinstance(data[0], list) and isinstance(data[0][0], (int, float)):
                return [self._mean_pool(data)] if len(texts) == 1 else data
            if isinstance(data[0], (int, float)):
                return [data]
        return [self._fallback_embed(t) for t in texts]

    def _mean_pool(self, token_embeddings: list) -> List[float]:
        arr = np.array(token_embeddings, dtype=np.float32)
        if arr.ndim == 2:
            return arr.mean(axis=0).tolist()
        return arr.tolist()

    def _fallback_embed(self, text: str, dim: int = 384) -> List[float]:
        np.random.seed(hash(text) % (2**32))
        vec = np.random.randn(dim).astype(np.float32)
        vec = vec / (np.linalg.norm(vec) + 1e-8)
        return vec.tolist()


embeddings = EmbeddingService()

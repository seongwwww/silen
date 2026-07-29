"""Vertex AI 메모 임베더. 본문·질문은 처리만 하고 로그에 남기지 않는다."""

import os

from google import genai
from google.genai import types

from silen_worker.embedding.service import (
    EMBEDDING_DIMENSION,
    EMBEDDING_MODEL,
    validate_embedding,
)


class GeminiEmbedder:
    def __init__(self) -> None:
        if not os.environ.get("GOOGLE_CLOUD_PROJECT"):
            raise RuntimeError("GOOGLE_CLOUD_PROJECT 미설정 — Vertex ADC 구성 필요")
        self._client = genai.Client()

    def embed(self, text: str, task_type: str) -> list[float]:
        response = self._client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text,
            config=types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=EMBEDDING_DIMENSION,
            ),
        )
        if not response.embeddings or response.embeddings[0].values is None:
            raise RuntimeError("embedding_response_missing")
        return validate_embedding(list(response.embeddings[0].values))


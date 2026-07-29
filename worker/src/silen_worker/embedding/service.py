"""임베딩 포트와 결정적 검증. Vertex·DB를 모르는 순수 계층."""

import math
from typing import Protocol

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSION = 768
DOCUMENT_TASK_TYPE = "RETRIEVAL_DOCUMENT"
QUERY_TASK_TYPE = "RETRIEVAL_QUERY"


class InvalidEmbeddingError(ValueError):
    """모델 출력이 저장 스키마와 맞지 않을 때 발생한다."""


class Embedder(Protocol):
    def embed(self, text: str, task_type: str) -> list[float]:
        """text를 고정 차원 벡터로 바꾼다."""


def validate_embedding(values: list[float]) -> list[float]:
    """차원과 유한값을 검증하고 float 목록으로 정규화한다."""
    if len(values) != EMBEDDING_DIMENSION:
        raise InvalidEmbeddingError("invalid_embedding_dimension")
    vector = [float(value) for value in values]
    if not all(math.isfinite(value) for value in vector):
        raise InvalidEmbeddingError("invalid_embedding_value")
    return vector


def vector_literal(values: list[float]) -> str:
    """psycopg 파라미터로 넘길 pgvector 리터럴을 만든다."""
    vector = validate_embedding(values)
    return "[" + ",".join(format(value, ".17g") for value in vector) + "]"


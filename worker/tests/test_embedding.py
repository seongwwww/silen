import math

import pytest

from silen_worker.embedding.service import (
    EMBEDDING_DIMENSION,
    InvalidEmbeddingError,
    validate_embedding,
)


def test_임베딩은_고정_768차원을_검증한다():
    vector = [0.0] * EMBEDDING_DIMENSION

    assert validate_embedding(vector) == vector


@pytest.mark.parametrize(
    "vector",
    (
        [],
        [0.0] * (EMBEDDING_DIMENSION - 1),
        [0.0] * (EMBEDDING_DIMENSION + 1),
        [math.nan] + [0.0] * (EMBEDDING_DIMENSION - 1),
        [math.inf] + [0.0] * (EMBEDDING_DIMENSION - 1),
    ),
)
def test_차원이나_값이_잘못된_임베딩은_거부한다(vector):
    with pytest.raises(InvalidEmbeddingError):
        validate_embedding(vector)


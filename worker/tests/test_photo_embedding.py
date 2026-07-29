"""사진 임베딩 규칙. 실제 호출 없이 검증한다(testing.md)."""

import pytest

from silen_worker.photo.service import (
    PHOTO_EMBEDDING_DIMENSION,
    PHOTO_EMBEDDING_MODEL,
    UnsupportedPhotoError,
    validate_photo_vector,
    should_embed,
)


def test_차원이_다르면_거부한다():
    """텍스트 임베딩(768)과 섞이면 한 인덱스에 두 모델이 들어간다."""
    with pytest.raises(ValueError):
        validate_photo_vector([0.1] * 768)


def test_정상_차원은_통과한다():
    assert len(validate_photo_vector([0.1] * PHOTO_EMBEDDING_DIMENSION)) == 1408


def test_유한하지_않은_값은_거부한다():
    with pytest.raises(ValueError):
        validate_photo_vector([float("nan")] * PHOTO_EMBEDDING_DIMENSION)


def test_사진이_아니면_임베딩하지_않는다():
    assert should_embed("photo", "image/png") is True
    assert should_embed("voice", "audio/mpeg") is False
    assert should_embed("link", None) is False


def test_지원하지_않는_이미지_형식은_거부한다():
    """모델이 못 읽는 형식을 올리면 호출만 낭비한다."""
    with pytest.raises(UnsupportedPhotoError):
        should_embed("photo", "image/tiff", strict=True)


def test_모델명을_고정한다():
    """모델이 바뀌면 벡터 공간이 달라져 기존 검색이 조용히 망가진다."""
    assert PHOTO_EMBEDDING_MODEL == "multimodalembedding@001"


def test_유사도_임계는_실측_구간_사이에_있다():
    """실측: 맞는 짝 +0.085~+0.107, 무관한 짝 +0.016~+0.046.
    임계가 이 사이에 없으면 관련 없는 사진이 모든 답변에 붙는다."""
    from silen_worker.photo.service import PHOTO_MIN_SIMILARITY

    assert 0.046 < PHOTO_MIN_SIMILARITY < 0.085

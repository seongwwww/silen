"""사진 임베딩 규칙. 외부 호출을 모르는 순수 계층이다.

텍스트 임베딩(gemini-embedding-001, 768)은 이미지를 받지 못한다.
multimodalembedding@001은 텍스트와 이미지를 같은 1408차원에 넣어 교차 검색이
되지만, 차원이 다르므로 한 인덱스에 섞지 않는다(ADR-0004).
"""

from math import isfinite

PHOTO_EMBEDDING_MODEL = "multimodalembedding@001"
PHOTO_EMBEDDING_DIMENSION = 1408

# 이 아래는 붙이지 않는다. 실측(코사인)에서 맞는 짝은 +0.085~+0.107,
# 무관한 짝은 +0.016~+0.046이었다. 임계가 없으면 관련 없는 사진이 모든
# 답변에 딸려 붙어 노이즈가 된다.
PHOTO_MIN_SIMILARITY = 0.065

# 모델이 읽을 수 있는 형식만. 나머지는 호출을 낭비한다.
SUPPORTED_MIME = frozenset({"image/png", "image/jpeg", "image/webp", "image/gif"})


class UnsupportedPhotoError(Exception):
    """모델이 읽지 못하는 형식."""


def validate_photo_vector(values: list[float]) -> list[float]:
    """차원과 유한값을 검증한다. 다른 모델의 벡터가 섞이면 검색이 조용히 망가진다."""
    if len(values) != PHOTO_EMBEDDING_DIMENSION:
        raise ValueError(
            f"photo embedding must be {PHOTO_EMBEDDING_DIMENSION} dimensions"
        )
    if not all(isfinite(value) for value in values):
        raise ValueError("photo embedding must be finite")
    return [float(value) for value in values]


def should_embed(
    asset_type: str,
    mime_type: str | None,
    *,
    strict: bool = False,
) -> bool:
    """사진만 임베딩한다. 음성·링크는 대상이 아니다."""
    if asset_type != "photo":
        return False
    if mime_type in SUPPORTED_MIME:
        return True
    if strict:
        raise UnsupportedPhotoError(f"unsupported photo mime: {mime_type}")
    return False

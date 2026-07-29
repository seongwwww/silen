"""multimodalembedding@001 호출. google-genai SDK가 이 모델을 태우지 않아
Vertex predict 엔드포인트를 직접 부른다(embed_content는 텍스트만 보낸다).

ADC로 인증한다(조직 정책이 API 키 금지). 본문·이미지는 로그에 남기지 않는다.
"""

import base64
from functools import lru_cache
import os

import google.auth
import google.auth.transport.requests
import requests

from silen_worker.photo.service import (
    PHOTO_EMBEDDING_MODEL,
    validate_photo_vector,
)

# 실측 지연: asia-northeast3 1.26초 · us-central1 1.65초 · asia-southeast1 1.65초.
# gemini-3.5-flash와 달리 이 모델은 여러 리전에 있어 가까운 곳을 고를 수 있다.
_DEFAULT_REGION = "asia-northeast3"
_TIMEOUT_SECONDS = 60


class MultimodalEmbedder:
    """텍스트와 이미지를 같은 공간에 넣는다. 질문 하나로 사진을 찾기 위한 것이다."""

    model = PHOTO_EMBEDDING_MODEL

    def __init__(self, region: str | None = None) -> None:
        self._region = region or os.environ.get(
            "VERTEX_MULTIMODAL_REGION", _DEFAULT_REGION
        )
        self._credentials, self._project = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        if not self._project:
            raise RuntimeError("GOOGLE_CLOUD_PROJECT 미설정 — Vertex ADC 구성 필요")

    def embed_image(self, image: bytes) -> list[float]:
        return self._predict({"image": {"bytesBase64Encoded": base64.b64encode(image).decode()}})

    def embed_text(self, text: str) -> list[float]:
        """질문을 사진과 같은 공간에 넣는다. 교차 검색의 한쪽 끝이다."""
        return self._predict({"text": text})

    def _predict(self, instance: dict) -> list[float]:
        self._credentials.refresh(google.auth.transport.requests.Request())
        url = (
            f"https://{self._region}-aiplatform.googleapis.com/v1/projects/"
            f"{self._project}/locations/{self._region}/publishers/google/models/"
            f"{PHOTO_EMBEDDING_MODEL}:predict"
        )
        response = requests.post(
            url,
            headers={"Authorization": f"Bearer {self._credentials.token}"},
            json={"instances": [instance]},
            timeout=_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        prediction = response.json()["predictions"][0]
        values = prediction.get("imageEmbedding") or prediction.get("textEmbedding")
        if values is None:
            raise RuntimeError("multimodal embedding response had no vector")
        return validate_photo_vector(values)


@lru_cache(maxsize=1)
def get_multimodal_embedder() -> MultimodalEmbedder:
    """클라이언트를 재사용한다. 요청마다 새로 만들면 연결 설정에만 몇 초가 든다."""
    return MultimodalEmbedder()

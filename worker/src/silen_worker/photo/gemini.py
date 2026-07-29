"""사진 캡션. 보이는 것만 명사로 적게 한다.

캡션은 검색·엔티티 후보로만 쓰고 일기 본문이나 회고 인용에는 넣지 않는다 —
사용자가 쓴 문장이 아니다.
"""

import os

from google import genai
from google.genai import types

_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")

_PROMPT = (
    "이 사진에서 눈에 보이는 사물·장소만 한국어 명사로 최대 5개, 쉼표로 나열해라.\n"
    "추측하지 마라. 감정·분위기·상황·사람의 상태를 적지 마라.\n"
    "확실하지 않으면 적지 마라. 문장이 아니라 명사만."
)


class GeminiCaptioner:
    """caption()은 원시 출력만 반환하고 검증은 호출자(caption_guardrail) 책임이다."""

    model = _MODEL

    def __init__(self) -> None:
        if not os.environ.get("GOOGLE_CLOUD_PROJECT"):
            raise RuntimeError("GOOGLE_CLOUD_PROJECT 미설정 — Vertex ADC 구성 필요")
        self._client = genai.Client()

    def caption(self, image: bytes, mime_type: str) -> str:
        response = self._client.models.generate_content(
            model=_MODEL,
            contents=[
                types.Part.from_bytes(data=image, mime_type=mime_type),
                _PROMPT,
            ],
        )
        return (response.text or "").strip()

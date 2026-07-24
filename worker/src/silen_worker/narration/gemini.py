"""Vertex AI Gemini 서술기. ADC로 인증(비밀 키 없음, 조직 정책이 API 키 금지).
입력은 구조화 사실만(build_prompt) — 메모 본문을 전송하지 않는다. Vertex는
데이터를 학습에 쓰지 않는다(추출 기능 Task 4에서 확인).

env: GOOGLE_GENAI_USE_VERTEXAI=true, GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION=global.
모델 gemini-3.5-flash(asia-east2엔 없어 location=global).
"""

import json
import os

from google import genai
from google.genai import types

from silen_worker.narration.service import NarrationInput, build_prompt

_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")

_RESPONSE_SCHEMA = types.Schema(
    type="OBJECT",
    properties={
        "headline": types.Schema(type="STRING"),
        "body": types.Schema(type="STRING"),
        "evidence_text": types.Schema(type="STRING"),
    },
    required=["headline", "body", "evidence_text"],
)


class GeminiNarrator:
    """Narrator 포트 구현. narrate()는 원시 출력만 반환하고 가드레일 검증은
    호출자(narrate_difference→service.guardrail) 책임이다."""

    model = _MODEL

    def __init__(self) -> None:
        if not os.environ.get("GOOGLE_CLOUD_PROJECT"):
            raise RuntimeError("GOOGLE_CLOUD_PROJECT 미설정 — Vertex ADC 구성 필요")
        self._client = genai.Client()

    def narrate(self, facts: NarrationInput) -> dict:
        # 구조화 출력 강제 + "번역자" 프롬프트. 실패 시 예외를 올려 호출자가
        # 재시도/스킵을 결정하게 한다. 본문은 애초에 프롬프트에 없다.
        resp = self._client.models.generate_content(
            model=_MODEL,
            contents=build_prompt(facts),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=_RESPONSE_SCHEMA,
            ),
        )
        return json.loads(resp.text)

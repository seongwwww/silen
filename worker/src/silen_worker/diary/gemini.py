"""Vertex AI Gemini 일기 서술기. ADC로 인증(비밀 키 없음). 그날 메모 본문을 프롬프트에
담아 하루 일기를 구조화 출력으로 받는다(추출 기능과 동일한 수용된 본문 전송 흐름).
Vertex는 데이터를 학습에 쓰지 않는다. 우리 로그·예외에 본문·일기를 남기지 않는다.

env: GOOGLE_GENAI_USE_VERTEXAI=true, GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION=global.
모델 gemini-3.5-flash(asia-east2엔 없어 location=global).
"""

import json
import os

from google import genai
from google.genai import types

from silen_worker.diary.service import DiaryInput, build_prompt

_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")

_RESPONSE_SCHEMA = types.Schema(
    type="OBJECT",
    properties={
        "one_line": types.Schema(type="STRING"),
        "body": types.Schema(type="STRING"),
        "used_memory_ids": types.Schema(type="ARRAY", items=types.Schema(type="STRING")),
        "used_difference_ids": types.Schema(type="ARRAY", items=types.Schema(type="STRING")),
    },
    required=["one_line", "body", "used_memory_ids", "used_difference_ids"],
)


class GeminiDiaryWriter:
    """DiaryWriter 포트 구현. write()는 원시 출력만 반환하고 가드레일 검증은
    호출자(generate_diary→service.guardrail) 책임이다."""

    model = _MODEL

    def __init__(self) -> None:
        if not os.environ.get("GOOGLE_CLOUD_PROJECT"):
            raise RuntimeError("GOOGLE_CLOUD_PROJECT 미설정 — Vertex ADC 구성 필요")
        self._client = genai.Client()

    def write(self, facts: DiaryInput) -> dict:
        resp = self._client.models.generate_content(
            model=_MODEL,
            contents=build_prompt(facts),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=_RESPONSE_SCHEMA,
            ),
        )
        return json.loads(resp.text)

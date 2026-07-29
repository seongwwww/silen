"""Vertex AI 회고 근거 선택기. 자유 서술을 받지 않아 근거 밖 문장을 차단한다."""

import json
from functools import lru_cache
import os

from google import genai
from google.genai import types

from silen_worker.recall.service import RecallCandidate

_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
_PROMPT = (
    "질문과 가장 관련 있는 기록만 고른다. memory_id는 후보에 있는 값을 그대로 복사하고, "
    "quote는 해당 기록 원문의 연속된 부분 문자열을 그대로 복사한다. "
    "설명·조언·추측·요약 문장을 만들지 않는다. 관련 기록이 없으면 selections를 비운다."
)
_RESPONSE_SCHEMA = types.Schema(
    type="OBJECT",
    properties={
        "selections": types.Schema(
            type="ARRAY",
            items=types.Schema(
                type="OBJECT",
                properties={
                    "memory_id": types.Schema(type="STRING"),
                    "quote": types.Schema(type="STRING"),
                },
                required=["memory_id", "quote"],
            ),
        )
    },
    required=["selections"],
)


class GeminiRecallSelector:
    def __init__(self) -> None:
        if not os.environ.get("GOOGLE_CLOUD_PROJECT"):
            raise RuntimeError("GOOGLE_CLOUD_PROJECT 미설정 — Vertex ADC 구성 필요")
        self._client = genai.Client()

    def select(self, question: str, candidates: list[RecallCandidate]) -> list[dict]:
        payload = {
            "question": question,
            "candidates": [
                {
                    "memory_id": candidate.memory_id,
                    "date": candidate.effective_at.isoformat(),
                    "raw_text": candidate.raw_text,
                }
                for candidate in candidates
            ],
        }
        response = self._client.models.generate_content(
            model=_MODEL,
            contents=f"{_PROMPT}\n\n{json.dumps(payload, ensure_ascii=False)}",
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
                response_schema=_RESPONSE_SCHEMA,
                # 근거 고르기는 추론이 아니라 선택이다. 사고 과정을 켜두면
                # 응답이 3배 느려진다(실측 1.1초 → 3.7초).
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        data = json.loads(response.text)
        selections = data.get("selections", [])
        return selections if isinstance(selections, list) else []



@lru_cache(maxsize=1)
def get_recall_selector() -> GeminiRecallSelector:
    """클라이언트를 재사용한다. 요청마다 새로 만들면 연결 설정에만 몇 초가 든다."""
    return GeminiRecallSelector()

"""Vertex AI Gemini 추출기. ADC로 인증(비밀 키 없음, 조직 정책이 API 키를 금지).
Vertex AI는 고객 프롬프트/응답 데이터를 파운데이션 모델 학습에 쓰지 않는다
(Google Cloud "Training Restriction" 서비스 약관 및 데이터 거버넌스 공지 기준,
Task 4 Step 1에서 확인). 본문(text)은 처리용이며 로그·예외 메시지에 남기지 않는다.

env: GOOGLE_GENAI_USE_VERTEXAI=true, GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION.

리전 메모: 이 프로젝트/모델 조합은 asia-east2에서 404(Publisher model not found)였다.
GOOGLE_CLOUD_LOCATION=global 로 스모크 성공(Task 4 Step 2). 모델은
gemini-2.0-flash 계열이 2026-06-01부로 폐기되어(discontinued) gemini-3.5-flash로
확인했다(Task 4 Step 1/2).
"""

import json
import os

from google import genai
from google.genai import types

from silen_worker.extraction.service import EntityType

_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")

_PROMPT = (
    "다음 텍스트에 등장하는 사람·장소·활동·사물을 뽑아라. "
    "텍스트에 없는 것을 지어내지 마라. 추론·해석·감정 판단을 하지 마라. "
    "각 name은 원문에 연속으로 나타나는 부분 문자열이어야 한다 — 원문 글자를 그대로 복사하고, "
    "사전형·기본형·활용형으로 바꾸지 마라. 앞뒤 조사만 떼되, 뗀 뒤에도 반드시 원문의 연속된 부분 문자열이어야 한다. "
    "예: '요가하고'→'요가', '한강에서'→'한강', '민수랑'→'민수', '자전거 타고'→'자전거 타'. "
    "엔티티가 없으면 빈 배열."
)

_ENTITY_TYPES: list[EntityType] = ["person", "place", "activity", "thing"]

_RESPONSE_SCHEMA = types.Schema(
    type="OBJECT",
    properties={
        "entities": types.Schema(
            type="ARRAY",
            items=types.Schema(
                type="OBJECT",
                properties={
                    "type": types.Schema(type="STRING", enum=_ENTITY_TYPES),
                    "name": types.Schema(type="STRING"),
                },
                required=["type", "name"],
            ),
        )
    },
    required=["entities"],
)


class GeminiExtractor:
    """LLMExtractor 포트 구현. extract()는 원시 후보만 반환하고 가드레일
    검증(service.guardrail)은 호출자 책임 — 여기서 필터링하지 않는다."""

    def __init__(self) -> None:
        # Vertex 설정(GOOGLE_GENAI_USE_VERTEXAI·PROJECT·LOCATION)과 ADC를
        # env·환경 신원에서 자동 해석한다. 프로젝트 미설정 시 명확히 실패.
        if not os.environ.get("GOOGLE_CLOUD_PROJECT"):
            raise RuntimeError("GOOGLE_CLOUD_PROJECT 미설정 — Vertex ADC 구성 필요")
        self._client = genai.Client()

    def extract(self, text: str) -> list[dict]:
        # 구조화 출력 강제(response_schema) + "지어내지 마라" 프롬프트.
        # 실패 시 예외를 그대로 올린다 — process_pending이 큐 메시지를
        # 삭제하지 않고 재시도하게 한다(backend.md 멱등성/에러 처리).
        # 타임아웃·재시도는 SDK 기본 재시도(tenacity 내장)에 위임하고,
        # 그 이상의 백오프/서킷브레이커는 큐 재시도 루프가 담당한다.
        resp = self._client.models.generate_content(
            model=_MODEL,
            contents=f"{_PROMPT}\n\n---\n{text}",
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=_RESPONSE_SCHEMA,
            ),
        )
        data = json.loads(resp.text)
        return data.get("entities", [])

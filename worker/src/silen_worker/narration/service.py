"""서술 오케스트레이션·프롬프트 조립·가드레일. LLM은 Narrator 포트로 주입한다.
프레임워크·DB·Gemini를 모른다(순수 로직) — 여기 테스트를 집중한다.
입력은 구조화 사실만(메모 본문 없음). 출력은 가드레일 통과분만.
"""

from dataclasses import dataclass
from typing import Protocol

from silen_worker.narration.constants import (
    BODY_MAX,
    EVIDENCE_MAX,
    FORBIDDEN_PHRASES,
    HEADLINE_MAX,
)


@dataclass(frozen=True)
class NarrationInput:
    difference_id: str
    user_id: str
    entity_name: str
    entity_type: str
    detection_method: str
    description: str
    date_iso: str


@dataclass(frozen=True)
class Narration:
    headline: str
    body: str
    evidence_text: str


class Narrator(Protocol):
    model: str

    def narrate(self, facts: NarrationInput) -> dict:
        """{"headline","body","evidence_text"} 원시 출력. 가드레일 전."""
        ...


_METHOD_LABEL = {
    "first_occurrence": "처음 등장",
    "freq_shift": "반복/빈도 변화",
}


def build_prompt(facts: NarrationInput) -> str:
    """구조화 사실만으로 프롬프트를 조립한다. 메모 본문은 넣지 않는다."""
    return (
        "너는 일기 앱 '실은'의 서술 담당이다. 통계 엔진이 이미 검증한 '다른 점' 하나를\n"
        "사람이 읽을 담백한 한국어 카드로 옮겨라. 너는 번역자이지 발견자가 아니다.\n"
        "규칙: 아래 사실에 없는 사건·인물·감정·인과를 만들지 마라. 조언·응원·교훈 금지.\n"
        "단정하지 말고 관찰체로. 없는 감정을 지어내지 마라. 반드시 엔티티 이름을 넣어라.\n\n"
        f"엔티티: {facts.entity_name} ({facts.entity_type})\n"
        f"차이 유형: {_METHOD_LABEL.get(facts.detection_method, facts.detection_method)}\n"
        f"통계 근거: {facts.description}\n"
        f"날짜: {facts.date_iso}\n\n"
        "출력(JSON): headline(12자 내외), body(1~2문장, 사실만), "
        "evidence_text(왜 찾았는지 한 줄, 통계 용어 순화)."
    )


def guardrail(raw: dict, facts: NarrationInput) -> Narration | None:
    """결정적 방어선. 통과 못 하면 None(저장 안 함).
    ① 세 필드 비어있지 않음 ② 길이 상한 ③ 엔티티명 정합(headline+body에 실재)
    ④ 조언·응원·인과 블록리스트 미포함."""
    if not isinstance(raw, dict):
        return None
    headline = (raw.get("headline") or "").strip()
    body = (raw.get("body") or "").strip()
    evidence = (raw.get("evidence_text") or "").strip()
    if not headline or not body or not evidence:
        return None
    if len(headline) > HEADLINE_MAX or len(body) > BODY_MAX or len(evidence) > EVIDENCE_MAX:
        return None
    if facts.entity_name not in f"{headline} {body}":
        return None
    blob = f"{headline} {body} {evidence}"
    if any(p in blob for p in FORBIDDEN_PHRASES):
        return None
    return Narration(headline=headline, body=body, evidence_text=evidence)

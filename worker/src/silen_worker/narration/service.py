"""서술 오케스트레이션·프롬프트 조립·가드레일. LLM은 Narrator 포트로 주입한다.
프레임워크·DB·Gemini를 모른다(순수 로직) — 여기 테스트를 집중한다.
입력은 구조화 사실만(메모 본문 없음). 출력은 가드레일 통과분만.
"""

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
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
    entity_id: str | None
    entity_name: str | None
    entity_type: str | None
    detection_method: str
    description: str
    date_iso: str
    dimension: str
    evidence_ids: tuple[str, ...]


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
    "freq_shift": "반복/빈도 변화",
    "zscore": "감정 기록 변화",
}

EMOTION_FORBIDDEN_PHRASES = (
    "힘드시겠",
    "힘들었겠",
    "괜찮",
    "힘내",
    "이겨낼",
    "잘하고",
    "수고",
    "토닥",
    "쉬어가",
    "우울",
    "불안",
    "슬프",
    "속상",
    "지쳤",
    "외롭",
    "스트레스",
    "행복",
    "기분",
    "마음이",
    "원인",
    "영향",
    "에서 비롯",
)

_NUMBER_PATTERN = re.compile(
    r"(?<![\d.A-Za-z_])[-+]?(?:\d+(?:\.\d+)?|\.\d+)(?![\d.A-Za-z_])"
)


def build_prompt(facts: NarrationInput) -> str:
    """구조화 사실만으로 프롬프트를 조립한다. 메모 본문은 넣지 않는다."""
    if not facts.evidence_ids:
        raise ValueError("narration requires evidence ids")
    evidence_ids = ", ".join(facts.evidence_ids)
    common = (
        "너는 일기 앱 '실은'의 서술 담당이다. 통계 엔진이 이미 검증한 '다른 점' 하나를\n"
        "사람이 읽을 담백한 한국어 카드로 옮겨라. 너는 번역자이지 발견자가 아니다.\n"
        "규칙: 아래 사실에 없는 사건·인물·감정·인과를 만들지 마라. 조언·응원·교훈 금지.\n"
        "단정하지 말고 관찰체로. 없는 감정을 지어내지 마라.\n"
        "사용자가 남긴 것은 '기록'이다. '일기'라고 부르지 마라 — 일기는 이 앱이\n"
        "따로 만들어 주는 산물이라 둘을 섞으면 안 된다.\n"
    )
    if facts.dimension == "emotion":
        subject = (
            "감정에 관해 쓸 수 있는 사실은 아래 근거에 적힌 라벨과 날짜 수뿐이다.\n"
            "사용자가 고른 라벨은 '좋음'·'그냥'·'별로' 셋뿐이다. 점수·평균·수치를\n"
            "지어내거나 옮기지 말고 이 라벨 그대로 말해라.\n"
            "사용자의 상태를 해석하지 말고 원인·위로·권유를 만들지 마라.\n\n"
            "차원: 감정 기록\n"
        )
    else:
        if not facts.entity_id or not facts.entity_name or not facts.entity_type:
            raise ValueError("entity narration requires entity identity")
        subject = (
            "반드시 엔티티 이름을 넣어라.\n\n"
            f"엔티티: {facts.entity_name} ({facts.entity_type})\n"
        )

    return (
        common
        + subject
        + f"차이 유형: {_METHOD_LABEL.get(facts.detection_method, facts.detection_method)}\n"
        f"통계 근거: {facts.description}\n"
        f"날짜: {facts.date_iso}\n\n"
        f"근거 ID: {evidence_ids} (추적용이며 출력 문장에 복사하지 마라)\n\n"
        "출력(JSON): headline(12자 내외), body(1~2문장, 사실만), "
        "evidence_text(왜 찾았는지 한 줄, 통계 용어 순화)."
    )


def guardrail(raw: dict, facts: NarrationInput) -> Narration | None:
    """결정적 방어선. 통과 못 하면 None(저장 안 함).
    엔티티 차이는 이름 정합을, 감정 차이는 수치·해석 금지를 별도로 검증한다."""
    if not isinstance(raw, dict):
        return None
    if not facts.evidence_ids:
        return None
    headline = str(raw.get("headline") or "").strip()
    body = str(raw.get("body") or "").strip()
    evidence = str(raw.get("evidence_text") or "").strip()
    if not headline or not body or not evidence:
        return None
    if len(headline) > HEADLINE_MAX or len(body) > BODY_MAX or len(evidence) > EVIDENCE_MAX:
        return None
    blob = f"{headline} {body} {evidence}"
    if any(p in blob for p in FORBIDDEN_PHRASES):
        return None

    if facts.dimension == "emotion":
        if any(p in blob for p in EMOTION_FORBIDDEN_PHRASES):
            return None
        allowed_numbers = _numbers(
            f"{facts.description} {facts.date_iso}"
        )
        if not _numbers(blob).issubset(allowed_numbers):
            return None
    else:
        if (
            not facts.entity_id
            or not facts.entity_name
            or not facts.entity_type
            or facts.entity_name not in f"{headline} {body}"
        ):
            return None

    return Narration(headline=headline, body=body, evidence_text=evidence)


def _numbers(text: str) -> set[Decimal]:
    """표기 차이(0.20/0.2)를 허용하면서 새 수치 삽입 여부를 비교한다."""
    numbers: set[Decimal] = set()
    for token in _NUMBER_PATTERN.findall(text):
        try:
            numbers.add(Decimal(token))
        except InvalidOperation:
            continue
    return numbers

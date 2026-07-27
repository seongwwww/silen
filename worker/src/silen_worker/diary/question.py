"""꼬리 질문 — 처음 등장한 것에 대해 하루 한 번만 묻는다(prompts-draft §6).

기본은 묻지 않는다. 물어도 부담이 없어야 하고, 심문하지 않는다.
답변은 별도로 저장하지 않는다 — 사용자가 남기는 새 기록이 곧 답이다.
"""

from typing import Protocol

from silen_worker.db import ConfirmedDifference

# 사람·장소·활동이 이야기가 된다. 사물은 묻지 않는다.
QUESTION_TARGET_TYPES = ("person", "place", "activity")

QUESTION_MAX = 60

# 심문조·강요. "답 안 해도 되게" 하려면 이런 말투를 막아야 한다.
FORBIDDEN_QUESTION_PHRASES = (
    "말해보세요",
    "말해 보세요",
    "설명하세요",
    "적어주세요",
    "해야",
    "반드시",
)


def pick_question_target(
    confirmed: list[ConfirmedDifference],
) -> ConfirmedDifference | None:
    """질문 대상 하나. 처음 등장한 사람 > 장소 > 활동 순. 없으면 None(묻지 않는다)."""
    firsts = [c for c in confirmed if c.detection_method == "first_occurrence"]
    for entity_type in QUESTION_TARGET_TYPES:
        for candidate in firsts:
            if candidate.entity_type == entity_type:
                return candidate
    return None


def build_question_prompt(target: ConfirmedDifference) -> str:
    return (
        "너는 일기 앱 '실은'의 질문 담당이다. 오늘 처음 등장한 것에 대해\n"
        "짧은 질문 하나를 만들어라.\n"
        "규칙: 부담 없는 말투로, 답하지 않아도 되게. 심문하지 마라.\n"
        "'무엇을 했냐'가 아니라 '어땠냐/어떤 사람이냐' 방향으로.\n"
        f"아래 표현을 그대로 써라: {target.entity_name}\n"
        f"{QUESTION_MAX}자 이내.\n\n"
        f"처음 등장: {target.entity_name} ({target.entity_type})\n\n"
        '출력(JSON): {"question": "..."}'
    )


def question_guardrail(raw: dict, target: ConfirmedDifference) -> str | None:
    """통과한 질문 문자열, 아니면 None(저장하지 않는다)."""
    if not isinstance(raw, dict):
        return None
    question = str(raw.get("question") or "").strip()
    if not question or len(question) > QUESTION_MAX:
        return None
    if target.entity_name not in question:
        return None
    if any(p in question for p in FORBIDDEN_QUESTION_PHRASES):
        return None
    return question


class QuestionWriter(Protocol):
    def ask(self, target: ConfirmedDifference) -> dict:
        """{"question": "..."} 원시 출력. 가드레일 전."""
        ...

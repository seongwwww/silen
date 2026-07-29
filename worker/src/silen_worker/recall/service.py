"""회고 후보 병합과 응답 가드레일. LLM·DB를 모르는 순수 계층."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

NO_RECALL_RESULT = "그런 기록은 찾지 못했어요"
RECALL_ANSWER = "기록에서 이런 내용을 찾았어요."
RECALL_CONFIRMATION = "이거 맞으세요?"
# LLM에 넘기는 후보 수. 늘리면 입력과 생성이 함께 늘어 응답이 느려지고,
# 사용자가 읽어야 할 근거 카드도 많아진다.
RECALL_LIMIT = 5
RRF_K = 60

_QUESTION_STOPWORDS = frozenset(
    {
        "언제",
        "어디",
        "뭐",
        "무엇",
        "어땠지",
        "했지",
        "갔지",
        "였지",
        "내가",
        "나",
        "기억",
        "기록",
    }
)


@dataclass(frozen=True)
class RecallCandidate:
    memory_id: str
    raw_text: str
    effective_at: datetime
    photo_path: str | None = None


class RecallSelector(Protocol):
    def select(self, question: str, candidates: list[RecallCandidate]) -> list[dict]:
        """후보에서 memory_id와 원문 그대로의 quote만 고른다."""


def keyword_terms(question: str) -> list[str]:
    """고유명사는 보존하고 질문형 군더더기는 제외한다."""
    normalized = "".join(char if char.isalnum() else " " for char in question)
    terms: list[str] = []
    for token in normalized.split():
        if len(token) < 2 or token in _QUESTION_STOPWORDS or token in terms:
            continue
        terms.append(token)
    return terms


def merge_hybrid_candidates(
    vector_candidates: list[RecallCandidate],
    keyword_candidates: list[RecallCandidate],
    limit: int = RECALL_LIMIT,
) -> list[RecallCandidate]:
    """두 순위에 RRF를 적용하고 날짜·ID까지 고정해 항상 같은 순서를 낸다."""
    candidates: dict[str, RecallCandidate] = {}
    scores: dict[str, float] = {}
    for ranked in (vector_candidates, keyword_candidates):
        for rank, candidate in enumerate(ranked, start=1):
            candidates[candidate.memory_id] = candidate
            scores[candidate.memory_id] = scores.get(candidate.memory_id, 0.0) + (
                1.0 / (RRF_K + rank)
            )
    ordered = sorted(
        candidates.values(),
        key=lambda item: (
            -scores[item.memory_id],
            -item.effective_at.timestamp(),
            item.memory_id,
        ),
    )
    return ordered[: max(0, limit)]


PHOTO_EVIDENCE_LIMIT = 3
PHOTO_ONLY_ANSWER = "글로 남긴 건 못 찾았고, 사진에서 비슷한 걸 찾았어요."


def with_photo_evidence(
    response: dict,
    photos: list[RecallCandidate],
    limit: int = PHOTO_EVIDENCE_LIMIT,
) -> dict:
    """사진 근거를 결정적으로 덧붙인다.

    LLM에게 사진을 고르게 하지 않는다 — 인용 가드레일은 원문 대조를 요구하는데
    사진만 있는 기록은 대조할 원문이 없어, LLM이 고르면 응답 전체가 폐기된다.
    벡터 순위 그대로 붙이고 인용은 비운다. 지어낸 문장이 생길 여지가 없다.
    """
    if not photos:
        return response

    evidence = list(response.get("evidence") or [])
    cited = {item["memoryId"] for item in evidence}
    added = 0
    for candidate in photos:
        if added >= limit or candidate.memory_id in cited:
            continue
        if not candidate.photo_path:
            continue
        evidence.append(
            {
                "memoryId": candidate.memory_id,
                "capturedAt": candidate.effective_at.isoformat(),
                "quote": "",
                "photoPath": candidate.photo_path,
            }
        )
        cited.add(candidate.memory_id)
        added += 1

    if not added:
        return response

    answer = response.get("answer") or ""
    return {
        **response,
        "answer": answer if evidence[0]["quote"] else PHOTO_ONLY_ANSWER,
        "evidence": evidence,
    }


def empty_recall_response() -> dict:
    return {
        "answer": NO_RECALL_RESULT,
        "confirmation": None,
        "evidence": [],
    }


def build_grounded_response(
    candidates: list[RecallCandidate],
    selections: list[dict],
) -> dict:
    """ID 부분집합·원문 substring을 모두 통과할 때만 응답을 만든다."""
    if not candidates or not selections:
        return empty_recall_response()
    by_id = {candidate.memory_id: candidate for candidate in candidates}
    seen: set[str] = set()
    evidence: list[dict] = []
    for selection in selections:
        memory_id = selection.get("memory_id")
        quote = selection.get("quote")
        if (
            not isinstance(memory_id, str)
            or not isinstance(quote, str)
            or memory_id in seen
        ):
            return empty_recall_response()
        candidate = by_id.get(memory_id)
        normalized_quote = quote.strip()
        if candidate is None or not normalized_quote or normalized_quote not in candidate.raw_text:
            return empty_recall_response()
        seen.add(memory_id)
        evidence.append(
            {
                "memoryId": memory_id,
                "capturedAt": candidate.effective_at.isoformat(),
                "quote": normalized_quote,
                "photoPath": candidate.photo_path,
            }
        )
    return {
        "answer": RECALL_ANSWER,
        "confirmation": RECALL_CONFIRMATION,
        "evidence": evidence,
    }

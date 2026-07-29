"""사진 캡션과 사진 엔티티 채택 규칙. LLM·DB를 모르는 순수 계층이다.

캡션은 사용자가 쓴 글이 아니라 AI가 만든 파생물이다. 그래서
`memories.raw_text`에 섞지 않고 `assets.extracted_text`에 따로 둔다
(원본 ↔ AI 생성물 분리).
"""

from silen_worker.extraction.constants import ENTITY_STOPWORDS
from silen_worker.extraction.service import ExtractedEntity, normalize_name

CAPTION_MAX = 120

# 캡션은 보이는 것만 적는다. 추측이 섞이면 사용자가 쓴 적 없는 해석이
# 검색·탐지로 흘러든다(과잉해석 금지).
_SPECULATION = (
    "같다",
    "같아",
    "듯",
    "보인다",
    "보여",
    "인 것",
    "추정",
    "아마",
    "느껴",
)


def caption_guardrail(raw: str) -> str | None:
    """통과 못 하면 None(저장 안 함)."""
    caption = (raw or "").strip()
    if not caption or len(caption) > CAPTION_MAX:
        return None
    if any(word in caption for word in _SPECULATION):
        return None
    return caption


def embeddable_text(raw_text: str | None, caption: str | None) -> str | None:
    """검색용 본문. 사진만 있는 기록은 지금까지 임베딩조차 되지 않아
    검색에서 통째로 사라졌다."""
    parts = [part for part in (raw_text, caption) if part and part.strip()]
    if not parts:
        return None
    return "\n".join(part.strip() for part in parts)


def anchored_entities(
    candidates: list[ExtractedEntity],
    user_vocabulary: set[str],
) -> list[ExtractedEntity]:
    """사진에서 뽑은 엔티티 중 **사용자가 텍스트로 쓴 적 있는 말**만 채택한다.

    텍스트 추출에는 "원문에 없으면 폐기"라는 앵커가 있지만 사진에는 없다.
    앵커 없이 받으면 사용자가 쓴 적도 없고 검증도 안 된 말로 차이가 뜬다.
    사용자의 언어 밖으로 나가지 않는 것이 여기서의 앵커다.
    """
    out: list[ExtractedEntity] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = normalize_name(candidate.name)
        if key in ENTITY_STOPWORDS or key in seen:
            continue
        if key not in user_vocabulary:
            continue
        seen.add(key)
        out.append(candidate)
    return out

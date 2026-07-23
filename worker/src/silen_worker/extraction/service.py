"""추출 오케스트레이션·가드레일·정규화. LLM은 LLMExtractor 포트로 주입한다.
프레임워크·DB·Gemini를 모른다(순수 로직) — 여기 테스트를 집중한다.
"""

from dataclasses import dataclass
from typing import Literal, Protocol

EntityType = Literal["person", "place", "activity", "thing"]
_VALID_TYPES = {"person", "place", "activity", "thing"}


@dataclass
class ExtractedEntity:
    type: EntityType
    name: str
    normalized_name: str


class LLMExtractor(Protocol):
    def extract(self, text: str) -> list[dict]:
        """[{"type","name"}] 원시 후보를 반환한다. 가드레일 전."""
        ...


def normalize_name(name: str) -> str:
    """보수적 병합 키. 공백 제거·소문자화만. 과병합 금지 — 이 이상 손대지 않는다."""
    return name.replace(" ", "").lower()


def guardrail(candidates: list[dict], text: str) -> list[ExtractedEntity]:
    """원문에 실재하지 않는 name·스키마 밖 type을 폐기한다(환각 0%).
    추출자이지 해석자가 아니다 — 확장·추론된 이름은 원문에 없어 자동 탈락한다."""
    out: list[ExtractedEntity] = []
    seen: set[tuple[str, str]] = set()
    for c in candidates:
        etype = c.get("type")
        raw_name = c.get("name")
        if etype not in _VALID_TYPES or not isinstance(raw_name, str):
            continue
        name = raw_name.strip()
        if not name:
            continue
        if name not in text:
            continue
        key = (etype, normalize_name(name))
        if key in seen:
            continue
        seen.add(key)
        out.append(ExtractedEntity(type=etype, name=name, normalized_name=normalize_name(name)))
    return out

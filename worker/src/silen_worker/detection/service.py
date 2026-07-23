"""결정적 차이 규칙. DB·LLM·프레임워크를 모른다 — 테스트를 여기 집중(spec §5.2).

입력: 오늘 포함 창 안의 엔티티별 등장 날짜 집합 + 전체 이력 존재 여부.
출력: DetectedDifference 목록. 오늘 등장한 엔티티만, 정확히 하나로 분류(상호 배타).
"""

from dataclasses import dataclass
from datetime import date, timedelta

from silen_worker.detection.constants import (
    FIRST_OCCURRENCE_CONFIDENCE,
    REEMERGENCE_CONFIDENCE_SPAN,
    REEMERGENCE_GAP_MIN,
    STREAK_CONFIDENCE_SPAN,
    STREAK_MIN,
    WINDOW_DAYS,
)


@dataclass(frozen=True)
class EntityWindow:
    entity_id: str
    entity_type: str
    dates: frozenset          # 창[target-(WINDOW-1)..target] 안의 로컬 날짜, target 포함 가정
    occurred_before: bool     # target 이전 전체 이력에 등장한 적 있는가


@dataclass(frozen=True)
class DetectedDifference:
    entity_id: str
    entity_type: str
    method: str               # 'first_occurrence' | 'freq_shift'
    description: str          # 통계 근거(사람에게 직접 노출 안 함)
    confidence: float


def _streak_len(dates: frozenset, target: date) -> int:
    """target에서 끝나는 연속 등장 일수."""
    n = 0
    d = target
    while d in dates:
        n += 1
        d -= timedelta(days=1)
    return n


def detect_differences(target_date: date, windows: list[EntityWindow]) -> list[DetectedDifference]:
    out: list[DetectedDifference] = []
    for w in windows:
        if target_date not in w.dates:
            continue  # 오늘 등장한 엔티티만 분류

        if not w.occurred_before:
            out.append(
                DetectedDifference(
                    w.entity_id, w.entity_type, "first_occurrence",
                    f"이 {w.entity_type} 첫 등장", FIRST_OCCURRENCE_CONFIDENCE,
                )
            )
            continue

        # freq_shift: 이력 있음. 창 안 반복 신호가 있을 때만.
        streak = _streak_len(w.dates, target_date)
        if streak >= STREAK_MIN:
            conf = min(1.0, (streak - 1) / STREAK_CONFIDENCE_SPAN)
            out.append(
                DetectedDifference(
                    w.entity_id, w.entity_type, "freq_shift",
                    f"최근 {streak}일 연속 등장", conf,
                )
            )
            continue

        prior = [d for d in w.dates if d < target_date]
        if prior:
            gap = (target_date - max(prior)).days
            if gap >= REEMERGENCE_GAP_MIN:
                conf = min(1.0, gap / REEMERGENCE_CONFIDENCE_SPAN)
                out.append(
                    DetectedDifference(
                        w.entity_id, w.entity_type, "freq_shift",
                        f"{gap}일 만에 재등장(최근 {WINDOW_DAYS}일 내)", conf,
                    )
                )
        # 그 외(산발적) → 차이 없음(오탐 억제)
    return out

"""결정적 엔티티 차이 규칙과 일일 카드 랭킹."""

from dataclasses import dataclass
from datetime import date

from silen_worker.detection.constants import REEMERGENCE_GAP_MIN
from silen_worker.detection.surprisal import surprisal_bits


@dataclass(frozen=True)
class EntityWindow:
    entity_id: str
    entity_type: str
    dates: frozenset[date]
    occurred_before: bool
    last_prior_date: date | None = None


@dataclass(frozen=True)
class DetectedDifference:
    entity_id: str
    entity_type: str
    method: str
    description: str
    confidence: float


def detect_differences(
    target_date: date,
    windows: list[EntityWindow],
    *,
    active_history_dates: frozenset[date],
    today_is_active: bool,
) -> list[DetectedDifference]:
    """활성 기록일을 분모로 부재와 오랜만의 재등장을 찾는다.

    오늘 기록이 없으면 생활의 부재로 오인하지 않도록 아무것도 만들지 않는다.
    연속 등장은 주간 리포트의 책임이라 여기서는 다루지 않는다.
    """
    if not today_is_active:
        return []

    active_history = frozenset(
        day for day in active_history_dates if day < target_date
    )
    active_days = len(active_history)
    out: list[DetectedDifference] = []

    for window in windows:
        present_today = target_date in window.dates
        history_dates = frozenset(
            day for day in window.dates if day in active_history
        )
        seen_days = len(history_dates)

        if present_today and not window.occurred_before:
            out.append(
                DetectedDifference(
                    window.entity_id,
                    window.entity_type,
                    "first_occurrence",
                    "처음 등장",
                    surprisal_bits(active_days, seen_days, True),
                )
            )
            continue

        last_prior = window.last_prior_date
        if last_prior is None and history_dates:
            last_prior = max(history_dates)

        if not present_today:
            if seen_days < 2 or last_prior is None:
                continue
            gap = (target_date - last_prior).days
            out.append(
                DetectedDifference(
                    window.entity_id,
                    window.entity_type,
                    "freq_shift",
                    (
                        f"과거 활성일 {active_days}일 중 {seen_days}일 기록됨, "
                        f"오늘 기록에는 언급 없음, 마지막 {gap}일 전"
                    ),
                    surprisal_bits(active_days, seen_days, False),
                )
            )
            continue

        if (
            window.occurred_before
            and last_prior is not None
            and (target_date - last_prior).days >= REEMERGENCE_GAP_MIN
        ):
            gap = (target_date - last_prior).days
            out.append(
                DetectedDifference(
                    window.entity_id,
                    window.entity_type,
                    "freq_shift",
                    (
                        f"{gap}일 만에 재등장"
                        f"(과거 활성일 {active_days}일 중 {seen_days}일 기록됨)"
                    ),
                    surprisal_bits(active_days, seen_days, True),
                )
            )

    return out

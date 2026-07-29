"""결정적 엔티티 차이 규칙과 일일 카드 랭킹."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Protocol, TypeVar

from silen_worker.detection.constants import (
    DAILY_DIFFERENCE_LIMIT,
    DISMISS_EXCLUDE_COUNT,
    MIN_ACTIVE_HISTORY_DAYS,
    REEMERGENCE_GAP_MIN,
    SURPRISAL_MIN_BITS,
)
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

    @property
    def dimension(self) -> str:
        return self.entity_type


class RankableDifference(Protocol):
    entity_id: str | None
    method: str
    confidence: float

    @property
    def dimension(self) -> str: ...


RankableT = TypeVar("RankableT", bound=RankableDifference)


def detect_differences(
    target_date: date,
    windows: list[EntityWindow],
    *,
    active_history_dates: frozenset[date],
    today_is_active: bool,
    include_absence: bool = True,
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
            # 하루가 끝나기 전에는 부재를 말하지 않는다. 오전에 "오늘 운동이
            # 없네요"는 사실이 아니라 아직 오지 않은 일에 대한 단정이다.
            if not include_absence:
                continue
            if seen_days < 2 or last_prior is None:
                continue
            gap = (target_date - last_prior).days
            out.append(
                DetectedDifference(
                    window.entity_id,
                    window.entity_type,
                    "freq_shift",
                    (
                        f"기록을 남긴 {active_days}일 중 {seen_days}일에 있었음, "
                        f"오늘 기록에는 없음, 마지막은 {gap}일 전"
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
                        f"(기록을 남긴 {active_days}일 중 {seen_days}일에 있었음)"
                    ),
                    surprisal_bits(active_days, seen_days, True),
                )
            )

    return out


def rank_differences(
    candidates: list[RankableT],
    dismiss_counts: Mapping[tuple[str | None, str, str], int],
    *,
    active_history_days: int,
) -> list[RankableT]:
    """놀라움과 최근 기각 이력으로 오늘 노출할 최대 3건을 고른다."""
    if active_history_days < MIN_ACTIVE_HISTORY_DAYS:
        return []

    ranked: list[tuple[float, RankableT]] = []
    for candidate in candidates:
        if candidate.method == "first_occurrence":
            continue
        if candidate.confidence < SURPRISAL_MIN_BITS:
            continue
        dismissed = dismiss_counts.get(
            (
                candidate.entity_id,
                candidate.dimension,
                candidate.method,
            ),
            0,
        )
        if dismissed >= DISMISS_EXCLUDE_COUNT:
            continue
        ranked.append(
            (candidate.confidence / (1 + dismissed), candidate)
        )

    ranked.sort(
        key=lambda item: (
            -item[0],
            item[1].entity_id or "",
            item[1].dimension,
            item[1].method,
        )
    )
    return [item[1] for item in ranked[:DAILY_DIFFERENCE_LIMIT]]

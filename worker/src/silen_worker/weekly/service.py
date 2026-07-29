"""Build deterministic weekly report slots from already verified observations."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from math import isclose, isfinite, log2
from statistics import NormalDist, fmean, pstdev
from typing import Iterable

from silen_worker.detection.emotion import (
    bits_ceiling,
    MIN_BASELINE_DAYS,
    P_FLOOR,
    SD_FLOOR,
    ZERO_ABS_TOLERANCE,
)


@dataclass(frozen=True)
class WeeklyMemory:
    memory_id: str
    local_date: date


@dataclass(frozen=True)
class EntityOccurrence:
    entity_id: str
    entity_type: str
    normalized_name: str
    memory_id: str
    local_date: date


@dataclass(frozen=True)
class FirstOccurrence:
    difference_id: str
    local_date: date
    entity_id: str
    normalized_name: str


@dataclass(frozen=True)
class EmotionObservation:
    memory_id: str
    local_date: date
    valence: float


@dataclass(frozen=True)
class ExistingEmotionDifference:
    difference_id: str
    local_date: date


@dataclass(frozen=True)
class WeeklySlot:
    slot: str
    difference_id: str | None
    entity_id: str | None
    entity_type: str | None
    local_date: date | None
    detection_method: str
    category: str
    description: str
    confidence: float
    evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class WeeklyReportPlan:
    week_start: date
    week_end: date
    slots: tuple[WeeklySlot, ...]


@dataclass(frozen=True)
class _EmotionScore:
    z: float
    bits: float
    mean: float
    value: float
    baseline_days: int


def completed_week_start(anchor: date, as_of: date) -> date | None:
    """Return the block that has just completed on ``as_of``.

    Reports are emitted only on exact seven-day boundaries measured from the
    user's first active memory date.
    """

    elapsed = (as_of - anchor).days
    if elapsed < 7 or elapsed % 7:
        return None
    return as_of - timedelta(days=7)


def completed_week_containing(
    anchor: date,
    target: date,
    as_of: date,
) -> date | None:
    """Return target's anchored block only after that block has completed."""

    elapsed = (target - anchor).days
    if elapsed < 0:
        return None
    week_start = anchor + timedelta(days=(elapsed // 7) * 7)
    return week_start if week_start + timedelta(days=7) <= as_of else None


def _in_block(local_date: date, start: date, end: date) -> bool:
    return start <= local_date <= end


def _most_frequent_slot(
    occurrences: Iterable[EntityOccurrence],
    week_start: date,
    week_end: date,
) -> WeeklySlot | None:
    grouped: dict[str, list[EntityOccurrence]] = defaultdict(list)
    for occurrence in occurrences:
        if _in_block(occurrence.local_date, week_start, week_end):
            grouped[occurrence.entity_id].append(occurrence)
    if not grouped:
        return None

    def sort_key(item: tuple[str, list[EntityOccurrence]]) -> tuple[int, str, str]:
        entity_id, rows = item
        return (-len(rows), rows[0].normalized_name, entity_id)

    entity_id, rows = min(grouped.items(), key=sort_key)
    representative = min(
        rows,
        key=lambda row: (
            row.normalized_name,
            row.entity_type,
            row.local_date,
            row.memory_id,
        ),
    )
    evidence_ids = tuple(
        row.memory_id
        for row in sorted(rows, key=lambda row: (row.local_date, row.memory_id))
    )
    count = len(rows)
    return WeeklySlot(
        slot="\uac00\uc7a5\ub9ce\uc774\ud55c\uac83",
        difference_id=None,
        entity_id=entity_id,
        entity_type=representative.entity_type,
        local_date=week_end,
        detection_method="pattern",
        category="\ud328\ud134",
        description=f"7\uc77c \uae30\ub85d\uc5d0\uc11c {count}\ud68c \uc5b8\uae09",
        confidence=float(count),
        evidence_ids=evidence_ids,
    )


def _first_occurrence_slot(
    occurrences: Iterable[FirstOccurrence],
    week_start: date,
    week_end: date,
) -> WeeklySlot | None:
    candidates = [
        occurrence
        for occurrence in occurrences
        if _in_block(occurrence.local_date, week_start, week_end)
    ]
    if not candidates:
        return None
    chosen = min(
        candidates,
        key=lambda row: (
            row.local_date,
            row.normalized_name,
            row.entity_id,
            row.difference_id,
        ),
    )
    return WeeklySlot(
        slot="\ucc98\uc74c\ud55c\uac83",
        difference_id=chosen.difference_id,
        entity_id=chosen.entity_id,
        entity_type=None,
        local_date=chosen.local_date,
        detection_method="first_occurrence",
        category="\uc624\ub298\uc758\ub2e4\ub978\uc810",
        description=f"{chosen.normalized_name}\uc744(\ub97c) \ucc98\uc74c \uae30\ub85d",
        confidence=0.0,
    )


def _emotion_score(value: float, baseline: list[float]) -> _EmotionScore | None:
    if len(baseline) < MIN_BASELINE_DAYS:
        return None
    mean = fmean(baseline)
    z = (value - mean) / max(pstdev(baseline), SD_FLOOR)
    if isclose(z, 0.0, abs_tol=ZERO_ABS_TOLERANCE):
        return None
    p = 2 * (1 - NormalDist().cdf(abs(z)))
    bits = min(bits_ceiling(len(baseline)), -log2(max(p, P_FLOOR)))
    return _EmotionScore(
        z=z,
        bits=bits,
        mean=mean,
        value=value,
        baseline_days=len(baseline),
    )


def _emotion_slot(
    observations: Iterable[EmotionObservation],
    existing: Iterable[ExistingEmotionDifference],
    week_start: date,
    week_end: date,
) -> WeeklySlot | None:
    grouped: dict[date, list[EmotionObservation]] = defaultdict(list)
    for observation in observations:
        if observation.local_date <= week_end and isfinite(observation.valence):
            grouped[observation.local_date].append(observation)

    daily = {
        local_date: fmean(row.valence for row in rows)
        for local_date, rows in grouped.items()
        if rows
    }
    candidates: list[tuple[date, _EmotionScore]] = []
    for local_date, value in daily.items():
        if not _in_block(local_date, week_start, week_end):
            continue
        baseline = [
            previous
            for previous_date, previous in daily.items()
            if previous_date < local_date
        ]
        score = _emotion_score(value, baseline)
        if score is not None:
            candidates.append((local_date, score))
    if not candidates:
        return None

    local_date, score = min(
        candidates,
        key=lambda item: (-abs(item[1].z), item[0]),
    )
    existing_ids = sorted(
        difference.difference_id
        for difference in existing
        if difference.local_date == local_date
    )
    evidence_ids = tuple(
        row.memory_id
        for evidence_date in sorted(grouped)
        if _in_block(evidence_date, week_start, week_end)
        for row in sorted(grouped[evidence_date], key=lambda item: item.memory_id)
    )
    return WeeklySlot(
        slot="\uac10\uc815\uc21c\uac04",
        difference_id=existing_ids[0] if existing_ids else None,
        entity_id=None,
        entity_type=None,
        local_date=local_date,
        detection_method="zscore",
        category="\uac10\uc815\uc804\ud658",
        description=(
            f"\ucd5c\uadfc {score.baseline_days}\uc77c \ud3c9\uade0 "
            f"{score.mean:.2f}, \ud574\ub2f9 \ub0a0 {score.value:.2f} "
            f"(z={score.z:.1f})"
        ),
        confidence=score.bits,
        evidence_ids=evidence_ids,
    )


def build_weekly_report(
    anchor: date,
    as_of: date,
    memories: Iterable[WeeklyMemory],
    entity_occurrences: Iterable[EntityOccurrence],
    first_occurrences: Iterable[FirstOccurrence],
    emotion_observations: Iterable[EmotionObservation],
    existing_emotion_differences: Iterable[ExistingEmotionDifference],
) -> WeeklyReportPlan | None:
    week_start = completed_week_start(anchor, as_of)
    if week_start is None:
        return None
    week_end = week_start + timedelta(days=6)
    if not any(
        _in_block(memory.local_date, week_start, week_end) for memory in memories
    ):
        return None

    slots = tuple(
        slot
        for slot in (
            _most_frequent_slot(entity_occurrences, week_start, week_end),
            _first_occurrence_slot(first_occurrences, week_start, week_end),
            _emotion_slot(
                emotion_observations,
                existing_emotion_differences,
                week_start,
                week_end,
            ),
        )
        if slot is not None
    )
    if not slots:
        return None
    return WeeklyReportPlan(week_start=week_start, week_end=week_end, slots=slots)

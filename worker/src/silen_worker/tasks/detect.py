"""사용자 로컬 날짜의 활성 기록을 버킷팅해 차이를 멱등 저장한다."""

from dataclasses import dataclass
from datetime import date, timedelta

import psycopg

from silen_worker.extraction.constants import ENTITY_STOPWORDS
from silen_worker.db import (
    fetch_dismiss_counts,
    fetch_latest_prior_occurrences,
    fetch_window_active_memories,
    fetch_window_emotions,
    fetch_window_occurrences,
    reconcile_daily_differences,
    replace_difference_evidence,
    upsert_difference,
    upsert_dimension_difference,
)
from silen_worker.detection.constants import (
    DISMISS_WINDOW_DAYS,
    WINDOW_DAYS,
)
from silen_worker.detection.emotion import (
    EmotionDifference,
    detect_emotion_difference,
)
from silen_worker.detection.service import (
    DetectedDifference,
    EntityWindow,
    detect_differences,
    rank_differences,
)
from silen_worker.time import local_date_for


@dataclass(frozen=True)
class DetectDayResult:
    saved_ids: list[str]
    narration_ids: list[str]


def detect_day(
    conn: psycopg.Connection,
    user_id: str,
    target_date_iso: str,
    *,
    closing: bool = True,
) -> DetectDayResult:
    """closing=False는 하루 중간 실행이다.

    아직 끝나지 않은 하루에 대해 부재("오늘 운동이 없네요")나 감정 이탈을
    말하면 사실이 아니라 단정이 된다. 중간 실행은 오늘 등장한 것에서 나오는
    차이(재등장 등)만 만들고, 이미 저장된 마감 결과를 정리하지도 않는다.
    """
    target = date.fromisoformat(target_date_iso)
    history_start = target - timedelta(days=WINDOW_DAYS)

    active_rows = fetch_window_active_memories(
        conn,
        user_id,
        target,
        WINDOW_DAYS,
    )
    active_by_date: dict[date, list[str]] = {}
    for row in active_rows:
        local = date.fromisoformat(
            local_date_for(row.captured_at, row.timezone)
        )
        if history_start <= local <= target:
            active_by_date.setdefault(local, []).append(row.memory_id)

    today_memory_ids = active_by_date.get(target, [])
    if not today_memory_ids:
        reconcile_daily_differences(conn, user_id, target, [])
        return DetectDayResult([], [])

    active_history_dates = frozenset(
        day for day in active_by_date if day < target
    )
    occurrence_rows = fetch_window_occurrences(
        conn,
        user_id,
        target,
        WINDOW_DAYS,
        ENTITY_STOPWORDS,
    )
    by_entity: dict[str, dict] = {}
    for row in occurrence_rows:
        local = date.fromisoformat(
            local_date_for(row.captured_at, row.timezone)
        )
        if not history_start <= local <= target:
            continue
        bucket = by_entity.setdefault(
            row.entity_id,
            {
                "type": row.entity_type,
                "dates": set(),
                "memory_ids": [],
                "prior_memory_id": None,
            },
        )
        bucket["dates"].add(local)
        bucket["memory_ids"].append(row.memory_id)

    latest_prior = fetch_latest_prior_occurrences(
        conn,
        user_id,
        list(by_entity),
        target,
    )
    windows: list[EntityWindow] = []
    for entity_id, bucket in by_entity.items():
        prior = latest_prior.get(entity_id)
        last_prior_date = (
            date.fromisoformat(local_date_for(prior[0], prior[1]))
            if prior is not None
            else None
        )
        if prior is not None:
            bucket["prior_memory_id"] = prior[2]
        windows.append(
            EntityWindow(
                entity_id,
                bucket["type"],
                frozenset(bucket["dates"]),
                prior is not None,
                last_prior_date,
            )
        )

    entity_candidates = detect_differences(
        target,
        windows,
        active_history_dates=active_history_dates,
        today_is_active=True,
        include_absence=closing,
    )

    emotion_entries: list[tuple[date, float]] = []
    emotion_memory_ids: list[str] = []
    for row in fetch_window_emotions(
        conn,
        user_id,
        target,
        WINDOW_DAYS,
    ):
        local = date.fromisoformat(
            local_date_for(row.captured_at, row.timezone)
        )
        if history_start <= local <= target:
            emotion_entries.append((local, row.valence))
            emotion_memory_ids.append(row.memory_id)
    emotion_candidate = (
        detect_emotion_difference(emotion_entries, target) if closing else None
    )

    first_occurrences = [
        candidate
        for candidate in entity_candidates
        if candidate.method == "first_occurrence"
    ]
    rankable: list[DetectedDifference | EmotionDifference] = [
        candidate
        for candidate in entity_candidates
        if candidate.method != "first_occurrence"
    ]
    if emotion_candidate is not None:
        rankable.append(emotion_candidate)

    dismiss_counts = fetch_dismiss_counts(
        conn,
        user_id,
        target - timedelta(days=DISMISS_WINDOW_DAYS),
        target,
    )
    ranked = rank_differences(
        rankable,
        dismiss_counts,
        active_history_days=len(active_history_dates),
    )

    saved_ids: list[str] = []
    for candidate in first_occurrences:
        difference_id = _save_entity_difference(
            conn,
            user_id,
            target,
            candidate,
            by_entity,
            today_memory_ids,
        )
        saved_ids.append(difference_id)

    narration_ids: list[str] = []
    for candidate in ranked:
        if isinstance(candidate, EmotionDifference):
            difference_id = upsert_dimension_difference(
                conn,
                user_id,
                target,
                candidate.dimension,
                candidate.method,
                candidate.category,
                candidate.description,
                candidate.confidence,
            )
            replace_difference_evidence(
                conn,
                user_id,
                difference_id,
                emotion_memory_ids,
            )
        else:
            difference_id = _save_entity_difference(
                conn,
                user_id,
                target,
                candidate,
                by_entity,
                today_memory_ids,
            )
        saved_ids.append(difference_id)
        narration_ids.append(difference_id)

    # 중간 실행은 정리하지 않는다. 마감 때 만든 부재 차이를 늦은 메모 하나가
    # 지워버리면 안 된다.
    if closing:
        reconcile_daily_differences(conn, user_id, target, saved_ids)
    return DetectDayResult(saved_ids, narration_ids)


def _save_entity_difference(
    conn: psycopg.Connection,
    user_id: str,
    target: date,
    candidate: DetectedDifference,
    by_entity: dict[str, dict],
    today_memory_ids: list[str],
) -> str:
    difference_id = upsert_difference(
        conn,
        user_id,
        target,
        candidate.entity_id,
        candidate.method,
        candidate.dimension,
        candidate.description,
        candidate.confidence,
    )
    entity_memory_ids = by_entity[candidate.entity_id]["memory_ids"]
    prior_memory_id = by_entity[candidate.entity_id]["prior_memory_id"]
    evidence_ids = (
        [*entity_memory_ids, *today_memory_ids]
        if target not in by_entity[candidate.entity_id]["dates"]
        else entity_memory_ids
    )
    if prior_memory_id is not None:
        evidence_ids = [*evidence_ids, prior_memory_id]
    replace_difference_evidence(
        conn,
        user_id,
        difference_id,
        evidence_ids,
    )
    return difference_id

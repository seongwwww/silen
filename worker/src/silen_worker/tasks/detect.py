"""사용자 로컬 날짜의 활성 기록을 버킷팅해 엔티티 차이를 멱등 저장한다."""

from datetime import date, timedelta

import psycopg

from silen_worker.db import (
    fetch_latest_prior_occurrences,
    fetch_window_active_memories,
    fetch_window_occurrences,
    replace_difference_evidence,
    upsert_difference,
)
from silen_worker.detection.constants import WINDOW_DAYS
from silen_worker.detection.service import EntityWindow, detect_differences
from silen_worker.time import local_date_for


def detect_day(
    conn: psycopg.Connection,
    user_id: str,
    target_date_iso: str,
) -> list[str]:
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
        return []

    active_history_dates = frozenset(
        day for day in active_by_date if day < target
    )
    occurrence_rows = fetch_window_occurrences(
        conn,
        user_id,
        target,
        WINDOW_DAYS,
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
        windows.append(
            EntityWindow(
                entity_id,
                bucket["type"],
                frozenset(bucket["dates"]),
                prior is not None,
                last_prior_date,
            )
        )

    written: list[str] = []
    for difference in detect_differences(
        target,
        windows,
        active_history_dates=active_history_dates,
        today_is_active=True,
    ):
        difference_id = upsert_difference(
            conn,
            user_id,
            target,
            difference.entity_id,
            difference.method,
            difference.entity_type,
            difference.description,
            difference.confidence,
        )
        entity_memory_ids = by_entity[difference.entity_id]["memory_ids"]
        evidence_ids = (
            [*entity_memory_ids, *today_memory_ids]
            if target not in by_entity[difference.entity_id]["dates"]
            else entity_memory_ids
        )
        replace_difference_evidence(
            conn,
            difference_id,
            evidence_ids,
        )
        written.append(difference_id)
    return written

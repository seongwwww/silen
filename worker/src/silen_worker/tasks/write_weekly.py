"""Persist a deterministic report for a just-completed anchored seven-day block."""

from datetime import date, timedelta

import psycopg

from silen_worker.db import (
    fetch_weekly_anchor,
    fetch_weekly_emotions,
    fetch_weekly_existing_emotion_differences,
    fetch_weekly_first_occurrences,
    fetch_weekly_memories,
    fetch_weekly_occurrences,
    replace_difference_evidence,
    replace_weekly_highlights,
    upsert_difference,
    upsert_dimension_difference,
    upsert_weekly_report,
)
from silen_worker.detection.constants import WINDOW_DAYS
from silen_worker.weekly.service import (
    EmotionObservation,
    EntityOccurrence,
    ExistingEmotionDifference,
    FirstOccurrence,
    WeeklyMemory,
    WeeklySlot,
    build_weekly_report,
    completed_week_containing,
    completed_week_start,
)


def _persist_slot(
    conn: psycopg.Connection,
    user_id: str,
    slot: WeeklySlot,
) -> str:
    if slot.difference_id is not None:
        return slot.difference_id
    if slot.local_date is None:
        raise ValueError("a new weekly difference requires a local date")

    if slot.detection_method == "pattern":
        if slot.entity_id is None or slot.entity_type is None:
            raise ValueError("a pattern difference requires an entity")
        difference_id = upsert_difference(
            conn,
            user_id,
            slot.local_date,
            slot.entity_id,
            slot.detection_method,
            slot.entity_type,
            slot.description,
            slot.confidence,
            category=slot.category,
        )
    elif slot.detection_method == "zscore":
        difference_id = upsert_dimension_difference(
            conn,
            user_id,
            slot.local_date,
            "emotion",
            slot.detection_method,
            slot.category,
            slot.description,
            slot.confidence,
        )
    else:
        raise ValueError(f"unsupported weekly method: {slot.detection_method}")

    replace_difference_evidence(
        conn,
        user_id,
        difference_id,
        list(slot.evidence_ids),
    )
    return difference_id


def generate_weekly_report(
    conn: psycopg.Connection,
    user_id: str,
    as_of_date_iso: str,
) -> str | None:
    """Return the report id, or None when no block/record/highlight is eligible."""

    as_of = date.fromisoformat(as_of_date_iso)
    anchor = fetch_weekly_anchor(conn, user_id)
    if anchor is None:
        return None
    week_start = completed_week_start(anchor, as_of)
    if week_start is None:
        return None
    week_end = week_start + timedelta(days=6)

    memories = [
        WeeklyMemory(row.memory_id, row.local_date)
        for row in fetch_weekly_memories(conn, user_id, week_start, week_end)
    ]
    occurrences = [
        EntityOccurrence(
            row.entity_id,
            row.entity_type,
            row.normalized_name,
            row.memory_id,
            row.local_date,
        )
        for row in fetch_weekly_occurrences(
            conn,
            user_id,
            week_start,
            week_end,
        )
    ]
    first_occurrences = [
        FirstOccurrence(
            row.difference_id,
            row.local_date,
            row.entity_id,
            row.normalized_name,
        )
        for row in fetch_weekly_first_occurrences(
            conn,
            user_id,
            week_start,
            week_end,
        )
    ]
    emotion_observations = [
        EmotionObservation(row.memory_id, row.local_date, row.valence)
        for row in fetch_weekly_emotions(
            conn,
            user_id,
            week_start - timedelta(days=WINDOW_DAYS),
            week_end,
        )
    ]
    existing_emotions = [
        ExistingEmotionDifference(row.difference_id, row.local_date)
        for row in fetch_weekly_existing_emotion_differences(
            conn,
            user_id,
            week_start,
            week_end,
        )
    ]
    plan = build_weekly_report(
        anchor,
        as_of,
        memories,
        occurrences,
        first_occurrences,
        emotion_observations,
        existing_emotions,
    )
    if plan is None:
        return None

    with conn.transaction():
        highlights = [
            (_persist_slot(conn, user_id, slot), slot.slot, 1)
            for slot in plan.slots
        ]
        report_id = upsert_weekly_report(conn, user_id, plan.week_start)
        replace_weekly_highlights(
            conn,
            user_id,
            report_id,
            highlights,
        )
    return report_id


def regenerate_weekly_report_for_date(
    conn: psycopg.Connection,
    user_id: str,
    target_date_iso: str,
    as_of_date_iso: str,
) -> str | None:
    """Rebuild target's completed anchored block, leaving open blocks alone."""

    target = date.fromisoformat(target_date_iso)
    as_of = date.fromisoformat(as_of_date_iso)
    anchor = fetch_weekly_anchor(conn, user_id)
    if anchor is None:
        return None
    week_start = completed_week_containing(anchor, target, as_of)
    if week_start is None:
        return None
    return generate_weekly_report(
        conn,
        user_id,
        (week_start + timedelta(days=7)).isoformat(),
    )

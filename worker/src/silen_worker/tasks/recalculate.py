"""Recalculate the bounded effects of one backdated memory."""

import logging
from datetime import datetime, timezone

import psycopg

from silen_worker.db import Memory, request_late_diary_regeneration
from silen_worker.narration.service import Narrator
from silen_worker.tasks.detect import detect_day
from silen_worker.tasks.narrate import narrate_difference
from silen_worker.tasks.write_weekly import regenerate_weekly_report_for_date
from silen_worker.time import local_date_for

logger = logging.getLogger(__name__)


def recalculate_if_past(
    conn: psycopg.Connection,
    memory: Memory,
    *,
    now: datetime | None = None,
    narrator: Narrator | None = None,
) -> str:
    """Recalculate only memory's local day and its completed weekly block."""

    current = now or datetime.now(timezone.utc)
    target_date_iso = local_date_for(memory.effective_at, memory.timezone)
    today_iso = local_date_for(current, memory.timezone)
    if target_date_iso > today_iso:
        logger.warning(
            "future effective date skipped user_id=%s memory_id=%s date=%s",
            memory.user_id,
            memory.id,
            target_date_iso,
        )
        return "future"
    if target_date_iso == today_iso:
        return "today"

    result = detect_day(
        conn,
        memory.user_id,
        target_date_iso,
        closing=True,
    )
    for difference_id in result.narration_ids:
        narrate_difference(
            conn,
            difference_id,
            narrator=narrator,
        )
    request_late_diary_regeneration(
        conn,
        memory.user_id,
        datetime.fromisoformat(target_date_iso).date(),
    )
    regenerate_weekly_report_for_date(
        conn,
        memory.user_id,
        target_date_iso,
        today_iso,
    )
    return "past"

from datetime import datetime, timezone
from types import SimpleNamespace

import silen_worker.tasks.recalculate as recalculate_task
from silen_worker.tasks.detect import DetectDayResult
from silen_worker.tasks.recalculate import recalculate_if_past


NOW = datetime(2026, 7, 29, 3, 0, tzinfo=timezone.utc)


def _memory(effective_at: datetime, timezone_name: str = "Asia/Seoul"):
    return SimpleNamespace(
        id="memory-1",
        user_id="user-1",
        raw_text="기록",
        effective_at=effective_at,
        timezone=timezone_name,
    )


def test_past_memory_recalculates_only_its_day_and_completed_week(monkeypatch):
    calls: list[tuple] = []
    monkeypatch.setattr(
        recalculate_task,
        "detect_day",
        lambda conn, user_id, date_iso, closing: (
            calls.append(("detect", user_id, date_iso, closing))
            or DetectDayResult(["difference-1"], ["difference-1"])
        ),
    )
    monkeypatch.setattr(
        recalculate_task,
        "narrate_difference",
        lambda conn, difference_id, narrator=None: (
            calls.append(("narrate", difference_id, narrator)) or "narration-1"
        ),
    )
    monkeypatch.setattr(
        recalculate_task,
        "request_late_diary_regeneration",
        lambda conn, user_id, target_date: (
            calls.append(("diary", user_id, target_date.isoformat())) or True
        ),
    )
    monkeypatch.setattr(
        recalculate_task,
        "regenerate_weekly_report_for_date",
        lambda conn, user_id, target_date_iso, as_of_date_iso: (
            calls.append(
                ("weekly", user_id, target_date_iso, as_of_date_iso)
            )
            or "report-1"
        ),
    )
    narrator = object()

    result = recalculate_if_past(
        object(),
        _memory(datetime(2026, 7, 20, 15, 30, tzinfo=timezone.utc)),
        now=NOW,
        narrator=narrator,
    )

    assert result == "past"
    assert calls == [
        ("detect", "user-1", "2026-07-21", True),
        ("narrate", "difference-1", narrator),
        ("diary", "user-1", "2026-07-21"),
        ("weekly", "user-1", "2026-07-21", "2026-07-29"),
    ]


def test_today_memory_is_left_for_the_existing_sweep(monkeypatch):
    monkeypatch.setattr(
        recalculate_task,
        "detect_day",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError()),
    )

    result = recalculate_if_past(
        object(),
        _memory(datetime(2026, 7, 28, 16, 0, tzinfo=timezone.utc)),
        now=NOW,
    )

    assert result == "today"


def test_future_local_date_is_skipped(monkeypatch):
    monkeypatch.setattr(
        recalculate_task,
        "detect_day",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError()),
    )

    result = recalculate_if_past(
        object(),
        _memory(datetime(2026, 7, 29, 16, 0, tzinfo=timezone.utc)),
        now=NOW,
    )

    assert result == "future"


def test_same_utc_instant_can_be_past_for_seoul_and_today_for_new_york(
    monkeypatch,
):
    detected: list[str] = []
    monkeypatch.setattr(
        recalculate_task,
        "detect_day",
        lambda conn, user_id, date_iso, closing: (
            detected.append(date_iso) or DetectDayResult([], [])
        ),
    )
    monkeypatch.setattr(
        recalculate_task,
        "request_late_diary_regeneration",
        lambda *args: False,
    )
    monkeypatch.setattr(
        recalculate_task,
        "regenerate_weekly_report_for_date",
        lambda *args: None,
    )
    instant = datetime(2026, 7, 28, 14, 30, tzinfo=timezone.utc)
    now = datetime(2026, 7, 28, 16, 0, tzinfo=timezone.utc)

    seoul = recalculate_if_past(
        object(),
        _memory(instant, "Asia/Seoul"),
        now=now,
    )
    new_york = recalculate_if_past(
        object(),
        _memory(instant, "America/New_York"),
        now=now,
    )

    assert seoul == "past"
    assert new_york == "today"
    assert detected == ["2026-07-28"]

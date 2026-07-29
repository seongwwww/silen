from datetime import date, timedelta

import pytest

from silen_worker.detection.emotion import bits_ceiling

from silen_worker.weekly.service import (
    EmotionObservation,
    EntityOccurrence,
    ExistingEmotionDifference,
    FirstOccurrence,
    WeeklyMemory,
    build_weekly_report,
    completed_week_containing,
    completed_week_start,
)


ANCHOR = date(2026, 7, 1)


def _memory(day: int, memory_id: str | None = None) -> WeeklyMemory:
    return WeeklyMemory(memory_id or f"m{day}", ANCHOR + timedelta(days=day))


def _entity(
    day: int,
    *,
    entity_id: str = "e1",
    normalized_name: str = "\uac80\uc740 \ucc28",
    memory_id: str | None = None,
) -> EntityOccurrence:
    return EntityOccurrence(
        entity_id=entity_id,
        entity_type="thing",
        normalized_name=normalized_name,
        memory_id=memory_id or f"m{day}",
        local_date=ANCHOR + timedelta(days=day),
    )


def test_no_completed_block_before_seven_days():
    assert completed_week_start(ANCHOR, ANCHOR + timedelta(days=6)) is None


def test_first_block_completes_on_day_seven():
    assert completed_week_start(ANCHOR, ANCHOR + timedelta(days=7)) == ANCHOR


def test_second_boundary_returns_second_block():
    assert completed_week_start(ANCHOR, ANCHOR + timedelta(days=14)) == (
        ANCHOR + timedelta(days=7)
    )


def test_completed_week_containing_finds_an_arbitrary_past_date():
    assert completed_week_containing(
        ANCHOR,
        ANCHOR + timedelta(days=9),
        ANCHOR + timedelta(days=20),
    ) == ANCHOR + timedelta(days=7)


def test_completed_week_containing_skips_the_open_block():
    assert (
        completed_week_containing(
            ANCHOR,
            ANCHOR + timedelta(days=9),
            ANCHOR + timedelta(days=12),
        )
        is None
    )


def test_completed_week_containing_rejects_a_date_before_anchor():
    assert (
        completed_week_containing(
            ANCHOR,
            ANCHOR - timedelta(days=1),
            ANCHOR + timedelta(days=20),
        )
        is None
    )


def test_non_boundary_does_not_build_report():
    report = build_weekly_report(
        ANCHOR,
        ANCHOR + timedelta(days=6),
        [_memory(0)],
        [_entity(0)],
        [],
        [],
        [],
    )

    assert report is None


def test_empty_week_does_not_build_report():
    report = build_weekly_report(
        ANCHOR,
        ANCHOR + timedelta(days=7),
        [],
        [],
        [],
        [],
        [],
    )

    assert report is None


def test_week_without_slots_does_not_build_report():
    report = build_weekly_report(
        ANCHOR,
        ANCHOR + timedelta(days=7),
        [_memory(0)],
        [],
        [],
        [],
        [],
    )

    assert report is None


def test_sparse_week_builds_most_frequent_slot():
    report = build_weekly_report(
        ANCHOR,
        ANCHOR + timedelta(days=7),
        [_memory(0), _memory(5)],
        [_entity(0), _entity(5)],
        [],
        [],
        [],
    )

    assert report is not None
    assert report.week_start == ANCHOR
    assert report.week_end == ANCHOR + timedelta(days=6)
    slot = report.slots[0]
    assert slot.slot == "\uac00\uc7a5\ub9ce\uc774\ud55c\uac83"
    assert slot.difference_id is None
    assert slot.entity_id == "e1"
    assert slot.detection_method == "pattern"
    assert slot.category == "\ud328\ud134"
    assert slot.description == "7\uc77c \uae30\ub85d\uc5d0\uc11c 2\ud68c \uc5b8\uae09"
    assert slot.evidence_ids == ("m0", "m5")


def test_frequency_tie_breaks_by_normalized_name_then_entity_id():
    memories = [_memory(0), _memory(1), _memory(2)]
    occurrences = [
        _entity(0, entity_id="e-z", normalized_name="\ub77c\uba74"),
        _entity(1, entity_id="e-b", normalized_name="\uae40\ubc25"),
        _entity(2, entity_id="e-a", normalized_name="\uae40\ubc25"),
    ]

    report = build_weekly_report(
        ANCHOR,
        ANCHOR + timedelta(days=7),
        memories,
        occurrences,
        [],
        [],
        [],
    )

    assert report is not None
    most = next(
        slot
        for slot in report.slots
        if slot.slot == "\uac00\uc7a5\ub9ce\uc774\ud55c\uac83"
    )
    assert most.entity_id == "e-a"


def test_first_occurrence_slot_selects_earliest_candidate():
    firsts = [
        FirstOccurrence("d2", ANCHOR + timedelta(days=2), "e2", "\ub77c\uba74"),
        FirstOccurrence("d1", ANCHOR + timedelta(days=1), "e1", "\uae40\ubc25"),
    ]

    report = build_weekly_report(
        ANCHOR,
        ANCHOR + timedelta(days=7),
        [_memory(0)],
        [],
        firsts,
        [],
        [],
    )

    assert report is not None
    first = next(
        slot for slot in report.slots if slot.slot == "\ucc98\uc74c\ud55c\uac83"
    )
    assert first.difference_id == "d1"


def test_emotion_slot_selects_largest_absolute_z_score():
    observations = [
        EmotionObservation(f"em{day}", ANCHOR + timedelta(days=day), 0.5)
        for day in range(5)
    ]
    observations.append(
        EmotionObservation("em5", ANCHOR + timedelta(days=5), -1.0)
    )

    report = build_weekly_report(
        ANCHOR,
        ANCHOR + timedelta(days=7),
        [_memory(0)],
        [],
        [],
        observations,
        [],
    )

    assert report is not None
    emotion = next(
        slot for slot in report.slots if slot.slot == "\uac10\uc815\uc21c\uac04"
    )
    assert emotion.difference_id is None
    assert emotion.local_date == ANCHOR + timedelta(days=5)
    assert emotion.detection_method == "zscore"
    assert emotion.category == "\uac10\uc815\uc804\ud658"
    assert emotion.confidence == pytest.approx(bits_ceiling(5))
    assert emotion.evidence_ids == tuple(f"em{day}" for day in range(6))


def test_emotion_slot_reuses_existing_zscore_difference():
    observations = [
        EmotionObservation(f"em{day}", ANCHOR + timedelta(days=day), 0.5)
        for day in range(5)
    ]
    observations.append(
        EmotionObservation("em5", ANCHOR + timedelta(days=5), -1.0)
    )
    existing = [
        ExistingEmotionDifference(
            "emotion-diff",
            ANCHOR + timedelta(days=5),
        )
    ]

    report = build_weekly_report(
        ANCHOR,
        ANCHOR + timedelta(days=7),
        [_memory(0)],
        [],
        [],
        observations,
        existing,
    )

    assert report is not None
    emotion = next(
        slot for slot in report.slots if slot.slot == "\uac10\uc815\uc21c\uac04"
    )
    assert emotion.difference_id == "emotion-diff"


def test_second_block_excludes_first_block_occurrences():
    report = build_weekly_report(
        ANCHOR,
        ANCHOR + timedelta(days=14),
        [_memory(0), _memory(7), _memory(8)],
        [_entity(0), _entity(7), _entity(8)],
        [],
        [],
        [],
    )

    assert report is not None
    assert report.week_start == ANCHOR + timedelta(days=7)
    most = next(
        slot
        for slot in report.slots
        if slot.slot == "\uac00\uc7a5\ub9ce\uc774\ud55c\uac83"
    )
    assert most.evidence_ids == ("m7", "m8")

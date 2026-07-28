from datetime import date

import pytest

from silen_worker.db import (
    fetch_weekly_anchor,
    fetch_weekly_emotions,
    fetch_weekly_memories,
    fetch_weekly_occurrences,
    replace_weekly_highlights,
    upsert_difference,
    upsert_weekly_report,
)
from tests.conftest import delete_user, seed_memory_at, seed_user


def _entity(conn, user_id: str, normalized_name: str) -> str:
    return conn.execute(
        "insert into public.entities "
        "(user_id, entity_type, name, normalized_name) "
        "values (%s, 'thing', %s, %s) returning id::text",
        (user_id, normalized_name, normalized_name),
    ).fetchone()[0]


def _link(conn, memory_id: str, entity_id: str) -> None:
    conn.execute(
        "insert into public.memory_entities "
        "(memory_id, entity_id, relation_type) "
        "values (%s, %s, 'mentioned')",
        (memory_id, entity_id),
    )


@pytest.mark.integration
def test_weekly_reads_use_owner_active_rows_and_local_dates(conn):
    alice = seed_user(conn)
    bob = seed_user(conn)
    try:
        conn.execute(
            "update public.users set timezone = 'America/Los_Angeles' where id = %s",
            (alice,),
        )
        before_midnight = seed_memory_at(
            conn, alice, "2026-07-01T06:30:00+00"
        )
        anchor = seed_memory_at(conn, alice, "2026-07-01T07:30:00+00")
        locked = seed_memory_at(conn, alice, "2026-07-02T07:30:00+00")
        deleted = seed_memory_at(conn, alice, "2026-07-03T07:30:00+00")
        foreign = seed_memory_at(conn, bob, "2026-07-01T08:00:00+00")
        conn.execute(
            "update public.memories set is_locked = true where id = %s",
            (locked,),
        )
        conn.execute(
            "update public.memories set deleted_at = now() where id = %s",
            (deleted,),
        )

        alice_entity = _entity(conn, alice, "\uae40\ubc25")
        bob_entity = _entity(conn, bob, "\uae40\ubc25")
        for memory_id, entity_id in (
            (anchor, alice_entity),
            (locked, alice_entity),
            (deleted, alice_entity),
            (foreign, bob_entity),
        ):
            _link(conn, memory_id, entity_id)
        conn.execute(
            "insert into public.emotions "
            "(memory_id, valence, confirmed_by_user) "
            "values (%s, 0.5, true), (%s, 0.8, true), (%s, -0.5, true)",
            (anchor, locked, foreign),
        )

        assert fetch_weekly_anchor(conn, alice) == date(2026, 6, 30)
        memories = fetch_weekly_memories(
            conn, alice, date(2026, 7, 1), date(2026, 7, 7)
        )
        occurrences = fetch_weekly_occurrences(
            conn, alice, date(2026, 7, 1), date(2026, 7, 7)
        )
        emotions = fetch_weekly_emotions(
            conn, alice, date(2026, 7, 1), date(2026, 7, 7)
        )

        assert [row.memory_id for row in memories] == [anchor]
        assert [row.memory_id for row in occurrences] == [anchor]
        assert [row.memory_id for row in emotions] == [anchor]
        assert memories[0].local_date == date(2026, 7, 1)
        assert before_midnight not in {row.memory_id for row in memories}
        assert foreign not in {row.memory_id for row in memories}
    finally:
        delete_user(conn, alice)
        delete_user(conn, bob)


@pytest.mark.integration
def test_weekly_report_and_highlights_are_idempotent_and_user_scoped(conn):
    alice = seed_user(conn)
    bob = seed_user(conn)
    try:
        alice_entity = _entity(conn, alice, "\uae40\ubc25")
        bob_entity = _entity(conn, bob, "\ub77c\uba74")
        alice_diff = upsert_difference(
            conn,
            alice,
            date(2026, 7, 7),
            alice_entity,
            "pattern",
            "thing",
            "7-day pattern",
            2.0,
            category="\ud328\ud134",
        )
        bob_diff = upsert_difference(
            conn,
            bob,
            date(2026, 7, 7),
            bob_entity,
            "pattern",
            "thing",
            "7-day pattern",
            2.0,
            category="\ud328\ud134",
        )

        report1 = upsert_weekly_report(conn, alice, date(2026, 7, 1))
        report2 = upsert_weekly_report(conn, alice, date(2026, 7, 1))
        assert report1 == report2

        replace_weekly_highlights(
            conn,
            alice,
            report1,
            [
                (alice_diff, "\uac00\uc7a5\ub9ce\uc774\ud55c\uac83", 1),
                (bob_diff, "\ucc98\uc74c\ud55c\uac83", 1),
            ],
        )
        replace_weekly_highlights(
            conn,
            alice,
            report1,
            [(alice_diff, "\uac00\uc7a5\ub9ce\uc774\ud55c\uac83", 1)],
        )

        rows = conn.execute(
            "select difference_id::text, slot, rank "
            "from public.weekly_report_highlights where report_id = %s",
            (report1,),
        ).fetchall()
        assert rows == [
            (alice_diff, "\uac00\uc7a5\ub9ce\uc774\ud55c\uac83", 1)
        ]
    finally:
        delete_user(conn, alice)
        delete_user(conn, bob)


@pytest.mark.integration
def test_difference_category_defaults_and_can_be_overridden(conn):
    user = seed_user(conn)
    try:
        entity = _entity(conn, user, "\uae40\ubc25")
        default_id = upsert_difference(
            conn,
            user,
            date(2026, 7, 1),
            entity,
            "first_occurrence",
            "thing",
            "first",
            1.0,
        )
        pattern_id = upsert_difference(
            conn,
            user,
            date(2026, 7, 2),
            entity,
            "pattern",
            "thing",
            "pattern",
            2.0,
            category="\ud328\ud134",
        )
        rows = conn.execute(
            "select id::text, category from public.differences "
            "where id = any(%s::uuid[]) order by date",
            ([default_id, pattern_id],),
        ).fetchall()
        assert rows == [
            (default_id, "\uc624\ub298\uc758\ub2e4\ub978\uc810"),
            (pattern_id, "\ud328\ud134"),
        ]
    finally:
        delete_user(conn, user)

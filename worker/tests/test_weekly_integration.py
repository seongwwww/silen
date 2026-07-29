from datetime import date

import pytest

from silen_worker.cli import run_weekly
from silen_worker.db import upsert_dimension_difference
from silen_worker.tasks.write_weekly import _persist_slot
from silen_worker.weekly.service import WeeklySlot
from silen_worker.tasks.write_weekly import generate_weekly_report
from tests.conftest import delete_user, seed_memory_at, seed_user


def _entity(conn, user_id: str, normalized_name: str = "\uae40\ubc25") -> str:
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
def test_generate_weekly_report_persists_pattern_and_is_idempotent(conn):
    alice = seed_user(conn)
    bob = seed_user(conn)
    try:
        entity = _entity(conn, alice)
        first_memory = seed_memory_at(
            conn, alice, "2026-07-01T02:00:00+00"
        )
        second_memory = seed_memory_at(
            conn, alice, "2026-07-05T02:00:00+00"
        )
        _link(conn, first_memory, entity)
        _link(conn, second_memory, entity)
        bob_memory = seed_memory_at(conn, bob, "2026-07-01T02:00:00+00")

        assert generate_weekly_report(conn, alice, "2026-07-07") is None
        report1 = generate_weekly_report(conn, alice, "2026-07-08")
        report2 = generate_weekly_report(conn, alice, "2026-07-08")

        assert report1 is not None
        assert report2 == report1
        report_count = conn.execute(
            "select count(*)::int from public.weekly_reports where user_id = %s",
            (alice,),
        ).fetchone()[0]
        difference_rows = conn.execute(
            "select id::text, category from public.differences "
            "where user_id = %s and detection_method = 'pattern'",
            (alice,),
        ).fetchall()
        highlights = conn.execute(
            "select h.difference_id::text, h.slot "
            "from public.weekly_report_highlights h "
            "join public.weekly_reports w on w.id = h.report_id "
            "where w.user_id = %s",
            (alice,),
        ).fetchall()
        evidence = conn.execute(
            "select memory_id::text from public.difference_evidence "
            "where difference_id = %s order by memory_id",
            (difference_rows[0][0],),
        ).fetchall()

        assert report_count == 1
        assert difference_rows[0][1] == "\ud328\ud134"
        assert highlights == [
            (difference_rows[0][0], "\uac00\uc7a5\ub9ce\uc774\ud55c\uac83")
        ]
        assert {row[0] for row in evidence} == {first_memory, second_memory}
        assert bob_memory not in {row[0] for row in evidence}

        ok, failed = run_weekly(
            conn,
            [(alice, "2026-07-08"), (bob, "2026-07-08")],
        )
        assert (ok, failed) == (2, 0)
    finally:
        delete_user(conn, alice)
        delete_user(conn, bob)


@pytest.mark.integration
def test_이미_있는_차이의_설명도_최신으로_바꾼다(conn):
    """옛 설명이 그대로 남으면 서술 규칙을 고쳐도 화면은 바뀌지 않는다.
    실제로 valence 수치가 리포트에 계속 노출됐다."""
    user = seed_user(conn)
    try:
        stale = upsert_dimension_difference(
            conn,
            user,
            date(2026, 7, 22),
            "emotion",
            "zscore",
            "감정전환",
            "최근 7일 평균 0.29, 해당 날 1.00 (z=1.6)",
            3.13,
        )
        slot = WeeklySlot(
            slot="감정순간",
            difference_id=stale,
            entity_id=None,
            entity_type=None,
            local_date=date(2026, 7, 22),
            detection_method="zscore",
            category="감정전환",
            description="최근 감정을 남긴 7일은 주로 '그냥'이었고, 이 날은 '좋음'",
            confidence=3.13,
            evidence_ids=(),
        )

        _persist_slot(conn, user, slot)

        row = conn.execute(
            "select description from public.differences where id = %s", (stale,)
        ).fetchone()
        assert "z=" not in row[0]
        assert "좋음" in row[0]
    finally:
        delete_user(conn, user)

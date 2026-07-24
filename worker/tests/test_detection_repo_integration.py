from datetime import date

import pytest

from silen_worker.db import (
    fetch_earliest_occurrence,
    fetch_window_occurrences,
    link_difference_evidence,
    upsert_difference,
)
from tests.conftest import seed_user, seed_memory_at, delete_user


def _entity(conn, user_id, name, etype="thing"):
    return conn.execute(
        "insert into public.entities (user_id, entity_type, name, normalized_name) "
        "values (%s, %s, %s, %s) returning id::text",
        (user_id, etype, name, name),
    ).fetchone()[0]


def _link(conn, memory_id, entity_id):
    conn.execute(
        "insert into public.memory_entities (memory_id, entity_id, relation_type) "
        "values (%s, %s, 'mentioned')",
        (memory_id, entity_id),
    )


@pytest.mark.integration
def test_window_조회는_user_스코프와_잠금삭제를_제외한다(conn):
    alice = seed_user(conn)
    bob = seed_user(conn)
    try:
        ea = _entity(conn, alice, "김밥")
        m_ok = seed_memory_at(conn, alice, "2026-07-23T01:00:00+00")
        _link(conn, m_ok, ea)
        # 잠긴 메모
        m_lock = seed_memory_at(conn, alice, "2026-07-23T02:00:00+00")
        conn.execute("update public.memories set is_locked = true where id = %s", (m_lock,))
        _link(conn, m_lock, ea)
        # 삭제된 메모
        m_del = seed_memory_at(conn, alice, "2026-07-23T03:00:00+00")
        conn.execute("update public.memories set deleted_at = now() where id = %s", (m_del,))
        _link(conn, m_del, ea)
        # 밥의 메모(타 사용자)
        eb = _entity(conn, bob, "김밥")
        m_bob = seed_memory_at(conn, bob, "2026-07-23T01:00:00+00")
        _link(conn, m_bob, eb)

        rows = fetch_window_occurrences(conn, alice, date(2026, 7, 23), 28)
        mem_ids = {r.memory_id for r in rows}
        assert m_ok in mem_ids
        assert m_lock not in mem_ids   # 잠금 제외
        assert m_del not in mem_ids    # 삭제 제외
        assert m_bob not in mem_ids    # 타 사용자 제외
    finally:
        delete_user(conn, alice)
        delete_user(conn, bob)


@pytest.mark.integration
def test_earliest는_가장_이른_언급을_준다(conn):
    user = seed_user(conn)
    try:
        ent = _entity(conn, user, "요가", "activity")
        seed_and_link_early = seed_memory_at(conn, user, "2026-07-01T00:00:00+00")
        _link(conn, seed_and_link_early, ent)
        late = seed_memory_at(conn, user, "2026-07-23T00:00:00+00")
        _link(conn, late, ent)
        got = fetch_earliest_occurrence(conn, user, [ent])
        assert ent in got
        assert got[ent][0].isoformat().startswith("2026-07-01")
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_difference_upsert는_멱등이고_근거를_링크한다(conn):
    user = seed_user(conn)
    try:
        ent = _entity(conn, user, "김밥")
        mem = seed_memory_at(conn, user, "2026-07-23T01:00:00+00")
        _link(conn, mem, ent)
        d = date(2026, 7, 23)

        did1 = upsert_difference(conn, user, d, ent, "first_occurrence", "thing", "이 thing 첫 등장", 1.0)
        link_difference_evidence(conn, did1, mem)
        # 재실행 — 같은 자연키 → 같은 행
        did2 = upsert_difference(conn, user, d, ent, "first_occurrence", "thing", "이 thing 첫 등장", 1.0)
        link_difference_evidence(conn, did2, mem)

        assert did1 == did2
        n = conn.execute(
            "select count(*)::int from public.differences where user_id = %s", (user,)
        ).fetchone()[0]
        assert n == 1
        ev = conn.execute(
            "select count(*)::int from public.difference_evidence where difference_id = %s", (did1,)
        ).fetchone()[0]
        assert ev == 1
    finally:
        delete_user(conn, user)

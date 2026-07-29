from datetime import date

import pytest

from silen_worker.db import (
    fetch_dismiss_counts,
    fetch_earliest_occurrence,
    fetch_latest_prior_occurrences,
    fetch_window_emotions,
    fetch_window_occurrences,
    link_difference_evidence,
    replace_difference_evidence,
    upsert_dimension_difference,
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

        conn.execute(
            "update public.memories set is_locked = false where id = %s",
            (m_lock,),
        )
        unlocked_ids = {
            row.memory_id
            for row in fetch_window_occurrences(
                conn,
                alice,
                date(2026, 7, 23),
                28,
            )
        }
        assert m_lock in unlocked_ids  # 해제하면 다음 run-daily 입력에 복귀
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
def test_emotion_조회는_본인_활성_메모만_반환한다(conn):
    alice = seed_user(conn)
    bob = seed_user(conn)
    try:
        kept = seed_memory_at(conn, alice, "2026-07-23T01:00:00+00")
        locked = seed_memory_at(conn, alice, "2026-07-23T02:00:00+00")
        deleted = seed_memory_at(conn, alice, "2026-07-23T03:00:00+00")
        foreign = seed_memory_at(conn, bob, "2026-07-23T01:00:00+00")
        conn.execute(
            "insert into public.emotions (memory_id, valence) "
            "values (%s, 0.5), (%s, 0.5), (%s, 0.5), (%s, 0.5), (%s, 0.5)",
            (
                kept,
                locked,
                deleted,
                foreign,
                seed_memory_at(conn, alice, "2026-07-23T04:00:00+00"),
            ),
        )
        conn.execute(
            "update public.emotions set confirmed_by_user = true "
            "where memory_id = any(%s::uuid[])",
            ([kept, locked, deleted, foreign],),
        )
        conn.execute(
            "update public.memories set is_locked = true where id = %s",
            (locked,),
        )
        conn.execute(
            "update public.memories set deleted_at = now() where id = %s",
            (deleted,),
        )

        rows = fetch_window_emotions(
            conn,
            alice,
            date(2026, 7, 23),
            28,
        )

        assert [row.memory_id for row in rows] == [kept]
    finally:
        delete_user(conn, alice)
        delete_user(conn, bob)


@pytest.mark.integration
def test_difference_upsert는_멱등이고_근거를_링크한다(conn):
    user = seed_user(conn)
    try:
        ent = _entity(conn, user, "김밥")
        mem = seed_memory_at(conn, user, "2026-07-23T01:00:00+00")
        _link(conn, mem, ent)
        d = date(2026, 7, 23)

        did1 = upsert_difference(conn, user, d, ent, "first_occurrence", "thing", "처음 등장", 1.0)
        link_difference_evidence(conn, did1, mem)
        # 재실행 — 같은 자연키 → 같은 행
        did2 = upsert_difference(conn, user, d, ent, "first_occurrence", "thing", "처음 등장", 1.0)
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


@pytest.mark.integration
def test_dimension_difference_upsert는_null_entity_자연키로_멱등이다(conn):
    user = seed_user(conn)
    try:
        target = date(2026, 7, 23)

        first = upsert_dimension_difference(
            conn,
            user,
            target,
            "emotion",
            "zscore",
            "감정전환",
            "최근 5일 평균 0.50, 오늘 -1.00 (z=-6.0)",
            8.0,
        )
        second = upsert_dimension_difference(
            conn,
            user,
            target,
            "emotion",
            "zscore",
            "감정전환",
            "최근 5일 평균 0.50, 오늘 -0.50 (z=-4.0)",
            7.0,
        )

        assert first == second
        row = conn.execute(
            "select count(*)::int, max(confidence) "
            "from public.differences where user_id = %s",
            (user,),
        ).fetchone()
        assert row == (1, pytest.approx(7.0))
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_dismiss_count는_최근_본인_기각만_센다(conn):
    alice = seed_user(conn)
    bob = seed_user(conn)
    try:
        alice_entity = _entity(conn, alice, "산책", "activity")
        bob_entity = _entity(conn, bob, "산책", "activity")
        for day, owner, entity in (
            (date(2026, 7, 20), alice, alice_entity),
            (date(2026, 7, 21), alice, alice_entity),
            (date(2026, 6, 1), alice, alice_entity),
            (date(2026, 7, 22), bob, bob_entity),
        ):
            conn.execute(
                "insert into public.differences "
                "(user_id, date, entity_id, dimension, description, "
                "detection_method, confidence, category, status) "
                "values (%s, %s, %s, 'activity', '통계 근거', "
                "'freq_shift', 3.0, '오늘의다른점', 'dismissed')",
                (owner, day, entity),
            )

        counts = fetch_dismiss_counts(
            conn,
            alice,
            date(2026, 7, 1),
            date(2026, 7, 23),
        )

        assert counts == {
            (alice_entity, "activity", "freq_shift"): 2,
        }
    finally:
        delete_user(conn, alice)
        delete_user(conn, bob)


@pytest.mark.integration
def test_dismiss_count는_미래와_stale_기각을_세지_않는다(conn):
    user = seed_user(conn)
    try:
        entity = _entity(conn, user, "산책", "activity")
        for day, evidence_state in (
            (date(2026, 7, 20), "intact"),
            (date(2026, 7, 21), "stale"),
            (date(2026, 7, 24), "intact"),
        ):
            conn.execute(
                "insert into public.differences "
                "(user_id, date, entity_id, dimension, description, "
                "detection_method, confidence, category, status, evidence_state) "
                "values (%s, %s, %s, 'activity', '통계 근거', "
                "'freq_shift', 3.0, '오늘의다른점', 'dismissed', %s)",
                (user, day, entity, evidence_state),
            )

        counts = fetch_dismiss_counts(
            conn,
            user,
            date(2026, 6, 25),
            date(2026, 7, 23),
        )

        assert counts == {(entity, "activity", "freq_shift"): 1}
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_마지막_과거_언급은_근거_memory_id까지_반환한다(conn):
    user = seed_user(conn)
    try:
        entity = _entity(conn, user, "노래")
        older = seed_memory_at(conn, user, "2026-05-01T01:00:00+00")
        latest = seed_memory_at(conn, user, "2026-06-01T01:00:00+00")
        _link(conn, older, entity)
        _link(conn, latest, entity)

        got = fetch_latest_prior_occurrences(
            conn,
            user,
            [entity],
            date(2026, 7, 23),
        )

        assert got[entity][2] == latest
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_근거_교체는_교차_사용자_차이와_메모를_건드리지_않는다(conn):
    alice = seed_user(conn)
    bob = seed_user(conn)
    try:
        alice_entity = _entity(conn, alice, "앨리스")
        bob_entity = _entity(conn, bob, "밥")
        alice_memory = seed_memory_at(conn, alice, "2026-07-23T01:00:00+00")
        bob_memory = seed_memory_at(conn, bob, "2026-07-23T01:00:00+00")
        alice_diff = upsert_difference(
            conn,
            alice,
            date(2026, 7, 23),
            alice_entity,
            "freq_shift",
            "thing",
            "통계 근거",
            3.0,
        )
        bob_diff = upsert_difference(
            conn,
            bob,
            date(2026, 7, 23),
            bob_entity,
            "freq_shift",
            "thing",
            "통계 근거",
            3.0,
        )
        link_difference_evidence(conn, bob_diff, bob_memory)

        replace_difference_evidence(conn, alice, bob_diff, [alice_memory])
        replace_difference_evidence(conn, alice, alice_diff, [bob_memory])

        bob_evidence = conn.execute(
            "select memory_id::text from public.difference_evidence "
            "where difference_id = %s",
            (bob_diff,),
        ).fetchall()
        alice_evidence = conn.execute(
            "select memory_id::text from public.difference_evidence "
            "where difference_id = %s",
            (alice_diff,),
        ).fetchall()
        assert [row[0] for row in bob_evidence] == [bob_memory]
        assert alice_evidence == []
    finally:
        delete_user(conn, alice)
        delete_user(conn, bob)

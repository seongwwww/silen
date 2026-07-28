from datetime import date, timedelta

import pytest

from silen_worker.tasks.detect import detect_day
from tests.conftest import delete_user, seed_memory_at, seed_user

TARGET = date(2026, 7, 23)


def _entity(conn, user_id, name, etype="thing"):
    return conn.execute(
        "insert into public.entities (user_id, entity_type, name, normalized_name) "
        "values (%s, %s, %s, %s) returning id::text",
        (user_id, etype, name, name),
    ).fetchone()[0]


def _memory(conn, user_id, day):
    return seed_memory_at(conn, user_id, f"{day.isoformat()}T02:00:00+00")


def _mention(conn, user_id, entity_id, day):
    memory_id = _memory(conn, user_id, day)
    conn.execute(
        "insert into public.memory_entities (memory_id, entity_id, relation_type) "
        "values (%s, %s, 'mentioned')",
        (memory_id, entity_id),
    )
    return memory_id


def _diffs(conn, user_id):
    return conn.execute(
        "select id::text, detection_method, description, confidence "
        "from public.differences where user_id = %s order by id",
        (user_id,),
    ).fetchall()


@pytest.mark.integration
def test_첫_등장은_저장하고_오늘_근거를_연결한다(conn):
    user = seed_user(conn)
    try:
        entity_id = _entity(conn, user, "낯선카페", "place")
        memory_id = _mention(conn, user, entity_id, TARGET)

        written = detect_day(conn, user, TARGET.isoformat())

        assert len(written) == 1
        difference = _diffs(conn, user)[0]
        assert difference[1:3] == ("first_occurrence", "처음 등장")
        evidence = conn.execute(
            "select memory_id::text from public.difference_evidence "
            "where difference_id = %s",
            (difference[0],),
        ).fetchall()
        assert [row[0] for row in evidence] == [memory_id]
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_기록_부재는_과거_언급과_오늘_활성_메모를_근거로_삼는다(conn):
    user = seed_user(conn)
    try:
        entity_id = _entity(conn, user, "산책", "activity")
        past_ids = [
            _mention(conn, user, entity_id, TARGET - timedelta(days=2)),
            _mention(conn, user, entity_id, TARGET - timedelta(days=1)),
        ]
        today_id = _memory(conn, user, TARGET)

        written = detect_day(conn, user, TARGET.isoformat())

        assert len(written) == 1
        difference = _diffs(conn, user)[0]
        assert difference[1] == "freq_shift"
        assert "오늘 기록에는 언급 없음" in difference[2]
        assert difference[3] == pytest.approx(2.5849625)
        evidence = conn.execute(
            "select memory_id::text from public.difference_evidence "
            "where difference_id = %s",
            (difference[0],),
        ).fetchall()
        assert {row[0] for row in evidence} == {*past_ids, today_id}
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_한_번만_기록된_엔티티의_부재는_만들지_않는다(conn):
    user = seed_user(conn)
    try:
        entity_id = _entity(conn, user, "산책", "activity")
        _mention(conn, user, entity_id, TARGET - timedelta(days=1))
        _memory(conn, user, TARGET)

        assert detect_day(conn, user, TARGET.isoformat()) == []
        assert _diffs(conn, user) == []
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_빈_날은_부재를_억지로_만들지_않는다(conn):
    user = seed_user(conn)
    try:
        entity_id = _entity(conn, user, "산책", "activity")
        _mention(conn, user, entity_id, TARGET - timedelta(days=2))
        _mention(conn, user, entity_id, TARGET - timedelta(days=1))

        assert detect_day(conn, user, TARGET.isoformat()) == []
        assert _diffs(conn, user) == []
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_오랜만의_재등장은_활성일_기준_bits를_저장한다(conn):
    user = seed_user(conn)
    try:
        entity_id = _entity(conn, user, "그노래", "thing")
        for offset in range(1, 15):
            day = TARGET - timedelta(days=offset)
            if offset == 9:
                _mention(conn, user, entity_id, day)
            else:
                _memory(conn, user, day)
        _mention(conn, user, entity_id, TARGET)

        written = detect_day(conn, user, TARGET.isoformat())

        assert len(written) == 1
        difference = _diffs(conn, user)[0]
        assert difference[1] == "freq_shift"
        assert difference[2] == (
            "9일 만에 재등장(과거 활성일 14일 중 1일 기록됨)"
        )
        assert difference[3] == pytest.approx(3.3219281)
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_연속_등장은_매일_차이로_저장하지_않는다(conn):
    user = seed_user(conn)
    try:
        entity_id = _entity(conn, user, "김밥")
        _mention(conn, user, entity_id, TARGET - timedelta(days=1))
        _mention(conn, user, entity_id, TARGET)

        assert detect_day(conn, user, TARGET.isoformat()) == []
        assert _diffs(conn, user) == []
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_재실행은_차이와_근거를_중복하지_않는다(conn):
    user = seed_user(conn)
    try:
        entity_id = _entity(conn, user, "요가", "activity")
        _mention(conn, user, entity_id, TARGET)

        first = detect_day(conn, user, TARGET.isoformat())
        second = detect_day(conn, user, TARGET.isoformat())

        assert first == second
        assert len(_diffs(conn, user)) == 1
        evidence_count = conn.execute(
            "select count(*)::int from public.difference_evidence "
            "where difference_id = %s",
            (first[0],),
        ).fetchone()[0]
        assert evidence_count == 1
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_타_사용자_활성일과_엔티티는_절대_섞이지_않는다(conn):
    alice = seed_user(conn)
    bob = seed_user(conn)
    try:
        alice_entity = _entity(conn, alice, "김밥")
        _mention(conn, alice, alice_entity, TARGET)
        bob_entity = _entity(conn, bob, "김밥")
        _mention(conn, bob, bob_entity, TARGET - timedelta(days=1))
        _mention(conn, bob, bob_entity, TARGET)

        detect_day(conn, alice, TARGET.isoformat())

        assert len(_diffs(conn, alice)) == 1
        assert _diffs(conn, bob) == []
    finally:
        delete_user(conn, alice)
        delete_user(conn, bob)

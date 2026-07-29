from datetime import date, timedelta

import pytest

from silen_worker.cli import run_daily, run_diary
from silen_worker.db import fetch_existing_diary, fetch_narration_id
from tests.conftest import delete_user, seed_memory, seed_memory_at, seed_user


class CountingNarrator:
    model = "stub"

    def __init__(self):
        self.calls = 0

    def narrate(self, facts):
        self.calls += 1
        return {
            "headline": f"{facts.entity_name} 기록 변화",
            "body": f"{facts.entity_name}: {facts.description}",
            "evidence_text": facts.description,
        }


class BoomNarrator:
    """특정 사용자에서만 터지는 서술기. 실패 격리 검증용."""

    model = "stub"

    def __init__(self, boom_user):
        self.boom_user = boom_user
        self.calls = 0

    def narrate(self, facts):
        self.calls += 1
        if facts.user_id == self.boom_user:
            raise RuntimeError("boom")
        return {
            "headline": f"{facts.entity_name} 기록 변화",
            "body": f"{facts.entity_name}: {facts.description}",
            "evidence_text": facts.description,
        }


class StubWriter:
    model = "stub"

    def write(self, facts):
        return {
            "one_line": "비슷한 하루.",
            "body": "특별할 것 없는 하루였다. 점심은 김밥.",
            "used_memory_ids": [m.memory_id for m in facts.memories],
            "used_difference_ids": [
                d.difference_id for d in facts.differences
            ],
        }


def _absence_materials(conn, user_id, name="김밥"):
    """두 활성일에 언급하고 오늘은 다른 메모를 남겨 기록 부재를 만든다."""
    ent = conn.execute(
        "insert into public.entities (user_id, entity_type, name, normalized_name) "
        "values (%s, 'thing', %s, %s) "
        "on conflict (user_id, entity_type, normalized_name) do update "
        "set name = excluded.name "
        "returning id::text",
        (user_id, name, name),
    ).fetchone()[0]
    for offset in (2, 1):
        day = date.today() - timedelta(days=offset)
        memory_id = seed_memory_at(
            conn,
            user_id,
            f"{day.isoformat()}T02:00:00+00",
        )
        conn.execute(
            "insert into public.memory_entities "
            "(memory_id, entity_id, relation_type) "
            "values (%s, %s, 'mentioned')",
            (memory_id, ent),
        )
    return seed_memory(conn, user_id, "오늘의 다른 기록")


def _today():
    return date.today().isoformat()


@pytest.mark.integration
def test_run_daily가_차이를_검출하고_서술한다(conn):
    user = seed_user(conn)
    try:
        _absence_materials(conn, user)
        narrator = CountingNarrator()
        ok, fail = run_daily(conn, [(user, _today())], narrator=narrator)

        assert (ok, fail) == (1, 0)
        diffs = conn.execute(
            "select id::text from public.differences where user_id = %s", (user,)
        ).fetchall()
        assert len(diffs) >= 1
        assert fetch_narration_id(conn, diffs[0][0]) is not None
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_run_daily를_두번_돌려도_LLM은_한번만(conn):
    """핵심 회귀: 스케줄러 반복 실행이 재과금을 만들지 않는다."""
    user = seed_user(conn)
    try:
        _absence_materials(conn, user)
        narrator = CountingNarrator()

        run_daily(conn, [(user, _today())], narrator=narrator)
        first_calls = narrator.calls
        run_daily(conn, [(user, _today())], narrator=narrator)

        assert first_calls >= 1
        assert narrator.calls == first_calls
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_run_daily는_잠근_오늘_기록을_빼고_해제하면_다시_쓴다(conn):
    user = seed_user(conn)
    try:
        today_memory = _absence_materials(conn, user)
        narrator = CountingNarrator()
        conn.execute(
            "update public.memories set is_locked = true where id = %s",
            (today_memory,),
        )

        run_daily(conn, [(user, _today())], narrator=narrator)
        assert narrator.calls == 0

        conn.execute(
            "update public.memories set is_locked = false where id = %s",
            (today_memory,),
        )
        run_daily(conn, [(user, _today())], narrator=narrator)
        assert narrator.calls >= 1
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_한_사용자_실패가_다른_사용자를_막지_않는다(conn):
    user_a = seed_user(conn)
    user_b = seed_user(conn)
    try:
        _absence_materials(conn, user_a)
        _absence_materials(conn, user_b)
        narrator = BoomNarrator(boom_user=user_a)

        ok, fail = run_daily(
            conn, [(user_a, _today()), (user_b, _today())], narrator=narrator
        )

        assert (ok, fail) == (1, 1)
        b_diffs = conn.execute(
            "select id::text from public.differences where user_id = %s", (user_b,)
        ).fetchall()
        assert fetch_narration_id(conn, b_diffs[0][0]) is not None
    finally:
        delete_user(conn, user_a)
        delete_user(conn, user_b)


@pytest.mark.integration
def test_run_diary가_일기를_만든다(conn):
    user = seed_user(conn)
    try:
        seed_memory(conn, user, "점심 김밥")
        ok, fail = run_diary(conn, [(user, _today())], writer=StubWriter())

        assert (ok, fail) == (1, 0)
        assert fetch_existing_diary(conn, user, date.today()) is not None
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_빈_날은_일기를_안만들지만_실패도_아니다(conn):
    user = seed_user(conn)
    try:
        ok, fail = run_diary(conn, [(user, _today())], writer=StubWriter())
        assert (ok, fail) == (1, 0)
        assert fetch_existing_diary(conn, user, date.today()) is None
    finally:
        delete_user(conn, user)

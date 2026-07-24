from datetime import date

import pytest

from silen_worker.db import (
    fetch_confirmed_differences, fetch_diary_memories, fetch_existing_diary,
    replace_diary_sections, replace_diary_sources, upsert_diary,
)
from tests.conftest import seed_user, seed_memory, delete_user


def _confirmed_difference(conn, user_id, name="김밥", headline="3일째 김밥"):
    # 날짜는 Python date.today()로 명시 — SQL current_date(DB tz)와 date.today()(로컬)가
    # UTC/KST 경계에서 어긋나 테스트가 flaky해지는 걸 막는다(결정적 시드).
    ent = conn.execute(
        "insert into public.entities (user_id, entity_type, name, normalized_name) "
        "values (%s, 'thing', %s, %s) returning id::text",
        (user_id, name, name),
    ).fetchone()[0]
    diff = conn.execute(
        """
        insert into public.differences
          (user_id, date, entity_id, dimension, description, detection_method,
           confidence, category, status, evidence_state)
        values (%s, %s, %s, 'thing', '최근 3일 연속 등장', 'freq_shift',
                0.5, '오늘의다른점', 'confirmed', 'intact')
        returning id::text
        """,
        (user_id, date.today(), ent),
    ).fetchone()[0]
    conn.execute(
        "insert into public.difference_narrations "
        "(user_id, difference_id, headline, body, evidence_text, model) "
        "values (%s, %s, %s, 'b', 'e', 'm')",
        (user_id, diff, headline),
    )
    return diff


@pytest.mark.integration
def test_그날_메모를_조회한다(conn):
    user = seed_user(conn)
    try:
        mem = seed_memory(conn, user, "점심 김밥")  # captured_at default now()
        rows = fetch_diary_memories(conn, user, date.today())
        ids = [r.memory_id for r in rows]
        assert mem in ids
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_빈본문_메모는_제외(conn):
    user = seed_user(conn)
    try:
        seed_memory(conn, user, "   ")  # 공백만
        rows = fetch_diary_memories(conn, user, date.today())
        assert rows == []
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_confirmed_차이와_headline을_조회한다(conn):
    user = seed_user(conn)
    try:
        diff = _confirmed_difference(conn, user, headline="3일째 김밥")
        got = fetch_confirmed_differences(conn, user, date.today())
        assert (diff, "3일째 김밥") in got
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_candidate_차이는_조회안됨(conn):
    user = seed_user(conn)
    try:
        ent = conn.execute(
            "insert into public.entities (user_id, entity_type, name, normalized_name) "
            "values (%s, 'thing', '김밥', '김밥') returning id::text", (user,)
        ).fetchone()[0]
        conn.execute(
            "insert into public.differences (user_id, date, entity_id, dimension, description, "
            "detection_method, confidence, category, status, evidence_state) "
            "values (%s, %s, %s, 'thing', 'x', 'freq_shift', 0.5, '오늘의다른점', "
            "'candidate', 'intact')", (user, date.today(), ent),
        )
        assert fetch_confirmed_differences(conn, user, date.today()) == []
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_일기_저장과_섹션_출처_교체(conn):
    user = seed_user(conn)
    try:
        mem = seed_memory(conn, user, "점심 김밥")
        diff = _confirmed_difference(conn, user, headline="3일째 김밥")
        did = upsert_diary(conn, user, date.today(), "본문 v1")
        replace_diary_sections(conn, did, "한 문장 v1", "본문 v1", [(diff, "3일째 김밥")])
        replace_diary_sources(conn, did, [mem])

        # 재저장(force 흐름): 다른 내용으로 교체
        did2 = upsert_diary(conn, user, date.today(), "본문 v2")
        assert did2 == did  # 하루 1건
        replace_diary_sections(conn, did, "한 문장 v2", "본문 v2", [])
        replace_diary_sources(conn, did, [])

        gen = conn.execute("select generated_text from public.diaries where id = %s", (did,)).fetchone()[0]
        assert gen == "본문 v2"
        sec = conn.execute(
            "select count(*)::int from public.diary_sections where diary_id = %s", (did,)
        ).fetchone()[0]
        assert sec == 2  # 오늘의한문장 + 본문 (다른점 0)
        src = conn.execute(
            "select count(*)::int from public.diary_sources where diary_id = %s", (did,)
        ).fetchone()[0]
        assert src == 0
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_기존_일기_조회(conn):
    user = seed_user(conn)
    try:
        assert fetch_existing_diary(conn, user, date.today()) is None
        did = upsert_diary(conn, user, date.today(), "본문")
        got = fetch_existing_diary(conn, user, date.today())
        assert got == (did, "draft")
    finally:
        delete_user(conn, user)

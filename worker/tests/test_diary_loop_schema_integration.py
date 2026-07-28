from datetime import date

import pytest

from tests.conftest import seed_user, delete_user


@pytest.mark.integration
def test_톤주문과_재생성요청을_저장한다(conn):
    user = seed_user(conn)
    try:
        diary = conn.execute(
            "insert into public.diaries (user_id, date, status, generated_text) "
            "values (%s, %s, 'draft', '본문') returning id::text",
            (user, date.today()),
        ).fetchone()[0]
        conn.execute(
            "update public.diaries set tone_instruction = %s, "
            "regenerate_requested_at = now() where id = %s",
            ("더 짧게", diary),
        )
        row = conn.execute(
            "select tone_instruction, regenerate_requested_at is not null "
            "from public.diaries where id = %s",
            (diary,),
        ).fetchone()
        assert row[0] == "더 짧게"
        assert row[1] is True
    finally:
        delete_user(conn, user)

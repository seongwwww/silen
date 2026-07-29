from datetime import date

import pytest

from silen_worker.db import request_late_diary_regeneration
from tests.conftest import delete_user, seed_user


@pytest.mark.integration
def test_late_regeneration_marker_is_owner_and_date_scoped(conn):
    alice = seed_user(conn)
    bob = seed_user(conn)
    target = date(2026, 7, 20)
    try:
        alice_diary = conn.execute(
            "insert into public.diaries "
            "(user_id, date, status, generated_text) "
            "values (%s, %s, 'draft', 'alice body') returning id::text",
            (alice, target),
        ).fetchone()[0]
        bob_diary = conn.execute(
            "insert into public.diaries "
            "(user_id, date, status, generated_text) "
            "values (%s, %s, 'draft', 'bob body') returning id::text",
            (bob, target),
        ).fetchone()[0]

        assert request_late_diary_regeneration(conn, alice, target)

        alice_row = conn.execute(
            "select generated_text, regenerate_requested_at is not null, "
            "regenerate_reason from public.diaries where id = %s",
            (alice_diary,),
        ).fetchone()
        bob_row = conn.execute(
            "select generated_text, regenerate_requested_at, "
            "regenerate_reason from public.diaries where id = %s",
            (bob_diary,),
        ).fetchone()
        assert alice_row == ("alice body", True, "late_record")
        assert bob_row == ("bob body", None, None)
    finally:
        delete_user(conn, alice)
        delete_user(conn, bob)

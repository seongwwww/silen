import pytest

from silen_worker.db import fetch_active_users, fetch_narration_id
from tests.conftest import seed_user, seed_memory, delete_user


def _difference_with_narration(conn, user_id, headline="3일째 김밥"):
    """차이 하나 + 그 서술을 만들고 (difference_id, narration_id)를 돌려준다."""
    ent = conn.execute(
        "insert into public.entities (user_id, entity_type, name, normalized_name) "
        "values (%s, 'thing', '김밥', '김밥') returning id::text",
        (user_id,),
    ).fetchone()[0]
    from datetime import date

    diff = conn.execute(
        """
        insert into public.differences
          (user_id, date, entity_id, dimension, description, detection_method,
           confidence, category, status, evidence_state)
        values (%s, %s, %s, 'thing', '최근 3일 연속 등장', 'freq_shift',
                0.5, '오늘의다른점', 'candidate', 'intact')
        returning id::text
        """,
        (user_id, date.today(), ent),
    ).fetchone()[0]
    nid = conn.execute(
        "insert into public.difference_narrations "
        "(user_id, difference_id, headline, body, evidence_text, model) "
        "values (%s, %s, %s, 'b', 'e', 'm') returning id::text",
        (user_id, diff, headline),
    ).fetchone()[0]
    return diff, nid


@pytest.mark.integration
def test_사용자를_타임존과_함께_열거한다(conn):
    user = seed_user(conn)
    try:
        rows = fetch_active_users(conn)
        found = [(u, tz) for (u, tz) in rows if u == user]
        assert len(found) == 1
        assert found[0][1] == "Asia/Seoul"
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_서술이_있으면_id를_돌려준다(conn):
    user = seed_user(conn)
    try:
        seed_memory(conn, user, "김밥 먹음")
        diff, nid = _difference_with_narration(conn, user)
        assert fetch_narration_id(conn, diff) == nid
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_서술이_없으면_None(conn):
    user = seed_user(conn)
    try:
        ent = conn.execute(
            "insert into public.entities (user_id, entity_type, name, normalized_name) "
            "values (%s, 'thing', '김밥', '김밥') returning id::text",
            (user,),
        ).fetchone()[0]
        from datetime import date

        diff = conn.execute(
            """
            insert into public.differences
              (user_id, date, entity_id, dimension, description, detection_method,
               confidence, category, status, evidence_state)
            values (%s, %s, %s, 'thing', 'x', 'freq_shift', 0.5, '오늘의다른점',
                    'candidate', 'intact')
            returning id::text
            """,
            (user, date.today(), ent),
        ).fetchone()[0]
        assert fetch_narration_id(conn, diff) is None
    finally:
        delete_user(conn, user)

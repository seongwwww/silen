import pytest

from tests.conftest import seed_user, seed_memory, delete_user


def _mk_difference(conn, user_id, memory_id):
    """엔티티 차이 하나를 만들어 그 id를 돌려준다. narration의 FK 대상."""
    ent = conn.execute(
        "insert into public.entities (user_id, entity_type, name, normalized_name) "
        "values (%s, 'thing', '김밥', '김밥') returning id::text",
        (user_id,),
    ).fetchone()[0]
    diff = conn.execute(
        """
        insert into public.differences
          (user_id, date, entity_id, dimension, description,
           detection_method, confidence, category, status, evidence_state)
        values (%s, current_date, %s, 'thing', '최근 3일 연속 등장',
                'freq_shift', 0.5, '오늘의다른점', 'candidate', 'intact')
        returning id::text
        """,
        (user_id, ent),
    ).fetchone()[0]
    return diff


@pytest.mark.integration
def test_서술을_저장하고_읽는다(conn):
    user = seed_user(conn)
    try:
        mem = seed_memory(conn, user, "김밥 먹음")
        diff = _mk_difference(conn, user, mem)
        conn.execute(
            "insert into public.difference_narrations "
            "(user_id, difference_id, headline, body, evidence_text, model) "
            "values (%s, %s, '3일째 김밥', '김밥을 최근 3일 연속으로 남기셨네요.', "
            "'요즘 자주 등장해서 찾았어요.', 'gemini-3.5-flash')",
            (user, diff),
        )
        row = conn.execute(
            "select headline from public.difference_narrations where difference_id = %s",
            (diff,),
        ).fetchone()
        assert row[0] == "3일째 김밥"
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_difference당_서술은_하나다(conn):
    user = seed_user(conn)
    try:
        mem = seed_memory(conn, user, "김밥 먹음")
        diff = _mk_difference(conn, user, mem)
        conn.execute(
            "insert into public.difference_narrations "
            "(user_id, difference_id, headline, body, evidence_text, model) "
            "values (%s, %s, 'a', 'b', 'c', 'm')",
            (user, diff),
        )
        with pytest.raises(psycopg_errors_UniqueViolation()):
            conn.execute(
                "insert into public.difference_narrations "
                "(user_id, difference_id, headline, body, evidence_text, model) "
                "values (%s, %s, 'a2', 'b2', 'c2', 'm')",
                (user, diff),
            )
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_difference_삭제시_서술도_사라진다(conn):
    user = seed_user(conn)
    try:
        mem = seed_memory(conn, user, "김밥 먹음")
        diff = _mk_difference(conn, user, mem)
        conn.execute(
            "insert into public.difference_narrations "
            "(user_id, difference_id, headline, body, evidence_text, model) "
            "values (%s, %s, 'a', 'b', 'c', 'm')",
            (user, diff),
        )
        conn.execute("delete from public.differences where id = %s", (diff,))
        left = conn.execute(
            "select 1 from public.difference_narrations where difference_id = %s", (diff,)
        ).fetchone()
        assert left is None
    finally:
        delete_user(conn, user)


def psycopg_errors_UniqueViolation():
    from psycopg import errors
    return errors.UniqueViolation

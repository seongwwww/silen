import pytest

from tests.conftest import seed_user, delete_user


def _entity(conn, user_id, name="민수", etype="person"):
    return conn.execute(
        "insert into public.entities (user_id, entity_type, name, normalized_name) "
        "values (%s, %s, %s, %s) returning id::text",
        (user_id, etype, name, name),
    ).fetchone()[0]


def _insert_diff(conn, user_id, entity_id, method="first_occurrence"):
    return conn.execute(
        "insert into public.differences "
        "  (user_id, date, entity_id, dimension, description, detection_method, category) "
        "values (%s, '2026-07-23', %s, 'person', '테스트', %s, '오늘의다른점') "
        "returning id::text",
        (user_id, entity_id, method),
    ).fetchone()[0]


@pytest.mark.integration
def test_같은_자연키_차이는_중복_생성되지_않는다(conn):
    user = seed_user(conn)
    try:
        ent = _entity(conn, user)
        _insert_diff(conn, user, ent)
        with pytest.raises(Exception):  # unique 위반
            _insert_diff(conn, user, ent)
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_엔티티_삭제시_entity_id는_null이_되고_difference는_남는다(conn):
    user = seed_user(conn)
    try:
        ent = _entity(conn, user)
        did = _insert_diff(conn, user, ent)
        conn.execute("delete from public.entities where id = %s", (ent,))
        row = conn.execute(
            "select entity_id from public.differences where id = %s", (did,)
        ).fetchone()
        assert row is not None      # difference 보존
        assert row[0] is None       # entity_id만 null
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_entity_id_null인_행은_자연키_제약을_받지_않는다(conn):
    user = seed_user(conn)
    try:
        # 미래 method(zscore 등) 시뮬레이션 — entity_id null 두 건이 충돌하지 않는다.
        for _ in range(2):
            conn.execute(
                "insert into public.differences "
                "  (user_id, date, dimension, description, detection_method, category) "
                "values (%s, '2026-07-23', 'x', 'y', 'zscore', '오늘의다른점')",
                (user,),
            )
        n = conn.execute(
            "select count(*)::int from public.differences where user_id = %s", (user,)
        ).fetchone()[0]
        assert n == 2
    finally:
        delete_user(conn, user)

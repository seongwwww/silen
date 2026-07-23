import pytest

from tests.conftest import seed_user, seed_memory, delete_user


def _mk_entity(conn, user_id, name):
    row = conn.execute(
        "insert into public.entities (user_id, entity_type, name, normalized_name) "
        "values (%s, 'person', %s, %s) returning id::text",
        (user_id, name, name),
    ).fetchone()
    return row[0]


@pytest.mark.integration
def test_mentioned_relation_type가_허용된다(conn):
    user = seed_user(conn)
    try:
        mem = seed_memory(conn, user, "민수 생각남")
        ent = _mk_entity(conn, user, "민수")
        conn.execute(
            "insert into public.memory_entities (memory_id, entity_id, relation_type) "
            "values (%s, %s, 'mentioned')",
            (mem, ent),
        )
        row = conn.execute(
            "select relation_type from public.memory_entities where memory_id = %s",
            (mem,),
        ).fetchone()
        assert row[0] == "mentioned"
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_마지막_링크가_사라지면_entity도_삭제된다(conn):
    user = seed_user(conn)
    try:
        mem = seed_memory(conn, user, "민수랑 점심")
        ent = _mk_entity(conn, user, "민수")
        conn.execute(
            "insert into public.memory_entities (memory_id, entity_id, relation_type) "
            "values (%s, %s, 'mentioned')",
            (mem, ent),
        )
        # 링크 삭제 → entity가 고아 → 트리거가 삭제
        conn.execute("delete from public.memory_entities where entity_id = %s", (ent,))
        left = conn.execute("select 1 from public.entities where id = %s", (ent,)).fetchone()
        assert left is None
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_다른_메모가_참조하면_entity는_유지된다(conn):
    user = seed_user(conn)
    try:
        mem1 = seed_memory(conn, user, "민수랑 점심")
        mem2 = seed_memory(conn, user, "민수 또 생각남")
        ent = _mk_entity(conn, user, "민수")
        conn.execute(
            "insert into public.memory_entities (memory_id, entity_id, relation_type) "
            "values (%s, %s, 'mentioned'), (%s, %s, 'mentioned')",
            (mem1, ent, mem2, ent),
        )
        # mem1의 링크만 삭제 → entity는 mem2가 아직 참조 → 유지
        conn.execute(
            "delete from public.memory_entities where memory_id = %s and entity_id = %s",
            (mem1, ent),
        )
        left = conn.execute("select 1 from public.entities where id = %s", (ent,)).fetchone()
        assert left is not None
    finally:
        delete_user(conn, user)

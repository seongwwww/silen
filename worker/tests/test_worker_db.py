import pytest

from silen_worker.db import fetch_memory
from tests.conftest import seed_user, seed_memory, delete_user


@pytest.mark.integration
def test_본인_메모는_조회된다(conn):
    user = seed_user(conn)
    try:
        memory_id = seed_memory(conn, user, "본인 메모")
        result = fetch_memory(conn, memory_id, user)
        assert result is not None
        assert result.id == memory_id
        assert result.raw_text == "본인 메모"
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_남의_user_id로는_조회되지_않는다(conn):
    # 워커가 user_id 필터를 지키는지 — 교차 사용자 격리의 코드 방어선.
    alice = seed_user(conn)
    bob = seed_user(conn)
    try:
        memory_id = seed_memory(conn, alice, "앨리스 메모")
        assert fetch_memory(conn, memory_id, bob) is None
    finally:
        delete_user(conn, alice)
        delete_user(conn, bob)

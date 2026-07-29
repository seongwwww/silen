"""사진 임베딩 저장·검색을 실제 Postgres로 검증한다.

단위 테스트는 DB를 스텁해 SQL 문법·벡터 연산자를 잡지 못한다.
"""

import pytest

from silen_worker.photo.repository import (
    search_photo_candidates,
    sync_photo_searchable,
    upsert_photo_embedding,
)
from silen_worker.photo.service import PHOTO_EMBEDDING_DIMENSION
from tests.conftest import delete_user, seed_memory_at, seed_user


def _asset(conn, memory_id: str, path: str) -> str:
    return conn.execute(
        "insert into public.assets (memory_id, asset_type, file_url, mime_type) "
        "values (%s, 'photo', %s, 'image/png') returning id::text",
        (memory_id, path),
    ).fetchone()[0]


def _vec(seed: float) -> list[float]:
    return [seed] * PHOTO_EMBEDDING_DIMENSION


@pytest.mark.integration
def test_사진_임베딩을_저장하고_찾는다(conn):
    alice = seed_user(conn)
    try:
        memory = seed_memory_at(conn, alice, "2026-07-19T03:00:00+00", "카페 사진")
        asset = _asset(conn, memory, f"{alice}/a.png")

        assert upsert_photo_embedding(conn, asset, memory, alice, _vec(0.5))
        # 같은 자산을 다시 넣어도 1건이다.
        assert upsert_photo_embedding(conn, asset, memory, alice, _vec(0.6))

        found = search_photo_candidates(conn, alice, _vec(0.6))
        assert [row[0] for row in found] == [memory]
        assert found[0][2] == f"{alice}/a.png"
    finally:
        delete_user(conn, alice)


@pytest.mark.integration
def test_남의_사진은_섞이지_않는다(conn):
    """교차 사용자 노출은 심각 결함이다(privacy.md)."""
    alice = seed_user(conn)
    bob = seed_user(conn)
    try:
        memory = seed_memory_at(conn, bob, "2026-07-19T03:00:00+00", "밥의 사진")
        asset = _asset(conn, memory, f"{bob}/b.png")
        upsert_photo_embedding(conn, asset, memory, bob, _vec(0.5))

        assert search_photo_candidates(conn, alice, _vec(0.5)) == []
    finally:
        delete_user(conn, alice)
        delete_user(conn, bob)


@pytest.mark.integration
def test_잠그면_사진도_검색에서_빠진다(conn):
    alice = seed_user(conn)
    try:
        memory = seed_memory_at(conn, alice, "2026-07-19T03:00:00+00", "잠글 사진")
        asset = _asset(conn, memory, f"{alice}/c.png")
        upsert_photo_embedding(conn, asset, memory, alice, _vec(0.5))

        conn.execute(
            "update public.memories set is_locked = true where id = %s", (memory,)
        )
        sync_photo_searchable(conn, memory)

        assert search_photo_candidates(conn, alice, _vec(0.5)) == []
    finally:
        delete_user(conn, alice)


@pytest.mark.integration
def test_메모를_지우면_사진_임베딩도_사라진다(conn):
    alice = seed_user(conn)
    try:
        memory = seed_memory_at(conn, alice, "2026-07-19T03:00:00+00", "지울 사진")
        asset = _asset(conn, memory, f"{alice}/d.png")
        upsert_photo_embedding(conn, asset, memory, alice, _vec(0.5))

        conn.execute("delete from public.memories where id = %s", (memory,))

        left = conn.execute(
            "select count(*) from public.photo_embeddings where memory_id = %s",
            (memory,),
        ).fetchone()[0]
        assert left == 0
    finally:
        delete_user(conn, alice)

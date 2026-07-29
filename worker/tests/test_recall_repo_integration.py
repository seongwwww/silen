"""회고 검색 SQL을 실제 Postgres로 검증한다.

단위 테스트는 DB를 스텁하므로 SQL 문법 오류를 구조적으로 잡지 못한다.
실제로 `ilike any(...) escape '\\'`가 통과해 배포 직전까지 살아남았다 —
ESCAPE 절은 LIKE 특수 구문에만 있고 ANY(배열) 연산자 형식엔 못 붙는다.
"""

import pytest

from silen_worker.recall.repository import search_keyword_candidates
from tests.conftest import seed_user, seed_memory_at, delete_user


@pytest.mark.integration
def test_키워드_검색이_실제로_실행된다(conn):
    alice = seed_user(conn)
    try:
        seed_memory_at(conn, alice, "2026-07-19T03:00:00+00", "그 카페에서 커피를 마셨다")
        seed_memory_at(conn, alice, "2026-07-20T03:00:00+00", "회사에 갔다")

        found = search_keyword_candidates(conn, alice, "카페 언제 갔지")

        assert [c.memory_id for c in found] != []
        assert any("카페" in c.raw_text for c in found)
    finally:
        delete_user(conn, alice)


@pytest.mark.integration
def test_남의_기록은_섞이지_않는다(conn):
    """교차 사용자 노출은 심각 결함이다(privacy.md)."""
    alice = seed_user(conn)
    bob = seed_user(conn)
    try:
        seed_memory_at(conn, bob, "2026-07-19T03:00:00+00", "밥의 카페 이야기")

        assert search_keyword_candidates(conn, alice, "카페") == []
    finally:
        delete_user(conn, alice)
        delete_user(conn, bob)


@pytest.mark.integration
def test_잠기거나_삭제된_기록은_빠진다(conn):
    alice = seed_user(conn)
    try:
        locked = seed_memory_at(conn, alice, "2026-07-19T03:00:00+00", "잠근 카페 기록")
        removed = seed_memory_at(conn, alice, "2026-07-20T03:00:00+00", "지운 카페 기록")
        conn.execute("update public.memories set is_locked = true where id = %s", (locked,))
        conn.execute("update public.memories set deleted_at = now() where id = %s", (removed,))

        assert search_keyword_candidates(conn, alice, "카페") == []
    finally:
        delete_user(conn, alice)


@pytest.mark.integration
def test_와일드카드는_문자_그대로_찾는다(conn):
    """%나 _를 넣어도 전체 매칭으로 번지지 않아야 한다."""
    alice = seed_user(conn)
    try:
        seed_memory_at(conn, alice, "2026-07-19T03:00:00+00", "할인 100% 받았다")
        seed_memory_at(conn, alice, "2026-07-20T03:00:00+00", "그냥 평범한 하루")

        found = search_keyword_candidates(conn, alice, "100%")

        assert len(found) == 1
        assert "100%" in found[0].raw_text
    finally:
        delete_user(conn, alice)

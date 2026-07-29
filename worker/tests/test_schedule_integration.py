import pytest

from silen_worker.cli import run_scheduled
from silen_worker.tasks.process import process_pending
from tests.conftest import delete_user, seed_memory_at, seed_user


TODAY = "2026-07-29"


class _NoEntities:
    def extract(self, text):
        return []


class _StubWriter:
    model = "stub"

    def write(self, facts):
        return {
            "one_line": "비슷한 하루.",
            "body": "기록에서 확인한 하루였다.",
            "used_memory_ids": [m.memory_id for m in facts.memories],
            "used_difference_ids": [
                d.difference_id for d in facts.differences
            ],
        }


def _diary_job_count(conn, user_id: str) -> int:
    return conn.execute(
        """
        select count(*)
        from pgmq.q_memory_jobs
        where message->>'user_id' = %s
          and message->>'job_type' = 'diary'
        """,
        (user_id,),
    ).fetchone()[0]


@pytest.mark.integration
def test_같은_날_두번_돌려도_요청과_잡은_하나(conn):
    user = seed_user(conn)
    try:
        seed_memory_at(conn, user, "2026-07-29T02:00:00+00")

        assert run_scheduled(conn, [(user, TODAY)]) == (1, 0, 0)
        assert run_scheduled(conn, [(user, TODAY)]) == (0, 1, 0)

        requests = conn.execute(
            """
            select count(*)
            from public.diary_generation_requests
            where user_id = %s and date = %s
            """,
            (user, TODAY),
        ).fetchone()[0]
        assert requests == 1
        assert _diary_job_count(conn, user) == 1
        request_id = conn.execute(
            """
            select id::text
            from public.diary_generation_requests
            where user_id = %s and date = %s
            """,
            (user, TODAY),
        ).fetchone()[0]
        processed = process_pending(
            only_user_id=user,
            extractor=_NoEntities(),
            diary_writer=_StubWriter(),
        )
        assert request_id in processed
        assert conn.execute(
            "select count(*) from public.diaries where user_id = %s and date = %s",
            (user, TODAY),
        ).fetchone()[0] == 1
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_메모가_없는_사용자는_대상이_아니다(conn):
    user = seed_user(conn)
    try:
        assert run_scheduled(conn, [(user, TODAY)]) == (0, 1, 0)
        assert _diary_job_count(conn, user) == 0
        assert conn.execute(
            "select count(*) from public.diary_generation_requests where user_id = %s",
            (user,),
        ).fetchone()[0] == 0
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_이미_일기가_있으면_건너뛴다(conn):
    user = seed_user(conn)
    try:
        seed_memory_at(conn, user, "2026-07-29T02:00:00+00")
        conn.execute(
            "insert into public.diaries (user_id, date) values (%s, %s)",
            (user, TODAY),
        )

        assert run_scheduled(conn, [(user, TODAY)]) == (0, 1, 0)
        assert _diary_job_count(conn, user) == 0
        assert conn.execute(
            "select count(*) from public.diary_generation_requests where user_id = %s",
            (user,),
        ).fetchone()[0] == 0
    finally:
        delete_user(conn, user)

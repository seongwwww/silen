import time
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

import silen_worker.tasks.process as process_task
from silen_worker.queue import delete_message, read_messages
from silen_worker.tasks.process import process_pending
from tests.conftest import StubEmbedder, seed_user, seed_memory, delete_user

_EMB = StubEmbedder()

class _NoEntities:
    def extract(self, text):
        return []


def _queued(conn, memory_id: str) -> bool:
    return (
        conn.execute(
            "select 1 from pgmq.q_memory_jobs "
            "where (message->>'memory_id') = %s",
            (memory_id,),
        ).fetchone()
        is not None
    )


@pytest.mark.integration
def test_메모_생성부터_처리까지_배관이_돈다(conn):
    user = seed_user(conn)
    try:
        # seed_memory의 insert가 트리거로 메시지를 넣는다.
        memory_id = seed_memory(conn, user, "처리될 메모")

        processed = process_pending(
            limit=10,
            embedder=_EMB, extractor=_NoEntities(),
            only_user_id=user,
        )

        assert memory_id in processed
        assert not _queued(conn, memory_id)
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_삭제하지_않은_메시지는_visibility_timeout_후_재전달된다(conn):
    queue = f"test_vt_{uuid.uuid4().hex[:16]}"
    conn.execute("select pgmq.create(%s)", (queue,))
    try:
        conn.execute("select pgmq.send(%s, %s)", (queue, '{"test":true}'))

        # vt=1로 읽고 지우지 않는다.
        first = read_messages(conn, queue, 1, 10)
        assert len(first) == 1
        # 즉시 다시 읽으면 숨겨져 있어 안 보인다.
        assert read_messages(conn, queue, 1, 10) == []
        # vt가 지나면 다시 보인다(at-least-once).
        time.sleep(1.5)
        again = read_messages(conn, queue, 1, 10)
        assert len(again) == 1
        # 정리.
        delete_message(conn, queue, again[0][0])
    finally:
        conn.execute("select pgmq.drop_queue(%s)", (queue,))


@pytest.mark.integration
def test_메모가_삭제됐어도_메시지는_치워진다(conn):
    user = seed_user(conn)
    try:
        memory_id = seed_memory(conn, user, "곧 삭제")
        # 메시지는 이미 큐에 있다. 메모를 지운다(메시지는 남는다).
        conn.execute("delete from public.memories where id = %s", (memory_id,))

        processed = process_pending(
            limit=10,
            embedder=_EMB, extractor=_NoEntities(),
            only_user_id=user,
        )

        # 처리 목록엔 없지만(메모 없음), 이 메모의 메시지는 치워졌다.
        assert memory_id not in processed
        assert not _queued(conn, memory_id)
    finally:
        delete_user(conn, user)


def test_스코프가_없으면_읽은_메시지를_모두_처리한다(monkeypatch):
    class _Connection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    messages = [
        (1, 1, {"memory_id": "memory-a", "user_id": "user-a"}),
        (2, 1, {"memory_id": "memory-b", "user_id": "user-b"}),
    ]
    deleted: list[int] = []

    monkeypatch.setattr(process_task, "connect", _Connection)
    monkeypatch.setattr(
        process_task,
        "read_messages",
        lambda conn, queue, vt, qty: messages,
    )
    monkeypatch.setattr(
        process_task,
        "fetch_memory",
        lambda conn, memory_id, user_id: SimpleNamespace(
            id=memory_id,
            user_id=user_id,
            raw_text=None,
            effective_at=datetime(2026, 7, 29, tzinfo=timezone.utc),
            timezone="Asia/Seoul",
        ),
    )
    monkeypatch.setattr(
        process_task,
        "delete_message",
        lambda conn, queue, msg_id: deleted.append(msg_id),
    )

    processed = process_pending(limit=10, embedder=_EMB, extractor=_NoEntities())

    assert processed == ["memory-a", "memory-b"]
    assert deleted == [1, 2]


def test_재계산_실패가_메모_잡을_되돌리지_않는다(monkeypatch):
    class _Connection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    deleted: list[int] = []
    monkeypatch.setattr(process_task, "connect", _Connection)
    monkeypatch.setattr(
        process_task,
        "read_messages",
        lambda conn, queue, vt, qty: [
            (9, 1, {"memory_id": "memory-a", "user_id": "user-a"})
        ],
    )
    monkeypatch.setattr(
        process_task,
        "fetch_memory",
        lambda conn, memory_id, user_id: SimpleNamespace(
            id=memory_id,
            user_id=user_id,
            raw_text=None,
            effective_at=datetime(2026, 7, 20, tzinfo=timezone.utc),
            timezone="Asia/Seoul",
        ),
    )
    monkeypatch.setattr(
        process_task,
        "recalculate_if_past",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("failed")),
        raising=False,
    )
    monkeypatch.setattr(
        process_task,
        "delete_message",
        lambda conn, queue, msg_id: deleted.append(msg_id),
    )

    processed = process_pending(
        limit=10,
        embedder=_EMB,
        extractor=_NoEntities(),
    )

    assert processed == ["memory-a"]
    assert deleted == [9]


def test_일기_생성_요청을_분기해_완료_처리한다(monkeypatch):
    class _Connection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    messages = [
        (
            7,
            1,
            {
                "job_type": "diary",
                "request_id": "request-a",
                "user_id": "user-a",
                "date": "2026-07-28",
            },
        ),
    ]
    deleted: list[int] = []
    completed: list[tuple[str, str, str]] = []

    monkeypatch.setattr(process_task, "connect", _Connection)
    monkeypatch.setattr(
        process_task,
        "read_messages",
        lambda conn, queue, vt, qty: messages,
    )
    monkeypatch.setattr(
        process_task,
        "claim_diary_generation_request",
        lambda conn, request_id, user_id: True,
        raising=False,
    )
    monkeypatch.setattr(
        process_task,
        "generate_diary",
        lambda conn, user_id, date_iso, writer=None: "diary-a",
        raising=False,
    )
    monkeypatch.setattr(
        process_task,
        "complete_diary_generation_request",
        lambda conn, request_id, user_id, diary_id: completed.append(
            (request_id, user_id, diary_id),
        ),
        raising=False,
    )
    monkeypatch.setattr(
        process_task,
        "delete_message",
        lambda conn, queue, msg_id: deleted.append(msg_id),
    )

    processed = process_pending(limit=10, embedder=_EMB, extractor=_NoEntities())

    assert processed == ["request-a"]
    assert completed == [("request-a", "user-a", "diary-a")]
    assert deleted == [7]


def test_일기_생성_재시도_상한이면_실패로_남기고_보관한다(monkeypatch):
    class _Connection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    messages = [
        (
            8,
            process_task.MAX_READS,
            {
                "job_type": "diary",
                "request_id": "request-b",
                "user_id": "user-b",
                "date": "2026-07-28",
            },
        ),
    ]
    failed: list[tuple[str, str, str, bool]] = []
    archived: list[int] = []

    monkeypatch.setattr(process_task, "connect", _Connection)
    monkeypatch.setattr(
        process_task,
        "read_messages",
        lambda conn, queue, vt, qty: messages,
    )
    monkeypatch.setattr(
        process_task,
        "claim_diary_generation_request",
        lambda conn, request_id, user_id: True,
    )

    def raise_generation_error(conn, user_id, date_iso):
        raise RuntimeError("private detail")

    monkeypatch.setattr(process_task, "generate_diary", raise_generation_error)
    monkeypatch.setattr(
        process_task,
        "fail_diary_generation_request",
        lambda conn, request_id, user_id, code, terminal: failed.append(
            (request_id, user_id, code, terminal),
        ),
    )
    monkeypatch.setattr(
        process_task,
        "archive_message",
        lambda conn, queue, msg_id: archived.append(msg_id),
    )

    processed = process_pending(limit=10, embedder=_EMB, extractor=_NoEntities())

    assert processed == []
    assert failed == [("request-b", "user-b", "RuntimeError", True)]
    assert archived == [8]

"""기존 활성 메모 임베딩 백필. 실제 실행은 사람이 명시적으로 한다."""

import psycopg

from silen_worker.embedding.repository import (
    fetch_embedding_users,
    fetch_missing_memories,
    upsert_memory_embedding,
)
from silen_worker.embedding.service import DOCUMENT_TASK_TYPE, Embedder


def backfill_embeddings(
    conn: psycopg.Connection,
    user_id: str | None = None,
    limit: int = 100,
    embedder: Embedder | None = None,
) -> tuple[int, int]:
    if limit < 1:
        return 0, 0
    if embedder is None:
        from silen_worker.embedding.gemini import GeminiEmbedder

        embedder = GeminiEmbedder()
    users = [user_id] if user_id is not None else fetch_embedding_users(conn)
    created = skipped = 0
    remaining = limit
    for scoped_user_id in users:
        if remaining <= 0:
            break
        memories = fetch_missing_memories(conn, scoped_user_id, remaining)
        for memory in memories:
            vector = embedder.embed(memory.raw_text, DOCUMENT_TASK_TYPE)
            if upsert_memory_embedding(
                conn,
                memory.id,
                memory.user_id,
                vector,
            ):
                created += 1
            else:
                skipped += 1
            remaining -= 1
    return created, skipped

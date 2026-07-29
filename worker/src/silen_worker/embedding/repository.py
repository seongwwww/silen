"""메모 임베딩 DB 접근. 모든 특권 쿼리는 user_id를 직접 강제한다."""

from dataclasses import dataclass

import psycopg

from silen_worker.embedding.service import EMBEDDING_MODEL, vector_literal


@dataclass(frozen=True)
class EmbeddingMemory:
    id: str
    user_id: str
    raw_text: str


def has_current_embedding(
    conn: psycopg.Connection,
    memory_id: str,
    user_id: str,
) -> bool:
    row = conn.execute(
        """
        select 1
          from public.memory_embeddings
         where memory_id = %s
           and user_id = %s
           and model = %s
        """,
        (memory_id, user_id, EMBEDDING_MODEL),
    ).fetchone()
    return row is not None


def upsert_memory_embedding(
    conn: psycopg.Connection,
    memory_id: str,
    user_id: str,
    values: list[float],
) -> bool:
    """외부 호출 뒤 부모 상태를 재검사하고 활성 메모에만 벡터를 저장한다."""
    row = conn.execute(
        """
        insert into public.memory_embeddings (
          memory_id,
          user_id,
          embedding,
          model,
          is_searchable
        )
        select m.id, m.user_id, %s::vector, %s, true
          from public.memories m
         where m.id = %s
           and m.user_id = %s
           and m.deleted_at is null
           and m.is_locked = false
           and m.raw_text is not null
           and btrim(m.raw_text) <> ''
        on conflict (memory_id) do update
          set embedding = excluded.embedding,
              model = excluded.model,
              is_searchable = true,
              created_at = now()
          where public.memory_embeddings.user_id = excluded.user_id
        returning memory_id
        """,
        (vector_literal(values), EMBEDDING_MODEL, memory_id, user_id),
    ).fetchone()
    return row is not None


def fetch_missing_memories(
    conn: psycopg.Connection,
    user_id: str,
    limit: int,
) -> list[EmbeddingMemory]:
    rows = conn.execute(
        """
        select m.id::text, m.user_id::text, m.raw_text
          from public.memories m
          left join public.memory_embeddings me
            on me.memory_id = m.id
           and me.user_id = m.user_id
           and me.model = %s
         where m.user_id = %s
           and m.deleted_at is null
           and m.is_locked = false
           and m.raw_text is not null
           and btrim(m.raw_text) <> ''
           and me.memory_id is null
         order by m.captured_at, m.id
         limit %s
        """,
        (EMBEDDING_MODEL, user_id, limit),
    ).fetchall()
    return [EmbeddingMemory(id=row[0], user_id=row[1], raw_text=row[2]) for row in rows]


def fetch_embedding_users(conn: psycopg.Connection) -> list[str]:
    rows = conn.execute(
        """
        select distinct m.user_id::text
          from public.memories m
          left join public.memory_embeddings me
            on me.memory_id = m.id
           and me.user_id = m.user_id
           and me.model = %s
         where m.deleted_at is null
           and m.is_locked = false
           and m.raw_text is not null
           and btrim(m.raw_text) <> ''
           and me.memory_id is null
         order by m.user_id::text
        """,
        (EMBEDDING_MODEL,),
    ).fetchall()
    return [row[0] for row in rows]


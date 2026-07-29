"""사진 임베딩 저장·검색. user 스코프를 강제하는 지점이다(backend.md).

워커는 RLS를 우회하므로 여기 user_id 필터가 유일한 격리 방어선이다.
"""

import psycopg

from silen_worker.photo.service import PHOTO_EMBEDDING_MODEL, validate_photo_vector


def upsert_photo_embedding(
    conn: psycopg.Connection,
    asset_id: str,
    memory_id: str,
    user_id: str,
    vector: list[float],
) -> bool:
    """자산당 1건. 재시도가 중복 벡터를 만들지 않는다."""
    row = conn.execute(
        """
        insert into public.photo_embeddings
          (asset_id, memory_id, user_id, embedding, model, is_searchable)
        select %s, %s, %s, %s::vector, %s,
               (m.is_locked = false and m.deleted_at is null)
          from public.memories m
         where m.id = %s and m.user_id = %s
        on conflict (asset_id) do update
           set embedding = excluded.embedding,
               model = excluded.model,
               is_searchable = excluded.is_searchable
        returning asset_id
        """,
        (
            asset_id,
            memory_id,
            user_id,
            validate_photo_vector(vector),
            PHOTO_EMBEDDING_MODEL,
            memory_id,
            user_id,
        ),
    ).fetchone()
    return row is not None


def search_photo_candidates(
    conn: psycopg.Connection,
    user_id: str,
    query_vector: list[float],
    limit: int = 8,
) -> list[tuple[str, str, str]]:
    """(memory_id, raw_text, photo_path). user_id를 벡터 계산보다 먼저 적용한다."""
    rows = conn.execute(
        """
        select p.memory_id::text, coalesce(m.raw_text, ''), a.file_url
          from public.photo_embeddings p
          join public.memories m on m.id = p.memory_id
          join public.assets a on a.id = p.asset_id
         where p.user_id = %s
           and p.is_searchable
           and m.is_locked = false
           and m.deleted_at is null
         order by p.embedding <=> %s::vector, p.memory_id
         limit %s
        """,
        (user_id, validate_photo_vector(query_vector), limit),
    ).fetchall()
    return [(row[0], row[1], row[2]) for row in rows]


def sync_photo_searchable(conn: psycopg.Connection, memory_id: str) -> None:
    """부모 메모의 잠금·삭제를 사진 임베딩에도 반영한다."""
    conn.execute(
        """
        update public.photo_embeddings p
           set is_searchable = (m.is_locked = false and m.deleted_at is null)
          from public.memories m
         where m.id = p.memory_id and p.memory_id = %s
        """,
        (memory_id,),
    )

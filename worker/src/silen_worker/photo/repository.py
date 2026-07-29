"""사진 임베딩 저장·검색. user 스코프를 강제하는 지점이다(backend.md).

워커는 RLS를 우회하므로 여기 user_id 필터가 유일한 격리 방어선이다.
"""

import psycopg

from silen_worker.photo.service import (
    PHOTO_EMBEDDING_MODEL,
    PHOTO_MIN_SIMILARITY,
    validate_photo_vector,
)


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
) -> list[tuple[str, str, object, str]]:
    """(memory_id, raw_text, effective_at, photo_path).
    user_id를 벡터 계산보다 먼저 적용한다."""
    rows = conn.execute(
        """
        select p.memory_id::text, coalesce(m.raw_text, ''), m.effective_at, a.file_url
          from public.photo_embeddings p
          join public.memories m on m.id = p.memory_id
          join public.assets a on a.id = p.asset_id
         where p.user_id = %s
           and p.is_searchable
           and m.is_locked = false
           and m.deleted_at is null
           -- <=> 는 코사인 거리다. 유사도 = 1 - 거리.
           and (1 - (p.embedding <=> %s::vector)) >= %s
         order by p.embedding <=> %s::vector, p.memory_id
         limit %s
        """,
        (
            user_id,
            validate_photo_vector(query_vector),
            PHOTO_MIN_SIMILARITY,
            validate_photo_vector(query_vector),
            limit,
        ),
    ).fetchall()
    return [(row[0], row[1], row[2], row[3]) for row in rows]


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


def fetch_user_vocabulary(conn: psycopg.Connection, user_id: str) -> set[str]:
    """사용자가 **텍스트로** 쓴 적 있는 엔티티 이름 집합.

    사진 엔티티의 앵커다. 사진에서만 보이는 말은 여기에 없어 걸러진다.
    """
    rows = conn.execute(
        """
        select distinct e.normalized_name
          from public.entities e
          join public.memory_entities me on me.entity_id = e.id
          join public.memories m on m.id = me.memory_id
         where e.user_id = %s
           and m.deleted_at is null
           and m.raw_text is not null
           and btrim(m.raw_text) <> ''
        """,
        (user_id,),
    ).fetchall()
    return {row[0] for row in rows}


def save_caption(conn: psycopg.Connection, asset_id: str, caption: str) -> None:
    """캡션은 assets.extracted_text에 둔다. memories.raw_text는 사용자 원본이라
    절대 건드리지 않는다(원본 ↔ AI 생성물 분리)."""
    conn.execute(
        "update public.assets set extracted_text = %s where id = %s",
        (caption, asset_id),
    )


def fetch_memory_photos(
    conn: psycopg.Connection, memory_id: str, user_id: str
) -> list[tuple[str, str, str]]:
    """(asset_id, file_url, mime_type). user 스코프를 강제한다."""
    rows = conn.execute(
        """
        select a.id::text, a.file_url, coalesce(a.mime_type, '')
          from public.assets a
          join public.memories m on m.id = a.memory_id
         where a.memory_id = %s
           and m.user_id = %s
           and a.asset_type = 'photo'
         order by a.id
        """,
        (memory_id, user_id),
    ).fetchall()
    return [(row[0], row[1], row[2]) for row in rows]

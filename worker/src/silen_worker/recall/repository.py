"""회고 하이브리드 검색. 특권 쿼리는 user_id와 활성 부모를 모두 강제한다."""

import psycopg

from silen_worker.embedding.service import EMBEDDING_MODEL, vector_literal
from silen_worker.recall.service import RecallCandidate, keyword_terms

_CANDIDATE_LIMIT = 20


def search_vector_candidates(
    conn: psycopg.Connection,
    user_id: str,
    query_vector: list[float],
    limit: int = _CANDIDATE_LIMIT,
) -> list[RecallCandidate]:
    """user_id·활성 상태를 MATERIALIZED CTE로 먼저 좁힌 뒤 거리를 계산한다."""
    rows = conn.execute(
        """
        with scoped as materialized (
          select me.memory_id, me.embedding, m.raw_text, m.effective_at,
                 (
                   select a.file_url
                     from public.assets a
                    where a.memory_id = m.id
                      and a.asset_type = 'photo'
                    order by a.id
                    limit 1
                 ) as photo_path
            from public.memory_embeddings me
            join public.memories m
              on m.id = me.memory_id
             and m.user_id = me.user_id
           where me.user_id = %s
             and me.model = %s
             and me.is_searchable = true
             and m.user_id = %s
             and m.is_locked = false
             and m.deleted_at is null
             and m.raw_text is not null
             and btrim(m.raw_text) <> ''
        )
        select memory_id::text, raw_text, effective_at, photo_path
          from scoped
         order by embedding <=> %s::vector, effective_at desc, memory_id
         limit %s
        """,
        (user_id, EMBEDDING_MODEL, user_id, vector_literal(query_vector), limit),
    ).fetchall()
    return [RecallCandidate(row[0], row[1], row[2], row[3]) for row in rows]


def search_keyword_candidates(
    conn: psycopg.Connection,
    user_id: str,
    question: str,
    limit: int = _CANDIDATE_LIMIT,
) -> list[RecallCandidate]:
    terms = keyword_terms(question)
    if not terms:
        return []
    # LIKE 와일드카드를 이스케이프한다. f-string 안에서 백슬래시를 쓰면
    # 3.12+ 문법이 되어 requires-python(>=3.11)을 깬다.
    escaped = [term.replace("%", r"\%").replace("_", r"\_") for term in terms]
    patterns = [f"%{term}%" for term in escaped]
    rows = conn.execute(
        """
        select m.id::text, m.raw_text, m.effective_at,
               (
                 select a.file_url
                   from public.assets a
                  where a.memory_id = m.id
                    and a.asset_type = 'photo'
                  order by a.id
                  limit 1
               ) as photo_path
          from public.memories m
         where m.user_id = %s
           and m.is_locked = false
           and m.deleted_at is null
           and m.raw_text is not null
           and btrim(m.raw_text) <> ''
           -- ESCAPE 절은 LIKE 특수 구문에만 있다. ANY(배열)은 연산자 형식이라
           -- 붙일 수 없다. 기본 이스케이프 문자가 이미 백슬래시라 필요도 없다.
           and m.raw_text ilike any(%s)
         order by m.effective_at desc, m.id
         limit %s
        """,
        (user_id, patterns, limit),
    ).fetchall()
    return [RecallCandidate(row[0], row[1], row[2], row[3]) for row in rows]

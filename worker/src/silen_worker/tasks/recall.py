"""회고 질문 한 건: 질문 임베딩 → 하이브리드 검색 → 근거 선택."""

from concurrent.futures import ThreadPoolExecutor

import psycopg

from silen_worker.embedding.service import Embedder, QUERY_TASK_TYPE
from silen_worker.recall.repository import (
    search_keyword_candidates,
    search_vector_candidates,
)
from silen_worker.photo.repository import search_photo_candidates
from silen_worker.recall.service import (
    RecallCandidate,
    RecallSelector,
    build_grounded_response,
    empty_recall_response,
    merge_hybrid_candidates,
    with_photo_evidence,
)


def answer_recall(
    conn: psycopg.Connection,
    user_id: str,
    question: str,
    embedder: Embedder | None = None,
    selector: RecallSelector | None = None,
    photo_embedder=None,
) -> dict:
    if embedder is None:
        from silen_worker.embedding.gemini import get_embedder

        embedder = get_embedder()
    # 두 임베딩은 서로 무관한 네트워크 호출이다. 순차로 돌리면 그만큼 사람이
    # 화면 앞에서 더 기다린다.
    with ThreadPoolExecutor(max_workers=2) as pool:
        text_future = pool.submit(embedder.embed, question, QUERY_TASK_TYPE)
        photo_future = pool.submit(_embed_photo_query, question, photo_embedder)
        query_vector = text_future.result()
        photo_vector = photo_future.result()

    vector = search_vector_candidates(conn, user_id, query_vector)
    keyword = search_keyword_candidates(conn, user_id, question)
    candidates = merge_hybrid_candidates(vector, keyword)

    # 사진은 텍스트와 다른 벡터 공간이라 따로 찾는다. 실패해도 글 결과는 살린다.
    photos = _search_photos(conn, user_id, photo_vector)

    if not candidates:
        return with_photo_evidence(empty_recall_response(), photos)
    if selector is None:
        from silen_worker.recall.gemini import get_recall_selector

        selector = get_recall_selector()
    grounded = build_grounded_response(candidates, selector.select(question, candidates))
    return with_photo_evidence(grounded, photos)


def _embed_photo_query(question: str, photo_embedder) -> list[float] | None:
    """사진 검색은 부가 기능이다. 여기서 실패해도 회고 답변 자체는 나와야 한다."""
    try:
        if photo_embedder is None:
            from silen_worker.photo.vertex import get_multimodal_embedder

            photo_embedder = get_multimodal_embedder()
        return photo_embedder.embed_text(question)
    except Exception:
        return None


def _search_photos(
    conn: psycopg.Connection,
    user_id: str,
    photo_vector: list[float] | None,
) -> list[RecallCandidate]:
    if photo_vector is None:
        return []
    try:
        rows = search_photo_candidates(conn, user_id, photo_vector)
    except Exception:
        return []
    return [
        RecallCandidate(
            memory_id=memory_id,
            raw_text=raw_text,
            effective_at=effective_at,
            photo_path=photo_path,
        )
        for memory_id, raw_text, effective_at, photo_path in rows
    ]


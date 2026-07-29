"""회고 질문 한 건: 질문 임베딩 → 하이브리드 검색 → 근거 선택."""

import psycopg

from silen_worker.embedding.service import Embedder, QUERY_TASK_TYPE
from silen_worker.recall.repository import (
    search_keyword_candidates,
    search_vector_candidates,
)
from silen_worker.recall.service import (
    RecallSelector,
    build_grounded_response,
    empty_recall_response,
    merge_hybrid_candidates,
)


def answer_recall(
    conn: psycopg.Connection,
    user_id: str,
    question: str,
    embedder: Embedder | None = None,
    selector: RecallSelector | None = None,
) -> dict:
    if embedder is None:
        from silen_worker.embedding.gemini import GeminiEmbedder

        embedder = GeminiEmbedder()
    query_vector = embedder.embed(question, QUERY_TASK_TYPE)
    vector = search_vector_candidates(conn, user_id, query_vector)
    keyword = search_keyword_candidates(conn, user_id, question)
    candidates = merge_hybrid_candidates(vector, keyword)
    if not candidates:
        return empty_recall_response()
    if selector is None:
        from silen_worker.recall.gemini import GeminiRecallSelector

        selector = GeminiRecallSelector()
    return build_grounded_response(candidates, selector.select(question, candidates))


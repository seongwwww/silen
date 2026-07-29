"""메모 잡 소비 — 엔티티 추출. pgmq에서 읽어 메모 텍스트를 추출하고 저장한다.

일회성. 프로덕션 주기 실행은 범위 밖. 실패 시 삭제하지 않아 visibility
timeout으로 재시도, 상한 초과 시 데드레터.
"""

from silen_worker.db import (
    claim_diary_generation_request,
    complete_diary_generation_request,
    connect,
    fail_diary_generation_request,
    fetch_memory,
    link_memory_entity,
    upsert_entity,
)
from silen_worker.embedding.repository import (
    has_current_embedding,
    upsert_memory_embedding,
)
from silen_worker.embedding.service import DOCUMENT_TASK_TYPE, Embedder
from silen_worker.extraction.service import LLMExtractor, guardrail
from datetime import datetime
import logging

from silen_worker.diary.service import DiaryWriter
from silen_worker.narration.service import Narrator
from silen_worker.recall.service import RecallSelector
from silen_worker.queue import (
    QUEUE,
    archive_message,
    complete_recall_message,
    delete_message,
    fail_recall_message,
    mark_recall_processing,
    read_messages,
    read_messages_for_user,
    reset_recall_for_retry,
)
from silen_worker.tasks.recall import answer_recall
from silen_worker.photo.pipeline import process_memory_photos
from silen_worker.tasks.recalculate import recalculate_if_past
from silen_worker.tasks.write_diary import generate_diary

VISIBILITY_TIMEOUT = 60  # 초. LLM 호출이 있어 A보다 넉넉히.
MAX_READS = 5
logger = logging.getLogger(__name__)


def _default_captioner():
    from silen_worker.photo.gemini import GeminiCaptioner

    return GeminiCaptioner()


def _default_photo_embedder():
    from silen_worker.photo.vertex import MultimodalEmbedder

    return MultimodalEmbedder()


def _default_extractor():
    from silen_worker.extraction.gemini import GeminiExtractor

    return GeminiExtractor()


def _default_read_image():
    """Storage에서 원본을 읽는다. 자격증명이 없으면 사진 처리를 건너뛴다."""
    from silen_worker.deletion.storage import SupabaseStorageDeletion

    return SupabaseStorageDeletion().download


def process_pending(
    limit: int = 10,
    extractor: LLMExtractor | None = None,
    only_user_id: str | None = None,
    diary_writer: DiaryWriter | None = None,
    embedder: Embedder | None = None,
    recall_selector: RecallSelector | None = None,
    photo_captioner=None,
    photo_embedder=None,
    read_image=None,
    narrator: Narrator | None = None,
    now: datetime | None = None,
) -> list[str]:
    """큐에서 최대 limit개 처리하고 처리한 memory_id를 반환한다.
    extractor는 LLMExtractor 포트. 테스트는 스텁, 프로덕션은 Gemini를 주입한다.

    only_user_id를 주면 그 사용자의 메시지만 처리하고 나머지는 삭제·아카이브하지
    않는다. None이면 프로덕션 기본 동작대로 읽은 메시지를 모두 처리한다.
    """
    processed: list[str] = []
    resolved_extractor = extractor
    resolved_embedder = embedder
    with connect() as conn:
        messages = (
            read_messages(conn, QUEUE, VISIBILITY_TIMEOUT, limit)
            if only_user_id is None
            else read_messages_for_user(
                conn,
                QUEUE,
                only_user_id,
                VISIBILITY_TIMEOUT,
                limit,
            )
        )
        for msg_id, read_ct, payload in messages:
            if payload.get("job_type") == "recall_result":
                delete_message(conn, QUEUE, msg_id)
                continue
            if payload.get("job_type") == "recall":
                request_id = payload.get("request_id")
                user_id = payload.get("user_id")
                query = payload.get("query")
                if not all(
                    isinstance(value, str)
                    for value in (request_id, user_id, query)
                ):
                    archive_message(conn, QUEUE, msg_id)
                    continue
                if not mark_recall_processing(
                    conn,
                    msg_id,
                    user_id,
                    request_id,
                ):
                    continue
                try:
                    response = answer_recall(
                        conn,
                        user_id,
                        query,
                        embedder=resolved_embedder,
                        selector=recall_selector,
                    )
                    complete_recall_message(
                        conn,
                        msg_id,
                        user_id,
                        request_id,
                        response,
                    )
                    processed.append(request_id)
                except Exception as exc:
                    if read_ct >= MAX_READS:
                        fail_recall_message(
                            conn,
                            msg_id,
                            user_id,
                            request_id,
                            type(exc).__name__,
                        )
                    else:
                        reset_recall_for_retry(
                            conn,
                            msg_id,
                            user_id,
                            request_id,
                        )
                continue
            if payload.get("job_type") == "diary":
                request_id = payload.get("request_id")
                user_id = payload.get("user_id")
                target_date = payload.get("date")
                if not all(
                    isinstance(value, str)
                    for value in (request_id, user_id, target_date)
                ):
                    archive_message(conn, QUEUE, msg_id)
                    continue
                if not claim_diary_generation_request(conn, request_id, user_id):
                    delete_message(conn, QUEUE, msg_id)
                    continue
                try:
                    diary_id = (
                        generate_diary(conn, user_id, target_date)
                        if diary_writer is None
                        else generate_diary(
                            conn,
                            user_id,
                            target_date,
                            writer=diary_writer,
                        )
                    )
                    if diary_id is None:
                        fail_diary_generation_request(
                            conn,
                            request_id,
                            user_id,
                            "generation_rejected",
                            True,
                        )
                    else:
                        complete_diary_generation_request(
                            conn,
                            request_id,
                            user_id,
                            diary_id,
                        )
                        processed.append(request_id)
                    delete_message(conn, QUEUE, msg_id)
                except Exception as exc:
                    terminal = read_ct >= MAX_READS
                    fail_diary_generation_request(
                        conn,
                        request_id,
                        user_id,
                        type(exc).__name__,
                        terminal,
                    )
                    if terminal:
                        archive_message(conn, QUEUE, msg_id)
                continue
            try:
                memory = fetch_memory(conn, payload["memory_id"], payload["user_id"])
                if memory is None:
                    delete_message(conn, QUEUE, msg_id)
                    continue
                if memory.raw_text:
                    if resolved_extractor is None:
                        from silen_worker.extraction.gemini import GeminiExtractor

                        resolved_extractor = GeminiExtractor()
                    candidates = resolved_extractor.extract(memory.raw_text)
                    for ent in guardrail(candidates, memory.raw_text):
                        entity_id = upsert_entity(
                            conn, memory.user_id, ent.type, ent.name, ent.normalized_name
                        )
                        link_memory_entity(conn, memory.id, entity_id)

                # 사진: 벡터·캡션·앵커 통과 엔티티. 실패해도 잡을 되돌리지
                # 않는다 — 추출은 이미 끝났고 되돌리면 유료 작업이 반복된다.
                search_text = memory.raw_text
                try:
                    search_text = process_memory_photos(
                        conn,
                        memory.id,
                        memory.user_id,
                        memory.raw_text,
                        captioner=photo_captioner or _default_captioner(),
                        embedder=photo_embedder or _default_photo_embedder(),
                        extractor=resolved_extractor or _default_extractor(),
                        read_image=read_image or _default_read_image(),
                    )
                except Exception as exc:
                    logger.warning(
                        "photo processing failed user_id=%s memory_id=%s error=%s",
                        memory.user_id,
                        memory.id,
                        type(exc).__name__,
                    )

                if search_text:
                    if not has_current_embedding(conn, memory.id, memory.user_id):
                        if resolved_embedder is None:
                            from silen_worker.embedding.gemini import GeminiEmbedder

                            resolved_embedder = GeminiEmbedder()
                        vector = resolved_embedder.embed(
                            search_text,
                            DOCUMENT_TASK_TYPE,
                        )
                        if not upsert_memory_embedding(
                            conn,
                            memory.id,
                            memory.user_id,
                            vector,
                        ):
                            delete_message(conn, QUEUE, msg_id)
                            continue
                try:
                    recalculate_if_past(
                        conn,
                        memory,
                        now=now,
                        narrator=narrator,
                    )
                except Exception as exc:
                    # Extraction and embedding already succeeded. Retrying the
                    # queue message would repeat paid work and can loop forever.
                    logger.warning(
                        "late recalculation failed user_id=%s memory_id=%s error=%s",
                        memory.user_id,
                        memory.id,
                        type(exc).__name__,
                    )
                processed.append(memory.id)
                delete_message(conn, QUEUE, msg_id)
            except Exception:
                if read_ct >= MAX_READS:
                    archive_message(conn, QUEUE, msg_id)
    return processed

"""메모 잡 소비 — 엔티티 추출. pgmq에서 읽어 메모 텍스트를 추출하고 저장한다.

일회성. 프로덕션 주기 실행은 범위 밖. 실패 시 삭제하지 않아 visibility
timeout으로 재시도, 상한 초과 시 데드레터.
"""

from silen_worker.db import connect, fetch_memory, upsert_entity, link_memory_entity
from silen_worker.extraction.service import LLMExtractor, guardrail
from silen_worker.queue import QUEUE, archive_message, delete_message, read_messages

VISIBILITY_TIMEOUT = 60  # 초. LLM 호출이 있어 A보다 넉넉히.
MAX_READS = 5


def process_pending(limit: int = 10, extractor: LLMExtractor | None = None) -> list[str]:
    """큐에서 최대 limit개 처리하고 처리한 memory_id를 반환한다.
    extractor는 LLMExtractor 포트. 테스트는 스텁, 프로덕션은 Gemini를 주입한다."""
    if extractor is None:
        from silen_worker.extraction.gemini import GeminiExtractor

        extractor = GeminiExtractor()

    processed: list[str] = []
    with connect() as conn:
        for msg_id, read_ct, payload in read_messages(conn, QUEUE, VISIBILITY_TIMEOUT, limit):
            try:
                memory = fetch_memory(conn, payload["memory_id"], payload["user_id"])
                if memory is None:
                    delete_message(conn, QUEUE, msg_id)
                    continue
                if memory.raw_text:
                    candidates = extractor.extract(memory.raw_text)
                    for ent in guardrail(candidates, memory.raw_text):
                        entity_id = upsert_entity(
                            conn, memory.user_id, ent.type, ent.name, ent.normalized_name
                        )
                        link_memory_entity(conn, memory.id, entity_id)
                processed.append(memory.id)
                delete_message(conn, QUEUE, msg_id)
            except Exception:
                if read_ct >= MAX_READS:
                    archive_message(conn, QUEUE, msg_id)
    return processed

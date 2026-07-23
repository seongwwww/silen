"""메모 잡 소비. pgmq에서 읽어 메모를 스코프 조회하고 메시지를 지운다.

일회성 — 프로덕션에서 어떻게 주기 실행할지(데몬·cron)는 범위 밖.
이번 슬라이스의 잡은 사소하다(조회 후 삭제). 엔티티 추출은 후속 스펙에서
이 자리를 채운다.
"""

from silen_worker.db import connect, fetch_memory
from silen_worker.queue import QUEUE, archive_message, delete_message, read_messages

VISIBILITY_TIMEOUT = 30  # 초. 처리 중 워커가 죽으면 이만큼 뒤 재전달된다.
MAX_READS = 5  # 이 횟수를 넘게 재전달되면 데드레터로 보낸다.


def process_pending(limit: int = 10) -> list[str]:
    """큐에서 최대 limit개 처리하고 처리한 memory_id를 반환한다."""
    processed: list[str] = []
    with connect() as conn:
        for msg_id, read_ct, payload in read_messages(conn, QUEUE, VISIBILITY_TIMEOUT, limit):
            try:
                memory = fetch_memory(conn, payload["memory_id"], payload["user_id"])
                if memory is not None:
                    processed.append(memory.id)
                # 메모가 없어도(삭제·잠금) 메시지는 지운다 — 재시도 의미 없음.
                delete_message(conn, QUEUE, msg_id)
            except Exception:
                # 삭제하지 않으면 visibility timeout 후 재전달된다.
                # 상한을 넘으면 데드레터로 보내 무한 재시도를 막는다.
                if read_ct >= MAX_READS:
                    archive_message(conn, QUEUE, msg_id)
    return processed

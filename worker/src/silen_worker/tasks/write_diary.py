"""일기 생성 경계. 그날 메모+확정 차이를 읽어 일기를 쓰고 가드레일을 통과하면 저장한다.
하루 1건 멱등·자동 재생성 금지(force는 draft만). diary_time 스케줄 배선은 범위 밖.
"""

from datetime import date

import psycopg

from silen_worker.db import (
    fetch_confirmed_differences, fetch_diary_memories, fetch_existing_diary,
    replace_diary_sections, replace_diary_sources, upsert_diary,
)
from silen_worker.diary.service import (
    DiaryDifference, DiaryInput, DiaryMemory, DiaryWriter, guardrail,
)
from silen_worker.time import local_date_for


def generate_diary(
    conn: psycopg.Connection,
    user_id: str,
    target_date_iso: str,
    force: bool = False,
    writer: DiaryWriter | None = None,
) -> str | None:
    """일기 diary_id, 또는 None(빈 날/가드레일 탈락). 기존 diary가 있으면
    force=False거나 유저가 손댄 것(status≠draft)이면 그대로 두고 diary_id 반환."""
    if writer is None:
        from silen_worker.diary.gemini import GeminiDiaryWriter

        writer = GeminiDiaryWriter()

    target = date.fromisoformat(target_date_iso)

    existing = fetch_existing_diary(conn, user_id, target)
    if existing is not None:
        diary_id, status = existing
        if not force or status != "draft":
            return diary_id  # 멱등·유저 편집 보호

    mem_rows = fetch_diary_memories(conn, user_id, target)
    memories = [
        DiaryMemory(r.memory_id, r.raw_text)
        for r in mem_rows
        if local_date_for(r.captured_at, r.timezone) == target_date_iso
    ]
    if not memories:
        return None  # 빈 날 — 억지 생성 안 함

    confirmed = fetch_confirmed_differences(conn, user_id, target)
    # 본문엔 '이야기가 되는' 반복만 녹인다. '처음 등장'은 나열이 자연스러워
    # recap 목록이 담당한다(본문에 넣으면 "~한 것도 처음이다"가 반복된다).
    body_diffs = [c for c in confirmed if c.detection_method == "freq_shift"]

    facts = DiaryInput(
        date_iso=target_date_iso,
        user_id=user_id,
        memories=memories,
        differences=[
            DiaryDifference(c.difference_id, c.headline, c.entity_name)
            for c in body_diffs
        ],
    )

    raw = writer.write(facts)
    diary = guardrail(raw, facts)
    if diary is None:
        return None

    diary_id = upsert_diary(conn, user_id, target, diary.body)
    if diary_id is None:
        # 경쟁 조건: status 확인 후 upsert 전에 유저가 편집 → 보호(덮지 않음).
        # 섹션·출처도 건드리지 않고 기존 일기 id를 그대로 반환한다.
        return existing[0] if existing is not None else None
    # recap 목록은 그날 확정된 차이 전부다(본문에 녹은 것만이 아니라).
    recap = [(c.difference_id, c.headline) for c in confirmed]
    replace_diary_sections(conn, diary_id, diary.one_line, diary.body, recap)
    replace_diary_sources(conn, diary_id, diary.used_memory_ids)
    return diary_id

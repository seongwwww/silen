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

    diffs = fetch_confirmed_differences(conn, user_id, target)
    facts = DiaryInput(
        date_iso=target_date_iso,
        user_id=user_id,
        memories=memories,
        differences=[DiaryDifference(d, h) for d, h in diffs],
    )

    raw = writer.write(facts)
    diary = guardrail(raw, facts)
    if diary is None:
        return None

    diary_id = upsert_diary(conn, user_id, target, diary.body)
    headline_by_id = {d.difference_id: d.headline for d in facts.differences}
    used_diff_pairs = [(did, headline_by_id.get(did, "")) for did in diary.used_difference_ids]
    replace_diary_sections(conn, diary_id, diary.one_line, diary.body, used_diff_pairs)
    replace_diary_sources(conn, diary_id, diary.used_memory_ids)
    return diary_id

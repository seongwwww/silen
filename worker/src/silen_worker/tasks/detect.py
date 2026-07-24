"""엔티티 통계 차이 검출 경계. 재료를 읽어 사용자 로컬 날짜로 버킷팅하고,
순수 규칙을 적용해 differences를 멱등 저장한다. 스케줄 트리거는 범위 밖 —
호출 가능한 함수. 탐지=통계, LLM 없음.
"""

from datetime import date

import psycopg

from silen_worker.db import (
    fetch_earliest_occurrence,
    fetch_window_occurrences,
    link_difference_evidence,
    upsert_difference,
)
from silen_worker.detection.constants import WINDOW_DAYS
from silen_worker.detection.service import EntityWindow, detect_differences
from silen_worker.time import local_date_for


def detect_day(conn: psycopg.Connection, user_id: str, target_date_iso: str) -> list[str]:
    target = date.fromisoformat(target_date_iso)
    window_start = target.toordinal() - (WINDOW_DAYS - 1)

    rows = fetch_window_occurrences(conn, user_id, target, WINDOW_DAYS)

    # 로컬 날짜로 버킷팅(하루 경계 단일 출처: time.local_date_for).
    by_entity: dict[str, dict] = {}
    for r in rows:
        local = date.fromisoformat(local_date_for(r.captured_at, r.timezone))
        if local.toordinal() < window_start or local > target:
            continue  # 창 밖 정밀 제외
        b = by_entity.setdefault(
            r.entity_id, {"type": r.entity_type, "dates": set(), "today": []}
        )
        b["dates"].add(local)
        if local == target:
            b["today"].append(r.memory_id)

    today_entities = {eid: b for eid, b in by_entity.items() if target in b["dates"]}
    if not today_entities:
        return []

    earliest = fetch_earliest_occurrence(conn, user_id, list(today_entities))
    windows = []
    for eid, b in today_entities.items():
        occurred_before = False
        er = earliest.get(eid)
        if er is not None:
            occurred_before = date.fromisoformat(local_date_for(er[0], er[1])) < target
        windows.append(EntityWindow(eid, b["type"], frozenset(b["dates"]), occurred_before))

    written: list[str] = []
    for diff in detect_differences(target, windows):
        did = upsert_difference(
            conn, user_id, target, diff.entity_id, diff.method,
            diff.entity_type, diff.description, diff.confidence,
        )
        for mid in today_entities[diff.entity_id]["today"]:
            link_difference_evidence(conn, did, mid)
        written.append(did)
    return written

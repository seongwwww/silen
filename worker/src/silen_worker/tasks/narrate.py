"""차이 서술 경계. 차이 하나를 읽어 서술하고 가드레일을 통과하면 저장한다.
스케줄/lazy 트리거 배선은 범위 밖 — 호출 가능한 함수. 탐지=통계, 서술=번역.
"""

import psycopg

from silen_worker.db import fetch_difference_for_narration, upsert_narration
from silen_worker.narration.service import Narrator, NarrationInput, guardrail


def narrate_difference(
    conn: psycopg.Connection, difference_id: str, narrator: Narrator | None = None
) -> str | None:
    """서술 성공 시 narration id, 대상 없음/가드레일 탈락 시 None."""
    if narrator is None:
        from silen_worker.narration.gemini import GeminiNarrator

        narrator = GeminiNarrator()

    facts_row = fetch_difference_for_narration(conn, difference_id)
    if facts_row is None:
        return None

    facts = NarrationInput(
        difference_id=facts_row.difference_id,
        user_id=facts_row.user_id,
        entity_name=facts_row.entity_name,
        entity_type=facts_row.entity_type,
        detection_method=facts_row.detection_method,
        description=facts_row.description,
        date_iso=facts_row.date_iso,
    )
    raw = narrator.narrate(facts)
    narration = guardrail(raw, facts)
    if narration is None:
        return None
    return upsert_narration(
        conn,
        facts.user_id,
        facts.difference_id,
        narration.headline,
        narration.body,
        narration.evidence_text,
        narrator.model,
    )

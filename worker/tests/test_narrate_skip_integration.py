from datetime import date

import pytest

from silen_worker.tasks.narrate import narrate_difference
from tests.conftest import seed_user, seed_memory, delete_user


class CountingNarrator:
    """LLM 호출 횟수를 센다. 재실행 과금 방지의 증거."""

    model = "stub"

    def __init__(self):
        self.calls = 0

    def narrate(self, facts):
        self.calls += 1
        return {
            "headline": f"{facts.entity_name} 반복",
            "body": f"{facts.entity_name}을 최근 3일 연속으로 남기셨네요.",
            "evidence_text": "요즘 자주 등장해서 찾았어요.",
        }


def _candidate_difference(conn, user_id):
    ent = conn.execute(
        "insert into public.entities (user_id, entity_type, name, normalized_name) "
        "values (%s, 'thing', '김밥', '김밥') returning id::text",
        (user_id,),
    ).fetchone()[0]
    return conn.execute(
        """
        insert into public.differences
          (user_id, date, entity_id, dimension, description, detection_method,
           confidence, category, status, evidence_state)
        values (%s, %s, %s, 'thing', '최근 3일 연속 등장', 'freq_shift',
                0.5, '오늘의다른점', 'candidate', 'intact')
        returning id::text
        """,
        (user_id, date.today(), ent),
    ).fetchone()[0]


@pytest.mark.integration
def test_이미_서술된_차이는_LLM을_다시_부르지_않는다(conn):
    user = seed_user(conn)
    try:
        seed_memory(conn, user, "김밥 먹음")
        diff = _candidate_difference(conn, user)
        narrator = CountingNarrator()

        first = narrate_difference(conn, diff, narrator=narrator)
        second = narrate_difference(conn, diff, narrator=narrator)

        assert first is not None
        assert second == first
        assert narrator.calls == 1
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_skip_if_exists_False면_다시_서술한다(conn):
    user = seed_user(conn)
    try:
        seed_memory(conn, user, "김밥 먹음")
        diff = _candidate_difference(conn, user)
        narrator = CountingNarrator()

        narrate_difference(conn, diff, narrator=narrator)
        narrate_difference(conn, diff, narrator=narrator, skip_if_exists=False)

        assert narrator.calls == 2
    finally:
        delete_user(conn, user)

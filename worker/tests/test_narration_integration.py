import pytest

from silen_worker.tasks.narrate import narrate_difference
from tests.conftest import seed_user, seed_memory, delete_user


class StubNarrator:
    """고정 출력을 내는 스텁. 실 Gemini 없이 파이프라인을 검증한다."""

    model = "stub"

    def __init__(self, raw):
        self._raw = raw

    def narrate(self, facts):
        return self._raw


def _seed_difference(conn, user_id, name="김밥"):
    ent = conn.execute(
        "insert into public.entities (user_id, entity_type, name, normalized_name) "
        "values (%s, 'thing', %s, %s) returning id::text",
        (user_id, name, name),
    ).fetchone()[0]
    diff = conn.execute(
        """
        insert into public.differences
          (user_id, date, entity_id, dimension, description,
           detection_method, confidence, category, status, evidence_state)
        values (%s, current_date, %s, 'thing', '최근 3일 연속 등장',
                'freq_shift', 0.5, '오늘의다른점', 'candidate', 'intact')
        returning id::text
        """,
        (user_id, ent),
    ).fetchone()[0]
    return diff


_GOOD = {
    "headline": "3일째 김밥",
    "body": "김밥을 최근 3일 연속으로 남기셨네요.",
    "evidence_text": "요즘 자주 등장해서 찾았어요.",
}


def _narration_row(conn, diff):
    return conn.execute(
        "select user_id::text, headline from public.difference_narrations "
        "where difference_id = %s",
        (diff,),
    ).fetchone()


@pytest.mark.integration
def test_서술이_저장되고_소유자에_귀속된다(conn):
    user = seed_user(conn)
    try:
        seed_memory(conn, user, "김밥 먹음")
        diff = _seed_difference(conn, user)
        nid = narrate_difference(conn, diff, narrator=StubNarrator(_GOOD))
        assert nid is not None
        row = _narration_row(conn, diff)
        assert row[0] == user           # user 스코프 귀속
        assert row[1] == "3일째 김밥"
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_재서술은_중복을_만들지_않는다(conn):
    user = seed_user(conn)
    try:
        seed_memory(conn, user, "김밥 먹음")
        diff = _seed_difference(conn, user)
        narrate_difference(conn, diff, narrator=StubNarrator(_GOOD))
        narrate_difference(conn, diff, narrator=StubNarrator(_GOOD))
        count = conn.execute(
            "select count(*)::int from public.difference_narrations where difference_id = %s",
            (diff,),
        ).fetchone()[0]
        assert count == 1
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_가드레일_탈락은_저장되지_않는다(conn):
    user = seed_user(conn)
    try:
        seed_memory(conn, user, "김밥 먹음")
        diff = _seed_difference(conn, user)
        bad = {"headline": "오늘의 반복", "body": "내일은 다른 걸 해보세요.",
               "evidence_text": "자주 나와서요."}  # 엔티티명 없음 + 조언
        nid = narrate_difference(conn, diff, narrator=StubNarrator(bad))
        assert nid is None
        assert _narration_row(conn, diff) is None
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_없는_difference는_None(conn):
    import uuid

    user = seed_user(conn)
    try:
        nid = narrate_difference(conn, str(uuid.uuid4()), narrator=StubNarrator(_GOOD))
        assert nid is None
    finally:
        delete_user(conn, user)

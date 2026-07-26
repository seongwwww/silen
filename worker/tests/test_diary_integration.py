import pytest

from silen_worker.db import fetch_existing_diary
from silen_worker.tasks.write_diary import generate_diary
from tests.conftest import seed_user, seed_memory, delete_user
from datetime import date


class StubWriter:
    model = "stub"

    def __init__(self, raw):
        self._raw = raw

    def write(self, facts):
        # 입력 메모 id를 근거로 그대로 반영(근거 정합 통과)
        r = dict(self._raw)
        r.setdefault("used_memory_ids", [m.memory_id for m in facts.memories])
        r.setdefault("used_difference_ids", [d.difference_id for d in facts.differences])
        return r


_GOOD = {"one_line": "비슷한 하루.", "body": "특별할 것 없는 하루였다. 점심은 김밥."}


def _today_iso():
    return date.today().isoformat()


@pytest.mark.integration
def test_일기가_저장된다(conn):
    user = seed_user(conn)
    try:
        seed_memory(conn, user, "점심 김밥")
        did = generate_diary(conn, user, _today_iso(), writer=StubWriter(_GOOD))
        assert did is not None
        row = conn.execute(
            "select generated_text, status from public.diaries where id = %s", (did,)
        ).fetchone()
        assert row[0] == _GOOD["body"]
        assert row[1] == "draft"
        sec = conn.execute(
            "select count(*)::int from public.diary_sections where diary_id = %s", (did,)
        ).fetchone()[0]
        assert sec == 2  # 오늘의한문장 + 본문
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_하루_1건_멱등_재호출은_noop(conn):
    user = seed_user(conn)
    try:
        seed_memory(conn, user, "점심 김밥")
        d1 = generate_diary(conn, user, _today_iso(), writer=StubWriter(_GOOD))
        d2 = generate_diary(conn, user, _today_iso(),
                            writer=StubWriter({"one_line": "다른 문장.", "body": "다른 본문."}))
        assert d1 == d2
        gen = conn.execute("select generated_text from public.diaries where id = %s", (d1,)).fetchone()[0]
        assert gen == _GOOD["body"]  # 덮어쓰지 않음(자동 재생성 금지)
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_force는_draft를_재생성한다(conn):
    user = seed_user(conn)
    try:
        seed_memory(conn, user, "점심 김밥")
        d1 = generate_diary(conn, user, _today_iso(), writer=StubWriter(_GOOD))
        d2 = generate_diary(conn, user, _today_iso(), force=True,
                            writer=StubWriter({"one_line": "새 문장.", "body": "새 본문 내용."}))
        assert d1 == d2
        gen = conn.execute("select generated_text from public.diaries where id = %s", (d1,)).fetchone()[0]
        assert gen == "새 본문 내용."
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_유저편집_일기는_force여도_보존(conn):
    user = seed_user(conn)
    try:
        seed_memory(conn, user, "점심 김밥")
        d1 = generate_diary(conn, user, _today_iso(), writer=StubWriter(_GOOD))
        conn.execute("update public.diaries set status='edited', edited_text='내 손으로 고침' where id = %s", (d1,))
        d2 = generate_diary(conn, user, _today_iso(), force=True,
                            writer=StubWriter({"one_line": "새 문장.", "body": "새 본문."}))
        assert d2 == d1
        row = conn.execute("select status, edited_text from public.diaries where id = %s", (d1,)).fetchone()
        assert row[0] == "edited" and row[1] == "내 손으로 고침"  # 보존
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_빈_날은_일기를_안만든다(conn):
    user = seed_user(conn)
    try:
        did = generate_diary(conn, user, _today_iso(), writer=StubWriter(_GOOD))
        assert did is None
        assert fetch_existing_diary(conn, user, date.today()) is None
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_가드레일_탈락은_저장안됨(conn):
    user = seed_user(conn)
    try:
        seed_memory(conn, user, "점심 김밥")
        # 근거(used_memory_ids)는 스텁이 입력 메모로 채우고 본문만 조언 →
        # 빈-근거가 아니라 블록리스트가 실제 탈락 사유가 되도록 한다.
        bad = {"one_line": "x", "body": "내일은 다른 걸 해보세요."}  # 조언
        did = generate_diary(conn, user, _today_iso(), writer=StubWriter(bad))
        assert did is None
        assert fetch_existing_diary(conn, user, date.today()) is None
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_일기_삭제시_섹션출처_연쇄삭제(conn):
    user = seed_user(conn)
    try:
        seed_memory(conn, user, "점심 김밥")
        did = generate_diary(conn, user, _today_iso(), writer=StubWriter(_GOOD))
        conn.execute("delete from public.diaries where id = %s", (did,))
        sec = conn.execute("select count(*)::int from public.diary_sections where diary_id = %s", (did,)).fetchone()[0]
        src = conn.execute("select count(*)::int from public.diary_sources where diary_id = %s", (did,)).fetchone()[0]
        assert sec == 0 and src == 0
    finally:
        delete_user(conn, user)

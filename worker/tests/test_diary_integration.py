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


class RecordingWriter(StubWriter):
    def __init__(self, raw):
        super().__init__(raw)
        self.facts = None

    def write(self, facts):
        self.facts = facts
        return super().write(facts)


_GOOD = {"one_line": "비슷한 하루.", "body": "특별할 것 없는 하루였다. 점심은 김밥."}


def _today_iso():
    return date.today().isoformat()


def _seed_difference(
    conn,
    user,
    *,
    status="candidate",
    evidence_state="intact",
    method="freq_shift",
    name="김밥",
    entity_type="thing",
):
    ent = conn.execute(
        "insert into public.entities (user_id, entity_type, name, normalized_name) "
        "values (%s, %s, %s, %s) returning id::text",
        (user, entity_type, name, name),
    ).fetchone()[0]
    return conn.execute(
        """
        insert into public.differences
          (user_id, date, entity_id, dimension, description, detection_method,
           confidence, category, status, evidence_state)
        values (%s, %s, %s, %s, '최근 기록에서 자주 언급됨', %s,
                3.0, '오늘의다른점', %s, %s)
        returning id::text
        """,
        (
            user,
            date.today(),
            ent,
            entity_type,
            method,
            status,
            evidence_state,
        ),
    ).fetchone()[0]


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
def test_재생성요청은_확정일기도_다시쓰고_요청을_비운다(conn):
    user = seed_user(conn)
    try:
        seed_memory(conn, user, "점심 김밥")
        did = generate_diary(conn, user, _today_iso(), writer=StubWriter(_GOOD))
        conn.execute(
            "update public.diaries set status='confirmed', edited_text='내 손으로 고침', "
            "tone_instruction='더 짧게', regenerate_requested_at=now(), "
            "regenerate_reason='user' where id = %s",
            (did,),
        )
        writer = RecordingWriter(
            {"one_line": "새 문장.", "body": "새 본문 내용. 점심은 김밥."}
        )

        regenerated = generate_diary(conn, user, _today_iso(), writer=writer)

        assert regenerated == did
        assert writer.facts is not None
        assert writer.facts.tone_instruction == "더 짧게"
        row = conn.execute(
            "select generated_text, edited_text, status, tone_instruction, "
            "regenerate_requested_at, regenerate_reason "
            "from public.diaries where id = %s",
            (did,),
        ).fetchone()
        assert row == (
            "새 본문 내용. 점심은 김밥.",
            None,
            "draft",
            None,
            None,
            None,
        )
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_사용자_톤프리셋을_writer에_전달한다(conn):
    user = seed_user(conn)
    try:
        seed_memory(conn, user, "점심 김밥")
        conn.execute(
            "update public.users set style_profile = '{\"preset\":\"따뜻\"}'::jsonb "
            "where id = %s",
            (user,),
        )
        writer = RecordingWriter(_GOOD)

        did = generate_diary(conn, user, _today_iso(), writer=writer)

        assert did is not None
        assert writer.facts is not None
        assert writer.facts.tone_preset == "따뜻"
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
def test_candidate_차이도_일기_본문과_recap에_반영된다(conn):
    user = seed_user(conn)
    try:
        seed_memory(conn, user, "점심 김밥")
        difference_id = _seed_difference(conn, user, status="candidate")
        writer = RecordingWriter(
            {
                "one_line": "비슷한 하루.",
                "body": "오늘 기록에는 김밥 언급이 평소보다 자주 있었다.",
            }
        )

        diary_id = generate_diary(conn, user, _today_iso(), writer=writer)

        assert diary_id is not None
        assert writer.facts is not None
        assert [item.difference_id for item in writer.facts.differences] == [
            difference_id
        ]
        recap = conn.execute(
            "select difference_id::text from public.diary_sections "
            "where diary_id = %s and section_type = '다른점'",
            (diary_id,),
        ).fetchall()
        assert recap == [(difference_id,)]
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_dismissed_차이는_일기_본문과_recap에서_제외된다(conn):
    user = seed_user(conn)
    try:
        seed_memory(conn, user, "점심 김밥")
        _seed_difference(conn, user, status="dismissed")
        writer = RecordingWriter(_GOOD)

        diary_id = generate_diary(conn, user, _today_iso(), writer=writer)

        assert diary_id is not None
        assert writer.facts is not None
        assert writer.facts.differences == []
        recap_count = conn.execute(
            "select count(*)::int from public.diary_sections "
            "where diary_id = %s and section_type = '다른점'",
            (diary_id,),
        ).fetchone()[0]
        assert recap_count == 0
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_candidate_차이를_생활_사실로_승격하면_일기를_저장하지_않는다(conn):
    user = seed_user(conn)
    try:
        seed_memory(conn, user, "점심 김밥")
        _seed_difference(conn, user, status="candidate")
        writer = StubWriter(
            {
                "one_line": "김밥을 자주 먹은 날.",
                "body": "오늘은 김밥을 평소보다 자주 먹었다.",
            }
        )

        assert generate_diary(conn, user, _today_iso(), writer=writer) is None
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


@pytest.mark.integration
def test_처음등장은_본문재료가_아니고_recap에만_남는다(conn):
    user = seed_user(conn)
    try:
        seed_memory(conn, user, "점심 김밥")
        # first_occurrence candidate도 opt-out 일기의 recap 재료다.
        ent = conn.execute(
            "insert into public.entities (user_id, entity_type, name, normalized_name) "
            "values (%s, 'thing', '김밥', '김밥') returning id::text", (user,)
        ).fetchone()[0]
        conn.execute(
            "insert into public.differences (user_id, date, entity_id, dimension, description, "
            "detection_method, confidence, category, status, evidence_state) "
            "values (%s, %s, %s, 'thing', '처음 등장', 'first_occurrence', 1.0, "
            "'오늘의다른점', 'candidate', 'intact')",
            (user, date.today(), ent),
        )

        seen = {}

        class RecordingWriter:
            model = "stub"

            def write(self, facts):
                seen["diffs"] = [d.difference_id for d in facts.differences]
                return {
                    "one_line": "비슷한 하루.",
                    "body": "특별할 것 없는 하루였다. 점심은 김밥.",
                    "used_memory_ids": [m.memory_id for m in facts.memories],
                    "used_difference_ids": [],
                }

        did = generate_diary(conn, user, _today_iso(), writer=RecordingWriter())
        assert did is not None
        assert seen["diffs"] == []  # 본문 재료에서 제외됐다

        recap = conn.execute(
            "select count(*)::int from public.diary_sections "
            "where diary_id = %s and section_type = '다른점'", (did,),
        ).fetchone()[0]
        assert recap == 1  # recap 목록엔 남는다
    finally:
        delete_user(conn, user)


class StubAsker:
    def __init__(self, question):
        self._question = question

    def ask(self, target):
        return {"question": self._question}


@pytest.mark.integration
def test_처음_등장한_사람이_있으면_질문이_생긴다(conn):
    user = seed_user(conn)
    try:
        seed_memory(conn, user, "지은이 만남")
        ent = conn.execute(
            "insert into public.entities (user_id, entity_type, name, normalized_name) "
            "values (%s, 'person', '지은', '지은') returning id::text", (user,)
        ).fetchone()[0]
        conn.execute(
            "insert into public.differences (user_id, date, entity_id, dimension, description, "
            "detection_method, confidence, category, status, evidence_state) "
            "values (%s, %s, %s, 'person', '처음 등장', 'first_occurrence', 1.0, "
            "'오늘의다른점', 'candidate', 'intact')",
            (user, date.today(), ent),
        )
        did = generate_diary(
            conn, user, _today_iso(), writer=StubWriter(_GOOD),
            asker=StubAsker("지은은 어떤 사람이었어요?"),
        )
        row = conn.execute(
            "select content from public.diary_sections "
            "where diary_id = %s and section_type = '질문'", (did,),
        ).fetchone()
        assert row is not None
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_대상이_없으면_질문이_생기지_않는다(conn):
    user = seed_user(conn)
    try:
        seed_memory(conn, user, "점심 김밥")
        did = generate_diary(
            conn, user, _today_iso(), writer=StubWriter(_GOOD),
            asker=StubAsker("아무 질문"),
        )
        count = conn.execute(
            "select count(*)::int from public.diary_sections "
            "where diary_id = %s and section_type = '질문'", (did,),
        ).fetchone()[0]
        assert count == 0
    finally:
        delete_user(conn, user)

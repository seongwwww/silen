import pytest

from silen_worker.tasks.detect import detect_day
from tests.conftest import seed_user, seed_memory_at, delete_user


def _entity(conn, user_id, name, etype="thing"):
    return conn.execute(
        "insert into public.entities (user_id, entity_type, name, normalized_name) "
        "values (%s, %s, %s, %s) returning id::text",
        (user_id, etype, name, name),
    ).fetchone()[0]


def _mention(conn, user_id, entity_id, captured_at_iso):
    mem = seed_memory_at(conn, user_id, captured_at_iso)
    conn.execute(
        "insert into public.memory_entities (memory_id, entity_id, relation_type) "
        "values (%s, %s, 'mentioned')",
        (mem, entity_id),
    )
    return mem


def _diffs(conn, user_id):
    return conn.execute(
        "select detection_method, description from public.differences "
        "where user_id = %s order by detection_method, description",
        (user_id,),
    ).fetchall()


@pytest.mark.integration
def test_첫_등장이_first_occurrence로_기록되고_근거가_연결된다(conn):
    user = seed_user(conn)
    try:
        ent = _entity(conn, user, "낯선카페", "place")
        mem = _mention(conn, user, ent, "2026-07-23T02:00:00+00")

        written = detect_day(conn, user, "2026-07-23")

        assert len(written) == 1
        rows = _diffs(conn, user)
        assert rows == [("first_occurrence", "이 place 첫 등장")]
        ev = conn.execute(
            "select memory_id::text from public.difference_evidence where difference_id = %s",
            (written[0],),
        ).fetchall()
        assert [e[0] for e in ev] == [mem]
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_이틀_연속이면_freq_shift_streak(conn):
    user = seed_user(conn)
    try:
        ent = _entity(conn, user, "김밥")
        _mention(conn, user, ent, "2026-07-22T02:00:00+00")
        _mention(conn, user, ent, "2026-07-23T02:00:00+00")
        detect_day(conn, user, "2026-07-23")
        assert _diffs(conn, user) == [("freq_shift", "최근 2일 연속 등장")]
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_재실행은_중복을_만들지_않는다(conn):
    user = seed_user(conn)
    try:
        ent = _entity(conn, user, "요가", "activity")
        _mention(conn, user, ent, "2026-07-23T02:00:00+00")
        detect_day(conn, user, "2026-07-23")
        detect_day(conn, user, "2026-07-23")
        n = conn.execute(
            "select count(*)::int from public.differences where user_id = %s", (user,)
        ).fetchone()[0]
        assert n == 1
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_빈_날은_0건_억지생성_안함(conn):
    user = seed_user(conn)
    try:
        # 오늘 언급 없음(어제만).
        ent = _entity(conn, user, "산책", "activity")
        _mention(conn, user, ent, "2026-07-22T02:00:00+00")
        written = detect_day(conn, user, "2026-07-23")
        assert written == []
        assert _diffs(conn, user) == []
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_타임존_경계_전날_늦은_메모는_오늘에_새지_않는다(conn):
    user = seed_user(conn)
    try:
        conn.execute("update public.users set timezone = 'Asia/Seoul' where id = %s", (user,))
        ent = _entity(conn, user, "김밥")
        # 07-22T14:30Z = 07-22 23:30 KST → 로컬 07-22 (오늘 아님)
        _mention(conn, user, ent, "2026-07-22T14:30:00+00")
        # 07-22T15:30Z = 07-23 00:30 KST → 로컬 07-23 (오늘)
        m_today = _mention(conn, user, ent, "2026-07-22T15:30:00+00")

        detect_day(conn, user, "2026-07-23")

        # 오늘 로컬에 처음(전체 이력에 07-22 KST 존재하므로 occurred_before=True),
        # 07-22 KST와 07-23 KST는 연속 → streak 2일.
        assert _diffs(conn, user) == [("freq_shift", "최근 2일 연속 등장")]
        ev = conn.execute(
            "select memory_id::text from public.difference_evidence", ()
        ).fetchall()
        # 근거는 오늘(07-23 KST) 메모만.
        assert [e[0] for e in ev] == [m_today]
    finally:
        delete_user(conn, user)


@pytest.mark.integration
def test_타_사용자_엔티티는_절대_섞이지_않는다(conn):
    alice = seed_user(conn)
    bob = seed_user(conn)
    try:
        ea = _entity(conn, alice, "김밥")
        _mention(conn, alice, ea, "2026-07-23T02:00:00+00")
        eb = _entity(conn, bob, "김밥")
        _mention(conn, bob, eb, "2026-07-23T02:00:00+00")

        detect_day(conn, alice, "2026-07-23")

        # 앨리스 것만 기록, 밥은 0건.
        na = conn.execute(
            "select count(*)::int from public.differences where user_id = %s", (alice,)
        ).fetchone()[0]
        nb = conn.execute(
            "select count(*)::int from public.differences where user_id = %s", (bob,)
        ).fetchone()[0]
        assert na == 1
        assert nb == 0
    finally:
        delete_user(conn, alice)
        delete_user(conn, bob)

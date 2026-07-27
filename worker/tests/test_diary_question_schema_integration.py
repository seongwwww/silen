import pytest

from tests.conftest import seed_user, delete_user


@pytest.mark.integration
def test_질문_섹션을_저장할_수_있다(conn):
    user = seed_user(conn)
    try:
        diary = conn.execute(
            "insert into public.diaries (user_id, date, status, generated_text) "
            "values (%s, current_date, 'draft', '본문') returning id::text",
            (user,),
        ).fetchone()[0]
        conn.execute(
            "insert into public.diary_sections (diary_id, section_type, content) "
            "values (%s, '질문', '오늘 처음 만난 사람은 어떤 분이었나요?')",
            (diary,),
        )
        row = conn.execute(
            "select content from public.diary_sections "
            "where diary_id = %s and section_type = '질문'",
            (diary,),
        ).fetchone()
        assert row is not None
    finally:
        delete_user(conn, user)

from datetime import date

import pytest

from silen_worker.tasks.delete_data import run_pending_deletions
from tests.conftest import delete_user, seed_memory, seed_user


class EmptyStorage:
    def __init__(self):
        self.deleted_users = []

    def delete_user_objects(self, user_id):
        self.deleted_users.append(user_id)

    def has_user_objects(self, user_id):
        return False


@pytest.mark.integration
@pytest.mark.destructive
def test_격리_사용자의_기록만_완전히_삭제하고_계정과_원장은_남긴다(conn):
    user_id = seed_user(conn)
    try:
        memory_id = seed_memory(conn, user_id, "격리 삭제 fixture")
        entity_id = conn.execute(
            """
            insert into public.entities
              (user_id, entity_type, name, normalized_name)
            values (%s, 'thing', 'fixture', 'fixture')
            returning id::text
            """,
            (user_id,),
        ).fetchone()[0]
        difference_id = conn.execute(
            """
            insert into public.differences
              (user_id, date, entity_id, dimension, description,
               detection_method, category)
            values (%s, %s, %s, 'thing', 'fixture', 'pattern', '패턴')
            returning id::text
            """,
            (user_id, date.today(), entity_id),
        ).fetchone()[0]
        conn.execute(
            """
            insert into public.difference_evidence (difference_id, memory_id)
            values (%s, %s)
            """,
            (difference_id, memory_id),
        )
        diary_id = conn.execute(
            """
            insert into public.diaries (user_id, date, generated_text)
            values (%s, %s, 'fixture')
            returning id::text
            """,
            (user_id, date.today()),
        ).fetchone()[0]
        conn.execute(
            """
            insert into public.diary_sources (diary_id, memory_id)
            values (%s, %s)
            """,
            (diary_id, memory_id),
        )
        report_id = conn.execute(
            """
            insert into public.weekly_reports (user_id, week)
            values (%s, '2026-07-21')
            returning id::text
            """,
            (user_id,),
        ).fetchone()[0]
        conn.execute(
            """
            insert into public.weekly_report_highlights
              (report_id, difference_id, slot, rank)
            values (%s, %s, '가장많이한것', 1)
            """,
            (report_id, difference_id),
        )
        deletion_id = conn.execute(
            """
            insert into public.deletions
              (user_id, trigger, target_type, target_id, status)
            values (%s, 'account', 'user', %s, 'running')
            returning id::text
            """,
            (user_id, user_id),
        ).fetchone()[0]

        storage = EmptyStorage()
        assert run_pending_deletions(conn, storage) == (1, 0)

        assert storage.deleted_users == [user_id]
        assert conn.execute(
            "select count(*) from public.memories where user_id = %s",
            (user_id,),
        ).fetchone()[0] == 0
        assert conn.execute(
            "select count(*) from public.users where id = %s",
            (user_id,),
        ).fetchone()[0] == 1
        ledger = conn.execute(
            """
            select status, steps_done, last_error
            from public.deletions where id = %s
            """,
            (deletion_id,),
        ).fetchone()
        assert ledger[0] == "completed"
        assert ledger[2] is None
    finally:
        conn.execute(
            "delete from public.deletions where user_id = %s",
            (user_id,),
        )
        delete_user(conn, user_id)

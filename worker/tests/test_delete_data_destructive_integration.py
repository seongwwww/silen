from datetime import date
import os
from urllib.request import Request, urlopen

import pytest

from silen_worker.deletion.storage import SupabaseStorageDeletion
from silen_worker.tasks.delete_data import run_pending_deletions
from tests.conftest import delete_user, seed_memory, seed_user


def _upload_storage_fixture(user_id: str) -> None:
    base_url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not base_url or not key:
        pytest.fail("local_storage_credentials_missing")
    request = Request(
        f"{base_url.rstrip('/')}/storage/v1/object/memories/"
        f"{user_id}/fixture.txt",
        data=b"isolated deletion fixture",
        headers={
            "apikey": key,
            "authorization": f"Bearer {key}",
            "content-type": "text/plain",
            "x-upsert": "true",
        },
        method="POST",
    )
    with urlopen(request, timeout=20) as response:
        response.read()


@pytest.mark.integration
@pytest.mark.destructive
def test_격리_사용자의_기록만_완전히_삭제하고_계정과_원장은_남긴다(conn):
    user_id = seed_user(conn)
    bystander_id = seed_user(conn)
    storage = SupabaseStorageDeletion()
    try:
        memory_id = seed_memory(conn, user_id, "격리 삭제 fixture")
        bystander_memory_id = seed_memory(
            conn,
            bystander_id,
            "삭제하면 안 되는 격리 fixture",
        )
        _upload_storage_fixture(user_id)
        assert storage.has_user_objects(user_id)
        conn.execute(
            """
            insert into public.assets
              (memory_id, asset_type, file_url, mime_type)
            values (%s, 'photo', %s, 'text/plain')
            """,
            (memory_id, f"{user_id}/fixture.txt"),
        )
        conn.execute(
            """
            insert into public.emotions
              (memory_id, valence, tags, confidence, confirmed_by_user)
            values (%s, 0.5, array['fixture'], 1.0, true)
            """,
            (memory_id,),
        )
        entity_id = conn.execute(
            """
            insert into public.entities
              (user_id, entity_type, name, normalized_name)
            values (%s, 'thing', 'fixture', 'fixture')
            returning id::text
            """,
            (user_id,),
        ).fetchone()[0]
        conn.execute(
            """
            insert into public.memory_entities
              (memory_id, entity_id, relation_type, confidence)
            values (%s, %s, 'mentioned', 1.0)
            """,
            (memory_id, entity_id),
        )
        conn.execute(
            """
            insert into public.signals
              (user_id, signal_type, value, observed_at, source)
            values (%s, 'checkin', 1, now(), 'derived')
            """,
            (user_id,),
        )
        conn.execute(
            """
            insert into public.baselines
              (user_id, dimension, stat, window_spec)
            values (%s, 'fixture', '{}'::jsonb, '7d')
            """,
            (user_id,),
        )
        conn.execute(
            """
            insert into public.consents (user_id, source, scope)
            values (%s, 'fixture', 'fixture')
            """,
            (user_id,),
        )
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
        conn.execute(
            """
            insert into public.diary_generation_requests
              (user_id, date, status, diary_id, completed_at)
            values (%s, %s, 'done', %s, now())
            """,
            (user_id, date.today(), diary_id),
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
        bystander_deletion_id = conn.execute(
            """
            insert into public.deletions
              (user_id, trigger, target_type, target_id, status)
            values (%s, 'account', 'user', %s, 'running')
            returning id::text
            """,
            (bystander_id, bystander_id),
        ).fetchone()[0]

        assert run_pending_deletions(
            conn,
            storage,
            only_user_id=user_id,
        ) == (1, 0)

        assert not storage.has_user_objects(user_id)
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
        assert conn.execute(
            "select count(*) from public.memories where id = %s",
            (bystander_memory_id,),
        ).fetchone()[0] == 1
        assert conn.execute(
            "select status from public.deletions where id = %s",
            (bystander_deletion_id,),
        ).fetchone()[0] == "running"
    finally:
        storage.delete_user_objects(user_id)
        conn.execute(
            "delete from public.deletions where user_id in (%s, %s)",
            (user_id, bystander_id),
        )
        delete_user(conn, user_id)
        delete_user(conn, bystander_id)

from datetime import date, timedelta

import pytest

from silen_worker.stats.repository import fetch_stats
from tests.conftest import delete_user, seed_memory_at, seed_user


@pytest.mark.integration
def test_stats는_읽기만_하고_격리_사용자의_지표를_집계한다(conn):
    before = fetch_stats(conn)
    user_id = seed_user(conn)
    try:
        today = date.today()
        for offset in range(3):
            seed_memory_at(
                conn,
                user_id,
                f"{(today - timedelta(days=offset)).isoformat()}T02:00:00+00",
            )
        entity_id = conn.execute(
            """
            insert into public.entities
              (user_id, entity_type, name, normalized_name)
            values (%s, 'thing', '통계 fixture', '통계 fixture')
            returning id::text
            """,
            (user_id,),
        ).fetchone()[0]
        for offset, status in enumerate(("confirmed", "dismissed")):
            conn.execute(
                """
                insert into public.differences
                  (user_id, date, entity_id, dimension, description,
                   detection_method, category, status)
                values (%s, %s, %s, 'thing', 'fixture',
                        'freq_shift', '오늘의다른점', %s)
                """,
                (user_id, today - timedelta(days=offset), entity_id, status),
            )
        conn.execute(
            """
            insert into public.differences
              (user_id, date, entity_id, dimension, description,
               detection_method, category, status, evidence_state)
            values (%s, %s, %s, 'thing', 'fixture',
                    'freq_shift', '오늘의다른점', 'candidate', 'stale')
            """,
            (user_id, today - timedelta(days=2), entity_id),
        )
        conn.execute(
            """
            insert into public.diaries (user_id, date, status)
            values (%s, %s, 'confirmed')
            """,
            (user_id, today),
        )

        after = fetch_stats(conn)

        assert after.confirmed_differences == before.confirmed_differences + 1
        assert after.dismissed_differences == before.dismissed_differences + 1
        assert after.card_differences == before.card_differences + 2
        assert after.active_days == before.active_days + 3
        assert after.confirmed_diaries == before.confirmed_diaries + 1
        assert after.users_three_days == before.users_three_days + 1
    finally:
        delete_user(conn, user_id)

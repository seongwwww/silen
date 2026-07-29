import psycopg

from silen_worker.stats.service import StatsSnapshot


def fetch_stats(conn: psycopg.Connection) -> StatsSnapshot:
    """운영 지표를 읽기만 한다. INSERT/UPDATE/DELETE를 수행하지 않는다."""
    row = conn.execute(
        """
        with active_days_by_user as (
          select
            m.user_id,
            count(
              distinct (m.captured_at at time zone u.timezone)::date
            )::int as day_count
          from public.memories m
          join public.users u on u.id = m.user_id
          where m.deleted_at is null
            and m.is_locked = false
          group by m.user_id
        )
        select
          (
            select count(*)::int from public.differences
            where status = 'confirmed'
          ),
          (
            select count(*)::int from public.differences
            where status = 'dismissed'
          ),
          (
            select count(*)::int from public.differences
            where detection_method <> 'first_occurrence'
              and category in ('오늘의다른점', '감정전환')
              and evidence_state = 'intact'
          ),
          coalesce(
            (select sum(day_count)::int from active_days_by_user),
            0
          ),
          (
            select count(*)::int from public.diaries
            where status = 'confirmed'
          ),
          (select count(*)::int from public.diaries),
          (
            select count(*)::int from active_days_by_user
            where day_count >= 3
          ),
          (
            select count(*)::int from active_days_by_user
            where day_count >= 7
          )
        """
    ).fetchone()
    return StatsSnapshot(*row)

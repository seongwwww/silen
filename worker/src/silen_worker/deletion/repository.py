import psycopg

from silen_worker.deletion.service import DeletionJob


class PostgresDeletionRepository:
    """특권 워커의 삭제 저장소. 모든 문장이 user_id를 함께 강제한다."""

    def __init__(self, conn: psycopg.Connection):
        self.conn = conn

    def fetch_pending(
        self,
        limit: int = 20,
        only_user_id: str | None = None,
    ) -> list[DeletionJob]:
        query = """
            select id::text, user_id::text, steps_done
            from public.deletions
            where trigger = 'account'
              and target_type = 'user'
              and target_id = user_id
              and status in ('running', 'failed')
        """
        params: list[object] = []
        if only_user_id is not None:
            query += " and user_id = %s"
            params.append(only_user_id)
        query += """
            order by created_at
            limit %s
        """
        params.append(limit)
        rows = self.conn.execute(query, params).fetchall()
        return [
            DeletionJob(row[0], row[1], frozenset(row[2] or ()))
            for row in rows
        ]

    def mark_running(self, deletion_id: str, user_id: str) -> None:
        self.conn.execute(
            """
            update public.deletions
            set status = 'running',
                attempts = attempts + 1,
                last_error = null
            where id = %s
              and user_id = %s
              and target_type = 'user'
              and target_id = %s
              and status in ('running', 'failed')
            """,
            (deletion_id, user_id, user_id),
        )

    def mark_step_done(
        self,
        deletion_id: str,
        user_id: str,
        step: str,
    ) -> None:
        self.conn.execute(
            """
            update public.deletions
            set steps_done = case
              when %s = any(steps_done) then steps_done
              else array_append(steps_done, %s)
            end
            where id = %s and user_id = %s
            """,
            (step, step, deletion_id, user_id),
        )

    def delete_weekly_reports(self, user_id: str) -> None:
        self.conn.execute(
            "delete from public.weekly_reports where user_id = %s",
            (user_id,),
        )

    def delete_diaries(self, user_id: str) -> None:
        self.conn.execute(
            "delete from public.diary_generation_requests where user_id = %s",
            (user_id,),
        )
        self.conn.execute(
            "delete from public.diaries where user_id = %s",
            (user_id,),
        )

    def delete_differences(self, user_id: str) -> None:
        self.conn.execute(
            "delete from public.differences where user_id = %s",
            (user_id,),
        )

    def delete_derived_data(self, user_id: str) -> None:
        for table in ("consents", "baselines", "signals", "entities"):
            self.conn.execute(
                f"delete from public.{table} where user_id = %s",
                (user_id,),
            )

    def delete_memories_and_jobs(self, user_id: str) -> None:
        queued = self.conn.execute(
            """
            select msg_id
            from pgmq.q_memory_jobs
            where message->>'user_id' = %s
            """,
            (user_id,),
        ).fetchall()
        for (message_id,) in queued:
            self.conn.execute(
                "select pgmq.delete('memory_jobs', %s)",
                (message_id,),
            )
        self.conn.execute(
            """
            delete from pgmq.a_memory_jobs
            where message->>'user_id' = %s
            """,
            (user_id,),
        )
        self.conn.execute(
            "delete from public.memories where user_id = %s",
            (user_id,),
        )

    def has_residual_data(self, user_id: str) -> bool:
        counts = self.conn.execute(
            """
            select
              (select count(*) from public.weekly_reports where user_id = %s)
              + (select count(*) from public.diaries where user_id = %s)
              + (
                  select count(*) from public.diary_generation_requests
                  where user_id = %s
                )
              + (select count(*) from public.differences where user_id = %s)
              + (select count(*) from public.entities where user_id = %s)
              + (select count(*) from public.signals where user_id = %s)
              + (select count(*) from public.baselines where user_id = %s)
              + (select count(*) from public.consents where user_id = %s)
              + (select count(*) from public.memories where user_id = %s)
              + (
                  select count(*) from pgmq.q_memory_jobs
                  where message->>'user_id' = %s
                )
              + (
                  select count(*) from pgmq.a_memory_jobs
                  where message->>'user_id' = %s
                )
            """,
            (user_id,) * 11,
        ).fetchone()[0]
        return counts > 0

    def mark_completed(self, deletion_id: str, user_id: str) -> None:
        self.conn.execute(
            """
            update public.deletions
            set status = 'completed',
                completed_at = now(),
                last_error = null
            where id = %s and user_id = %s
            """,
            (deletion_id, user_id),
        )

    def mark_failed(
        self,
        deletion_id: str,
        user_id: str,
        error_code: str,
    ) -> None:
        self.conn.execute(
            """
            update public.deletions
            set status = 'failed', last_error = %s
            where id = %s and user_id = %s
            """,
            (error_code, deletion_id, user_id),
        )

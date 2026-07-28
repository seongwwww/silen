import psycopg

from silen_worker.deletion.repository import PostgresDeletionRepository
from silen_worker.deletion.service import StorageDeletionPort, run_deletion
from silen_worker.deletion.storage import SupabaseStorageDeletion


def run_pending_deletions(
    conn: psycopg.Connection,
    storage: StorageDeletionPort | None = None,
    limit: int = 20,
    only_user_id: str | None = None,
) -> tuple[int, int]:
    """running/failed 전체 기록 삭제를 재개한다. (완료 수, 실패 수)"""
    repository = PostgresDeletionRepository(conn)
    storage_port = storage or SupabaseStorageDeletion()
    completed = 0
    failed = 0
    for job in repository.fetch_pending(limit, only_user_id):
        if run_deletion(job, repository, storage_port):
            completed += 1
        else:
            failed += 1
    return completed, failed

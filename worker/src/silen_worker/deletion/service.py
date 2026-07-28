from dataclasses import dataclass
from typing import Protocol


STORAGE_STEP = "storage"
WEEKLY_STEP = "weekly_reports"
DIARIES_STEP = "diaries"
DIFFERENCES_STEP = "differences"
DERIVED_STEP = "entities_signals"
MEMORIES_STEP = "memories"
VERIFY_STEP = "verify"

DELETION_STEPS = (
    STORAGE_STEP,
    WEEKLY_STEP,
    DIARIES_STEP,
    DIFFERENCES_STEP,
    DERIVED_STEP,
    MEMORIES_STEP,
    VERIFY_STEP,
)


@dataclass(frozen=True)
class DeletionJob:
    deletion_id: str
    user_id: str
    steps_done: frozenset[str]


class StorageDeletionPort(Protocol):
    def delete_user_objects(self, user_id: str) -> None: ...

    def has_user_objects(self, user_id: str) -> bool: ...


class DeletionDataPort(Protocol):
    def mark_running(self, deletion_id: str, user_id: str) -> None: ...

    def mark_step_done(
        self, deletion_id: str, user_id: str, step: str
    ) -> None: ...

    def delete_weekly_reports(self, user_id: str) -> None: ...

    def delete_diaries(self, user_id: str) -> None: ...

    def delete_differences(self, user_id: str) -> None: ...

    def delete_derived_data(self, user_id: str) -> None: ...

    def delete_memories_and_jobs(self, user_id: str) -> None: ...

    def has_residual_data(self, user_id: str) -> bool: ...

    def mark_completed(self, deletion_id: str, user_id: str) -> None: ...

    def mark_failed(
        self, deletion_id: str, user_id: str, error_code: str
    ) -> None: ...


class ResidualDataError(RuntimeError):
    pass


def _failure_code(step: str) -> str:
    if step == STORAGE_STEP:
        return "storage_delete_failed"
    if step == VERIFY_STEP:
        return "residual_data"
    return "database_delete_failed"


def run_deletion(
    job: DeletionJob,
    data: DeletionDataPort,
    storage: StorageDeletionPort,
) -> bool:
    """완료하면 True, 실패 원장 기록 후 False.

    단계 동작은 모두 멱등이며, 성공한 단계만 steps_done에 기록해 실패 뒤 재개한다.
    오류 메시지·객체 경로는 원장에 쓰지 않고 고정 코드만 남긴다.
    """
    data.mark_running(job.deletion_id, job.user_id)
    steps_done = set(job.steps_done)

    actions = {
        STORAGE_STEP: lambda: storage.delete_user_objects(job.user_id),
        WEEKLY_STEP: lambda: data.delete_weekly_reports(job.user_id),
        DIARIES_STEP: lambda: data.delete_diaries(job.user_id),
        DIFFERENCES_STEP: lambda: data.delete_differences(job.user_id),
        DERIVED_STEP: lambda: data.delete_derived_data(job.user_id),
        MEMORIES_STEP: lambda: data.delete_memories_and_jobs(job.user_id),
        VERIFY_STEP: lambda: _verify(data, storage, job.user_id),
    }

    for step in DELETION_STEPS:
        if step in steps_done:
            continue
        try:
            actions[step]()
            data.mark_step_done(job.deletion_id, job.user_id, step)
            steps_done.add(step)
        except Exception:
            data.mark_failed(
                job.deletion_id,
                job.user_id,
                _failure_code(step),
            )
            return False

    data.mark_completed(job.deletion_id, job.user_id)
    return True


def _verify(
    data: DeletionDataPort,
    storage: StorageDeletionPort,
    user_id: str,
) -> None:
    if data.has_residual_data(user_id) or storage.has_user_objects(user_id):
        raise ResidualDataError

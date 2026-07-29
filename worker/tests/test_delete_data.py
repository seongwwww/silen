from silen_worker.deletion.service import (
    DELETION_STEPS,
    DeletionJob,
    run_deletion,
)


class FakeStorage:
    def __init__(self, fail=False, residual=False):
        self.fail = fail
        self.residual = residual
        self.users = []

    def delete_user_objects(self, user_id):
        self.users.append(user_id)
        if self.fail:
            raise RuntimeError("sensitive/path.jpg")

    def has_user_objects(self, user_id):
        return self.residual


class FakeData:
    def __init__(self, residual=False, fail_step=None):
        self.residual = residual
        self.fail_step = fail_step
        self.calls = []
        self.failed = None

    def _call(self, name, user_id):
        self.calls.append((name, user_id))
        if self.fail_step == name:
            raise RuntimeError("본문이나 경로가 포함될 수 있는 원시 오류")

    def mark_running(self, deletion_id, user_id):
        self.calls.append(("running", deletion_id, user_id))

    def mark_step_done(self, deletion_id, user_id, step):
        self.calls.append(("done", step, deletion_id, user_id))

    def delete_weekly_reports(self, user_id):
        self._call("weekly_reports", user_id)

    def delete_diaries(self, user_id):
        self._call("diaries", user_id)

    def delete_differences(self, user_id):
        self._call("differences", user_id)

    def delete_derived_data(self, user_id):
        self._call("entities_signals", user_id)

    def delete_memories_and_jobs(self, user_id):
        self._call("memories", user_id)

    def has_residual_data(self, user_id):
        self._call("verify", user_id)
        return self.residual

    def mark_completed(self, deletion_id, user_id):
        self.calls.append(("completed", deletion_id, user_id))

    def mark_failed(self, deletion_id, user_id, error_code):
        self.failed = (deletion_id, user_id, error_code)


def test_전체_단계를_순서대로_마치고_completed를_기록한다():
    data = FakeData()
    storage = FakeStorage()

    assert run_deletion(
        DeletionJob("d1", "u1", frozenset()),
        data,
        storage,
    )

    assert storage.users == ["u1"]
    completed_steps = [
        call[1] for call in data.calls if call[0] == "done"
    ]
    assert completed_steps == list(DELETION_STEPS)
    assert data.calls[-1] == ("completed", "d1", "u1")


def test_이미_끝난_단계는_건너뛰고_실패_지점부터_재개한다():
    data = FakeData()
    storage = FakeStorage()
    done = frozenset(("storage", "weekly_reports", "diaries"))

    assert run_deletion(DeletionJob("d1", "u1", done), data, storage)

    assert storage.users == []
    assert ("weekly_reports", "u1") not in data.calls
    assert ("diaries", "u1") not in data.calls
    assert ("differences", "u1") in data.calls


def test_storage_실패는_경로나_원문_대신_고정_코드만_남긴다():
    data = FakeData()

    assert not run_deletion(
        DeletionJob("d1", "u1", frozenset()),
        data,
        FakeStorage(fail=True),
    )

    assert data.failed == ("d1", "u1", "storage_delete_failed")
    assert not any(call[0] == "completed" for call in data.calls)


def test_db_실패도_원시_오류_대신_고정_코드만_남긴다():
    data = FakeData(fail_step="differences")

    assert not run_deletion(
        DeletionJob("d1", "u1", frozenset()),
        data,
        FakeStorage(),
    )

    assert data.failed == ("d1", "u1", "database_delete_failed")


def test_잔존_데이터가_있으면_completed로_표시하지_않는다():
    data = FakeData(residual=True)

    assert not run_deletion(
        DeletionJob("d1", "u1", frozenset()),
        data,
        FakeStorage(),
    )

    assert data.failed == ("d1", "u1", "residual_data")
    assert not any(call[0] == "completed" for call in data.calls)


def test_스토리지_잔존_객체도_completed를_막는다():
    data = FakeData()

    assert not run_deletion(
        DeletionJob("d1", "u1", frozenset()),
        data,
        FakeStorage(residual=True),
    )

    assert data.failed == ("d1", "u1", "residual_data")

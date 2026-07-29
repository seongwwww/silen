"""주기 점검(sweep) 대상 계산. 사용자가 CLI를 치지 않아도 워커가 알아서 한다."""

from datetime import datetime, timezone

from silen_worker.cli import build_sweep_plan


# (user_id, timezone, diary_hour)
_USERS = [
    ("seoul", "Asia/Seoul", 21),
    ("newyork", "America/New_York", 21),
]


def _at(hour_utc: int) -> datetime:
    return datetime(2026, 7, 29, hour_utc, 0, tzinfo=timezone.utc)


def test_예약_시각_전이면_중간_점검만_한다():
    """UTC 03:00 = 서울 정오. 하루가 안 끝났으니 부재를 말하면 안 된다."""
    plan = build_sweep_plan(_USERS[:1], _at(3))

    assert plan == [("seoul", "2026-07-29", False)]


def test_예약_시각이_지나면_마감으로_돌린다():
    """UTC 13:00 = 서울 22시. 21시를 넘겼다."""
    plan = build_sweep_plan(_USERS[:1], _at(13))

    assert plan == [("seoul", "2026-07-29", True)]


def test_타임존마다_마감_시점이_다르다():
    """UTC 13:00 = 서울 22시(마감), 뉴욕 09시(중간)."""
    plan = dict((user, closing) for user, _, closing in build_sweep_plan(_USERS, _at(13)))

    assert plan == {"seoul": True, "newyork": False}


def test_날짜도_사용자_로컬_기준이다():
    """UTC 16:00 = 서울 다음날 01시, 뉴욕 같은 날 12시."""
    dates = {user: day for user, day, _ in build_sweep_plan(_USERS, _at(16))}

    assert dates == {"seoul": "2026-07-30", "newyork": "2026-07-29"}


def test_사용자가_없으면_할_일도_없다():
    assert build_sweep_plan([], _at(13)) == []


def test_run은_큐를_비우고_주기_점검을_한다(monkeypatch):
    """평소엔 이 명령 하나만 켜두면 된다."""
    import silen_worker.cli as cli

    swept: list[int] = []
    monkeypatch.setattr(cli, "process_pending", lambda **_: [])
    monkeypatch.setattr(cli, "connect", lambda: _NullConn())
    monkeypatch.setattr(cli, "sweep", lambda conn, **_: swept.append(1))

    cli.run(rounds=3, sweep_seconds=1000, sleep=lambda _: None, clock=lambda: 0.0)

    # 첫 회에 한 번 돌고, 주기가 안 찼으면 다시 돌지 않는다.
    assert swept == [1]


def test_주기가_지나면_다시_점검한다(monkeypatch):
    import silen_worker.cli as cli

    swept: list[int] = []
    ticks = iter([0.0, 100.0, 200.0])
    monkeypatch.setattr(cli, "process_pending", lambda **_: [])
    monkeypatch.setattr(cli, "connect", lambda: _NullConn())
    monkeypatch.setattr(cli, "sweep", lambda conn, **_: swept.append(1))

    cli.run(
        rounds=3,
        sweep_seconds=60,
        sleep=lambda _: None,
        clock=lambda: next(ticks),
    )

    assert len(swept) == 3


class _NullConn:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def test_탐지가_실패하면_일기를_예약하지_않는다(monkeypatch):
    """차이를 못 찾은 채 일기를 만들면 '평범한 하루'로 굳어버린다.
    한 번 만든 일기는 자동 재생성하지 않으므로 되돌릴 수 없다."""
    import silen_worker.cli as cli

    scheduled: list[str] = []
    monkeypatch.setattr(cli, "fetch_scheduled_users", lambda conn: _USERS[:1])
    monkeypatch.setattr(cli, "run_daily", lambda *a, **k: (0, 1))  # 실패 1
    monkeypatch.setattr(cli, "run_scheduled", lambda conn, t: scheduled.append(t))
    monkeypatch.setattr(cli, "run_weekly", lambda conn, t: (0, 0))
    monkeypatch.setattr(cli, "run_regenerations", lambda conn, t: (0, 0))

    cli.sweep(_NullConn(), now=_at(13))

    assert scheduled == []


def test_탐지가_성공하면_일기를_예약한다(monkeypatch):
    import silen_worker.cli as cli

    scheduled: list[str] = []
    monkeypatch.setattr(cli, "fetch_scheduled_users", lambda conn: _USERS[:1])
    monkeypatch.setattr(cli, "run_daily", lambda *a, **k: (1, 0))
    monkeypatch.setattr(cli, "run_scheduled", lambda conn, t: scheduled.append(t))
    monkeypatch.setattr(cli, "run_weekly", lambda conn, t: (0, 0))
    monkeypatch.setattr(cli, "run_regenerations", lambda conn, t: (0, 0))

    cli.sweep(_NullConn(), now=_at(13))

    assert scheduled == [[("seoul", "2026-07-29")]]


def test_어제_마감을_놓쳤으면_따라잡는다(monkeypatch):
    """워커가 자정을 넘겨 재시작하면 전날은 영영 마감되지 않는다."""
    import silen_worker.cli as cli

    closed: list[tuple[str, bool]] = []
    monkeypatch.setattr(cli, "fetch_scheduled_users", lambda conn: _USERS[:1])
    monkeypatch.setattr(
        cli,
        "run_daily",
        lambda conn, targets, narrator=None, closing=True: (
            closed.append((targets[0][1], closing)) or (1, 0)
        ),
    )
    monkeypatch.setattr(cli, "run_scheduled", lambda conn, t: (1, 0, 0))
    monkeypatch.setattr(cli, "run_weekly", lambda conn, t: (0, 0))
    monkeypatch.setattr(cli, "run_regenerations", lambda conn, t: (0, 0))

    cli.sweep(_NullConn(), now=_at(3))  # 서울 정오 — 오늘은 아직 중간

    assert ("2026-07-28", True) in closed
    assert ("2026-07-29", False) in closed

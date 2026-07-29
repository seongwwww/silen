"""run-pending --watch. 회고 응답처럼 사람이 화면 앞에서 기다리는 잡은
스케줄러 주기(분)로는 늦다. 큐를 짧은 간격으로 계속 소비한다."""

import silen_worker.cli as cli
from silen_worker.cli import build_parser, watch_pending


class _Sleeper:
    def __init__(self) -> None:
        self.calls: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


def _stub_process(batches, monkeypatch):
    """process_pending이 차례대로 batches를 반환하게 한다. 소진되면 빈 배치."""
    queue = list(batches)

    def fake(limit=10, extractor=None, **_):
        return queue.pop(0) if queue else []

    monkeypatch.setattr(cli, "process_pending", fake)


def test_지정한_횟수만큼_돌고_처리한_수를_반환한다(monkeypatch):
    _stub_process([["m1"], ["m2", "m3"]], monkeypatch)
    sleeper = _Sleeper()

    assert watch_pending(rounds=3, sleep=sleeper) == 3


def test_큐가_비면_간격만큼_잠든다(monkeypatch):
    _stub_process([], monkeypatch)
    sleeper = _Sleeper()

    watch_pending(rounds=2, interval=0.5, sleep=sleeper)

    assert sleeper.calls == [0.5, 0.5]


def test_처리할_일이_있으면_잠들지_않는다(monkeypatch):
    """일이 밀려 있는데 자면 응답이 그만큼 늦는다."""
    _stub_process([["m1"]], monkeypatch)
    sleeper = _Sleeper()

    watch_pending(rounds=1, sleep=sleeper)

    assert sleeper.calls == []


def test_중단하면_그때까지_처리한_수를_반환한다(monkeypatch):
    def fake(limit=10, extractor=None, **_):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "process_pending", fake)

    # Ctrl+C가 예외로 새어나가면 종료 코드가 더러워진다.
    assert watch_pending(rounds=5, sleep=_Sleeper()) == 0


def test_watch는_기본이_아니다():
    """기존 스케줄러는 1회 실행에 의존한다. 기본 동작을 바꾸지 않는다."""
    args = build_parser().parse_args(["run-pending"])

    assert args.watch is False
    assert args.interval == 1.0

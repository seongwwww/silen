from silen_worker.cli import run_stats
from silen_worker.stats.service import StatsSnapshot, format_stats


def test_네_지표와_opt_out_설명을_출력한다():
    lines = format_stats(
        StatsSnapshot(
            confirmed_differences=41,
            dismissed_differences=9,
            card_differences=21,
            active_days=10,
            confirmed_diaries=7,
            total_diaries=11,
            users_three_days=4,
            users_seven_days=2,
        )
    )

    assert lines[0] == "명시적 긍정 비율 82%  (confirmed 41 / dismissed 9)"
    assert lines[1] == "하루 평균 차이   2.1건"
    assert lines[2] == "일기 확정률      64%"
    assert lines[3] == "관측일수 분포    3일+ 4명 · 7일+ 2명"
    assert "카드 전체 정확도가 아닙니다" in lines[4]


def test_분모가_없으면_0퍼센트로_오해시키지_않는다():
    lines = format_stats(
        StatsSnapshot(0, 0, 0, 0, 0, 0, 0, 0)
    )

    assert "집계 전" in lines[0]
    assert "집계 전" in lines[1]
    assert "집계 전" in lines[2]


def test_stats_명령은_읽은_지표를_그대로_출력한다(monkeypatch, capsys):
    snapshot = StatsSnapshot(2, 1, 3, 2, 1, 2, 1, 0)
    monkeypatch.setattr(
        "silen_worker.cli.fetch_stats",
        lambda _conn: snapshot,
    )

    lines = run_stats(object())

    assert capsys.readouterr().out.splitlines() == lines
    assert lines[0].startswith("명시적 긍정 비율")
    assert lines[-1].startswith("설명:")

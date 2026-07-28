from datetime import datetime, timezone

from silen_worker.cli import (
    build_parser,
    build_targets,
    build_weekly_targets,
    local_yesterday,
)

_USERS = [("u1", "Asia/Seoul"), ("u2", "America/New_York")]


def test_서울_자정_전이면_어제는_전날():
    now = datetime(2026, 7, 27, 14, 30, tzinfo=timezone.utc)
    assert local_yesterday("Asia/Seoul", now) == "2026-07-26"


def test_서울_자정_후면_어제가_하루_넘어간다():
    now = datetime(2026, 7, 27, 16, 0, tzinfo=timezone.utc)
    assert local_yesterday("Asia/Seoul", now) == "2026-07-27"


def test_타임존마다_어제가_다르다():
    now = datetime(2026, 7, 27, 16, 0, tzinfo=timezone.utc)
    assert local_yesterday("Asia/Seoul", now) == "2026-07-27"
    assert local_yesterday("America/New_York", now) == "2026-07-26"


def test_인자_없으면_전체_사용자의_각자_어제():
    now = datetime(2026, 7, 27, 16, 0, tzinfo=timezone.utc)
    targets = build_targets(_USERS, user=None, date_iso=None, now=now)
    assert targets == [("u1", "2026-07-27"), ("u2", "2026-07-26")]


def test_date를_주면_모든_대상에_그대로_쓴다():
    now = datetime(2026, 7, 27, 16, 0, tzinfo=timezone.utc)
    targets = build_targets(_USERS, user=None, date_iso="2026-01-01", now=now)
    assert targets == [("u1", "2026-01-01"), ("u2", "2026-01-01")]


def test_user를_주면_그_사용자만():
    now = datetime(2026, 7, 27, 16, 0, tzinfo=timezone.utc)
    targets = build_targets(_USERS, user="u2", date_iso=None, now=now)
    assert targets == [("u2", "2026-07-26")]


def test_없는_user면_빈_목록():
    now = datetime(2026, 7, 27, 16, 0, tzinfo=timezone.utc)
    assert build_targets(_USERS, user="없음", date_iso=None, now=now) == []


def test_파서가_네_명령을_안다():
    parser = build_parser()
    assert parser.parse_args(["run-pending"]).command == "run-pending"
    assert parser.parse_args(["run-daily"]).command == "run-daily"
    assert parser.parse_args(["run-diary"]).command == "run-diary"
    assert parser.parse_args(["run-weekly"]).command == "run-weekly"


def test_파서_기본값과_옵션():
    parser = build_parser()
    args = parser.parse_args(["run-daily"])
    assert args.user is None and args.date is None

    args = parser.parse_args(["run-daily", "--user", "u1", "--date", "2026-07-01"])
    assert args.user == "u1" and args.date == "2026-07-01"

    assert parser.parse_args(["run-diary"]).force is False
    assert parser.parse_args(["run-diary", "--force"]).force is True

    args = parser.parse_args(["run-pending"])
    assert args.limit == 10 and args.max_batches == 50


def test_weekly_target은_각_사용자의_로컬_오늘이다():
    now = datetime(2026, 7, 27, 16, 0, tzinfo=timezone.utc)
    targets = build_weekly_targets(_USERS, user=None, date_iso=None, now=now)
    assert targets == [("u1", "2026-07-28"), ("u2", "2026-07-27")]


def test_weekly_target도_user와_date로_좁힐_수_있다():
    now = datetime(2026, 7, 27, 16, 0, tzinfo=timezone.utc)
    targets = build_weekly_targets(
        _USERS,
        user="u2",
        date_iso="2026-07-08",
        now=now,
    )
    assert targets == [("u2", "2026-07-08")]


def test_run_diary_도움말은_확정이_관문이라고_말하지_않는다():
    help_text = build_parser().format_help()

    assert "기각하지 않은 차이 반영" in help_text
    assert "확정 차이 반영" not in help_text

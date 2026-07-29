"""워커 CLI — 파이프라인 진입점. 주기 실행은 외부 스케줄러에 위임한다.

새 도메인 로직 없음: 기존 tasks/* 함수를 부르는 얇은 오케스트레이션 계층이다.
대상 계산(local_yesterday·build_targets)은 DB를 모르는 순수 함수라 단위 테스트한다.

로그는 JSON 한 줄을 stdout에 찍는다. **사용자 기록 본문·일기 텍스트는 절대
남기지 않는다** — user_id·카운트·id·예외 타입명만(backend.md·privacy.md).
"""

import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone

from silen_worker.db import connect, fetch_active_users, fetch_scheduled_users
from silen_worker.stats.repository import fetch_stats
from silen_worker.stats.service import format_stats
from silen_worker.tasks.detect import detect_day
from silen_worker.tasks.narrate import narrate_difference
from silen_worker.tasks.process import process_pending
from silen_worker.tasks.schedule import schedule_diary
from silen_worker.tasks.write_diary import generate_diary
from silen_worker.tasks.write_weekly import generate_weekly_report
from silen_worker.time import local_date_for, local_hour_for


def local_yesterday(tz: str, now: datetime) -> str:
    """사용자 로컬 기준 '어제'(YYYY-MM-DD). 자정이 지나야 그 하루가 완결된다."""
    today_local = date.fromisoformat(local_date_for(now, tz))
    return (today_local - timedelta(days=1)).isoformat()


def build_targets(
    users: list[tuple[str, str]],
    user: str | None,
    date_iso: str | None,
    now: datetime,
) -> list[tuple[str, str]]:
    """처리할 (user_id, date_iso) 목록. user를 주면 그 사용자만, date_iso를 주면
    모든 대상에 그 날짜를 쓴다. 없으면 각자 로컬 어제."""
    selected = [(uid, tz) for uid, tz in users if user is None or uid == user]
    return [
        (uid, date_iso if date_iso is not None else local_yesterday(tz, now))
        for uid, tz in selected
    ]


def build_weekly_targets(
    users: list[tuple[str, str]],
    user: str | None,
    date_iso: str | None,
    now: datetime,
) -> list[tuple[str, str]]:
    """Weekly targets use each user's local today, the block boundary."""

    selected = [(uid, tz) for uid, tz in users if user is None or uid == user]
    return [
        (
            uid,
            date_iso if date_iso is not None else local_date_for(now, tz),
        )
        for uid, tz in selected
    ]


def build_scheduled_targets(
    users: list[tuple[str, str, int]],
    now: datetime,
) -> list[tuple[str, str]]:
    """로컬 예약 시각이 지난 사용자와 오늘 날짜만 고른다."""
    return [
        (user_id, local_date_for(now, time_zone))
        for user_id, time_zone, diary_hour in users
        if local_hour_for(now, time_zone) >= diary_hour
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="silen-worker", description="실은 워커 파이프라인 실행"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_pending = sub.add_parser("run-pending", help="큐 소비 → 엔티티 추출")
    p_pending.add_argument("--limit", type=int, default=10, help="한 배치 크기")
    p_pending.add_argument(
        "--max-batches",
        dest="max_batches",
        type=int,
        default=50,
        help="무한 루프 방지 상한",
    )
    sub.add_parser("stats", help="읽기 전용 MVP 운영 지표 출력")
    sub.add_parser(
        "run-scheduled",
        help="사용자 로컬 예약 시각이 지난 일기 요청을 멱등하게 등록",
    )

    for name, help_text in (
        ("run-daily", "차이 검출 → 서술"),
        ("run-diary", "일기 생성(기각하지 않은 차이 반영)"),
        ("run-weekly", "막 끝난 7일 블록의 주간 리포트 생성"),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--user", default=None, help="이 사용자만 처리(기본: 전체)")
        default_day = "오늘" if name == "run-weekly" else "어제"
        p.add_argument(
            "--date",
            default=None,
            help=f"YYYY-MM-DD(기본: 각자 로컬 {default_day})",
        )
        if name == "run-diary":
            p.add_argument(
                "--force",
                action="store_true",
                help="이미 있는 draft 일기를 다시 생성(유저 편집본은 보존)",
            )

    return parser


def _emit(event: dict) -> None:
    """구조화 로그 한 줄. 본문·일기 텍스트를 절대 싣지 않는다."""
    print(json.dumps(event, ensure_ascii=False))


def resolve_targets(
    conn, user: str | None, date_iso: str | None, now: datetime | None = None
) -> list[tuple[str, str]]:
    """DB에서 사용자를 읽어 처리 대상 (user_id, date_iso) 목록을 만든다."""
    return build_targets(
        fetch_active_users(conn),
        user,
        date_iso,
        now or datetime.now(timezone.utc),
    )


def resolve_weekly_targets(
    conn, user: str | None, date_iso: str | None, now: datetime | None = None
) -> list[tuple[str, str]]:
    """Build report-boundary targets from each user's current local date."""

    return build_weekly_targets(
        fetch_active_users(conn),
        user,
        date_iso,
        now or datetime.now(timezone.utc),
    )


def resolve_scheduled_targets(
    conn,
    now: datetime | None = None,
) -> list[tuple[str, str]]:
    """DB 사용자 설정으로 지금 예약할 일기 날짜를 계산한다."""
    return build_scheduled_targets(
        fetch_scheduled_users(conn),
        now or datetime.now(timezone.utc),
    )


def run_pending(extractor=None, limit: int = 10, max_batches: int = 50) -> int:
    """큐가 빌 때까지(또는 상한까지) 소비하고 처리한 memory 개수를 반환한다.
    process_pending은 conn을 받지 않고 자체 접속한다(기존 인터페이스 유지)."""
    total = 0
    for _ in range(max_batches):
        processed = process_pending(limit=limit, extractor=extractor)
        total += len(processed)
        if len(processed) < limit:
            break
    _emit({"event": "run_pending.done", "processed": total})
    return total


def run_daily(conn, targets: list[tuple[str, str]], narrator=None) -> tuple[int, int]:
    """사용자별로 차이를 검출하고 서술한다. (성공 수, 실패 수) 반환.
    한 사용자의 실패가 나머지를 막지 않는다."""
    ok = fail = 0
    for user_id, date_iso in targets:
        try:
            result = detect_day(conn, user_id, date_iso)
            narrated = 0
            for difference_id in result.narration_ids:
                if (
                    narrate_difference(conn, difference_id, narrator=narrator)
                    is not None
                ):
                    narrated += 1
            _emit(
                {
                    "event": "run_daily.user",
                    "user_id": user_id,
                    "date": date_iso,
                    "differences": len(result.saved_ids),
                    "narrated": narrated,
                }
            )
            ok += 1
        except Exception as exc:  # 사용자 단위 격리
            fail += 1
            _emit(
                {
                    "event": "run_daily.error",
                    "user_id": user_id,
                    "date": date_iso,
                    "error": type(exc).__name__,  # 메시지는 본문이 섞일 수 있어 제외
                }
            )
    return ok, fail


def run_diary(
    conn, targets: list[tuple[str, str]], writer=None, force: bool = False
) -> tuple[int, int]:
    """사용자별로 일기를 생성한다. (성공 수, 실패 수) 반환.
    빈 날은 생성하지 않지만 실패가 아니다."""
    ok = fail = 0
    for user_id, date_iso in targets:
        try:
            diary_id = generate_diary(
                conn, user_id, date_iso, force=force, writer=writer
            )
            _emit(
                {
                    "event": "run_diary.user",
                    "user_id": user_id,
                    "date": date_iso,
                    "created": diary_id is not None,
                }
            )
            ok += 1
        except Exception as exc:  # 사용자 단위 격리
            fail += 1
            _emit(
                {
                    "event": "run_diary.error",
                    "user_id": user_id,
                    "date": date_iso,
                    "error": type(exc).__name__,
                }
            )
    return ok, fail


def run_scheduled(
    conn,
    targets: list[tuple[str, str]],
) -> tuple[int, int, int]:
    """예약 대상을 요청 원장과 기존 큐에 넣는다. (생성, 건너뜀, 실패)"""
    created = skipped = failed = 0
    for user_id, date_iso in targets:
        try:
            request_id = schedule_diary(conn, user_id, date_iso)
            if request_id is None:
                skipped += 1
            else:
                created += 1
            _emit(
                {
                    "event": "run_scheduled.user",
                    "user_id": user_id,
                    "date": date_iso,
                    "created": request_id is not None,
                }
            )
        except Exception as exc:
            failed += 1
            _emit(
                {
                    "event": "run_scheduled.error",
                    "user_id": user_id,
                    "date": date_iso,
                    "error": type(exc).__name__,
                }
            )
    return created, skipped, failed


def run_weekly(conn, targets: list[tuple[str, str]]) -> tuple[int, int]:
    """Generate eligible weekly reports, isolating failures per user."""

    ok = fail = 0
    for user_id, date_iso in targets:
        try:
            report_id = generate_weekly_report(conn, user_id, date_iso)
            _emit(
                {
                    "event": "run_weekly.user",
                    "user_id": user_id,
                    "date": date_iso,
                    "created": report_id is not None,
                }
            )
            ok += 1
        except Exception as exc:
            fail += 1
            _emit(
                {
                    "event": "run_weekly.error",
                    "user_id": user_id,
                    "date": date_iso,
                    "error": type(exc).__name__,
                }
            )
    return ok, fail


def run_stats(conn) -> list[str]:
    """쓰기 없이 네 MVP 운영 지표와 해석 주의를 출력한다."""
    lines = format_stats(fetch_stats(conn))
    for line in lines:
        print(line)
    return lines


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "run-pending":
        run_pending(limit=args.limit, max_batches=args.max_batches)
        return 0

    with connect() as conn:
        if args.command == "stats":
            run_stats(conn)
            return 0

        if args.command == "run-scheduled":
            targets = resolve_scheduled_targets(conn)
            created, skipped, failed = run_scheduled(conn, targets)
            _emit(
                {
                    "event": "run-scheduled.done",
                    "created": created,
                    "skipped": skipped,
                    "failed": failed,
                }
            )
            return 1 if failed else 0

        targets = (
            resolve_weekly_targets(conn, args.user, args.date)
            if args.command == "run-weekly"
            else resolve_targets(conn, args.user, args.date)
        )
        if args.user is not None and not targets:
            print(f"사용자를 찾을 수 없습니다: {args.user}", file=sys.stderr)
            return 1

        if args.command == "run-daily":
            ok, fail = run_daily(conn, targets)
        elif args.command == "run-weekly":
            ok, fail = run_weekly(conn, targets)
        else:
            ok, fail = run_diary(conn, targets, force=args.force)

    _emit({"event": f"{args.command}.done", "ok": ok, "failed": fail})
    return 1 if fail else 0

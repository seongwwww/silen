"""워커 CLI — 파이프라인 진입점. 주기 실행은 외부 스케줄러에 위임한다.

새 도메인 로직 없음: 기존 tasks/* 함수를 부르는 얇은 오케스트레이션 계층이다.
대상 계산(local_yesterday·build_targets)은 DB를 모르는 순수 함수라 단위 테스트한다.

로그는 JSON 한 줄을 stdout에 찍는다. **사용자 기록 본문·일기 텍스트는 절대
남기지 않는다** — user_id·카운트·id·예외 타입명만(backend.md·privacy.md).
"""

import argparse
from datetime import date, datetime, timedelta

from silen_worker.time import local_date_for


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

    for name, help_text in (
        ("run-daily", "차이 검출 → 서술"),
        ("run-diary", "일기 생성(확정 차이 반영)"),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--user", default=None, help="이 사용자만 처리(기본: 전체)")
        p.add_argument("--date", default=None, help="YYYY-MM-DD(기본: 각자 로컬 어제)")
        if name == "run-diary":
            p.add_argument(
                "--force",
                action="store_true",
                help="이미 있는 draft 일기를 다시 생성(유저 편집본은 보존)",
            )

    return parser

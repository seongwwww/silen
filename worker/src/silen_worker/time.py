"""사용자 로컬 자정 기준 '하루' 정의.

Next.js의 lib/time/day.ts와 동일한 계약을 따른다.
두 런타임이 코드를 공유할 수 없으므로 fixtures/day-boundary.json이
계약서 역할을 하며, 양쪽 테스트가 같은 파일을 읽는다.
"""

from datetime import datetime
from zoneinfo import ZoneInfo


def local_date_for(instant: datetime, time_zone: str) -> str:
    """UTC 시각과 IANA 타임존을 받아 YYYY-MM-DD 로컬 날짜를 반환한다."""
    return instant.astimezone(ZoneInfo(time_zone)).strftime("%Y-%m-%d")

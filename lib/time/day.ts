/**
 * 사용자 로컬 자정을 기준으로 한 "하루"의 날짜를 반환한다.
 * "하루"의 정의는 이 모듈에서만 관리한다(backend.md).
 *
 * en-CA 로케일은 YYYY-MM-DD 형식을 보장하며, Intl이 IANA 타임존의
 * DST 전환을 처리하므로 고정 오프셋 계산을 하지 않는다.
 *
 * Python 워커의 silen_worker.time.local_date_for와 동일한 계약을 따른다.
 * 두 런타임이 코드를 공유할 수 없으므로 fixtures/day-boundary.json이
 * 계약서 역할을 하며, 양쪽 테스트가 같은 파일을 읽는다.
 */
export function localDateFor(instant: Date, timeZone: string): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(instant);
}

type DateParts = {
  year: number;
  month: number;
  day: number;
};

function parseDate(date: string): DateParts {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date);
  if (!match) throw new Error(`Invalid local date: ${date}`);
  return {
    year: Number(match[1]),
    month: Number(match[2]),
    day: Number(match[3]),
  };
}

function nextDate({ year, month, day }: DateParts): DateParts {
  const instant = new Date(Date.UTC(year, month - 1, day + 1));
  return {
    year: instant.getUTCFullYear(),
    month: instant.getUTCMonth() + 1,
    day: instant.getUTCDate(),
  };
}

function zonedMidnight(parts: DateParts, timeZone: string): Date {
  const wallClockAsUtc = Date.UTC(parts.year, parts.month - 1, parts.day);
  const formatter = new Intl.DateTimeFormat("en-US", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  });

  let candidate = wallClockAsUtc;
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const values = Object.fromEntries(
      formatter
        .formatToParts(new Date(candidate))
        .filter((part) => part.type !== "literal")
        .map((part) => [part.type, Number(part.value)]),
    );
    const representedWallClock = Date.UTC(
      values.year,
      values.month - 1,
      values.day,
      values.hour,
      values.minute,
      values.second,
    );
    candidate += wallClockAsUtc - representedWallClock;
  }
  return new Date(candidate);
}

/** 사용자 로컬 날짜를 DB 조회용 UTC 반열린 구간 [start, end)으로 바꾼다. */
export function utcRangeForLocalDate(
  date: string,
  timeZone: string,
): { start: string; end: string } {
  const startParts = parseDate(date);
  return {
    start: zonedMidnight(startParts, timeZone).toISOString(),
    end: zonedMidnight(nextDate(startParts), timeZone).toISOString(),
  };
}

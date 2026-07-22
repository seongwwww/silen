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

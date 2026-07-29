import { describe, it, expect } from "vitest";
import fixture from "@/fixtures/day-boundary.json";
import { localDateFor, utcRangeForLocalDate } from "./day";

describe("localDateFor", () => {
  for (const testCase of fixture.cases) {
    it(testCase.name, () => {
      const result = localDateFor(new Date(testCase.instant), testCase.timezone);
      expect(result).toBe(testCase.expectedLocalDate);
    });
  }
});

describe("utcRangeForLocalDate", () => {
  it("한국 시간의 하루를 UTC 반열린 구간으로 바꾼다", () => {
    expect(utcRangeForLocalDate("2026-07-22", "Asia/Seoul")).toEqual({
      start: "2026-07-21T15:00:00.000Z",
      end: "2026-07-22T15:00:00.000Z",
    });
  });

  it("DST가 바뀌는 날의 실제 길이를 보존한다", () => {
    expect(utcRangeForLocalDate("2026-03-08", "America/New_York")).toEqual({
      start: "2026-03-08T05:00:00.000Z",
      end: "2026-03-09T04:00:00.000Z",
    });
  });
});

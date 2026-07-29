import { describe, it, expect } from "vitest";
import {
  assertValidDiaryTransition,
  QUICK_TONE_ORDERS,
  TONE_INSTRUCTION_MAX_LENGTH,
  InvalidDiaryTransitionError,
  type DiaryStatus,
  type QuickToneOrder,
} from "./diary";

const allowed: [DiaryStatus, DiaryStatus][] = [
  ["draft", "edited"],
  ["draft", "confirmed"],
  ["edited", "confirmed"],
  ["confirmed", "edited"],
];

const forbidden: [DiaryStatus, DiaryStatus][] = [
  ["draft", "draft"],
  ["edited", "draft"],
  ["confirmed", "draft"],
  ["confirmed", "confirmed"],
];

describe("일기 상태 전이", () => {
  it.each(allowed)("%s → %s 는 허용된다", (from, to) => {
    expect(() => assertValidDiaryTransition(from, to)).not.toThrow();
  });

  it.each(forbidden)("%s → %s 는 거부된다", (from, to) => {
    expect(() => assertValidDiaryTransition(from, to)).toThrow(
      InvalidDiaryTransitionError,
    );
  });
});

describe("일회성 톤 주문", () => {
  it("빠른 주문은 짧게와 유머만 제공한다", () => {
    const expected: QuickToneOrder[] = ["짧게", "유머"];
    expect(QUICK_TONE_ORDERS).toEqual(expected);
  });

  it("자유 주문 길이 상한을 한곳에서 제공한다", () => {
    expect(TONE_INSTRUCTION_MAX_LENGTH).toBeGreaterThanOrEqual(100);
    expect(TONE_INSTRUCTION_MAX_LENGTH).toBeLessThanOrEqual(200);
  });
});

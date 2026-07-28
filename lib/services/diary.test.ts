import { describe, it, expect } from "vitest";
import {
  assertValidDiaryTransition,
  InvalidDiaryTransitionError,
  type DiaryStatus,
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

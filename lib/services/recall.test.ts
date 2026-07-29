import { describe, expect, it } from "vitest";
import {
  InvalidRecallQueryError,
  RECALL_QUERY_MAX,
  validateRecallQuery,
} from "./recall";

describe("회고 질문 검증", () => {
  it("질문의 앞뒤 공백을 제거한다", () => {
    expect(validateRecallQuery("  카페 언제 갔지  ")).toBe("카페 언제 갔지");
  });

  it("빈 질문을 거부한다", () => {
    expect(() => validateRecallQuery("   ")).toThrow(InvalidRecallQueryError);
  });

  it("100자를 넘는 질문을 거부한다", () => {
    expect(() => validateRecallQuery("가".repeat(RECALL_QUERY_MAX + 1))).toThrow(
      InvalidRecallQueryError,
    );
  });
});


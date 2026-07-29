import { describe, expect, it, vi } from "vitest";
import {
  InvalidRecallQueryError,
  searchRecall,
  type RecallSearchPort,
} from "./recall";

function port(): RecallSearchPort {
  return {
    search: vi.fn(async () => [
      {
        id: "m1",
        rawText: "  오래 전에 들었던 노래가 다시 생각났다.  ",
        capturedAt: "2026-07-14T12:00:00Z",
      },
    ]),
  };
}

describe("회고 키워드 검색", () => {
  it("빈 질의는 저장소를 호출하지 않고 빈 결과를 돌려준다", async () => {
    const repo = port();

    await expect(searchRecall(repo, "u1", "   ")).resolves.toEqual([]);
    expect(repo.search).not.toHaveBeenCalled();
  });

  it("질의를 trim하고 날짜·발췌 결과로 바꾼다", async () => {
    const repo = port();

    const result = await searchRecall(repo, "u1", "  노래  ");

    expect(repo.search).toHaveBeenCalledWith("u1", "노래");
    expect(result).toEqual([
      {
        id: "m1",
        capturedAt: "2026-07-14T12:00:00Z",
        excerpt: "오래 전에 들었던 노래가 다시 생각났다.",
      },
    ]);
  });

  it("100자를 넘는 질의는 거부한다", async () => {
    await expect(searchRecall(port(), "u1", "가".repeat(101))).rejects.toBeInstanceOf(
      InvalidRecallQueryError,
    );
  });

  it("긴 본문 발췌는 160자로 제한한다", async () => {
    const repo: RecallSearchPort = {
      search: async () => [
        { id: "m1", rawText: "가".repeat(200), capturedAt: "2026-07-14T12:00:00Z" },
      ],
    };

    const [result] = await searchRecall(repo, "u1", "가");

    expect(result.excerpt).toHaveLength(160);
  });
});

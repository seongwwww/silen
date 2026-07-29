import { describe, expect, it, vi } from "vitest";
import {
  requestTodayDiary,
  type DiaryGenerationQueuePort,
} from "./diaryGeneration";

function stubQueue(): DiaryGenerationQueuePort {
  return {
    enqueue: vi.fn().mockResolvedValue(undefined),
  };
}

describe("requestTodayDiary", () => {
  it("사용자 로컬 오늘 날짜만 큐에 넣는다", async () => {
    const queue = stubQueue();

    const result = await requestTodayDiary(queue, {
      now: new Date("2026-07-28T01:00:00.000Z"),
      timeZone: "America/Los_Angeles",
    });

    expect(queue.enqueue).toHaveBeenCalledWith("2026-07-27");
    expect(result).toEqual({ accepted: true, date: "2026-07-27" });
  });

  it("큐가 중복을 멱등 처리하도록 동일한 날짜 계약을 유지한다", async () => {
    const queue = stubQueue();
    const input = {
      now: new Date("2026-07-28T14:59:59.000Z"),
      timeZone: "Asia/Seoul",
    };

    await requestTodayDiary(queue, input);
    await requestTodayDiary(queue, input);

    expect(queue.enqueue).toHaveBeenNthCalledWith(1, "2026-07-28");
    expect(queue.enqueue).toHaveBeenNthCalledWith(2, "2026-07-28");
  });
});

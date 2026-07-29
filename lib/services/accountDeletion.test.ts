import { describe, expect, it, vi } from "vitest";
import {
  requestAccountDataDeletion,
  type AccountDeletionPort,
} from "./accountDeletion";

describe("전체 기록 삭제 요청", () => {
  it("저장소가 만든 원장 ID를 그대로 반환한다", async () => {
    const port: AccountDeletionPort = {
      request: vi.fn(async () => "deletion-1"),
    };

    await expect(requestAccountDataDeletion(port)).resolves.toEqual({
      id: "deletion-1",
      status: "running",
    });
    expect(port.request).toHaveBeenCalledOnce();
  });
});

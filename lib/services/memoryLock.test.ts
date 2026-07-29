import { describe, expect, it, vi } from "vitest";
import {
  MemoryLockConflictError,
  setMemoryLock,
  type MemoryLockPort,
} from "./memoryLock";

describe("기억 잠금", () => {
  it("읽은 잠금 값을 기대값으로 넘겨 원자적으로 바꾼다", async () => {
    const port: MemoryLockPort = {
      updateLock: vi.fn().mockResolvedValue(true),
    };

    await setMemoryLock(port, "memory-1", true, false);

    expect(port.updateLock).toHaveBeenCalledWith(
      "memory-1",
      true,
      false,
    );
  });

  it("기대값이 달라 0행이면 충돌로 처리한다", async () => {
    const port: MemoryLockPort = {
      updateLock: vi.fn().mockResolvedValue(false),
    };

    await expect(
      setMemoryLock(port, "memory-1", true, false),
    ).rejects.toBeInstanceOf(MemoryLockConflictError);
  });
});

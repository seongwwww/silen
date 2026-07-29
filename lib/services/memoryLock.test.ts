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
      requestDiaryRegeneration: vi.fn().mockResolvedValue(undefined),
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
      requestDiaryRegeneration: vi.fn().mockResolvedValue(undefined),
    };

    await expect(
      setMemoryLock(port, "memory-1", true, false),
    ).rejects.toBeInstanceOf(MemoryLockConflictError);
  });
});

describe("잠근 기억과 이미 만들어진 일기", () => {
  function port(overrides: Partial<MemoryLockPort> = {}): MemoryLockPort {
    return {
      updateLock: async () => true,
      requestDiaryRegeneration: async () => {},
      ...overrides,
    };
  }

  it("잠그면 그 기록을 쓴 일기에 다시 만들기를 요청한다", async () => {
    // 잠금이 탐지·검색에서만 빠지고 이미 쓰인 일기 본문에 원문이 남으면
    // 프라이버시가 반쪽이다(privacy.md).
    const asked: string[] = [];
    await setMemoryLock(
      port({ requestDiaryRegeneration: async (id) => void asked.push(id) }),
      "m1",
      true,
      false,
    );
    expect(asked).toEqual(["m1"]);
  });

  it("잠금을 풀 때는 요청하지 않는다", async () => {
    const asked: string[] = [];
    await setMemoryLock(
      port({ requestDiaryRegeneration: async (id) => void asked.push(id) }),
      "m1",
      false,
      true,
    );
    expect(asked).toEqual([]);
  });

  it("잠금이 안 바뀌었으면 재생성도 요청하지 않는다", async () => {
    const asked: string[] = [];
    await expect(
      setMemoryLock(
        port({
          updateLock: async () => false,
          requestDiaryRegeneration: async (id) => void asked.push(id),
        }),
        "m1",
        true,
        false,
      ),
    ).rejects.toThrow(MemoryLockConflictError);
    expect(asked).toEqual([]);
  });
});

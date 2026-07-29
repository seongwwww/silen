export interface MemoryLockPort {
  updateLock(
    memoryId: string,
    isLocked: boolean,
    expected: boolean,
  ): Promise<boolean>;
}

export class MemoryLockConflictError extends Error {
  constructor() {
    super("기억의 잠금 상태가 이미 바뀌었다");
    this.name = "MemoryLockConflictError";
  }
}

/** 읽은 값을 기대값으로 함께 넘겨 오래된 화면이 새 상태를 덮어쓰지 않게 한다. */
export async function setMemoryLock(
  port: MemoryLockPort,
  memoryId: string,
  isLocked: boolean,
  expected: boolean,
): Promise<void> {
  const changed = await port.updateLock(memoryId, isLocked, expected);
  if (!changed) throw new MemoryLockConflictError();
}

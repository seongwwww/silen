export interface MemoryLockPort {
  updateLock(
    memoryId: string,
    isLocked: boolean,
    expected: boolean,
  ): Promise<boolean>;
  /** 이 기록을 근거로 쓴 일기에 다시 만들기 요청을 남긴다. */
  requestDiaryRegeneration(memoryId: string): Promise<void>;
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

  // 잠금이 탐지·검색에서만 빠지고 이미 쓰인 일기 본문에 원문이 남으면
  // 프라이버시가 반쪽이다. 자동으로 다시 쓰지는 않고 요청만 남긴다 —
  // 다음 워커 주기가 잠긴 기록을 뺀 채로 새로 만든다.
  if (isLocked) await port.requestDiaryRegeneration(memoryId);
}

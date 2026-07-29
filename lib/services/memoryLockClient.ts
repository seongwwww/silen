export type UpdateMemoryLock = (
  memoryId: string,
  isLocked: boolean,
  expected: boolean,
) => Promise<void>;

/** 브라우저 경계에서만 쓰는 잠금 API adapter. */
export const updateMemoryLockInBrowser: UpdateMemoryLock = async (
  memoryId,
  isLocked,
  expected,
) => {
  const response = await fetch(`/api/memories/${encodeURIComponent(memoryId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ isLocked, expected }),
  });
  if (!response.ok) throw new Error(`memory_lock_failed_${response.status}`);
};

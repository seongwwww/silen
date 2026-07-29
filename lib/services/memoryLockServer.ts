import type { SupabaseClient } from "@supabase/supabase-js";
import { createMemoryLockRepository } from "@/lib/repositories/memoryLockRepository";
import { setMemoryLock } from "./memoryLock";

/** Route Handler가 저장소 구현을 직접 알지 않게 하는 서버 합성 facade. */
export async function setMemoryLockForSession(
  client: SupabaseClient,
  memoryId: string,
  isLocked: boolean,
  expected: boolean,
): Promise<void> {
  return setMemoryLock(
    createMemoryLockRepository(client),
    memoryId,
    isLocked,
    expected,
  );
}

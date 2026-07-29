import type { SupabaseClient } from "@supabase/supabase-js";
import type { MemoryLockPort } from "@/lib/services/memoryLock";

/** 세션 RLS와 기대값을 함께 적용하는 잠금 전용 저장소. */
export function createMemoryLockRepository(
  client: SupabaseClient,
): MemoryLockPort {
  return {
    async updateLock(memoryId, isLocked, expected) {
      const { data, error } = await client
        .from("memories")
        .update({ is_locked: isLocked })
        .eq("id", memoryId)
        .eq("is_locked", expected)
        .is("deleted_at", null)
        .select("id");
      if (error) throw error;
      return (data?.length ?? 0) > 0;
    },
  };
}

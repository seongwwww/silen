import type { SupabaseClient } from "@supabase/supabase-js";
import type { MemoryRepository } from "@/lib/services/memory";
import type { TodayMemoryPort } from "@/lib/services/today";

/**
 * authenticated 세션 클라이언트로 MemoryRepository를 구현한다.
 * user_id는 세션에서 오고 RLS with-check가 위조를 막으므로 service_role을
 * 쓰지 않는다. emotion·asset은 부모 경유 RLS로 검증된다.
 */
export function createMemoryRepository(
  client: SupabaseClient,
): MemoryRepository & TodayMemoryPort {
  return {
    async insertMemory(row) {
      const { data, error } = await client
        .from("memories")
        .insert({
          user_id: row.userId,
          raw_text: row.rawText,
          occurred_at: row.occurredAt,
          source_type: "manual",
          memory_type: "moment",
        })
        .select("id")
        .single();
      if (error) throw error;
      return { id: data.id as string };
    },

    async insertEmotion(row) {
      const { error } = await client
        .from("emotions")
        .insert({ memory_id: row.memoryId, valence: row.valence, confirmed_by_user: true });
      if (error) throw error;
    },

    async insertAsset(row) {
      const { error } = await client.from("assets").insert({
        memory_id: row.memoryId,
        asset_type: "photo",
        file_url: row.fileUrl,
        mime_type: row.mimeType,
      });
      if (error) throw error;
    },

    async listBetween(start, end) {
      const { data, error } = await client
        .from("memories")
        .select("id, raw_text, effective_at")
        .gte("effective_at", start)
        .lt("effective_at", end)
        .is("deleted_at", null)
        .eq("is_locked", false)
        .not("raw_text", "is", null)
        .neq("raw_text", "")
        .order("effective_at", { ascending: false });
      if (error) throw error;
      return (data ?? []).map((row) => ({
        id: row.id as string,
        rawText: row.raw_text as string,
        capturedAt: row.effective_at as string,
      }));
    },

    async listActiveCapturedAt() {
      const { data, error } = await client
        .from("memories")
        .select("effective_at")
        .is("deleted_at", null)
        .eq("is_locked", false)
        .not("raw_text", "is", null)
        .neq("raw_text", "");
      if (error) throw error;
      return (data ?? []).map((row) => row.effective_at as string);
    },

  };
}

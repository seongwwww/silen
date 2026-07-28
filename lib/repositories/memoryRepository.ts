import type { SupabaseClient } from "@supabase/supabase-js";
import type { MemoryRepository } from "@/lib/services/memory";
import {
  RECALL_RESULT_LIMIT,
  type RecallSearchPort,
} from "@/lib/services/recall";
import type { TodayMemoryPort } from "@/lib/services/today";

function escapeIlikeLiteral(value: string): string {
  return value.replaceAll("\\", "\\\\").replaceAll("%", "\\%").replaceAll("_", "\\_");
}

/**
 * authenticated 세션 클라이언트로 MemoryRepository를 구현한다.
 * user_id는 세션에서 오고 RLS with-check가 위조를 막으므로 service_role을
 * 쓰지 않는다. emotion·asset은 부모 경유 RLS로 검증된다.
 */
export function createMemoryRepository(
  client: SupabaseClient,
): MemoryRepository & TodayMemoryPort & RecallSearchPort {
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
        .select("id, raw_text, captured_at")
        .gte("captured_at", start)
        .lt("captured_at", end)
        .is("deleted_at", null)
        .eq("is_locked", false)
        .not("raw_text", "is", null)
        .neq("raw_text", "")
        .order("captured_at", { ascending: false });
      if (error) throw error;
      return (data ?? []).map((row) => ({
        id: row.id as string,
        rawText: row.raw_text as string,
        capturedAt: row.captured_at as string,
      }));
    },

    async listActiveCapturedAt() {
      const { data, error } = await client
        .from("memories")
        .select("captured_at")
        .is("deleted_at", null)
        .eq("is_locked", false)
        .not("raw_text", "is", null)
        .neq("raw_text", "");
      if (error) throw error;
      return (data ?? []).map((row) => row.captured_at as string);
    },

    async search(userId, query) {
      const pattern = `%${escapeIlikeLiteral(query)}%`;
      const { data, error } = await client
        .from("memories")
        .select("id, raw_text, captured_at")
        .eq("user_id", userId)
        .is("deleted_at", null)
        .eq("is_locked", false)
        .not("raw_text", "is", null)
        .ilike("raw_text", pattern)
        .order("captured_at", { ascending: false })
        .limit(RECALL_RESULT_LIMIT);
      if (error) throw error;
      return (data ?? []).map((row) => ({
        id: row.id as string,
        rawText: row.raw_text as string,
        capturedAt: row.captured_at as string,
      }));
    },
  };
}

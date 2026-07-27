import type { SupabaseClient } from "@supabase/supabase-js";
import type { DiffStatus, ReviewItem } from "@/lib/services/difference";

const MAX_EVIDENCE = 3;

/** 세션 클라이언트로 차이를 조회/수정한다. RLS(user_id=auth.uid())가 소유권을 강제하므로
 * service_role을 쓰지 않는다. */
export function createDifferenceRepository(client: SupabaseClient) {
  return {
    /** 기대한 현재 상태(expected)일 때만 원자적으로 바꾼다. 읽기와 쓰기 사이에
     * 다른 요청이 상태를 바꾸면(TOCTOU) 0행이 되어 전이 규칙 우회를 차단한다.
     * 타인 차이도 RLS로 0행. */
    async updateStatus(id: string, status: DiffStatus, expected: DiffStatus): Promise<boolean> {
      const { data, error } = await client
        .from("differences")
        .update({ status })
        .eq("id", id)
        .eq("status", expected)
        .select("id");
      if (error) throw error;
      return (data?.length ?? 0) > 0;
    },

    async listCandidatesForReview(): Promise<ReviewItem[]> {
      const { data, error } = await client
        .from("differences")
        .select(
          "id, category, difference_narrations!inner(headline), difference_evidence(memories(raw_text, is_locked, deleted_at))",
        )
        .eq("status", "candidate")
        .eq("evidence_state", "intact")
        .order("date", { ascending: false });
      if (error) throw error;
      return (data ?? []).map((row) => {
        const headline = (row.difference_narrations as { headline: string }[] | { headline: string })
          ? (Array.isArray(row.difference_narrations)
              ? row.difference_narrations[0]?.headline
              : (row.difference_narrations as { headline: string }).headline) ?? ""
          : "";
        const evidence = ((row.difference_evidence ?? []) as unknown as {
          memories: { raw_text: string | null; is_locked: boolean; deleted_at: string | null } | null;
        }[])
          .map((e) => e.memories)
          .filter((m): m is { raw_text: string; is_locked: boolean; deleted_at: string | null } =>
            !!m && !m.is_locked && !m.deleted_at && !!m.raw_text && m.raw_text.trim().length > 0)
          .map((m) => m.raw_text.trim())
          .slice(0, MAX_EVIDENCE);
        return { id: row.id as string, headline, category: row.category as string, evidence };
      });
    },
  };
}

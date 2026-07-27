import type { SupabaseClient } from "@supabase/supabase-js";
import type { DiaryView } from "@/lib/services/diary";

type SectionRow = { section_type: string; content: string };
type SourceRow = {
  memories: {
    raw_text: string | null;
    is_locked: boolean;
    deleted_at: string | null;
  } | null;
};

/** 세션 클라이언트로 일기를 조회한다. RLS(diaries=본인, sections/sources=부모 소유자)가
 * 소유권을 강제하므로 service_role을 쓰지 않는다. */
export function createDiaryRepository(client: SupabaseClient) {
  return {
    /** 가장 최근 일기 하나. run-diary는 '어제'를 대상으로 돌기 때문에
     * 오늘 날짜로 찾지 않고 최신 하나를 가져온다. */
    async findLatest(): Promise<DiaryView | null> {
      const { data, error } = await client
        .from("diaries")
        .select(
          "date, status, generated_text, edited_text, " +
            "diary_sections(section_type, content), " +
            "diary_sources(memories(raw_text, is_locked, deleted_at))",
        )
        .order("date", { ascending: false })
        .limit(1);
      if (error) throw error;
      const row = data?.[0];
      if (!row) return null;

      const sections = (row.diary_sections ?? []) as unknown as SectionRow[];
      const sources = (row.diary_sources ?? []) as unknown as SourceRow[];

      return {
        date: row.date as string,
        oneLine:
          sections.find((section) => section.section_type === "오늘의한문장")
            ?.content ?? "",
        body:
          (row.edited_text as string | null) ??
          (row.generated_text as string | null) ??
          "",
        differences: sections
          .filter((section) => section.section_type === "다른점")
          .map((section) => section.content),
        // 잠긴·삭제된·빈 메모는 노출하지 않는다(privacy.md).
        evidence: sources
          .map((source) => source.memories)
          .filter(
            (
              memory,
            ): memory is {
              raw_text: string;
              is_locked: boolean;
              deleted_at: string | null;
            } =>
              !!memory &&
              !memory.is_locked &&
              !memory.deleted_at &&
              !!memory.raw_text &&
              memory.raw_text.trim().length > 0,
          )
          .map((memory) => memory.raw_text),
        isEdited: (row.status as string) !== "draft",
      };
    },

    /** 일기 재료가 될 수 있는 기록이 하나라도 있는가.
     * '기록도 없음'과 '기록은 있는데 일기가 아직 없음'을 가르는 데만 쓴다. */
    async hasAnyMemory(): Promise<boolean> {
      const { data, error } = await client
        .from("memories")
        .select("id")
        .is("deleted_at", null)
        .eq("is_locked", false)
        .not("raw_text", "is", null)
        .neq("raw_text", "")
        .limit(1);
      if (error) throw error;
      return (data?.length ?? 0) > 0;
    },
  };
}

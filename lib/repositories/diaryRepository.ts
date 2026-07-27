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

// `as const`로 리터럴 타입을 유지한다. 문자열을 `+`로 이어붙이거나 리터럴
// 타입을 잃으면 supabase-js의 select 타입 추론이 깨져 row.diary_sections가
// GenericStringError가 된다(tsc에서만 드러남).
const DIARY_SELECT =
  "date, status, generated_text, edited_text, diary_sections(section_type, content), diary_sources(memories(raw_text, is_locked, deleted_at))" as const;

/** 조회 행 하나를 표시용 뷰로 옮긴다. findLatest·findByDate가 공유한다. */
function toDiaryView(row: {
  date: unknown;
  status: unknown;
  generated_text: unknown;
  edited_text: unknown;
  diary_sections: unknown;
  diary_sources: unknown;
}): DiaryView {
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
}

/** 세션 클라이언트로 일기를 조회한다. RLS(diaries=본인, sections/sources=부모 소유자)가
 * 소유권을 강제하므로 service_role을 쓰지 않는다. */
export function createDiaryRepository(client: SupabaseClient) {
  return {
    /** 가장 최근 일기 하나. run-diary는 '어제'를 대상으로 돌기 때문에
     * 오늘 날짜로 찾지 않고 최신 하나를 가져온다. */
    async findLatest(): Promise<DiaryView | null> {
      const { data, error } = await client
        .from("diaries")
        .select(DIARY_SELECT)
        .order("date", { ascending: false })
        .limit(1);
      if (error) throw error;
      const row = data?.[0];
      return row ? toDiaryView(row) : null;
    },

    /** 그 날짜의 일기. 없으면 null(호출자가 404로 처리한다). */
    async findByDate(date: string): Promise<DiaryView | null> {
      const { data, error } = await client
        .from("diaries")
        .select(DIARY_SELECT)
        .eq("date", date)
        .limit(1);
      if (error) throw error;
      const row = data?.[0];
      return row ? toDiaryView(row) : null;
    },

    /** 기준 날짜의 앞뒤로 **실제 일기가 있는** 날짜. 날짜-1이 아니라
     * 존재하는 일기로 점프하기 위한 것이다(빈 날엔 일기가 없다). */
    async findNeighborDates(
      date: string,
    ): Promise<{ prev: string | null; next: string | null }> {
      const [prevResult, nextResult] = await Promise.all([
        client
          .from("diaries")
          .select("date")
          .lt("date", date)
          .order("date", { ascending: false })
          .limit(1),
        client
          .from("diaries")
          .select("date")
          .gt("date", date)
          .order("date", { ascending: true })
          .limit(1),
      ]);
      if (prevResult.error) throw prevResult.error;
      if (nextResult.error) throw nextResult.error;
      return {
        prev: (prevResult.data?.[0]?.date as string | undefined) ?? null,
        next: (nextResult.data?.[0]?.date as string | undefined) ?? null,
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

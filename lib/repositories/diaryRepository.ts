import type { SupabaseClient } from "@supabase/supabase-js";
import type { DiaryStatus, DiaryView } from "@/lib/services/diary";

type SectionRow = { id: string; section_type: string; content: string };
type SourceRow = {
  memories: {
    id: string;
    raw_text: string | null;
    is_locked: boolean;
    deleted_at: string | null;
    assets: { file_url: string; asset_type: string }[] | null;
  } | null;
};

// `as const`로 리터럴 타입을 유지한다. 문자열을 `+`로 이어붙이거나 리터럴
// 타입을 잃으면 supabase-js의 select 타입 추론이 깨져 row.diary_sections가
// GenericStringError가 된다(tsc에서만 드러남).
const DIARY_SELECT =
  "id, date, status, generated_text, edited_text, tone_instruction, regenerate_requested_at, regenerate_reason, diary_sections(id, section_type, content), diary_sources(memories(id, raw_text, is_locked, deleted_at, assets(file_url, asset_type)))" as const;

const SIGNED_URL_TTL_SECONDS = 60 * 10;

/** 근거 사진에 서명 URL을 붙인다. 버킷이 비공개라 경로만으로는 못 본다.
 * 짧게 만료시켜 URL이 새어도 오래 쓰이지 않게 한다. */
async function withPhotoUrls(
  client: SupabaseClient,
  view: DiaryView,
): Promise<DiaryView> {
  const paths = view.evidence
    .map((item) => item.photoPath)
    .filter((path): path is string => path !== null);
  if (paths.length === 0) return view;

  const { data } = await client.storage
    .from("memories")
    .createSignedUrls(paths, SIGNED_URL_TTL_SECONDS);
  const urlByPath = new Map(
    (data ?? []).map((entry) => [entry.path ?? "", entry.signedUrl]),
  );

  return {
    ...view,
    evidence: view.evidence.map((item) => ({
      ...item,
      photoUrl: item.photoPath ? (urlByPath.get(item.photoPath) ?? null) : null,
    })),
  };
}

/** 조회 행 하나를 표시용 뷰로 옮긴다. findLatest·findByDate가 공유한다. */
function toDiaryView(row: {
  id: unknown;
  date: unknown;
  status: unknown;
  generated_text: unknown;
  edited_text: unknown;
  tone_instruction: unknown;
  regenerate_requested_at: unknown;
  regenerate_reason: unknown;
  diary_sections: unknown;
  diary_sources: unknown;
}): DiaryView {
  const sections = (row.diary_sections ?? []) as unknown as SectionRow[];
  const sources = (row.diary_sources ?? []) as unknown as SourceRow[];

  return {
    id: row.id as string,
    date: row.date as string,
    status: (row.status as DiaryStatus) ?? "draft",
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
    // 잠긴·삭제된 메모는 노출하지 않는다(privacy.md).
    // 사진만 있는 기록도 근거다 — 글이 없다고 빼지 않는다.
    evidence: sources
      .map((source) => source.memories)
      .filter(
        (
          memory,
        ): memory is {
          id: string;
          raw_text: string | null;
          is_locked: boolean;
          deleted_at: string | null;
          assets: { file_url: string; asset_type: string }[] | null;
        } => !!memory && !memory.is_locked && !memory.deleted_at,
      )
      .map((memory) => ({
        memoryId: memory.id,
        text: memory.raw_text?.trim() ? memory.raw_text : null,
        photoPath:
          (memory.assets ?? []).find((asset) => asset.asset_type === "photo")
            ?.file_url ?? null,
      }))
      .filter((item) => item.text !== null || item.photoPath !== null),
    isEdited: (row.status as string) !== "draft",
    question: (() => {
      const found = sections.find((section) => section.section_type === "질문");
      return found ? { sectionId: found.id, text: found.content } : null;
    })(),
    toneInstruction: (row.tone_instruction as string | null) ?? null,
    regenerateRequested: row.regenerate_requested_at != null,
    regenerateReason: (row.regenerate_reason as string | null) ?? null,
  };
}

/** 세션 클라이언트로 일기를 조회한다. RLS(diaries=본인, sections/sources=부모 소유자)가
 * 소유권을 강제하므로 service_role을 쓰지 않는다. */
export function createDiaryRepository(client: SupabaseClient) {
  return {
    /** 인증 세션의 사용자 로컬 날짜에 대한 생성 작업을 요청한다.
     * RPC는 auth.uid()로 소유자를 정하고 중복 요청을 멱등 처리한다. */
    async enqueue(date: string): Promise<void> {
      const { error } = await client.rpc("request_diary_generation", {
        target_date: date,
      });
      if (error) throw error;
    },

    async findGenerationRequest(date: string): Promise<{
      status: "queued" | "processing" | "done" | "failed";
    } | null> {
      const { data, error } = await client
        .from("diary_generation_requests")
        .select("status")
        .eq("date", date)
        .limit(1);
      if (error) throw error;
      const status = data?.[0]?.status as
        | "queued"
        | "processing"
        | "done"
        | "failed"
        | undefined;
      return status ? { status } : null;
    },

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
      return row ? withPhotoUrls(client, toDiaryView(row)) : null;
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
      return row ? withPhotoUrls(client, toDiaryView(row)) : null;
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

    /** 기록 화면이 질문을 맥락으로 보여줄 때 쓴다. RLS가 소유권을 강제한다. */
    async findQuestionById(sectionId: string): Promise<string | null> {
      const { data, error } = await client
        .from("diary_sections")
        .select("content")
        .eq("id", sectionId)
        .eq("section_type", "질문")
        .limit(1);
      if (error) throw error;
      return (data?.[0]?.content as string | undefined) ?? null;
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

    /** 편집 본문과 상태를 함께 바꾼다. 기대 상태와 다르면 0행 → false(TOCTOU).
     * generated_text(AI 초안)는 절대 건드리지 않는다 — 원본↔생성물 분리. */
    async updateDraft(
      id: string,
      editedText: string,
      status: DiaryStatus,
      expected: DiaryStatus,
    ): Promise<boolean> {
      const { data, error } = await client
        .from("diaries")
        .update({ edited_text: editedText, status })
        .eq("id", id)
        .eq("status", expected)
        .select("id");
      if (error) throw error;
      return (data?.length ?? 0) > 0;
    },

    /** 상태만 바꾼다(본문 수정 없이 확정·되돌리기). */
    async updateStatus(
      id: string,
      status: DiaryStatus,
      expected: DiaryStatus,
    ): Promise<boolean> {
      const { data, error } = await client
        .from("diaries")
        .update({ status })
        .eq("id", id)
        .eq("status", expected)
        .select("id");
      if (error) throw error;
      return (data?.length ?? 0) > 0;
    },

    /** 재생성 요청을 남긴다. 다음 생성이 1회 소비한다. */
    async requestRegenerate(
      id: string,
      toneInstruction: string | null,
    ): Promise<boolean> {
      const { data, error } = await client
        .from("diaries")
        .update({
          tone_instruction: toneInstruction,
          regenerate_requested_at: new Date().toISOString(),
          // 사용자가 누른 요청이다. 늦은 기록 유입과 화면에서 다르게 말한다.
          regenerate_reason: "user",
        })
        .eq("id", id)
        .select("id");
      if (error) throw error;
      return (data?.length ?? 0) > 0;
    },
  };
}

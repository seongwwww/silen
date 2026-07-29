import type { SupabaseClient } from "@supabase/supabase-js";
import { localDateFor, utcRangeForLocalDate } from "@/lib/time/day";

export type WeeklySlot = "가장많이한것" | "처음한것" | "감정순간";

export type WeeklyHighlightView = {
  headline: string;
  detail: string;
};

export type WeeklyReportView = {
  id: string;
  weekStart: string;
  weekEnd: string;
  days: {
    date: string;
    count: number;
    isSurprising: boolean;
  }[];
  highlights: Record<WeeklySlot, WeeklyHighlightView | null>;
};

type HighlightRow = {
  slot: WeeklySlot;
  rank: number;
  differences:
    | {
        date: string;
        description: string | null;
        confidence: number | null;
        entities: { name: string } | { name: string }[] | null;
        difference_narrations:
          | { headline: string; body: string }
          | { headline: string; body: string }[]
          | null;
      }
    | {
        date: string;
        description: string | null;
        confidence: number | null;
        entities: { name: string } | { name: string }[] | null;
        difference_narrations:
          | { headline: string; body: string }
          | { headline: string; body: string }[]
          | null;
      }[]
    | null;
};

const HIGHLIGHT_SELECT =
  "slot, rank, differences!inner(date, description, confidence, entities(name), difference_narrations(headline, body))" as const;

const SLOTS: WeeklySlot[] = ["가장많이한것", "처음한것", "감정순간"];

function addUtcDays(date: string, days: number): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date);
  if (!match) throw new Error("주간 리포트 시작 날짜가 올바르지 않아요.");
  const value = new Date(
    Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3]) + days),
  );
  return value.toISOString().slice(0, 10);
}

function firstRelation<T>(value: T | T[] | null): T | null {
  return Array.isArray(value) ? (value[0] ?? null) : value;
}

function toHighlight(
  slot: WeeklySlot,
  row: HighlightRow,
): WeeklyHighlightView | null {
  const difference = firstRelation(row.differences);
  if (!difference) return null;
  const entity = firstRelation(difference.entities);
  const narration = firstRelation(difference.difference_narrations);
  const headline =
    narration?.headline.trim() ||
    entity?.name.trim() ||
    (slot === "감정순간" ? "감정 기록이 크게 달랐던 날" : "");
  if (!headline) return null;

  const description = difference.description?.trim() ?? "";
  const countMatch = /^7일 기록에서 (\d+)회 언급$/.exec(description);
  const detail =
    narration?.body.trim() ||
    (slot === "처음한것"
      ? "이번 7일 기록에 처음 등장했어요."
      : countMatch
        ? `7일 기록에서 ${countMatch[1]}번 언급됐어요.`
      : description);
  return {
    headline,
    detail: detail || "이번 7일 기록에서 찾았어요.",
  };
}

/** 인증 세션 클라이언트로 최신 주간 리포트를 읽는다.
 * 직접 user_id 필터와 RLS를 함께 적용하고, stale·dismissed 차이는 소비하지 않는다. */
export function createWeeklyRepository(client: SupabaseClient) {
  return {
    async findLatest(
      userId: string,
      timeZone: string,
    ): Promise<WeeklyReportView | null> {
      const { data: reports, error: reportError } = await client
        .from("weekly_reports")
        .select("id, week")
        .eq("user_id", userId)
        .order("week", { ascending: false })
        .limit(1);
      if (reportError) throw reportError;
      const report = reports?.[0];
      if (!report) return null;

      const reportId = report.id as string;
      const weekStart = report.week as string;
      const weekEnd = addUtcDays(weekStart, 6);
      const exclusiveEnd = addUtcDays(weekStart, 7);
      const startInstant = utcRangeForLocalDate(weekStart, timeZone).start;
      const endInstant = utcRangeForLocalDate(exclusiveEnd, timeZone).start;

      const [highlightResult, memoryResult, differenceResult] =
        await Promise.all([
          client
            .from("weekly_report_highlights")
            .select(HIGHLIGHT_SELECT)
            .eq("report_id", reportId)
            .eq("differences.user_id", userId)
            .eq("differences.evidence_state", "intact")
            .neq("differences.status", "dismissed")
            .order("rank", { ascending: true }),
          client
            .from("memories")
            .select("effective_at")
            .eq("user_id", userId)
            .gte("effective_at", startInstant)
            .lt("effective_at", endInstant)
            .is("deleted_at", null)
            .eq("is_locked", false),
          client
            .from("differences")
            .select("date, confidence")
            .eq("user_id", userId)
            .eq("evidence_state", "intact")
            .neq("status", "dismissed")
            .neq("detection_method", "pattern")
            .gte("date", weekStart)
            .lt("date", exclusiveEnd)
            .not("confidence", "is", null),
        ]);
      if (highlightResult.error) throw highlightResult.error;
      if (memoryResult.error) throw memoryResult.error;
      if (differenceResult.error) throw differenceResult.error;

      const counts = new Map<string, number>();
      for (const row of memoryResult.data ?? []) {
        const date = localDateFor(
          new Date(row.effective_at as string),
          timeZone,
        );
        counts.set(date, (counts.get(date) ?? 0) + 1);
      }

      const confidenceRows = (differenceResult.data ?? []) as {
        date: string;
        confidence: number;
      }[];
      const maxConfidence =
        confidenceRows.length > 0
          ? Math.max(...confidenceRows.map((row) => row.confidence))
          : null;
      const surprisingDates = new Set(
        maxConfidence == null
          ? []
          : confidenceRows
              .filter((row) => row.confidence === maxConfidence)
              .map((row) => row.date),
      );

      const rows = (highlightResult.data ?? []) as unknown as HighlightRow[];
      const highlights: Record<WeeklySlot, WeeklyHighlightView | null> = {
        가장많이한것: null,
        처음한것: null,
        감정순간: null,
      };
      for (const slot of SLOTS) {
        const row = rows.find((item) => item.slot === slot);
        highlights[slot] = row ? toHighlight(slot, row) : null;
      }

      return {
        id: reportId,
        weekStart,
        weekEnd,
        days: Array.from({ length: 7 }, (_, index) => {
          const date = addUtcDays(weekStart, index);
          return {
            date,
            count: counts.get(date) ?? 0,
            isSurprising: surprisingDates.has(date),
          };
        }),
        highlights,
      };
    },
  };
}

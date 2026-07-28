import { localDateFor, utcRangeForLocalDate } from "@/lib/time/day";

export type TodayMemory = {
  id: string;
  rawText: string;
  capturedAt: string;
};

export type TodayDifference = {
  id: string;
  headline: string;
  category: string;
  evidence: string[];
};

export interface TodayMemoryPort {
  listBetween(start: string, end: string): Promise<TodayMemory[]>;
  listActiveCapturedAt(): Promise<string[]>;
}

export interface TodayDifferencePort {
  listForDate(date: string): Promise<TodayDifference[]>;
}

export interface TodayDiaryPort {
  findByDate(date: string): Promise<{ id: string; oneLine: string } | null>;
  findGenerationRequest(
    date: string,
  ): Promise<
    { status: "queued" | "processing" | "done" | "failed" } | null
  >;
}

export type TodayView = {
  dateIso: string;
  dateLabel: string;
  isLearning: boolean;
  differences: TodayDifference[];
  memories: {
    count: number;
    previews: string[];
  };
  diary:
    | { state: "quiet" }
    | { state: "processing" }
    | { state: "ready"; id: string; oneLine: string };
  wrap:
    | { state: "none" }
    | {
        state:
          | "available"
          | "closing"
          | "discovery"
          | "requested"
          | "processing"
          | "failed";
        title: string;
        body: string;
      }
    | {
        state: "arrived";
        label: "DAILY WRAP";
        title: string;
        body: string;
      };
};

type BuildTodayViewInput = {
  now: Date;
  timeZone: string;
  memory: TodayMemoryPort;
  difference: TodayDifferencePort;
  diary: TodayDiaryPort;
  diaryTime?: string;
};

function preview(text: string): string {
  return Array.from(text.replace(/\s+/g, " ").trim()).slice(0, 20).join("");
}

function localTimeFor(instant: Date, timeZone: string): string {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone,
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(instant);
  const hour = parts.find((part) => part.type === "hour")?.value ?? "00";
  const minute = parts.find((part) => part.type === "minute")?.value ?? "00";
  return `${hour}:${minute}`;
}

export async function buildTodayView({
  now,
  timeZone,
  memory,
  difference,
  diary,
  diaryTime = "22:00",
}: BuildTodayViewInput): Promise<TodayView> {
  const dateIso = localDateFor(now, timeZone);
  const range = utcRangeForLocalDate(dateIso, timeZone);

  const [
    memories,
    activeCapturedAt,
    differences,
    todayDiary,
    generationRequest,
  ] =
    await Promise.all([
      memory.listBetween(range.start, range.end),
      memory.listActiveCapturedAt(),
      difference.listForDate(dateIso),
      diary.findByDate(dateIso),
      diary.findGenerationRequest(dateIso),
    ]);

  const activeDays = new Set(
    activeCapturedAt.map((capturedAt) =>
      localDateFor(new Date(capturedAt), timeZone),
    ),
  );
  const isLearning = activeDays.size < 3;
  const visibleDifferences = isLearning ? [] : differences;
  const wrap: TodayView["wrap"] = todayDiary
    ? {
        state: "arrived",
        label: "DAILY WRAP",
        title: "오늘의 일기가 도착했어요",
        body: `오늘 남긴 ${memories.length}개의 기록을 한 편으로 묶었어요.`,
      }
    : generationRequest?.status === "queued"
      ? {
          state: "requested",
          title: "일기 만들기를 요청했어요",
          body: "완성되면 이 화면에서 바로 보여드릴게요.",
        }
      : generationRequest?.status === "processing"
        ? {
            state: "processing",
            title: "오늘 기록을 한 편으로 묶고 있어요",
            body: "실제 생성 작업이 진행 중이에요.",
          }
        : generationRequest?.status === "failed"
          ? {
              state: "failed",
              title: "일기를 만들지 못했어요",
              body: "잠시 후 다시 시도할 수 있어요.",
            }
          : visibleDifferences.length > 0
      ? {
          state: "discovery",
          title: "기록에서 눈에 띄는 차이를 찾았어요",
          body: visibleDifferences[0].headline,
        }
          : memories.length === 0
            ? { state: "none" }
            : localTimeFor(now, timeZone) >= diaryTime.slice(0, 5)
              ? {
                  state: "closing",
                  title: "오늘을 정리할 시간이에요",
                  body: `지금까지 남긴 ${memories.length}개의 기록으로 일기를 만들 수 있어요.`,
                }
              : {
                  state: "available",
                  title: "오늘 기록으로 일기를 만들 수 있어요",
                  body: `${memories.length}개의 기록을 한 편으로 묶어볼까요?`,
                };

  return {
    dateIso,
    dateLabel: new Intl.DateTimeFormat("ko-KR", {
      timeZone,
      month: "long",
      day: "numeric",
      weekday: "long",
    }).format(now),
    isLearning,
    differences: visibleDifferences,
    memories: {
      count: memories.length,
      previews: memories.slice(0, 3).map((item) => preview(item.rawText)),
    },
    diary: todayDiary
      ? {
          state: "ready",
          id: todayDiary.id,
          oneLine: todayDiary.oneLine,
        }
      : memories.length === 0
        ? { state: "quiet" }
        : { state: "processing" },
    wrap,
  };
}

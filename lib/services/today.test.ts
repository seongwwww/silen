import { describe, expect, it } from "vitest";
import {
  buildTodayView,
  type TodayDiaryPort,
  type TodayDifferencePort,
  type TodayMemoryPort,
  previewOf,
} from "./today";

const NOW = new Date("2026-07-22T03:00:00.000Z");
const TIME_ZONE = "Asia/Seoul";

function ports({
  memories = [],
  activeCapturedAt = [],
  differences = [],
  diary = null,
  generationRequest = null,
}: {
  memories?: { id: string; rawText: string; capturedAt: string }[];
  activeCapturedAt?: string[];
  differences?: {
    id: string;
    headline: string;
    category: string;
    evidence: string[];
  }[];
  diary?: { id: string; oneLine: string } | null;
  generationRequest?: {
    status: "queued" | "processing" | "done" | "failed";
  } | null;
} = {}): {
  memory: TodayMemoryPort;
  difference: TodayDifferencePort;
  diary: TodayDiaryPort;
} {
  return {
    memory: {
      listBetween: async () => memories,
      listActiveCapturedAt: async () => activeCapturedAt,
    },
    difference: {
      listForDate: async () => differences,
    },
    diary: {
      findByDate: async () => diary,
      findGenerationRequest: async () => generationRequest,
    },
  };
}

describe("buildTodayView", () => {
  it("메모가 없으면 조용한 상태를 만든다", async () => {
    const view = await buildTodayView({
      now: NOW,
      timeZone: TIME_ZONE,
      ...ports(),
    });

    expect(view.dateIso).toBe("2026-07-22");
    expect(view.dateLabel).toBe("7월 22일 수요일");
    expect(view.memories).toEqual({ count: 0, previews: [] });
    expect(view.diary).toEqual({ state: "quiet" });
    expect(view.wrap).toEqual({ state: "none" });
  });

  it("관측 활성일이 3일 미만이면 학습 중으로 표시한다", async () => {
    const view = await buildTodayView({
      now: NOW,
      timeZone: TIME_ZONE,
      ...ports({
        activeCapturedAt: [
          "2026-07-21T03:00:00.000Z",
          "2026-07-22T03:00:00.000Z",
        ],
        differences: [
          {
            id: "diff-1",
            headline: "표시하면 안 되는 후보",
            category: "오늘의다른점",
            evidence: [],
          },
        ],
      }),
    });

    expect(view.isLearning).toBe(true);
    expect(view.differences).toEqual([]);
  });

  it("오늘 메모의 개수와 20자 미리보기를 만든다", async () => {
    const view = await buildTodayView({
      now: NOW,
      timeZone: TIME_ZONE,
      ...ports({
        memories: [
          {
            id: "mem-1",
            rawText: "  아주   긴 오늘 기록은 스무 글자까지만 차분하게 보여준다  ",
            capturedAt: "2026-07-22T02:00:00.000Z",
          },
          {
            id: "mem-2",
            rawText: "두 번째 기록",
            capturedAt: "2026-07-22T01:00:00.000Z",
          },
        ],
        activeCapturedAt: [
          "2026-07-20T03:00:00.000Z",
          "2026-07-21T03:00:00.000Z",
          "2026-07-22T03:00:00.000Z",
        ],
      }),
    });

    expect(view.memories.count).toBe(2);
    expect(view.memories.previews[0]).toBe(
      "아주 긴 오늘 기록은 스무 글자까지만",
    );
    expect(view.diary).toEqual({
      state: "processing",
      message: "오늘 밤 9시에 묶어드릴게요",
    });
  });

  it("설정한 시각을 홈의 자동 일기 문구에 넣는다", async () => {
    const view = await buildTodayView({
      now: NOW,
      timeZone: TIME_ZONE,
      diaryHour: 21,
      ...ports({
        memories: [
          {
            id: "mem-1",
            rawText: "오늘 기록",
            capturedAt: "2026-07-22T02:00:00.000Z",
          },
        ],
      }),
    });

    expect(view.diary).toEqual({
      state: "processing",
      message: "오늘 밤 9시에 묶어드릴게요",
    });
  });

  it("관측 3일째부터 오늘 차이를 보여준다", async () => {
    const difference = {
      id: "diff-1",
      headline: "운동 이야기가 오늘 기록에는 없었어요",
      category: "오늘의다른점",
      evidence: [],
    };
    const view = await buildTodayView({
      now: NOW,
      timeZone: TIME_ZONE,
      ...ports({
        activeCapturedAt: [
          "2026-07-20T03:00:00.000Z",
          "2026-07-21T03:00:00.000Z",
          "2026-07-22T03:00:00.000Z",
        ],
        differences: [difference],
      }),
    });

    expect(view.isLearning).toBe(false);
    expect(view.differences).toEqual([difference]);
    expect(view.wrap).toEqual({
      state: "discovery",
      title: "기록에서 눈에 띄는 차이를 찾았어요",
      body: "운동 이야기가 오늘 기록에는 없었어요",
    });
  });

  it("오늘 일기가 있으면 한 줄과 함께 ready 상태를 만든다", async () => {
    const view = await buildTodayView({
      now: NOW,
      timeZone: TIME_ZONE,
      ...ports({
        memories: [
          {
            id: "mem-1",
            rawText: "오늘 기록",
            capturedAt: "2026-07-22T02:00:00.000Z",
          },
        ],
        diary: { id: "diary-1", oneLine: "조용하지만 조금 달랐던 하루" },
      }),
    });

    expect(view.diary).toEqual({
      state: "ready",
      id: "diary-1",
      oneLine: "조용하지만 조금 달랐던 하루",
    });
    expect(view.wrap).toEqual({
      state: "arrived",
      label: "DAILY WRAP",
      title: "오늘의 일기가 도착했어요",
      body: "오늘 남긴 1개의 기록을 한 편으로 묶었어요.",
    });
  });

  it("사용자가 정한 일기 시간이 지나면 하루 마감 상태를 만든다", async () => {
    const view = await buildTodayView({
      now: new Date("2026-07-22T14:00:00.000Z"),
      timeZone: TIME_ZONE,
      diaryHour: 22,
      ...ports({
        memories: [
          {
            id: "mem-1",
            rawText: "오늘 기록",
            capturedAt: "2026-07-22T13:00:00.000Z",
          },
        ],
      }),
    });

    expect(view.wrap).toEqual({
      state: "closing",
      title: "오늘을 정리할 시간이에요",
      body: "지금까지 남긴 1개의 기록으로 일기를 만들 수 있어요.",
    });
  });

  it("수동 생성 요청이 큐에 있으면 추측 없이 요청 상태를 보여준다", async () => {
    const view = await buildTodayView({
      now: NOW,
      timeZone: TIME_ZONE,
      ...ports({
        memories: [
          {
            id: "mem-1",
            rawText: "오늘 기록",
            capturedAt: "2026-07-22T02:00:00.000Z",
          },
        ],
        generationRequest: { status: "queued" },
      }),
    });

    expect(view.wrap).toEqual({
      state: "requested",
      title: "일기 만들기를 요청했어요",
      body: "완성되면 이 화면에서 바로 보여드릴게요.",
    });
  });
});

describe("사진만 남긴 기록", () => {
  it("빈 줄 대신 사진이 있다고 알려준다", () => {
    // 사진만 남기면 rawText가 비어 미리보기가 빈 줄이 된다.
    // 남긴 것이 화면에서 사라진 것처럼 보인다.
    expect(previewOf("")).toBe("사진 한 장");
    expect(previewOf("   ")).toBe("사진 한 장");
  });

  it("글이 있으면 글을 보여준다", () => {
    expect(previewOf("퇴근길에 카페")).toBe("퇴근길에 카페");
  });
});

import type { TodayView } from "@/lib/services/today";

export type DemoState =
  | "quiet"
  | "available"
  | "closing"
  | "discovery"
  | "requested"
  | "processing"
  | "arrived"
  | "failed";

const base: TodayView = {
  dateIso: "2026-07-28",
  dateLabel: "7월 28일 화요일",
  isLearning: false,
  differences: [],
  memories: {
    count: 3,
    previews: [
      "점심 뒤에 천천히 산책했다",
      "오랜만에 좋아하는 음악을 들었다",
      "저녁 공기가 조금 선선했다",
    ],
  },
  diary: { state: "processing" },
  wrap: {
    state: "available",
    title: "오늘 기록으로 일기를 만들 수 있어요",
    body: "3개의 기록을 한 편으로 묶어볼까요?",
  },
};

export const DEMO_LABELS: Record<DemoState, string> = {
  quiet: "기록 없음",
  available: "일기 생성 가능",
  closing: "하루 정리 시간",
  discovery: "의미 있는 차이 발견",
  requested: "생성 요청됨",
  processing: "실제 처리 중",
  arrived: "Daily Wrap 도착",
  failed: "생성 실패",
};

export function isDemoState(value: string | undefined): value is DemoState {
  return !!value && value in DEMO_LABELS;
}

export const DEMO_VIEWS: Record<DemoState, TodayView> = {
  quiet: {
    ...base,
    isLearning: true,
    memories: { count: 0, previews: [] },
    diary: { state: "quiet" },
    wrap: { state: "none" },
  },
  available: base,
  closing: {
    ...base,
    wrap: {
      state: "closing",
      title: "오늘을 정리할 시간이에요",
      body: "지금까지 남긴 3개의 기록으로 일기를 만들 수 있어요.",
    },
  },
  discovery: {
    ...base,
    differences: [
      {
        id: "demo-difference",
        headline: "평소보다 산책 이야기가 눈에 띄었어요",
        category: "오늘의다른점",
        evidence: ["점심 뒤에 천천히 산책했다"],
      },
    ],
    wrap: {
      state: "discovery",
      title: "기록에서 눈에 띄는 차이를 찾았어요",
      body: "평소보다 산책 이야기가 눈에 띄었어요",
    },
  },
  requested: {
    ...base,
    wrap: {
      state: "requested",
      title: "일기 만들기를 요청했어요",
      body: "완성되면 이 화면에서 바로 보여드릴게요.",
    },
  },
  processing: {
    ...base,
    wrap: {
      state: "processing",
      title: "오늘 기록을 한 편으로 묶고 있어요",
      body: "실제 생성 작업이 진행 중이에요.",
    },
  },
  arrived: {
    ...base,
    diary: {
      state: "ready",
      id: "demo-diary",
      oneLine: "익숙한 하루 사이로 작은 산책이 남았다.",
    },
    wrap: {
      state: "arrived",
      label: "DAILY WRAP",
      title: "오늘의 일기가 도착했어요",
      body: "오늘 남긴 3개의 기록을 한 편으로 묶었어요.",
    },
  },
  failed: {
    ...base,
    wrap: {
      state: "failed",
      title: "일기를 만들지 못했어요",
      body: "잠시 후 다시 시도할 수 있어요.",
    },
  },
};

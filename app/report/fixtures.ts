import type { WeeklyReportView } from "@/lib/repositories/weeklyRepository";

/** 실제 DB·API를 건드리지 않고 완성 화면을 확인하는 프런트 전용 fixture. */
export const DEMO_WEEKLY_REPORT: WeeklyReportView = {
  id: "demo-weekly-report",
  weekStart: "2026-07-21",
  weekEnd: "2026-07-27",
  days: [
    { date: "2026-07-21", count: 1, isSurprising: false },
    { date: "2026-07-22", count: 3, isSurprising: true },
    { date: "2026-07-23", count: 0, isSurprising: false },
    { date: "2026-07-24", count: 2, isSurprising: false },
    { date: "2026-07-25", count: 1, isSurprising: false },
    { date: "2026-07-26", count: 0, isSurprising: false },
    { date: "2026-07-27", count: 1, isSurprising: false },
  ],
  highlights: {
    가장많이한것: {
      headline: "산책",
      detail: "7일 기록에서 3번 언급됐어요.",
    },
    처음한것: {
      headline: "새 노래",
      detail: "이번 7일 기록에 처음 등장했어요.",
    },
    감정순간: {
      headline: "감정 기록이 크게 달랐던 날",
      detail: "최근 기록 평균보다 7월 22일 값이 낮았어요.",
    },
  },
};

// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { TodayView } from "@/lib/services/today";
import { TodayScreen } from "./TodayScreen";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: vi.fn() }),
}));

function view(overrides: Partial<TodayView> = {}): TodayView {
  return {
    dateIso: "2026-07-22",
    dateLabel: "7월 22일 수요일",
    isLearning: true,
    differences: [],
    memories: { count: 0, previews: [] },
    diary: { state: "quiet" },
    wrap: { state: "none" },
    ...overrides,
  };
}

describe("TodayScreen", () => {
  it("학습 중인 조용한 날과 기록 진입점을 보여준다", () => {
    render(<TodayScreen view={view()} />);

    expect(screen.getByRole("heading", { name: "오늘" })).toBeInTheDocument();
    expect(screen.getByText("7월 22일 수요일")).toBeInTheDocument();
    expect(
      screen.getByText("아직 평소를 익히는 중이에요"),
    ).toBeInTheDocument();
    expect(screen.getByText("오늘의 메모 · 0개")).toBeInTheDocument();
    expect(screen.getAllByText("오늘은 아직 조용하네요")).toHaveLength(2);
    expect(
      screen.getByRole("link", { name: "+ 지금 남기기" }),
    ).toHaveAttribute("href", "/record");
  });

  it("발견한 차이, 메모 미리보기, 완성된 일기를 함께 보여준다", () => {
    render(
      <TodayScreen
        view={view({
          isLearning: false,
          differences: [
            {
              id: "diff-1",
              headline: "평소와 다른 작은 장면이 있었어요",
              category: "오늘의다른점",
              evidence: [],
            },
          ],
          memories: { count: 1, previews: ["점심 산책에서 본 구름"] },
          diary: {
            state: "ready",
            id: "diary-1",
            oneLine: "조용하지만 조금 달랐던 하루",
          },
          wrap: {
            state: "arrived",
            label: "DAILY WRAP",
            title: "오늘의 일기가 도착했어요",
            body: "오늘 남긴 1개의 기록을 한 편으로 묶었어요.",
          },
        })}
      />,
    );

    expect(
      screen.getByText("평소와 다른 작은 장면이 있었어요"),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "맞아요" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "아니에요" })).toBeInTheDocument();
    expect(screen.getByText("점심 산책에서 본 구름")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "일기 열기" }),
    ).toHaveAttribute("href", "/diary/2026-07-22");
    expect(screen.getByText("DAILY WRAP")).toBeInTheDocument();
    expect(
      screen.getByText("오늘의 일기가 도착했어요"),
    ).toBeInTheDocument();
  });

  it("메모가 있고 일기가 없으면 웹에서 직접 만들 수 있다", () => {
    render(
      <TodayScreen
        view={view({
          memories: { count: 2, previews: ["첫 기록", "두 번째 기록"] },
          diary: { state: "processing" },
          wrap: {
            state: "available",
            title: "오늘 기록으로 일기를 만들 수 있어요",
            body: "2개의 기록을 한 편으로 묶어볼까요?",
          },
        })}
      />,
    );

    expect(
      screen.getByRole("button", { name: "오늘 일기 만들기" }),
    ).toBeInTheDocument();
  });
});

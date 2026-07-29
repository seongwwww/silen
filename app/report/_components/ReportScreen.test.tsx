// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ReportScreen } from "./ReportScreen";

const report = {
  id: "report-1",
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
      headline: "김밥",
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

describe("주간 리포트 화면", () => {
  it("제목과 7일 메모 막대를 보여주고 큰 차이가 있던 날을 글로도 표시한다", () => {
    render(<ReportScreen report={report} />);

    expect(
      screen.getByRole("heading", { name: "당신이 몰랐던 이번 주" }),
    ).toBeInTheDocument();
    const chart = screen.getByRole("list", { name: "7일 메모 흐름" });
    expect(within(chart).getAllByRole("listitem")).toHaveLength(7);
    expect(
      within(chart).getByLabelText("7월 22일 메모 3개, 큰 차이 발견"),
    ).toBeInTheDocument();
    expect(within(chart).getByText("큰 차이")).toBeInTheDocument();
  });

  it("세 슬롯과 근거가 있는 내용을 정해진 순서로 보여준다", () => {
    render(<ReportScreen report={report} />);

    const cards = screen.getAllByTestId("weekly-slot");
    expect(cards).toHaveLength(3);
    expect(within(cards[0]).getByText("가장 많이 기록한 것")).toBeInTheDocument();
    expect(within(cards[0]).getByText("김밥")).toBeInTheDocument();
    expect(within(cards[1]).getByText("이번 주 처음 기록한 것")).toBeInTheDocument();
    expect(within(cards[2]).getByText("감정이 크게 달랐던 날")).toBeInTheDocument();
    expect(
      screen.getByText("이번 주 기록에서 찾은 모습이에요"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "공유 카드 만들기" }),
    ).toBeInTheDocument();
  });

  it("비어 있는 슬롯은 사실을 만들지 않고 담담하게 표시한다", () => {
    render(
      <ReportScreen
        report={{
          ...report,
          highlights: {
            가장많이한것: report.highlights.가장많이한것,
            처음한것: null,
            감정순간: null,
          },
        }}
      />,
    );

    expect(
      screen.getAllByText("이번 7일 기록에서는 찾지 못했어요."),
    ).toHaveLength(2);
  });

  it("리포트가 없으면 정확한 빈 상태 문구만 보여준다", () => {
    render(<ReportScreen report={null} />);

    expect(
      screen.getByText("아직 묶을 7일 기록이 없어요"),
    ).toBeInTheDocument();
    expect(screen.queryByText(/남았/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /공유/ })).not.toBeInTheDocument();
  });
});

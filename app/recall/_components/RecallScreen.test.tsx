// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { RecallScreen } from "./RecallScreen";

describe("회고 검색 화면", () => {
  it("검색 전에는 입력 안내를 보여준다", () => {
    render(<RecallScreen query="" results={[]} />);

    expect(screen.getByRole("heading", { name: "그거 뭐였지" })).toBeInTheDocument();
    expect(screen.getByRole("searchbox", { name: "기록 검색" })).toHaveAttribute(
      "maxLength",
      "100",
    );
    expect(screen.getByText("찾고 싶은 말을 적어보세요")).toBeInTheDocument();
  });

  it("검색 결과를 날짜 태그와 원문 발췌로 보여준다", () => {
    render(
      <RecallScreen
        query="노래"
        results={[
          {
            id: "m1",
            capturedAt: "2026-07-14T12:00:00Z",
            excerpt: "오래 전에 들었던 노래가 다시 생각났다.",
          },
        ]}
      />,
    );

    expect(screen.getByText("7.14")).toBeInTheDocument();
    expect(
      screen.getByText("오래 전에 들었던 노래가 다시 생각났다."),
    ).toBeInTheDocument();
    expect(screen.queryByText("그런 기록은 아직 없어요")).not.toBeInTheDocument();
  });

  it("검색 결과가 없으면 담담한 빈 상태를 보여준다", () => {
    render(<RecallScreen query="없는말" results={[]} />);

    expect(screen.getByText("그런 기록은 아직 없어요")).toBeInTheDocument();
  });
});

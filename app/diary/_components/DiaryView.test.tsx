// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DiaryArticle } from "./DiaryView";
import type { DiaryView } from "@/lib/services/diary";

const base: DiaryView = {
  id: "d1",
  date: "2026-07-26",
  status: "draft",
  oneLine: "비슷한 하루, 그래도 조금 일찍.",
  body: "특별할 것 없는 하루였다. 점심은 김밥.",
  differences: ["평소보다 일찍 퇴근"],
  evidence: ["점심 김밥"],
  isEdited: false,
  question: null,
};

describe("DiaryArticle", () => {
  it("날짜·한 문장·본문·다른 점을 보여준다", () => {
    render(<DiaryArticle diary={base} />);
    expect(screen.getByText("2026-07-26")).toBeInTheDocument();
    expect(screen.getByText(base.oneLine)).toBeInTheDocument();
    expect(screen.getByText(base.body)).toBeInTheDocument();
    expect(screen.getByText("평소보다 일찍 퇴근")).toBeInTheDocument();
  });

  it("AI 생성물임을 라벨로 밝힌다", () => {
    render(<DiaryArticle diary={base} />);
    expect(screen.getByText("AI가 쓴 초안")).toBeInTheDocument();
  });

  it("사용자가 고친 일기는 초안이라고 하지 않는다", () => {
    render(<DiaryArticle diary={{ ...base, isEdited: true }} />);
    expect(screen.queryByText("AI가 쓴 초안")).not.toBeInTheDocument();
    expect(screen.getByText("내가 고친 일기")).toBeInTheDocument();
  });

  it("한 문장이 없으면 그 영역을 렌더하지 않는다", () => {
    render(<DiaryArticle diary={{ ...base, oneLine: "" }} />);
    expect(screen.getByText(base.body)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { level: 2 })).not.toBeInTheDocument();
  });

  it("근거 접기를 함께 보여준다", () => {
    render(<DiaryArticle diary={base} />);
    expect(
      screen.getByRole("button", { name: /무엇을 보고 썼는지/ }),
    ).toBeInTheDocument();
  });

  it("오늘 처음 제목을 보여준다", () => {
    render(<DiaryArticle diary={base} />);
    expect(screen.getByText("오늘 처음")).toBeInTheDocument();
  });

  it("질문이 있으면 카드를 보여준다", () => {
    render(
      <DiaryArticle
        diary={{
          ...base,
          question: { sectionId: "s1", text: "지은은 어떤 사람이었어요?" },
        }}
      />,
    );
    expect(
      screen.getByRole("link", { name: "지은은 어떤 사람이었어요?" }),
    ).toBeInTheDocument();
  });
});

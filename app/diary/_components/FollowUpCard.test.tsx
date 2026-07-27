// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { FollowUpCard } from "./FollowUpCard";

describe("FollowUpCard", () => {
  it("질문을 보여주고 기록 화면으로 링크한다", () => {
    render(<FollowUpCard sectionId="sec-1" text="지은은 어떤 사람이었어요?" />);
    const link = screen.getByRole("link", { name: "지은은 어떤 사람이었어요?" });
    expect(link).toHaveAttribute("href", "/?section=sec-1");
  });

  it("URL에 질문 텍스트를 담지 않는다", () => {
    render(<FollowUpCard sectionId="sec-1" text="지은은 어떤 사람이었어요?" />);
    expect(screen.getByRole("link").getAttribute("href")).not.toContain("지은");
  });

  it("44px 터치 타깃", () => {
    render(<FollowUpCard sectionId="sec-1" text="질문" />);
    expect(screen.getByRole("link").className).toContain("min-h-11");
  });
});

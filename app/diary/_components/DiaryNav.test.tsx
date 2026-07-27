// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DiaryNav } from "./DiaryNav";

describe("DiaryNav", () => {
  it("이전·다음 일기로 가는 링크를 보여준다", () => {
    render(<DiaryNav prev="2026-07-10" next="2026-07-30" />);
    expect(screen.getByRole("link", { name: "이전 일기" })).toHaveAttribute(
      "href",
      "/diary/2026-07-10",
    );
    expect(screen.getByRole("link", { name: "다음 일기" })).toHaveAttribute(
      "href",
      "/diary/2026-07-30",
    );
  });

  it("이전 일기가 없으면 링크가 아니라 비활성이다", () => {
    render(<DiaryNav prev={null} next="2026-07-30" />);
    expect(
      screen.queryByRole("link", { name: "이전 일기" }),
    ).not.toBeInTheDocument();
    // 사라지지 않고 경계임을 알린다(색만으로 전달하지 않음)
    expect(screen.getByText("이전 일기")).toHaveAttribute(
      "aria-disabled",
      "true",
    );
  });

  it("다음 일기가 없으면 링크가 아니라 비활성이다", () => {
    render(<DiaryNav prev="2026-07-10" next={null} />);
    expect(
      screen.queryByRole("link", { name: "다음 일기" }),
    ).not.toBeInTheDocument();
    expect(screen.getByText("다음 일기")).toHaveAttribute(
      "aria-disabled",
      "true",
    );
  });

  it("44px 터치 타깃을 만족한다", () => {
    render(<DiaryNav prev="2026-07-10" next="2026-07-30" />);
    expect(
      screen.getByRole("link", { name: "이전 일기" }).className,
    ).toContain("min-h-11");
    expect(
      screen.getByRole("link", { name: "다음 일기" }).className,
    ).toContain("min-h-11");
  });
});

// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TabBar } from "./TabBar";

let pathname = "/";

vi.mock("next/navigation", () => ({
  usePathname: () => pathname,
}));

describe("TabBar", () => {
  beforeEach(() => {
    pathname = "/";
  });

  it("실제로 존재하는 네 화면을 보여준다", () => {
    render(<TabBar />);

    expect(screen.getAllByRole("link")).toHaveLength(4);
    expect(screen.getByRole("link", { name: "오늘" })).toHaveAttribute(
      "href",
      "/",
    );
    expect(screen.getByRole("link", { name: "일기" })).toHaveAttribute(
      "href",
      "/diary",
    );
    expect(screen.getByRole("link", { name: "설정" })).toHaveAttribute(
      "href",
      "/settings",
    );
    expect(screen.getByRole("link", { name: "회고" })).toHaveAttribute(
      "href",
      "/recall",
    );
  });

  it("현재 경로를 aria-current와 글자 굵기로 구분한다", () => {
    pathname = "/diary/2026-07-22";
    render(<TabBar />);

    const active = screen.getByRole("link", { name: "일기" });
    expect(active).toHaveAttribute("aria-current", "page");
    expect(active.className).toContain("font-semibold");
    expect(screen.getByRole("link", { name: "오늘" })).not.toHaveAttribute(
      "aria-current",
    );
  });

  it("각 탭이 44px 이상 터치 영역을 가진다", () => {
    render(<TabBar />);
    for (const link of screen.getAllByRole("link")) {
      expect(link.className).toContain("min-h-11");
    }
  });
});

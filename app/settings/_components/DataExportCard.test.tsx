// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DataExportCard } from "./DataExportCard";

describe("DataExportCard", () => {
  it("사진 바이너리가 빠지는 기록 JSON임을 정확히 안내한다", () => {
    render(<DataExportCard />);

    expect(
      screen.getByRole("heading", { name: "내 데이터" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/사진 파일은 포함되지 않아요/)).toBeInTheDocument();
    const link = screen.getByRole("link", {
      name: "기록 JSON 내보내기",
    });
    expect(link).toHaveAttribute("href", "/api/export");
    expect(link).toHaveAttribute("download");
    expect(link.className).toContain("min-h-11");
  });
});

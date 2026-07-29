// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EvidencePhoto } from "./EvidencePhoto";

describe("EvidencePhoto", () => {
  it("서명 URL이 만료되면 깨진 이미지 대신 다시 열기 안내를 보여준다", () => {
    render(<EvidencePhoto src="https://example.test/expired.png" />);

    fireEvent.error(screen.getByRole("img", { name: "이 기록에 붙인 사진" }));

    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(
      screen.getByText("사진을 다시 보려면 화면을 새로고침해 주세요"),
    ).toBeInTheDocument();
  });
});

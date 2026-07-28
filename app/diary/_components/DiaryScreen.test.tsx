// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DiaryScreen } from "./DiaryScreen";

describe("DiaryScreen", () => {
  it("상단에서 주간 리포트로 이동할 수 있다", () => {
    render(
      <DiaryScreen
        diary={null}
        hasMemory={false}
        neighbors={{ prev: null, next: null }}
      />,
    );

    expect(screen.getByRole("link", { name: "7일 리포트" })).toHaveAttribute(
      "href",
      "/report",
    );
  });
});

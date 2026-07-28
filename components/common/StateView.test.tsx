// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import {
  EmptyState,
  ErrorState,
  LoadingState,
  OfflineState,
  ProcessingState,
} from "./StateView";

describe("StateView", () => {
  it("empty·loading·processing·error·offline 상태를 각각 제공한다", () => {
    const { rerender } = render(<EmptyState message="비어 있음" />);
    expect(screen.getByText("비어 있음")).toBeInTheDocument();

    rerender(<LoadingState />);
    expect(screen.getByRole("status")).toHaveAccessibleName("불러오는 중");

    rerender(<ProcessingState message="묶는 중" />);
    expect(screen.getByRole("status")).toHaveTextContent("묶는 중");

    rerender(<ErrorState />);
    expect(screen.getByText("불러오지 못했어요.")).toBeInTheDocument();

    rerender(<OfflineState />);
    expect(screen.getByText("지금은 오프라인이에요.")).toBeInTheDocument();
  });
});

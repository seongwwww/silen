// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { TodayDifferenceList } from "./TodayDifferenceList";

describe("TodayDifferenceList", () => {
  it("판단을 저장한 차이 카드를 목록에서 걷어낸다", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
    render(
      <TodayDifferenceList
        items={[
          {
            id: "diff-1",
            headline: "평소와 다른 작은 장면",
            category: "오늘의다른점",
            evidence: [],
          },
        ]}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "맞아요" }));

    await waitFor(() =>
      expect(
        screen.queryByText("평소와 다른 작은 장면"),
      ).not.toBeInTheDocument(),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/differences/diff-1",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ status: "confirmed" }),
      }),
    );
  });
});

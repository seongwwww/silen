// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ShareCardPanel } from "./ShareCardPanel";

const highlights = {
  가장많이한것: {
    headline: "김밥",
    detail: "7일 기록에서 4번 언급됐어요.",
  },
  처음한것: {
    headline: "그 카페",
    detail: "이번 7일 기록에 처음 등장했어요.",
  },
  감정순간: {
    headline: "목요일이 달랐어요",
    detail: "최근 기록보다 감정이 크게 달랐어요.",
  },
};

describe("공유 카드 패널", () => {
  it("공유 버튼을 눌러야 선택과 미리보기를 보여준다", async () => {
    render(
      <ShareCardPanel
        highlights={highlights}
        weekStart="2026-07-21"
        download={vi.fn()}
      />,
    );

    expect(screen.queryByRole("region", { name: "공유 카드 미리보기" })).not.toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: "공유 카드 만들기" }),
    );

    const preview = screen.getByRole("region", { name: "공유 카드 미리보기" });
    expect(within(preview).getByText("이번 주의 나")).toBeInTheDocument();
    expect(within(preview).getByText("김밥")).toBeInTheDocument();
    expect(within(preview).getByText("그 카페")).toBeInTheDocument();
    expect(within(preview).getByText("목요일이 달랐어요")).toBeInTheDocument();
    expect(screen.getAllByRole("checkbox")).toHaveLength(3);
    for (const checkbox of screen.getAllByRole("checkbox")) {
      expect(checkbox).toBeChecked();
    }
  });

  it("항목을 빼면 미리보기와 PNG 입력에서 모두 빠진다", async () => {
    const download = vi.fn().mockResolvedValue(undefined);
    render(
      <ShareCardPanel
        highlights={highlights}
        weekStart="2026-07-21"
        download={download}
      />,
    );
    await userEvent.click(
      screen.getByRole("button", { name: "공유 카드 만들기" }),
    );
    await userEvent.click(
      screen.getByRole("checkbox", { name: "처음 · 그 카페" }),
    );

    const preview = screen.getByRole("region", { name: "공유 카드 미리보기" });
    expect(within(preview).queryByText("그 카페")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "PNG로 저장" }));

    expect(download).toHaveBeenCalledTimes(1);
    const [items, weekStart] = download.mock.calls[0];
    expect(items.map((item: { slot: string }) => item.slot)).toEqual([
      "가장많이한것",
      "감정순간",
    ]);
    expect(weekStart).toBe("2026-07-21");
  });

  it("버튼은 44px 터치 타깃이고 공개 링크를 만들지 않는다", async () => {
    render(
      <ShareCardPanel
        highlights={highlights}
        weekStart="2026-07-21"
        download={vi.fn()}
      />,
    );
    const open = screen.getByRole("button", { name: "공유 카드 만들기" });
    expect(open.className).toContain("min-h-11");
    await userEvent.click(open);
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
});

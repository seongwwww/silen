// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { toast } from "sonner";
import { DataDeletionCard } from "./DataDeletionCard";

vi.mock("sonner", () => ({
  toast: Object.assign(vi.fn(), { error: vi.fn() }),
}));

describe("전체 기록 삭제", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal("fetch", vi.fn(async () => new Response(null, { status: 202 })));
    Object.defineProperty(navigator, "onLine", {
      configurable: true,
      value: true,
    });
  });

  it("첫 클릭에서는 삭제 범위를 구체적으로 확인한다", async () => {
    render(<DataDeletionCard />);

    await userEvent.click(
      screen.getByRole("button", { name: "전체 기록 삭제" }),
    );

    expect(
      screen.getByText(
        "원본 기록·사진·일기·차이·주간 리포트가 삭제됩니다. 계정은 유지되며, 삭제한 기록은 되돌릴 수 없습니다.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "삭제 요청하기" }),
    ).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
  });

  it("두 번째 확인 뒤에만 DELETE 요청을 보낸다", async () => {
    render(<DataDeletionCard />);
    await userEvent.click(
      screen.getByRole("button", { name: "전체 기록 삭제" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "삭제 요청하기" }),
    );

    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith("/api/account/data", {
        method: "DELETE",
      }),
    );
    expect(
      screen.getByText("삭제 요청을 받았어요. 계정은 그대로 유지돼요."),
    ).toBeInTheDocument();
  });

  it("취소하면 요청 없이 첫 상태로 돌아간다", async () => {
    render(<DataDeletionCard />);
    await userEvent.click(
      screen.getByRole("button", { name: "전체 기록 삭제" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "취소" }));

    expect(
      screen.getByRole("button", { name: "전체 기록 삭제" }),
    ).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
  });

  it("오프라인이면 요청하지 않고 오류를 알린다", async () => {
    Object.defineProperty(navigator, "onLine", {
      configurable: true,
      value: false,
    });
    render(<DataDeletionCard />);
    await userEvent.click(
      screen.getByRole("button", { name: "전체 기록 삭제" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "삭제 요청하기" }),
    );

    expect(fetch).not.toHaveBeenCalled();
    expect(toast.error).toHaveBeenCalledWith(
      "지금은 오프라인이에요. 연결되면 다시 시도해 주세요.",
    );
  });

  it("실패하면 확인 상태를 유지해 다시 시도할 수 있다", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(null, { status: 500 }),
    );
    render(<DataDeletionCard />);
    await userEvent.click(
      screen.getByRole("button", { name: "전체 기록 삭제" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "삭제 요청하기" }),
    );

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith(
        "삭제를 요청하지 못했어요. 다시 시도해 주세요.",
      ),
    );
    expect(
      screen.getByRole("button", { name: "삭제 요청하기" }),
    ).toBeEnabled();
  });

  it("모든 버튼은 44px 이상 터치 영역을 가진다", async () => {
    render(<DataDeletionCard />);
    expect(
      screen.getByRole("button", { name: "전체 기록 삭제" }).className,
    ).toContain("min-h-11");
    await userEvent.click(
      screen.getByRole("button", { name: "전체 기록 삭제" }),
    );
    for (const button of screen.getAllByRole("button")) {
      expect(button.className).toContain("min-h-11");
    }
  });
});

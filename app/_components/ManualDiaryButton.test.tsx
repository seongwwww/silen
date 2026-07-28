// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { toast } from "sonner";
import { ManualDiaryButton } from "./ManualDiaryButton";

const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh }),
}));

vi.mock("sonner", () => ({
  toast: Object.assign(vi.fn(), { error: vi.fn() }),
}));

function setOnLine(value: boolean) {
  Object.defineProperty(navigator, "onLine", {
    value,
    configurable: true,
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  setOnLine(true);
});

describe("ManualDiaryButton", () => {
  it("오늘 일기를 만드는 POST 요청을 보내고 화면을 새로 고친다", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);

    render(<ManualDiaryButton />);
    await userEvent.click(
      screen.getByRole("button", { name: "오늘 일기 만들기" }),
    );

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith("/api/diaries/generate", {
        method: "POST",
      }),
    );
    expect(toast).toHaveBeenCalledWith("일기 만들기를 요청했어요");
    expect(refresh).toHaveBeenCalledTimes(1);
    expect(
      screen.getByRole("button", { name: "일기 만들기를 요청했어요" }),
    ).toBeDisabled();
    expect(
      screen.getByText("완성되면 이 화면에서 바로 보여드릴게요."),
    ).toBeInTheDocument();
  });

  it("요청 중에는 문구를 바꾸고 중복 요청을 막는다", async () => {
    let resolveRequest!: (value: { ok: boolean }) => void;
    const pending = new Promise<{ ok: boolean }>((resolve) => {
      resolveRequest = resolve;
    });
    const fetchMock = vi.fn().mockReturnValue(pending);
    vi.stubGlobal("fetch", fetchMock);

    render(<ManualDiaryButton />);
    const button = screen.getByRole("button", { name: "오늘 일기 만들기" });
    await userEvent.click(button);

    expect(
      screen.getByRole("button", { name: "일기를 준비하고 있어요" }),
    ).toBeDisabled();
    await userEvent.click(
      screen.getByRole("button", { name: "일기를 준비하고 있어요" }),
    );
    expect(fetchMock).toHaveBeenCalledTimes(1);

    resolveRequest({ ok: true });
    await waitFor(() => expect(refresh).toHaveBeenCalledTimes(1));
  });

  it("오프라인이면 요청하지 않고 다시 시도할 수 있게 알린다", async () => {
    setOnLine(false);
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    render(<ManualDiaryButton />);
    await userEvent.click(
      screen.getByRole("button", { name: "오늘 일기 만들기" }),
    );

    expect(fetchMock).not.toHaveBeenCalled();
    expect(toast.error).toHaveBeenCalledWith(
      "지금은 오프라인이에요. 연결되면 다시 시도해 주세요.",
    );
  });

  it("요청 실패를 조용한 문구로 알리고 버튼을 복구한다", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));

    render(<ManualDiaryButton />);
    await userEvent.click(
      screen.getByRole("button", { name: "오늘 일기 만들기" }),
    );

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith(
        "일기를 만들지 못했어요. 다시 시도해 주세요.",
      ),
    );
    expect(
      screen.getByRole("button", { name: "오늘 일기 만들기" }),
    ).toBeEnabled();
  });

  it("버튼의 터치 영역은 44px 이상이다", () => {
    render(<ManualDiaryButton />);

    expect(
      screen.getByRole("button", { name: "오늘 일기 만들기" }),
    ).toHaveClass("min-h-11");
  });
});

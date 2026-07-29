// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";
import { RegenerateButton } from "./RegenerateButton";

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
  vi.restoreAllMocks();
  setOnLine(true);
});

describe("RegenerateButton", () => {
  it("빠른 주문을 색과 보이는 라벨로 선택하고 요청한다", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
    render(<RegenerateButton id="d1" status="draft" />);

    const shortOrder = screen.getByRole("button", { name: /짧게/ });
    await userEvent.click(shortOrder);
    expect(shortOrder).toHaveAttribute("aria-pressed", "true");
    expect(shortOrder).toHaveClass("bg-accent");
    expect(screen.getByText("선택됨", { selector: "span" })).toBeVisible();

    await userEvent.click(
      screen.getByRole("button", { name: "다시 만들기" }),
    );
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/diaries/d1/regenerate",
        {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ toneInstruction: "짧게" }),
        },
      ),
    );
  });

  it("유머 빠른 주문도 선택할 수 있다", async () => {
    render(<RegenerateButton id="d1" status="draft" />);

    await userEvent.click(screen.getByRole("button", { name: /유머/ }));

    expect(screen.getByRole("button", { name: /유머/ })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByText("선택: 유머")).toBeInTheDocument();
  });

  it("자유 주문을 전송하고 글자 수를 보여준다", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
    render(<RegenerateButton id="d1" status="draft" />);

    await userEvent.type(
      screen.getByLabelText("자유 주문"),
      "조금 더 건조하게",
    );
    expect(screen.getByText(/9 \/ \d+자/)).toBeInTheDocument();
    expect(screen.getByText("선택: 자유 주문")).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: "다시 만들기" }),
    );

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/diaries/d1/regenerate",
        expect.objectContaining({
          body: JSON.stringify({
            toneInstruction: "조금 더 건조하게",
          }),
        }),
      ),
    );
  });

  it("편집본 경고 뒤에도 고른 주문을 보존한다", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
    render(<RegenerateButton id="d1" status="edited" />);
    await userEvent.click(screen.getByRole("button", { name: /유머/ }));
    await userEvent.click(
      screen.getByRole("button", { name: "다시 만들기" }),
    );
    expect(fetchMock).not.toHaveBeenCalled();
    expect(
      screen.getByText("고친 내용이 사라져요. 그래도 다시 만들까요?"),
    ).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: "다시 만들기" }),
    );
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/diaries/d1/regenerate",
        expect.objectContaining({
          body: JSON.stringify({ toneInstruction: "유머" }),
        }),
      ),
    );
  });

  it("요청은 다음 생성 때 반영된다고 알린다", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true }));
    render(<RegenerateButton id="d1" status="draft" />);
    await userEvent.click(
      screen.getByRole("button", { name: "다시 만들기" }),
    );
    await waitFor(() =>
      expect(
        screen.getByText("다음 일기를 만들 때 반영돼요."),
      ).toBeInTheDocument(),
    );
  });

  it("저장된 pending 상태를 첫 렌더부터 계속 보여준다", () => {
    render(
      <RegenerateButton
        id="d1"
        status="draft"
        initialRequested
        initialToneInstruction="짧게"
      />,
    );

    expect(
      screen.getByText("다음 일기를 만들 때 반영돼요."),
    ).toBeInTheDocument();
    expect(screen.getByText("주문: 짧게")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "다시 만들기" }),
    ).not.toBeInTheDocument();
  });

  it("연속 클릭에도 요청은 한 번만 보낸다", async () => {
    let resolveRequest!: (response: { ok: boolean }) => void;
    const pending = new Promise<{ ok: boolean }>((resolve) => {
      resolveRequest = resolve;
    });
    const fetchMock = vi.fn().mockReturnValue(pending);
    vi.stubGlobal("fetch", fetchMock);
    render(<RegenerateButton id="d1" status="draft" />);

    const button = screen.getByRole("button", { name: "다시 만들기" });
    await userEvent.click(button);
    await userEvent.click(button);
    expect(fetchMock).toHaveBeenCalledTimes(1);

    resolveRequest({ ok: true });
    await waitFor(() =>
      expect(
        screen.getByText("다음 일기를 만들 때 반영돼요."),
      ).toBeInTheDocument(),
    );
  });

  it("오프라인이면 요청하지 않고 다시 시도할 수 있게 한다", async () => {
    setOnLine(false);
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(<RegenerateButton id="d1" status="draft" />);

    await userEvent.click(
      screen.getByRole("button", { name: "다시 만들기" }),
    );

    expect(fetchMock).not.toHaveBeenCalled();
    expect(toast.error).toHaveBeenCalledWith(
      "지금은 오프라인이에요. 연결되면 다시 시도해 주세요.",
    );
    expect(
      screen.getByRole("button", { name: "다시 만들기" }),
    ).toBeEnabled();
  });

  it("실패하면 버튼과 주문을 복구한다", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));
    render(<RegenerateButton id="d1" status="draft" />);
    await userEvent.click(screen.getByRole("button", { name: /짧게/ }));

    await userEvent.click(
      screen.getByRole("button", { name: "다시 만들기" }),
    );

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith(
        "다시 만들기를 요청하지 못했어요. 다시 시도해 주세요.",
      ),
    );
    expect(
      screen.getByRole("button", { name: "다시 만들기" }),
    ).toBeEnabled();
    expect(screen.getByRole("button", { name: /짧게/ })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("모든 조작 요소는 44px 터치 타깃이다", () => {
    render(<RegenerateButton id="d1" status="draft" />);
    for (const button of screen.getAllByRole("button")) {
      expect(button).toHaveClass("min-h-11");
    }
    expect(screen.getByLabelText("자유 주문")).toHaveClass("min-h-11");
  });
});

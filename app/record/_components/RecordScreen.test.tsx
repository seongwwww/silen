// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { RecordScreen } from "./RecordScreen";

const push = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

describe("RecordScreen", () => {
  beforeEach(() => {
    push.mockReset();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true }));
    Object.defineProperty(navigator, "onLine", {
      value: true,
      configurable: true,
    });
  });

  it("일반 기록을 저장하면 오늘 화면으로 돌아간다", async () => {
    render(<RecordScreen question={null} />);

    await userEvent.type(screen.getByRole("textbox"), "오늘의 작은 기록");
    await userEvent.click(
      screen.getByRole("button", { name: "기록하기" }),
    );

    await waitFor(() => expect(push).toHaveBeenCalledWith("/"));
  });

  it("질문에 이어 쓰는 동안에는 같은 화면에 머문다", async () => {
    render(<RecordScreen question="조금 더 떠오르는 게 있나요?" />);

    await userEvent.type(screen.getByRole("textbox"), "이어 쓰는 기록");
    await userEvent.click(
      screen.getByRole("button", { name: "기록하기" }),
    );

    await waitFor(() => expect(screen.getByRole("textbox")).toHaveValue(""));
    expect(push).not.toHaveBeenCalled();
  });
});

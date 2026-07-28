// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TonePicker } from "./TonePicker";

beforeEach(() => vi.restoreAllMocks());

describe("TonePicker", () => {
  it("담백·따뜻 두 프리셋과 현재 선택을 보여준다", () => {
    render(<TonePicker initial="담백" />);
    expect(
      screen.getByRole("button", { name: "담백" }),
    ).toHaveAttribute("aria-pressed", "true");
    expect(
      screen.getByRole("button", { name: "따뜻" }),
    ).toHaveAttribute("aria-pressed", "false");
  });

  it("고르면 PATCH를 보내고 선택 상태가 바뀐다", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
    render(<TonePicker initial="담백" />);

    await userEvent.click(screen.getByRole("button", { name: "따뜻" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(fetchMock).toHaveBeenCalledWith("/api/users/me", {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ tonePreset: "따뜻" }),
    });
    expect(
      screen.getByRole("button", { name: "따뜻" }),
    ).toHaveAttribute("aria-pressed", "true");
  });

  it("모든 프리셋이 44px 터치 타깃이다", () => {
    render(<TonePicker initial="담백" />);
    for (const button of screen.getAllByRole("button")) {
      expect(button.className).toContain("min-h-11");
    }
  });
});

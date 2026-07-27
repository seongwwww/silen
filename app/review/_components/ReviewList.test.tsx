// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ReviewList } from "./ReviewList";

import { Toaster } from "@/components/ui/sonner";

Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});
Object.defineProperties(HTMLElement.prototype, {
  setPointerCapture: { configurable: true, value: vi.fn() },
  releasePointerCapture: { configurable: true, value: vi.fn() },
  hasPointerCapture: { configurable: true, value: vi.fn(() => false) },
});

const items = [{ id: "d1", headline: "3일째 김밥", category: "오늘의다른점", evidence: ["점심에 김밥"] }];
beforeEach(() => vi.restoreAllMocks());
const renderList = () => render(<><ReviewList items={items} /><Toaster /></>);

describe("ReviewList", () => {
  it("맞아요 탭하면 카드가 사라지고 PATCH가 confirmed로 불린다", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
    renderList();
    await userEvent.click(screen.getByRole("button", { name: "맞아요" }));
    expect(screen.queryByText("3일째 김밥")).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/differences/d1", expect.objectContaining({ method: "PATCH" }));
  });
  it("PATCH 실패면 카드가 복원된다", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));
    renderList();
    await userEvent.click(screen.getByRole("button", { name: "아니에요" }));
    await waitFor(() => expect(screen.getByText("3일째 김밥")).toBeInTheDocument());
  });
  it("되돌리기 토스트로 카드가 복원된다", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true }));
    renderList();
    await userEvent.click(screen.getByRole("button", { name: "맞아요" }));
    await userEvent.click(await screen.findByRole("button", { name: "되돌리기" }));
    await waitFor(() => expect(screen.getByText("3일째 김밥")).toBeInTheDocument());
  });
});

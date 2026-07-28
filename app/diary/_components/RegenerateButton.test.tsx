// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RegenerateButton } from "./RegenerateButton";

beforeEach(() => vi.restoreAllMocks());

describe("RegenerateButton", () => {
  it("draft면 경고 없이 바로 요청한다", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
    render(<RegenerateButton id="d1" status="draft" />);
    await userEvent.click(
      screen.getByRole("button", { name: "다시 만들기" }),
    );
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
  });

  it("편집본이면 사라진다고 알리고 한 번 더 확인받는다", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
    render(<RegenerateButton id="d1" status="edited" />);
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
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
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

  it("44px 터치 타깃", () => {
    render(<RegenerateButton id="d1" status="draft" />);
    expect(
      screen.getByRole("button", { name: "다시 만들기" }).className,
    ).toContain("min-h-11");
  });
});

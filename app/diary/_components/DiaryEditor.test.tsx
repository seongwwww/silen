// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DiaryEditor } from "./DiaryEditor";

beforeEach(() => vi.restoreAllMocks());

const base = { id: "d1", body: "AI가 쓴 본문", status: "draft" as const };

describe("DiaryEditor", () => {
  it("기본은 읽기 상태이고 고치기·확정 버튼이 있다", () => {
    render(<DiaryEditor {...base} />);
    expect(
      screen.getByRole("button", { name: "고치기" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "확정" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("고치기를 누르면 편집창이 열린다", async () => {
    render(<DiaryEditor {...base} />);
    await userEvent.click(screen.getByRole("button", { name: "고치기" }));
    expect(screen.getByRole("textbox")).toHaveValue("AI가 쓴 본문");
  });

  it("저장하면 편집 본문과 edited 상태를 보낸다", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
    render(<DiaryEditor {...base} />);
    await userEvent.click(screen.getByRole("button", { name: "고치기" }));
    await userEvent.clear(screen.getByRole("textbox"));
    await userEvent.type(screen.getByRole("textbox"), "내가 고친 글");
    await userEvent.click(screen.getByRole("button", { name: "저장" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [, init] = fetchMock.mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({
      editedText: "내가 고친 글",
      status: "edited",
    });
  });

  it("확정하면 confirmed를 보낸다", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
    render(<DiaryEditor {...base} />);
    await userEvent.click(screen.getByRole("button", { name: "확정" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      status: "confirmed",
    });
  });

  it("확정된 일기는 되돌리기를 보여준다", () => {
    render(<DiaryEditor {...base} status="confirmed" />);
    expect(
      screen.getByRole("button", { name: "다시 고치기" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "확정" }),
    ).not.toBeInTheDocument();
  });

  it("모든 버튼이 44px 터치 타깃이다", () => {
    render(<DiaryEditor {...base} />);
    for (const b of screen.getAllByRole("button")) {
      expect(b.className).toContain("min-h-11");
    }
  });
});

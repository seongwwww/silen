// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { MemoryLockControl } from "./MemoryLockControl";

vi.mock("sonner", () => ({
  toast: Object.assign(vi.fn(), { error: vi.fn() }),
}));

describe("MemoryLockControl", () => {
  it("서버가 성공한 뒤에만 본문을 가리고 잠금 해제를 제공한다", async () => {
    let resolveUpdate: (() => void) | undefined;
    const updateLock = vi
      .fn()
      .mockImplementationOnce(
        () =>
        new Promise<void>((resolve) => {
          resolveUpdate = resolve;
        }),
      )
      .mockResolvedValueOnce(undefined);
    render(
      <MemoryLockControl memoryId="m1" updateLock={updateLock}>
        <p>내 원래 기록</p>
      </MemoryLockControl>,
    );

    await userEvent.click(screen.getByRole("button", { name: "기억 잠그기" }));
    expect(screen.getByText("내 원래 기록")).toBeInTheDocument();

    resolveUpdate?.();
    expect(
      await screen.findByRole("button", { name: "잠금 풀기" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("내 원래 기록")).not.toBeInTheDocument();
    expect(screen.getByText("잠긴 기억")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "잠금 풀기" }));
    expect(updateLock).toHaveBeenLastCalledWith("m1", false, true);
    expect(await screen.findByText("내 원래 기록")).toBeInTheDocument();
  });

  it("실패하면 원래 상태와 본문을 유지한다", async () => {
    const updateLock = vi.fn().mockRejectedValue(new Error("conflict"));
    render(
      <MemoryLockControl memoryId="m1" updateLock={updateLock}>
        <p>내 원래 기록</p>
      </MemoryLockControl>,
    );

    await userEvent.click(screen.getByRole("button", { name: "기억 잠그기" }));

    expect(await screen.findByText("내 원래 기록")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "기억 잠그기" })).toBeInTheDocument();
  });

  it("효과를 설명하고 44px 터치 타깃을 쓴다", () => {
    render(
      <MemoryLockControl memoryId="m1" updateLock={vi.fn()}>
        <p>기록</p>
      </MemoryLockControl>,
    );

    expect(
      screen.getByText("잠근 기억은 검색·일기·차이 찾기에서 빠져요"),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "기억 잠그기" }).className).toContain(
      "min-h-11",
    );
  });
});

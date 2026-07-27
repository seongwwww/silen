// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ConfirmActions } from "./ConfirmActions";

describe("ConfirmActions", () => {
  it("맞아요/아니에요 라벨과 접근가능 이름이 있다", () => {
    render(<ConfirmActions onConfirm={() => {}} onDismiss={() => {}} />);
    expect(screen.getByRole("button", { name: "맞아요" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "아니에요" })).toBeInTheDocument();
  });
  it("탭하면 콜백이 불린다", async () => {
    const onConfirm = vi.fn(), onDismiss = vi.fn();
    render(<ConfirmActions onConfirm={onConfirm} onDismiss={onDismiss} />);
    await userEvent.click(screen.getByRole("button", { name: "맞아요" }));
    await userEvent.click(screen.getByRole("button", { name: "아니에요" }));
    expect(onConfirm).toHaveBeenCalledOnce();
    expect(onDismiss).toHaveBeenCalledOnce();
  });
});

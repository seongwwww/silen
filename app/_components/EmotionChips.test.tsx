// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EmotionChips } from "./EmotionChips";

describe("EmotionChips", () => {
  it("세 가지 감정을 라벨로 보여준다", () => {
    render(<EmotionChips value={undefined} onChange={() => {}} />);
    expect(screen.getByRole("button", { name: "좋았어요" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "그냥" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "별로" })).toBeInTheDocument();
  });

  it("선택 상태를 aria-pressed로 알린다(색만으로 전달하지 않음)", () => {
    render(<EmotionChips value="good" onChange={() => {}} />);
    expect(screen.getByRole("button", { name: "좋았어요" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("button", { name: "그냥" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });

  it("고르면 해당 값을 알린다", async () => {
    const onChange = vi.fn();
    render(<EmotionChips value={undefined} onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: "별로" }));
    expect(onChange).toHaveBeenCalledWith("bad");
  });

  it("같은 걸 다시 누르면 해제한다", async () => {
    const onChange = vi.fn();
    render(<EmotionChips value="neutral" onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: "그냥" }));
    expect(onChange).toHaveBeenCalledWith(undefined);
  });
});

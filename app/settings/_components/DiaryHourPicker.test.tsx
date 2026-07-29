// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DiaryHourPicker } from "./DiaryHourPicker";

beforeEach(() => vi.restoreAllMocks());

describe("DiaryHourPicker", () => {
  it("현재 시각과 질문을 보인다", () => {
    render(<DiaryHourPicker initial={21} />);

    expect(
      screen.getByRole("combobox", {
        name: "몇 시에 하루를 묶어드릴까요",
      }),
    ).toHaveValue("21");
  });

  it("시각을 바꾸면 PATCH하고 선택을 유지한다", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
    render(<DiaryHourPicker initial={21} />);

    await userEvent.selectOptions(
      screen.getByRole("combobox", {
        name: "몇 시에 하루를 묶어드릴까요",
      }),
      "20",
    );

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(fetchMock).toHaveBeenCalledWith("/api/users/me", {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ diaryHour: 20 }),
    });
    expect(
      screen.getByRole("combobox", {
        name: "몇 시에 하루를 묶어드릴까요",
      }),
    ).toHaveValue("20");
  });

  it("선택 상자는 44px 터치 타깃이다", () => {
    render(<DiaryHourPicker initial={21} />);
    expect(
      screen.getByRole("combobox", {
        name: "몇 시에 하루를 묶어드릴까요",
      }).className,
    ).toContain("min-h-11");
  });
});

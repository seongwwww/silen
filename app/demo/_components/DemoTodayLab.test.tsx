// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DemoTodayLab } from "./DemoTodayLab";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: vi.fn() }),
  usePathname: () => "/demo",
}));

describe("DemoTodayLab", () => {
  it("URL에서 고른 목 상태로 바로 시작할 수 있다", () => {
    render(<DemoTodayLab initialState="arrived" />);

    expect(screen.getByText("DAILY WRAP")).toBeInTheDocument();
  });

  it("목 데이터 상태를 바꿔 Daily Wrap 도착 화면을 확인한다", async () => {
    render(<DemoTodayLab />);

    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "테스트 상태" }),
      "arrived",
    );

    expect(screen.getByText("DAILY WRAP")).toBeInTheDocument();
    expect(
      screen.getByText("오늘의 일기가 도착했어요"),
    ).toBeInTheDocument();
  });

  it("데모의 일기 생성 버튼은 실제 API를 호출하지 않는다", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(<DemoTodayLab />);

    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "테스트 상태" }),
      "available",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "오늘 일기 만들기" }),
    );

    expect(fetchMock).not.toHaveBeenCalled();
    expect(
      screen.getByRole("button", { name: "일기 만들기를 요청했어요" }),
    ).toBeDisabled();
  });

  it("데모의 차이 판단도 실제 API 없이 화면에서 확인한다", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(<DemoTodayLab />);

    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "테스트 상태" }),
      "discovery",
    );
    await userEvent.click(screen.getByRole("button", { name: "맞아요" }));

    expect(fetchMock).not.toHaveBeenCalled();
    expect(
      screen.queryByRole("heading", { name: "오늘의 다른 점" }),
    ).not.toBeInTheDocument();
  });
});

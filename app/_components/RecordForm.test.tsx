// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RecordForm } from "./RecordForm";

const input = () => screen.getByLabelText("오늘의 기록");
const sendButton = () => screen.getByRole("button", { name: "기록하기" });

// navigator 객체 전체를 stub하면 userEvent가 쓰는 clipboard가 사라져 깨진다.
// onLine 속성만 갈아끼운다.
function setOnLine(value: boolean) {
  Object.defineProperty(navigator, "onLine", { value, configurable: true });
}

beforeEach(() => {
  vi.restoreAllMocks();
  setOnLine(true);
});

describe("RecordForm", () => {
  it("빈 입력이면 전송할 수 없다", () => {
    render(<RecordForm />);
    expect(sendButton()).toBeDisabled();
  });

  it("공백만 있어도 전송할 수 없다", async () => {
    render(<RecordForm />);
    await userEvent.type(input(), "   ");
    expect(sendButton()).toBeDisabled();
  });

  it("텍스트와 감정을 바디에 담아 보낸다", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
    render(<RecordForm />);
    await userEvent.type(input(), "점심에 김밥");
    await userEvent.click(screen.getByRole("button", { name: "좋았어요" }));
    await userEvent.click(sendButton());
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/memories");
    expect(JSON.parse(init.body)).toEqual({
      text: "점심에 김밥",
      emotion: "good",
    });
  });

  it("감정을 안 고르면 emotion을 보내지 않는다", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
    render(<RecordForm />);
    await userEvent.type(input(), "그냥 하루");
    await userEvent.click(sendButton());
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      text: "그냥 하루",
    });
  });

  it("성공하면 입력을 비우고 머문다", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true }));
    render(<RecordForm />);
    await userEvent.type(input(), "김밥");
    await userEvent.click(sendButton());
    await waitFor(() => expect(input()).toHaveValue(""));
  });

  it("실패하면 입력을 보존한다", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));
    render(<RecordForm />);
    await userEvent.type(input(), "잃으면 안 되는 글");
    await userEvent.click(sendButton());
    await waitFor(() => expect(input()).toHaveValue("잃으면 안 되는 글"));
  });

  it("이중 클릭에도 한 번만 보낸다(POST는 멱등이 아니다)", async () => {
    let resolve!: (value: unknown) => void;
    const pending = new Promise((pendingResolve) => {
      resolve = pendingResolve;
    });
    const fetchMock = vi.fn().mockReturnValue(pending);
    vi.stubGlobal("fetch", fetchMock);
    render(<RecordForm />);
    await userEvent.type(input(), "중복 금지");
    const button = sendButton();
    await userEvent.click(button);
    await userEvent.click(button);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    resolve({ ok: true });
  });

  it("오프라인이면 보내지 않고 입력을 보존한다", async () => {
    setOnLine(false);
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(<RecordForm />);
    await userEvent.type(input(), "오프라인 글");
    await userEvent.click(sendButton());
    expect(fetchMock).not.toHaveBeenCalled();
    expect(input()).toHaveValue("오프라인 글");
  });

  it("질문이 주어지면 맥락으로 보여준다", () => {
    render(<RecordForm question="지은은 어떤 사람이었어요?" />);
    expect(screen.getByText("지은은 어떤 사람이었어요?")).toBeInTheDocument();
  });
});

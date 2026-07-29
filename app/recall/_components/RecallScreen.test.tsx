// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RecallScreen } from "./RecallScreen";

const fetchMock = vi.fn();

beforeEach(() => {
  // 모듈 전역 mock이라 초기화하지 않으면 앞 테스트의 호출이 누적된다.
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  Object.defineProperty(window.navigator, "onLine", {
    configurable: true,
    value: true,
  });
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("회고 채팅 화면", () => {
  it("처음에는 대화 없이 질문 안내를 보여준다", () => {
    render(<RecallScreen />);

    expect(screen.getByRole("heading", { name: "그거 뭐였지" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "기록에게 질문" })).toHaveAttribute(
      "maxLength",
      "100",
    );
    expect(screen.getByText("찾고 싶은 일을 물어보세요")).toBeInTheDocument();
  });

  it("처리 중 상태 뒤 실제 근거와 확인 질문을 보여준다", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    fetchMock
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ requestId: "00000000-0000-4000-8000-000000000001" }), {
          status: 202,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ status: "processing" }), {
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            status: "done",
            response: {
              answer: "기록에서 이런 내용을 찾았어요.",
              confirmation: "이거 맞으세요?",
              evidence: [
                {
                  memoryId: "m1",
                  capturedAt: "2026-07-14T12:00:00Z",
                  quote: "그 카페에서 오래 이야기했다.",
                },
              ],
            },
          }),
          { headers: { "Content-Type": "application/json" } },
        ),
      );

    render(<RecallScreen timeZone="Asia/Seoul" pollIntervalMs={10} />);
    fireEvent.change(screen.getByRole("textbox", { name: "기록에게 질문" }), {
      target: { value: "카페 언제 갔지" },
    });
    fireEvent.click(screen.getByRole("button", { name: "물어보기" }));

    expect(await screen.findByText("기록에서 찾고 있어요")).toBeInTheDocument();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30);
    });

    expect(screen.getByText("기록에서 이런 내용을 찾았어요.")).toBeInTheDocument();
    expect(screen.getByText("그 카페에서 오래 이야기했다.")).toBeInTheDocument();
    expect(screen.getByText("7.14")).toBeInTheDocument();
    expect(screen.getByText("이거 맞으세요?")).toBeInTheDocument();
  });

  it("근거가 없으면 정확한 빈 결과 문구를 보여준다", async () => {
    fetchMock
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ requestId: "00000000-0000-4000-8000-000000000002" }), {
          status: 202,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            status: "done",
            response: {
              answer: "그런 기록은 찾지 못했어요",
              confirmation: null,
              evidence: [],
            },
          }),
          { headers: { "Content-Type": "application/json" } },
        ),
      );

    render(<RecallScreen pollIntervalMs={1} />);
    fireEvent.change(screen.getByRole("textbox", { name: "기록에게 질문" }), {
      target: { value: "달에 간 날" },
    });
    fireEvent.click(screen.getByRole("button", { name: "물어보기" }));

    expect(await screen.findByText("그런 기록은 찾지 못했어요")).toBeInTheDocument();
  });

  it("오프라인이면 네트워크를 부르지 않고 오프라인 상태를 보여준다", async () => {
    Object.defineProperty(window.navigator, "onLine", {
      configurable: true,
      value: false,
    });

    render(<RecallScreen />);
    fireEvent.change(screen.getByRole("textbox", { name: "기록에게 질문" }), {
      target: { value: "카페" },
    });
    fireEvent.click(screen.getByRole("button", { name: "물어보기" }));

    expect(await screen.findByText("인터넷 연결을 확인해 주세요")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("요청 실패는 다시 시도할 수 있는 오류 상태를 보여준다", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("network"));

    render(<RecallScreen />);
    fireEvent.change(screen.getByRole("textbox", { name: "기록에게 질문" }), {
      target: { value: "카페" },
    });
    fireEvent.click(screen.getByRole("button", { name: "물어보기" }));

    await waitFor(() =>
      expect(screen.getByText("기록을 찾지 못했어요")).toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: "다시 시도" })).toBeInTheDocument();
  });
});


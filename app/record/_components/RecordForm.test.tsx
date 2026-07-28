// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RecordForm } from "./RecordForm";

const input = () => screen.getByLabelText("오늘의 기록");
const sendButton = () => screen.getByRole("button", { name: "남기기" });

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
    expect(screen.getByText("이 질문에서 이어 쓰는 중")).toBeInTheDocument();
    expect(screen.getByText("지은은 어떤 사람이었어요?")).toBeInTheDocument();
    expect(
      screen.getByText(
        "한 번에 다 적지 않아도 괜찮아요. 같은 질문에서 여러 번 이어 쓸 수 있어요.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "이렇게 남긴 기록도 쌓여, 나중에 작은 차이를 찾는 단서가 돼요.",
      ),
    ).toBeInTheDocument();
  });

  it("원할 때만 생각 단서를 한 가지씩 바꿔 보여준다", async () => {
    render(<RecordForm question="지은은 어떤 사람이었어요?" />);

    const cueButton = screen.getByRole("button", {
      name: "다른 각도로 떠올려보기",
    });
    expect(
      screen.queryByText("같이 떠오르는 장면이 있나요?"),
    ).not.toBeInTheDocument();

    await userEvent.click(cueButton);
    expect(
      screen.getByText("같이 떠오르는 장면이 있나요?"),
    ).toBeInTheDocument();

    await userEvent.click(
      screen.getByRole("button", { name: "다른 단서 보기" }),
    );
    expect(
      screen.getByText("미처 남기지 않은 부분이 있나요?"),
    ).toBeInTheDocument();
  });

  it("일반 기록에는 질문 세션 단서를 보여주지 않는다", () => {
    render(<RecordForm />);
    expect(
      screen.queryByRole("button", { name: "다른 각도로 떠올려보기" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(
        "이렇게 남긴 기록도 쌓여, 나중에 작은 차이를 찾는 단서가 돼요.",
      ),
    ).not.toBeInTheDocument();
  });

  it("같은 질문에서 여러 번 기록해도 질문 맥락이 남는다", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
    render(<RecordForm question="지은은 어떤 사람이었어요?" />);

    await userEvent.type(input(), "첫 번째 기록");
    await userEvent.click(sendButton());
    await waitFor(() => expect(input()).toHaveValue(""));

    await userEvent.type(input(), "두 번째 기록");
    await userEvent.click(sendButton());
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));

    expect(screen.getByText("지은은 어떤 사람이었어요?")).toBeInTheDocument();
  });
});

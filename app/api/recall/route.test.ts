import { beforeEach, describe, expect, it, vi } from "vitest";

const getUser = vi.fn();
const enqueue = vi.fn();
const poll = vi.fn();

vi.mock("@/lib/repositories/supabase", () => ({
  createServerSupabase: vi.fn().mockResolvedValue({
    auth: { getUser },
  }),
}));

vi.mock("@/lib/repositories/recallRepository", () => ({
  createRecallRepository: vi.fn(() => ({ enqueue, poll })),
}));

describe("/api/recall", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("세션이 없으면 질문을 큐에 넣지 않는다", async () => {
    getUser.mockResolvedValue({ data: { user: null } });
    const { POST } = await import("./route");

    const response = await POST(
      new Request("http://localhost/api/recall", {
        method: "POST",
        body: JSON.stringify({
          requestId: "00000000-0000-4000-8000-000000000001",
          question: "카페 언제 갔지",
        }),
      }),
    );

    expect(response.status).toBe(401);
    expect(enqueue).not.toHaveBeenCalled();
  });

  it("검증한 질문을 기존 큐에 멱등 적재한다", async () => {
    getUser.mockResolvedValue({ data: { user: { id: "u1" } } });
    enqueue.mockResolvedValue(undefined);
    const { POST } = await import("./route");

    const response = await POST(
      new Request("http://localhost/api/recall", {
        method: "POST",
        body: JSON.stringify({
          requestId: "00000000-0000-4000-8000-000000000001",
          question: "  카페 언제 갔지  ",
        }),
      }),
    );

    expect(response.status).toBe(202);
    expect(enqueue).toHaveBeenCalledWith(
      "00000000-0000-4000-8000-000000000001",
      "카페 언제 갔지",
    );
  });

  it("다른 사용자 정보는 입력으로 받지 않고 polling 결과만 반환한다", async () => {
    getUser.mockResolvedValue({ data: { user: { id: "u1" } } });
    poll.mockResolvedValue({ status: "processing" });
    const { GET } = await import("./route");

    const response = await GET(
      new Request(
        "http://localhost/api/recall?requestId=00000000-0000-4000-8000-000000000001",
      ),
    );

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ status: "processing" });
    expect(poll).toHaveBeenCalledWith("00000000-0000-4000-8000-000000000001");
  });
});

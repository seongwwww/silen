import { beforeEach, describe, expect, it, vi } from "vitest";

const getUser = vi.fn();
const findTimeZone = vi.fn();
const enqueue = vi.fn();

vi.mock("@/lib/repositories/supabase", () => ({
  createServerSupabase: vi.fn().mockResolvedValue({
    auth: { getUser },
  }),
}));

vi.mock("@/lib/repositories/userRepository", () => ({
  createUserRepository: vi.fn(() => ({ findTimeZone })),
}));

vi.mock("@/lib/repositories/diaryRepository", () => ({
  createDiaryRepository: vi.fn(() => ({ enqueue })),
}));

describe("POST /api/diaries/generate", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useRealTimers();
  });

  it("세션이 없으면 401이고 큐를 건드리지 않는다", async () => {
    getUser.mockResolvedValue({ data: { user: null } });
    const { POST } = await import("./route");

    const response = await POST();

    expect(response.status).toBe(401);
    expect(enqueue).not.toHaveBeenCalled();
  });

  it("사용자 로컬 오늘 일기를 멱등 요청하고 202를 돌려준다", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-28T01:00:00.000Z"));
    getUser.mockResolvedValue({ data: { user: { id: "user-1" } } });
    findTimeZone.mockResolvedValue("America/Los_Angeles");
    enqueue.mockResolvedValue(undefined);
    const { POST } = await import("./route");

    const response = await POST();

    expect(response.status).toBe(202);
    expect(await response.json()).toEqual({
      accepted: true,
      date: "2026-07-27",
    });
    expect(enqueue).toHaveBeenCalledWith("2026-07-27");
  });

  it("큐 적재 실패는 내부 정보를 숨긴 500으로 돌려준다", async () => {
    getUser.mockResolvedValue({ data: { user: { id: "user-1" } } });
    findTimeZone.mockResolvedValue("Asia/Seoul");
    enqueue.mockRejectedValue(new Error("database detail"));
    const { POST } = await import("./route");

    const response = await POST();

    expect(response.status).toBe(500);
    expect(await response.json()).toEqual({
      error: {
        code: "server_error",
        message: "일기 생성 요청에 실패했습니다",
      },
    });
  });
});

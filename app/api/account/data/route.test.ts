import { beforeEach, describe, expect, it, vi } from "vitest";

const getUser = vi.fn();
const requestForSession = vi.fn();

vi.mock("@/lib/repositories/supabase", () => ({
  createServerSupabase: vi.fn(async () => ({
    auth: { getUser },
  })),
}));
vi.mock("@/lib/services/accountDeletionServer", () => ({
  requestAccountDataDeletionForSession: requestForSession,
}));

describe("DELETE /api/account/data", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getUser.mockResolvedValue({ data: { user: { id: "user-1" } } });
    requestForSession.mockResolvedValue({
      id: "deletion-1",
      status: "running",
    });
  });

  it("인증 사용자의 삭제 원장 요청을 만들고 202를 돌려준다", async () => {
    const { DELETE } = await import("./route");

    const response = await DELETE();

    expect(response.status).toBe(202);
    expect(await response.json()).toEqual({
      id: "deletion-1",
      status: "running",
    });
    expect(requestForSession).toHaveBeenCalledOnce();
  });

  it("세션이 없으면 401이고 원장을 요청하지 않는다", async () => {
    getUser.mockResolvedValue({ data: { user: null } });
    const { DELETE } = await import("./route");

    const response = await DELETE();

    expect(response.status).toBe(401);
    expect(requestForSession).not.toHaveBeenCalled();
  });

  it("저장소 오류 본문을 노출하지 않고 고정된 500 오류를 돌려준다", async () => {
    requestForSession.mockRejectedValue(
      new Error("private database detail"),
    );
    const { DELETE } = await import("./route");

    const response = await DELETE();

    expect(response.status).toBe(500);
    expect(await response.json()).toEqual({
      error: {
        code: "server_error",
        message: "삭제를 요청하지 못했습니다",
      },
    });
  });
});

import { beforeEach, describe, expect, it, vi } from "vitest";

const getUser = vi.fn();
const request = vi.fn();

vi.mock("@/lib/repositories/supabase", () => ({
  createServerSupabase: vi.fn(async () => ({
    auth: { getUser },
  })),
}));
vi.mock("@/lib/repositories/accountDeletionRepository", () => ({
  createAccountDeletionRepository: vi.fn(() => ({ request })),
}));

describe("DELETE /api/account/data", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getUser.mockResolvedValue({ data: { user: { id: "user-1" } } });
    request.mockResolvedValue("deletion-1");
  });

  it("인증 사용자의 삭제 원장 요청을 만들고 202를 돌려준다", async () => {
    const { DELETE } = await import("./route");

    const response = await DELETE();

    expect(response.status).toBe(202);
    expect(await response.json()).toEqual({
      id: "deletion-1",
      status: "running",
    });
    expect(request).toHaveBeenCalledOnce();
  });

  it("세션이 없으면 401이고 원장을 요청하지 않는다", async () => {
    getUser.mockResolvedValue({ data: { user: null } });
    const { DELETE } = await import("./route");

    const response = await DELETE();

    expect(response.status).toBe(401);
    expect(request).not.toHaveBeenCalled();
  });
});

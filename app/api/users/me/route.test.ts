import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const getUser = vi.fn();
const updateTonePreset = vi.fn();
const updateDiaryHour = vi.fn();

vi.mock("@/lib/repositories/supabase", () => ({
  createServerSupabase: vi.fn().mockResolvedValue({
    auth: { getUser },
  }),
}));

vi.mock("@/lib/repositories/userRepository", () => ({
  createUserRepository: vi.fn(() => ({
    updateTonePreset,
    updateDiaryHour,
  })),
}));

describe("PATCH /api/users/me", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getUser.mockResolvedValue({ data: { user: { id: "user-1" } } });
    updateTonePreset.mockResolvedValue(true);
    updateDiaryHour.mockResolvedValue(true);
  });

  it("일기 시각을 0~23 정수로 저장한다", async () => {
    const { PATCH } = await import("./route");
    const response = await PATCH(
      new NextRequest("http://localhost/api/users/me", {
        method: "PATCH",
        body: JSON.stringify({ diaryHour: 20 }),
        headers: { "content-type": "application/json" },
      }),
    );

    expect(response.status).toBe(204);
    expect(updateDiaryHour).toHaveBeenCalledWith(20);
    expect(updateTonePreset).not.toHaveBeenCalled();
  });

  it("범위 밖 시각은 400이고 저장하지 않는다", async () => {
    const { PATCH } = await import("./route");
    const response = await PATCH(
      new NextRequest("http://localhost/api/users/me", {
        method: "PATCH",
        body: JSON.stringify({ diaryHour: 24 }),
        headers: { "content-type": "application/json" },
      }),
    );

    expect(response.status).toBe(400);
    expect(updateDiaryHour).not.toHaveBeenCalled();
  });
});

import { beforeEach, describe, expect, it, vi } from "vitest";
import { TONE_INSTRUCTION_MAX_LENGTH } from "@/lib/services/diary";

const getUser = vi.fn();
const requestRegenerate = vi.fn();

vi.mock("@/lib/repositories/supabase", () => ({
  createServerSupabase: vi.fn().mockResolvedValue({
    auth: { getUser },
  }),
}));

vi.mock("@/lib/repositories/diaryRepository", () => ({
  createDiaryRepository: vi.fn(() => ({ requestRegenerate })),
}));

const context = {
  params: Promise.resolve({ id: "diary-1" }),
};

function request(body?: string) {
  return new Request("http://localhost/api/diaries/diary-1/regenerate", {
    method: "POST",
    ...(body === undefined
      ? {}
      : {
          body,
          headers: { "content-type": "application/json" },
        }),
  });
}

describe("POST /api/diaries/[id]/regenerate", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getUser.mockResolvedValue({ data: { user: { id: "user-1" } } });
    requestRegenerate.mockResolvedValue(true);
  });

  it("빈 body는 기존 호출과 호환해 주문 없이 재생성을 요청한다", async () => {
    const { POST } = await import("./route");

    const response = await POST(request(), context);

    expect(response.status).toBe(204);
    expect(requestRegenerate).toHaveBeenCalledWith("diary-1", null);
  });

  it("선택적 주문을 trim해서 저장한다", async () => {
    const { POST } = await import("./route");

    const response = await POST(
      request(JSON.stringify({ toneInstruction: "  더 짧고 건조하게  " })),
      context,
    );

    expect(response.status).toBe(204);
    expect(requestRegenerate).toHaveBeenCalledWith(
      "diary-1",
      "더 짧고 건조하게",
    );
  });

  it.each([
    ["빈 객체", {}],
    ["명시적 null", { toneInstruction: null }],
    ["공백 문자열", { toneInstruction: " \n\t " }],
  ])("%s는 주문 없음으로 정규화한다", async (_label, body) => {
    const { POST } = await import("./route");

    const response = await POST(request(JSON.stringify(body)), context);

    expect(response.status).toBe(204);
    expect(requestRegenerate).toHaveBeenCalledWith("diary-1", null);
  });

  it("trim한 주문은 길이 상한까지 허용한다", async () => {
    const { POST } = await import("./route");
    const instruction = "가".repeat(TONE_INSTRUCTION_MAX_LENGTH);

    const response = await POST(
      request(JSON.stringify({ toneInstruction: ` ${instruction} ` })),
      context,
    );

    expect(response.status).toBe(204);
    expect(requestRegenerate).toHaveBeenCalledWith("diary-1", instruction);
  });

  it.each([
    ["잘못된 JSON", "{"],
    ["문자열이 아닌 주문", JSON.stringify({ toneInstruction: 1 })],
    [
      "길이 상한을 넘는 주문",
      JSON.stringify({
        toneInstruction: "가".repeat(TONE_INSTRUCTION_MAX_LENGTH + 1),
      }),
    ],
    ["알 수 없는 필드", JSON.stringify({ toneInstruction: null, force: true })],
    ["객체가 아닌 body", JSON.stringify(null)],
  ])("%s는 400이고 저장소를 호출하지 않는다", async (_label, body) => {
    const { POST } = await import("./route");

    const response = await POST(request(body), context);

    expect(response.status).toBe(400);
    expect(await response.json()).toEqual({
      error: {
        code: "invalid_body",
        message: "요청 형식이 올바르지 않습니다",
      },
    });
    expect(requestRegenerate).not.toHaveBeenCalled();
  });

  it("세션이 없으면 401이고 저장소를 호출하지 않는다", async () => {
    getUser.mockResolvedValue({ data: { user: null } });
    const { POST } = await import("./route");

    const response = await POST(request(), context);

    expect(response.status).toBe(401);
    expect(requestRegenerate).not.toHaveBeenCalled();
  });

  it("세션이 없으면 body가 잘못돼도 401을 우선한다", async () => {
    getUser.mockResolvedValue({ data: { user: null } });
    const { POST } = await import("./route");

    const response = await POST(request("{"), context);

    expect(response.status).toBe(401);
    expect(requestRegenerate).not.toHaveBeenCalled();
  });

  it("본인에게 보이는 일기가 없으면 404를 돌려준다", async () => {
    requestRegenerate.mockResolvedValue(false);
    const { POST } = await import("./route");

    const response = await POST(
      request(JSON.stringify({ toneInstruction: "짧게" })),
      context,
    );

    expect(response.status).toBe(404);
    expect(requestRegenerate).toHaveBeenCalledWith("diary-1", "짧게");
  });
});

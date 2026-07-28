import { beforeEach, describe, expect, it, vi } from "vitest";
import type { DataExportCollections } from "@/lib/services/dataExport";

const getUser = vi.fn();
const findAllByUserId = vi.fn();

vi.mock("@/lib/repositories/supabase", () => ({
  createServerSupabase: vi.fn().mockResolvedValue({
    auth: { getUser },
  }),
}));

vi.mock("@/lib/repositories/dataExportRepository", () => ({
  createDataExportRepository: vi.fn(() => ({ findAllByUserId })),
}));

const emptyCollections: DataExportCollections = {
  memories: [],
  emotions: [],
  assets: [],
  entities: [],
  memory_entities: [],
  differences: [],
  difference_narrations: [],
  difference_evidence: [],
  diaries: [],
  diary_sections: [],
  diary_sources: [],
  weekly_reports: [],
  weekly_report_highlights: [],
};

describe("GET /api/export", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getUser.mockResolvedValue({ data: { user: { id: "user-1" } } });
    findAllByUserId.mockResolvedValue(emptyCollections);
  });

  it("세션이 없으면 401이고 데이터를 읽지 않는다", async () => {
    getUser.mockResolvedValue({ data: { user: null } });
    const { GET } = await import("./route");

    const response = await GET();

    expect(response.status).toBe(401);
    expect(findAllByUserId).not.toHaveBeenCalled();
    expect(await response.json()).toEqual({
      error: {
        code: "unauthorized",
        message: "세션이 필요합니다",
      },
    });
  });

  it("본인 기록 JSON을 첨부 파일로 내려준다", async () => {
    findAllByUserId.mockResolvedValue({
      ...emptyCollections,
      memories: [{ id: "memory-1", raw_text: "내 기록" }],
    });
    const { GET } = await import("./route");

    const response = await GET();
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(response.headers.get("cache-control")).toBe("no-store");
    expect(response.headers.get("content-disposition")).toMatch(
      /^attachment; filename="silen-records-\d{4}-\d{2}-\d{2}\.json"$/,
    );
    expect(response.headers.get("content-type")).toContain(
      "application/json",
    );
    expect(findAllByUserId).toHaveBeenCalledWith("user-1");
    expect(body.formatVersion).toBe(1);
    expect(body.exportedAt).toMatch(/Z$/);
    expect(body.data.memories).toEqual([
      { id: "memory-1", raw_text: "내 기록" },
    ]);
    expect(body.data.assets).toEqual([]);
  });

  it("조회 실패는 본문과 내부 오류를 숨기고 로그에도 남기지 않는다", async () => {
    findAllByUserId.mockRejectedValue(
      new Error("private raw text database detail"),
    );
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const logSpy = vi.spyOn(console, "log").mockImplementation(() => {});
    const { GET } = await import("./route");

    const response = await GET();

    expect(response.status).toBe(500);
    expect(await response.json()).toEqual({
      error: {
        code: "server_error",
        message: "내보내기에 실패했습니다",
      },
    });
    expect(errorSpy).not.toHaveBeenCalled();
    expect(logSpy).not.toHaveBeenCalled();
  });
});

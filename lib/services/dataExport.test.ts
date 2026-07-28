import { describe, expect, it, vi } from "vitest";
import {
  buildUserDataExport,
  type DataExportCollections,
  type DataExportPort,
} from "./dataExport";

export const emptyCollections: DataExportCollections = {
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

describe("기록 JSON 내보내기 서비스", () => {
  it("본인 id로 읽은 컬렉션을 버전과 생성 시각으로 감싼다", async () => {
    const findAllByUserId = vi.fn().mockResolvedValue({
      ...emptyCollections,
      memories: [{ id: "memory-1", raw_text: "기록" }],
    });
    const port: DataExportPort = { findAllByUserId };
    const now = new Date("2026-07-28T12:34:56.000Z");

    const result = await buildUserDataExport(port, "user-1", now);

    expect(findAllByUserId).toHaveBeenCalledWith("user-1");
    expect(result).toEqual({
      formatVersion: 1,
      exportedAt: "2026-07-28T12:34:56.000Z",
      data: {
        ...emptyCollections,
        memories: [{ id: "memory-1", raw_text: "기록" }],
      },
    });
  });
});

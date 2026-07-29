export type DataExportRow = Record<string, unknown>;

export interface DataExportCollections {
  memories: DataExportRow[];
  emotions: DataExportRow[];
  assets: DataExportRow[];
  entities: DataExportRow[];
  memory_entities: DataExportRow[];
  differences: DataExportRow[];
  difference_narrations: DataExportRow[];
  difference_evidence: DataExportRow[];
  diaries: DataExportRow[];
  diary_sections: DataExportRow[];
  diary_sources: DataExportRow[];
  weekly_reports: DataExportRow[];
  weekly_report_highlights: DataExportRow[];
}

export interface DataExportPort {
  findAllByUserId(userId: string): Promise<DataExportCollections>;
}

export interface UserDataExport {
  formatVersion: 1;
  exportedAt: string;
  data: DataExportCollections;
}

/** 저장소에서 본인 데이터만 읽어 안정적인 JSON 문서 계약으로 감싼다. */
export async function buildUserDataExport(
  repository: DataExportPort,
  userId: string,
  now = new Date(),
): Promise<UserDataExport> {
  const data = await repository.findAllByUserId(userId);
  return {
    formatVersion: 1,
    exportedAt: now.toISOString(),
    data,
  };
}

export const RECALL_QUERY_MAX = 100;
export const RECALL_RESULT_LIMIT = 20;
export const RECALL_EXCERPT_MAX = 160;

export interface RecallMemoryRow {
  id: string;
  rawText: string;
  capturedAt: string;
}

export interface RecallSearchPort {
  search(userId: string, query: string): Promise<RecallMemoryRow[]>;
}

export interface RecallResult {
  id: string;
  capturedAt: string;
  excerpt: string;
}

export class InvalidRecallQueryError extends Error {
  constructor() {
    super(`검색어는 ${RECALL_QUERY_MAX}자 이하여야 한다`);
    this.name = "InvalidRecallQueryError";
  }
}

export async function searchRecall(
  repo: RecallSearchPort,
  userId: string,
  rawQuery: string,
): Promise<RecallResult[]> {
  const query = rawQuery.trim();
  if (!query) return [];
  if (query.length > RECALL_QUERY_MAX) {
    throw new InvalidRecallQueryError();
  }

  const rows = await repo.search(userId, query);
  return rows.map((row) => ({
    id: row.id,
    capturedAt: row.capturedAt,
    excerpt: row.rawText.trim().slice(0, RECALL_EXCERPT_MAX),
  }));
}

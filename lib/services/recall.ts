export const RECALL_QUERY_MAX = 100;

export interface RecallEvidence {
  memoryId: string;
  capturedAt: string;
  quote: string;
  /** 서버가 Storage 경로를 짧은 서명 URL로 바꾼 뒤에만 내려준다. */
  photoUrl?: string | null;
}

export interface RecallAnswer {
  answer: string;
  confirmation: string | null;
  evidence: RecallEvidence[];
}

export type RecallPollResult =
  | { status: "queued" | "processing" }
  | { status: "done"; response: RecallAnswer }
  | { status: "error"; errorCode?: string }
  | { status: "missing" };

export interface RecallQueuePort {
  enqueue(requestId: string, question: string): Promise<void>;
  poll(requestId: string): Promise<RecallPollResult>;
}

export class InvalidRecallQueryError extends Error {
  constructor() {
    super(`질문은 1자 이상 ${RECALL_QUERY_MAX}자 이하여야 한다`);
    this.name = "InvalidRecallQueryError";
  }
}

export function validateRecallQuery(rawQuery: string): string {
  const query = rawQuery.trim();
  if (!query || query.length > RECALL_QUERY_MAX) {
    throw new InvalidRecallQueryError();
  }
  return query;
}

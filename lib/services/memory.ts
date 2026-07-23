/**
 * 기록 도메인 규칙. 프레임워크·HTTP·Supabase 타입을 모른다(backend.md).
 * 저장소는 MemoryRepository로 주입받는다.
 */

export type EmotionChoice = "good" | "neutral" | "bad";

export interface MemoryRepository {
  insertMemory(row: {
    userId: string;
    rawText: string | null;
    occurredAt: string | null;
  }): Promise<{ id: string }>;
  insertEmotion(row: { memoryId: string; valence: number }): Promise<void>;
  insertAsset(row: { memoryId: string; fileUrl: string; mimeType: string | null }): Promise<void>;
}

export type CreateMemoryInput = {
  userId: string;
  text?: string;
  emotion?: EmotionChoice;
  assetPaths?: string[];
  occurredAt?: string;
};

/** text와 asset이 둘 다 없을 때. 빈 기록은 만들지 않는다(제품 원칙). */
export class EmptyMemoryError extends Error {
  constructor() {
    super("text와 asset 중 최소 하나가 필요하다");
    this.name = "EmptyMemoryError";
  }
}

/** assetPaths에 세션 사용자 폴더가 아닌 경로가 있을 때(누출 방어). */
export class ForeignAssetPathError extends Error {
  constructor() {
    super("assetPaths는 본인 폴더로 시작해야 한다");
    this.name = "ForeignAssetPathError";
  }
}

const VALENCE: Record<EmotionChoice, number> = { good: 1, neutral: 0, bad: -1 };

const MIME_BY_EXT: Record<string, string> = {
  jpg: "image/jpeg",
  jpeg: "image/jpeg",
  png: "image/png",
  webp: "image/webp",
  gif: "image/gif",
  heic: "image/heic",
};

function deriveMime(path: string): string | null {
  const ext = path.split(".").pop()?.toLowerCase() ?? "";
  return MIME_BY_EXT[ext] ?? null;
}

export async function createMemory(
  repo: MemoryRepository,
  input: CreateMemoryInput,
): Promise<{ memoryId: string }> {
  const trimmed = input.text?.trim() ?? "";
  const hasText = trimmed.length > 0;
  const paths = input.assetPaths ?? [];
  const hasAssets = paths.length > 0;

  if (!hasText && !hasAssets) {
    throw new EmptyMemoryError();
  }

  // 경로 검증: RLS는 파일 소유권을 안 보므로 여기가 유일한 방어선(스펙 §5).
  for (const path of paths) {
    if ((path.split("/")[0] ?? "") !== input.userId) {
      throw new ForeignAssetPathError();
    }
  }

  const { id: memoryId } = await repo.insertMemory({
    userId: input.userId,
    rawText: hasText ? trimmed : null,
    occurredAt: input.occurredAt ?? null,
  });

  if (input.emotion) {
    await repo.insertEmotion({ memoryId, valence: VALENCE[input.emotion] });
  }

  for (const path of paths) {
    await repo.insertAsset({ memoryId, fileUrl: path, mimeType: deriveMime(path) });
  }

  return { memoryId };
}

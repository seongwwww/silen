/**
 * 사진 업로드 흐름. 저장소를 포트로 주입받아 Storage·Supabase 타입을 모른다.
 * 검증은 photo.ts의 순수 규칙을 그대로 쓴다.
 */

import { validatePhoto } from "./photo";

export { photoObjectPath } from "./photo";

export interface PhotoStoragePort {
  /** 세션을 보장하고 사용자 id를 돌려준다. 업로드는 본인 폴더에만 가능하다. */
  currentUserId(): Promise<string>;
  upload(userId: string, file: File, uuid: string): Promise<string>;
}

/** 성공하면 `{user_id}/{uuid}.{ext}` 저장 경로를 돌려준다.
 * 실패는 그대로 던진다 — 호출자가 사용자에게 알리고 글은 지우지 않는다. */
export async function uploadPhoto(
  storage: PhotoStoragePort,
  file: File,
): Promise<string> {
  validatePhoto(file);
  const userId = await storage.currentUserId();
  return storage.upload(userId, file, crypto.randomUUID());
}

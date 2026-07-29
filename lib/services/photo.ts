/**
 * 사진 첨부 규칙. 프레임워크·Supabase 타입을 모른다(backend.md).
 *
 * 확장자로 mime을 되살리는 쪽(memory.ts deriveMime)과 짝을 이룬다 —
 * 여기서 통과시킨 확장자는 거기서도 알아볼 수 있어야 한다.
 */

export const PHOTO_MAX_BYTES = 8 * 1024 * 1024;

/** 업로드를 허용하는 확장자. memory.ts의 MIME_BY_EXT와 같은 집합이다. */
const EXT_BY_TYPE: Record<string, string> = {
  "image/jpeg": "jpg",
  "image/png": "png",
  "image/webp": "webp",
  "image/gif": "gif",
  "image/heic": "heic",
};

export class UnsupportedPhotoTypeError extends Error {
  constructor() {
    super("지원하지 않는 이미지 형식이다");
    this.name = "UnsupportedPhotoTypeError";
  }
}

export class PhotoTooLargeError extends Error {
  constructor() {
    super("사진이 너무 크다");
    this.name = "PhotoTooLargeError";
  }
}

export type PhotoFileInfo = { type: string; size: number; name: string };

export function validatePhoto(file: PhotoFileInfo): void {
  if (!EXT_BY_TYPE[file.type]) throw new UnsupportedPhotoTypeError();
  if (file.size > PHOTO_MAX_BYTES) throw new PhotoTooLargeError();
}

/**
 * 저장 경로를 만든다. 규약은 `{user_id}/{uuid}.{ext}`.
 *
 * 최상위 폴더가 소유자라 Storage 정책과 서버 검증이 둘 다 이걸 본다.
 * 원본 파일명은 쓰지 않는다 — 개인정보가 섞이고 경로 조작 여지가 생긴다.
 */
export function photoObjectPath(
  userId: string,
  fileName: string,
  uuid: string,
): string {
  const ext = fileName.split(".").pop()?.toLowerCase() ?? "";
  return `${userId}/${uuid}.${ext}`;
}

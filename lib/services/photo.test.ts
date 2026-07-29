import { describe, it, expect } from "vitest";
import {
  PHOTO_MAX_BYTES,
  PhotoTooLargeError,
  UnsupportedPhotoTypeError,
  photoObjectPath,
  validatePhoto,
} from "./photo";

describe("사진 검증", () => {
  it("지원하는 이미지는 통과한다", () => {
    expect(() =>
      validatePhoto({ type: "image/jpeg", size: 1024, name: "a.jpg" }),
    ).not.toThrow();
  });

  it("이미지가 아니면 거부한다", () => {
    expect(() =>
      validatePhoto({ type: "application/pdf", size: 10, name: "a.pdf" }),
    ).toThrow(UnsupportedPhotoTypeError);
  });

  it("확장자를 모르면 거부한다", () => {
    // 경로 확장자로 mime을 되살리므로(memory.ts) 모르는 확장자는 받지 않는다.
    expect(() =>
      validatePhoto({ type: "image/tiff", size: 10, name: "a.tiff" }),
    ).toThrow(UnsupportedPhotoTypeError);
  });

  it("상한을 넘으면 거부한다", () => {
    expect(() =>
      validatePhoto({ type: "image/png", size: PHOTO_MAX_BYTES + 1, name: "a.png" }),
    ).toThrow(PhotoTooLargeError);
  });

  it("상한과 같으면 통과한다", () => {
    expect(() =>
      validatePhoto({ type: "image/png", size: PHOTO_MAX_BYTES, name: "a.png" }),
    ).not.toThrow();
  });
});

describe("저장 경로", () => {
  it("본인 폴더 아래에 확장자를 지켜 만든다", () => {
    // 최상위 폴더가 소유자다(supabase/README.md Storage 절).
    expect(photoObjectPath("u1", "사진.JPG", "abc")).toBe("u1/abc.jpg");
  });

  it("파일명을 경로에 쓰지 않는다", () => {
    // 파일명에 개인정보나 경로 조작이 섞일 수 있다.
    const path = photoObjectPath("u1", "../../etc/passwd.png", "abc");
    expect(path).toBe("u1/abc.png");
  });
});

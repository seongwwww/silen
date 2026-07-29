import { describe, it, expect, vi } from "vitest";
import { PhotoTooLargeError, UnsupportedPhotoTypeError } from "./photo";
import { uploadPhoto, type PhotoStoragePort } from "./photoUpload";

function port(overrides: Partial<PhotoStoragePort> = {}): PhotoStoragePort {
  return {
    currentUserId: async () => "u1",
    upload: async (userId, file) => `${userId}/x.${file.name.split(".").pop()}`,
    ...overrides,
  };
}

const jpeg = { type: "image/jpeg", size: 100, name: "a.jpg" } as File;

describe("사진 업로드", () => {
  it("검증을 통과하면 저장 경로를 돌려준다", async () => {
    await expect(uploadPhoto(port(), jpeg)).resolves.toBe("u1/x.jpg");
  });

  it("형식이 안 맞으면 업로드를 시도조차 하지 않는다", async () => {
    const upload = vi.fn();
    await expect(
      uploadPhoto(port({ upload }), { type: "application/pdf", size: 1, name: "a.pdf" } as File),
    ).rejects.toThrow(UnsupportedPhotoTypeError);
    expect(upload).not.toHaveBeenCalled();
  });

  it("너무 크면 업로드를 시도조차 하지 않는다", async () => {
    const upload = vi.fn();
    await expect(
      uploadPhoto(port({ upload }), {
        type: "image/png",
        size: 99 * 1024 * 1024,
        name: "a.png",
      } as File),
    ).rejects.toThrow(PhotoTooLargeError);
    expect(upload).not.toHaveBeenCalled();
  });

  it("업로드 실패는 삼키지 않는다", async () => {
    const failing = port({
      upload: async () => {
        throw new Error("storage_down");
      },
    });
    await expect(uploadPhoto(failing, jpeg)).rejects.toThrow("storage_down");
  });
});

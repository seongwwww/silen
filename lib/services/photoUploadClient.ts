import { createBrowserPhotoRepository } from "@/lib/repositories/photoRepository";
import { uploadPhoto } from "./photoUpload";

/** 화면이 저장소·Storage를 직접 알지 않게 하는 클라이언트 합성 facade. */
export function uploadPhotoInBrowser(file: File): Promise<string> {
  return uploadPhoto(createBrowserPhotoRepository(), file);
}

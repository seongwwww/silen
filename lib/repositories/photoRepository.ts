import { createBrowserClient } from "@supabase/ssr";
import type { SupabaseClient } from "@supabase/supabase-js";
import { photoObjectPath, type PhotoStoragePort } from "@/lib/services/photoUpload";

const BUCKET = "memories";

/** Storage 접근은 저장소 계층에서만 한다(backend.md).
 * 세션이 없으면 익명으로 만든다 — 업로드는 인증된 본인 폴더에만 쓸 수 있다. */
export function createPhotoRepository(client: SupabaseClient): PhotoStoragePort {
  return {
    async currentUserId() {
      const {
        data: { user },
      } = await client.auth.getUser();
      if (user) return user.id;

      const { data, error } = await client.auth.signInAnonymously();
      if (error || !data.user) throw new Error("session_failed");
      return data.user.id;
    },

    async upload(userId, file, uuid) {
      const path = photoObjectPath(userId, file.name, uuid);
      // upsert를 켜면 uuid 충돌 시 남의 파일을 덮을 여지가 생긴다.
      const { error } = await client.storage
        .from(BUCKET)
        .upload(path, file, { contentType: file.type, upsert: false });
      if (error) throw error;
      return path;
    },
  };
}

/** 브라우저용 조립. `supabase.ts`는 최상단에서 next/headers를 임포트해
 * 클라이언트 번들에 넣을 수 없으므로 여기서 직접 만든다. */
export function createBrowserPhotoRepository(): PhotoStoragePort {
  return createPhotoRepository(
    createBrowserClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    ),
  );
}

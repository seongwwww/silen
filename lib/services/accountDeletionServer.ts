import type { SupabaseClient } from "@supabase/supabase-js";
import { createAccountDeletionRepository } from "@/lib/repositories/accountDeletionRepository";
import { requestAccountDataDeletion } from "./accountDeletion";

/** Route Handler가 저장소 구현을 직접 알지 않게 하는 서버 합성 facade. */
export async function requestAccountDataDeletionForSession(
  client: SupabaseClient,
) {
  return requestAccountDataDeletion(
    createAccountDeletionRepository(client),
  );
}

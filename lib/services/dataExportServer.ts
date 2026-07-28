import type { SupabaseClient } from "@supabase/supabase-js";
import { createDataExportRepository } from "@/lib/repositories/dataExportRepository";
import { buildUserDataExport } from "./dataExport";

/** Route Handler가 저장소 구현을 직접 알지 않게 하는 서버 합성 facade. */
export async function exportUserDataForSession(
  client: SupabaseClient,
  userId: string,
) {
  return buildUserDataExport(
    createDataExportRepository(client),
    userId,
  );
}

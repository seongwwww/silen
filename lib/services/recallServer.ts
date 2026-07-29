import type { SupabaseClient } from "@supabase/supabase-js";
import { createRecallRepository } from "@/lib/repositories/recallRepository";
import { validateRecallQuery, type RecallPollResult } from "./recall";

/** Route Handler가 저장소 구현을 직접 알지 않게 하는 서버 합성 facade.
 * 질문 검증은 서비스가 하고, 경계는 결과만 받는다. */
export async function enqueueRecallForSession(
  client: SupabaseClient,
  requestId: string,
  question: string,
): Promise<void> {
  return createRecallRepository(client).enqueue(
    requestId,
    validateRecallQuery(question),
  );
}

export async function pollRecallForSession(
  client: SupabaseClient,
  requestId: string,
): Promise<RecallPollResult> {
  return createRecallRepository(client).poll(requestId);
}

import type { SupabaseClient } from "@supabase/supabase-js";
import type { RecallPollResult, RecallQueuePort } from "@/lib/services/recall";

function isPollResult(value: unknown): value is RecallPollResult {
  if (!value || typeof value !== "object" || !("status" in value)) return false;
  const status = (value as { status?: unknown }).status;
  return (
    status === "queued" ||
    status === "processing" ||
    status === "done" ||
    status === "error" ||
    status === "missing"
  );
}

export function createRecallRepository(client: SupabaseClient): RecallQueuePort {
  return {
    async enqueue(requestId, question) {
      const { error } = await client.rpc("request_recall", {
        target_request_id: requestId,
        question,
      });
      if (error) throw error;
    },

    async poll(requestId) {
      const { data, error } = await client.rpc("poll_recall", {
        target_request_id: requestId,
      });
      if (error) throw error;
      if (!isPollResult(data)) throw new Error("invalid_recall_poll_result");
      return data;
    },
  };
}


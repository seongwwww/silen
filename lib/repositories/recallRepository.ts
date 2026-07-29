import type { SupabaseClient } from "@supabase/supabase-js";
import type { RecallPollResult, RecallQueuePort } from "@/lib/services/recall";

const SIGNED_URL_TTL_SECONDS = 60 * 10;

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
      if (data.status !== "done") return data;

      const response = data.response as unknown as Omit<
        typeof data.response,
        "evidence"
      > & {
        evidence: Array<{
          memoryId: string;
          capturedAt: string;
          quote: string;
          photoPath?: unknown;
        }>;
      };
      const paths = response.evidence
        .map((item) =>
          typeof item.photoPath === "string" ? item.photoPath : null,
        )
        .filter((path): path is string => path !== null);
      const { data: signed } =
        paths.length > 0
          ? await client.storage
              .from("memories")
              .createSignedUrls(paths, SIGNED_URL_TTL_SECONDS)
          : { data: [] };
      const urlByPath = new Map(
        (signed ?? []).map((item) => [item.path ?? "", item.signedUrl]),
      );
      return {
        status: "done",
        response: {
          ...response,
          evidence: response.evidence.map((item) => {
            const { photoPath, ...evidence } = item;
            return {
              ...evidence,
              photoUrl:
                typeof photoPath === "string"
                  ? (urlByPath.get(photoPath) ?? null)
                  : null,
            };
          }),
        },
      };
    },
  };
}

import type { SupabaseClient } from "@supabase/supabase-js";
import type { AccountDeletionPort } from "@/lib/services/accountDeletion";

/** auth.uid()만 받는 security-definer RPC라 클라이언트가 대상 user_id를 고를 수 없다. */
export function createAccountDeletionRepository(
  client: SupabaseClient,
): AccountDeletionPort {
  return {
    async request() {
      const { data, error } = await client.rpc(
        "request_account_data_deletion",
      );
      if (error) throw error;
      if (typeof data !== "string") {
        throw new Error("deletion_request_id_missing");
      }
      return data;
    },
  };
}

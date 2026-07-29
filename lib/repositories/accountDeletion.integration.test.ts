import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { Client } from "pg";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import {
  adminClient,
  ANON_KEY,
  cleanupTestUser,
  SUPABASE_URL,
} from "./testSupport";
import { createAccountDeletionRepository } from "./accountDeletionRepository";

const CONNECTION_STRING =
  process.env.SUPABASE_DB_URL ??
  "postgresql://postgres:postgres@127.0.0.1:54322/postgres";

let admin: SupabaseClient;
let db: Client;
let userId: string;

beforeAll(async () => {
  admin = adminClient();
  db = new Client({ connectionString: CONNECTION_STRING });
  await db.connect();
  userId = (
    await admin.auth.admin.createUser({
      email: "account-delete@example.com",
      email_confirm: true,
    })
  ).data.user!.id;
});

afterAll(async () => {
  await cleanupTestUser(userId, db);
  await db.end();
});

async function userClient() {
  const { data, error } = await admin.auth.admin.generateLink({
    type: "magiclink",
    email: "account-delete@example.com",
  });
  if (error) throw error;
  if (!data.properties) throw new Error("magiclink_missing");
  const client = createClient(SUPABASE_URL, ANON_KEY, {
    auth: { autoRefreshToken: false, persistSession: false },
  });
  await client.auth.verifyOtp({
    token_hash: data.properties.hashed_token,
    type: "magiclink",
  });
  return client;
}

describe("전체 기록 삭제 요청 RPC", () => {
  it("target_id를 본인 user_id로 고정하고 이중 요청을 한 행으로 수렴한다", async () => {
    const repo = createAccountDeletionRepository(await userClient());

    const first = await repo.request();
    const second = await repo.request();

    expect(second).toBe(first);
    const rows = await db.query(
      "select id::text, user_id::text, target_type, target_id::text, status "
        + "from public.deletions where user_id=$1",
      [userId],
    );
    expect(rows.rows).toEqual([
      {
        id: first,
        user_id: userId,
        target_type: "user",
        target_id: userId,
        status: "running",
      },
    ]);
  });
});

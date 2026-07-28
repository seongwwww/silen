import { randomUUID } from "node:crypto";
import { describe, it, expect, beforeAll, afterAll } from "vitest";
import { Client } from "pg";
import { adminClient, cleanupTestUser } from "./testSupport";
import type { SupabaseClient } from "@supabase/supabase-js";

const CONNECTION_STRING =
  process.env.SUPABASE_DB_URL ?? "postgresql://postgres:postgres@127.0.0.1:54322/postgres";

let admin: SupabaseClient;
let db: Client;
let user: string;

beforeAll(async () => {
  admin = adminClient();
  db = new Client({ connectionString: CONNECTION_STRING });
  await db.connect();
  const { data, error } = await admin.auth.admin.createUser({
    email: `queue-${randomUUID()}@test.local`,
    email_confirm: true,
  });
  if (error || !data.user) throw error ?? new Error("테스트 사용자 생성 실패");
  user = data.user.id;
});

afterAll(async () => {
  await cleanupTestUser(user, db);
  await db.end();
});

describe("적재 트리거", () => {
  it("메모를 만들지 않으면 이 사용자의 메시지도 없다", async () => {
    const res = await db.query(
      "select msg_id from pgmq.q_memory_jobs where (message->>'user_id') = $1",
      [user],
    );
    expect(res.rowCount).toBe(0);
  });

  it("메모가 생기면 큐에 {memory_id, user_id} 메시지가 들어간다", async () => {
    const { data } = await admin
      .from("memories")
      .insert({ user_id: user, source_type: "manual", memory_type: "moment" })
      .select("id")
      .single();
    const memoryId = data!.id;

    const res = await db.query(
      "select message from pgmq.q_memory_jobs where (message->>'memory_id') = $1",
      [memoryId],
    );
    const messages = res.rows.map((r) => r.message);
    expect(messages).toContainEqual({ memory_id: memoryId, user_id: user });
  });
});

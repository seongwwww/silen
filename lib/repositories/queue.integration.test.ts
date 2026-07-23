import { describe, it, expect, beforeAll, afterAll, beforeEach } from "vitest";
import { Client } from "pg";
import { adminClient } from "./testSupport";
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
  const { data } = await admin.auth.admin.createUser({
    email: "queue-test@example.com",
    email_confirm: true,
  });
  user = data.user!.id;
});

afterAll(async () => {
  await admin.auth.admin.deleteUser(user);
  await db.end();
});

// 큐를 비워 테스트 간 간섭을 없앤다.
beforeEach(async () => {
  await db.query("select pgmq.purge_queue('memory_jobs')");
});

describe("적재 트리거", () => {
  it("메모가 생기면 큐에 {memory_id, user_id} 메시지가 들어간다", async () => {
    const { data } = await admin
      .from("memories")
      .insert({ user_id: user, source_type: "manual", memory_type: "moment" })
      .select("id")
      .single();
    const memoryId = data!.id;

    const res = await db.query("select message from pgmq.read('memory_jobs', 30, 10)");
    const messages = res.rows.map((r) => r.message);
    expect(messages).toContainEqual({ memory_id: memoryId, user_id: user });
  });

  it("메모가 없으면 메시지도 없다", async () => {
    const res = await db.query("select msg_id from pgmq.read('memory_jobs', 30, 10)");
    expect(res.rowCount).toBe(0);
  });
});

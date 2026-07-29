import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { Client } from "pg";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import {
  adminClient,
  ANON_KEY,
  cleanupTestUser,
  SUPABASE_URL,
} from "./testSupport";
import { createRecallRepository } from "./recallRepository";

const CONNECTION_STRING =
  process.env.SUPABASE_DB_URL ??
  "postgresql://postgres:postgres@127.0.0.1:54322/postgres";

let admin: SupabaseClient;
let db: Client;
let userId: string;

async function userClient(email: string): Promise<SupabaseClient> {
  const { data, error } = await admin.auth.admin.generateLink({
    type: "magiclink",
    email,
  });
  if (error || !data.properties) throw error ?? new Error("magiclink 없음");
  const client = createClient(SUPABASE_URL, ANON_KEY, {
    auth: { autoRefreshToken: false, persistSession: false },
  });
  const { error: verifyError } = await client.auth.verifyOtp({
    token_hash: data.properties.hashed_token,
    type: "magiclink",
  });
  if (verifyError) throw verifyError;
  return client;
}

beforeAll(async () => {
  admin = adminClient();
  db = new Client({ connectionString: CONNECTION_STRING });
  await db.connect();
  const created = await admin.auth.admin.createUser({
    email: "recall-photo@example.com",
    email_confirm: true,
  });
  userId = created.data.user!.id;
});

afterAll(async () => {
  await cleanupTestUser(userId, db);
  await db.end();
});

describe("회고 결과 사진", () => {
  it("본인 경로만 짧은 서명 URL로 바꾸고 내부 경로는 응답에서 지운다", async () => {
    const client = await userClient("recall-photo@example.com");
    const memoryId = (
      await db.query(
        "insert into public.memories (user_id, raw_text, source_type, memory_type) " +
          "values ($1, '카페 사진 기록', 'manual', 'moment') returning id",
        [userId],
      )
    ).rows[0].id as string;
    const path = `${userId}/recall-photo.png`;
    const { error: uploadError } = await client.storage
      .from("memories")
      .upload(path, new Uint8Array([137, 80, 78, 71]), {
        contentType: "image/png",
      });
    if (uploadError) throw uploadError;
    await db.query(
      "insert into public.assets (memory_id, asset_type, file_url, mime_type) " +
        "values ($1, 'photo', $2, 'image/png')",
      [memoryId, path],
    );

    const requestId = crypto.randomUUID();
    const repo = createRecallRepository(client);
    await repo.enqueue(requestId, "카페 언제 갔지");
    await db.query(
      "update pgmq.q_memory_jobs set message = $1::jsonb " +
        "where message->>'request_id' = $2 and message->>'user_id' = $3",
      [
        JSON.stringify({
          job_type: "recall_result",
          request_id: requestId,
          user_id: userId,
          status: "done",
          response: {
            answer: "기록에서 이런 내용을 찾았어요.",
            confirmation: "이거 맞으세요?",
            evidence: [
              {
                memoryId,
                capturedAt: "2026-07-14T12:00:00+00:00",
                quote: "카페 사진 기록",
                photoPath: path,
              },
            ],
          },
        }),
        requestId,
        userId,
      ],
    );

    const result = await repo.poll(requestId);
    expect(result.status).toBe("done");
    if (result.status !== "done") throw new Error("완료 응답 아님");
    const evidence = result.response.evidence[0];
    expect(evidence.photoUrl).toContain("/storage/v1/object/sign/memories/");
    expect(evidence).not.toHaveProperty("photoPath");
    expect((await fetch(evidence.photoUrl!)).ok).toBe(true);
  });
});

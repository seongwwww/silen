import { describe, it, expect, beforeAll, afterAll } from "vitest";
import { Client } from "pg";

const BASE = process.env.APP_BASE_URL ?? "http://localhost:3000";
const CONNECTION_STRING =
  process.env.SUPABASE_DB_URL ?? "postgresql://postgres:postgres@127.0.0.1:54322/postgres";

let db: Client;
let createdUser: string | undefined;
let sessionCookie: string | undefined;

beforeAll(async () => {
  db = new Client({ connectionString: CONNECTION_STRING });
  await db.connect();
});

afterAll(async () => {
  if (createdUser) {
    await db.query(
      `select pgmq.delete('memory_jobs', msg_id)
         from pgmq.q_memory_jobs
        where (message->>'user_id') = $1`,
      [createdUser],
    );
    await db.query(
      "delete from pgmq.a_memory_jobs where (message->>'user_id') = $1",
      [createdUser],
    );
    await db.query("delete from public.deletions where user_id = $1", [
      createdUser,
    ]);
    await db.query("delete from auth.users where id = $1", [createdUser]);
  }
  await db.end();
});

function cookieHeader(response: Response): string | undefined {
  const raw = response.headers.get("set-cookie");
  return raw
    ?.split(/,(?=[^;,]+=)/)
    .map((cookie) => cookie.split(";")[0])
    .join("; ");
}

describe("POST /api/memories (라이브)", () => {
  it("익명으로 텍스트 메모를 만들면 201과 memoryId를 준다", async () => {
    const res = await fetch(`${BASE}/api/memories`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ text: "라이브 스모크 메모" }),
    });
    expect(res.status).toBe(201);
    const { memoryId } = await res.json();
    expect(memoryId).toBeTruthy();
    sessionCookie = cookieHeader(res);
    expect(sessionCookie).toBeTruthy();

    const row = await db.query(
      "select id, user_id from public.memories where id = $1",
      [memoryId],
    );
    expect(row.rowCount).toBe(1);
    createdUser = row.rows[0].user_id;
  });

  it("빈 본문은 400으로 거부한다", async () => {
    if (!sessionCookie) throw new Error("이전 요청의 익명 세션 쿠키가 없습니다");
    const res = await fetch(`${BASE}/api/memories`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        cookie: sessionCookie,
      },
      body: JSON.stringify({}),
    });
    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error.code).toBe("empty_memory");
  });
});

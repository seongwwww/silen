import { describe, it, expect, beforeAll, afterAll } from "vitest";
import { Client } from "pg";

const BASE = process.env.APP_BASE_URL ?? "http://localhost:3000";
const CONNECTION_STRING =
  process.env.SUPABASE_DB_URL ?? "postgresql://postgres:postgres@127.0.0.1:54322/postgres";

let db: Client;

beforeAll(async () => {
  db = new Client({ connectionString: CONNECTION_STRING });
  await db.connect();
});

afterAll(async () => {
  await db.end();
});

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

    const row = await db.query("select id from public.memories where id = $1", [memoryId]);
    expect(row.rowCount).toBe(1);
  });

  it("빈 본문은 400으로 거부한다", async () => {
    const res = await fetch(`${BASE}/api/memories`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({}),
    });
    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error.code).toBe("empty_memory");
  });
});

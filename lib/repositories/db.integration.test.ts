import { describe, it, expect, afterAll } from "vitest";
import { Client } from "pg";

const CONNECTION_STRING =
  process.env.SUPABASE_DB_URL ?? "postgresql://postgres:postgres@127.0.0.1:54322/postgres";

const client = new Client({ connectionString: CONNECTION_STRING });
let connected = false;

async function getClient(): Promise<Client> {
  if (!connected) {
    await client.connect();
    connected = true;
  }
  return client;
}

afterAll(async () => {
  if (connected) await client.end();
});

describe("로컬 Supabase 스키마", () => {
  it("ADR-0002가 요구하는 확장이 설치되어 있다", async () => {
    const db = await getClient();
    const result = await db.query<{ extname: string }>(
      "select extname from pg_extension where extname in ('vector', 'postgis')",
    );
    const names = result.rows.map((row) => row.extname).sort();
    expect(names).toEqual(["postgis", "vector"]);
  });
});

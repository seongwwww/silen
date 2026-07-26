import { describe, it, expect } from "vitest";
const BASE = process.env.APP_BASE_URL ?? "http://localhost:3000";

describe("PATCH /api/differences/[id] (라이브)", () => {
  it("잘못된 status는 400", async () => {
    const res = await fetch(`${BASE}/api/differences/00000000-0000-0000-0000-000000000000`, {
      method: "PATCH", headers: { "content-type": "application/json" }, body: JSON.stringify({ status: "bogus" }),
    });
    expect(res.status).toBe(400);
  });
});

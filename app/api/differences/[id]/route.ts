import { NextResponse, type NextRequest } from "next/server";
import { z } from "zod";
import { createServerSupabase } from "@/lib/repositories/supabase";
import { createDifferenceRepository } from "@/lib/repositories/differenceRepository";
import { assertValidTransition, InvalidTransitionError, type DiffStatus } from "@/lib/services/difference";

const bodySchema = z.object({ status: z.enum(["candidate", "confirmed", "dismissed"]) });

export async function PATCH(request: NextRequest, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  let parsed;
  try {
    parsed = bodySchema.parse(await request.json());
  } catch {
    return NextResponse.json({ error: { code: "invalid_body", message: "요청 형식이 올바르지 않습니다" } }, { status: 400 });
  }

  const supabase = await createServerSupabase();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) {
    return NextResponse.json({ error: { code: "unauthorized", message: "세션이 필요합니다" } }, { status: 401 });
  }

  const repo = createDifferenceRepository(supabase);
  // 현재 status를 읽어 전이를 검증한다(본인 것만 보임 — RLS).
  const { data: current } = await supabase.from("differences").select("status").eq("id", id).maybeSingle();
  if (!current) {
    return NextResponse.json({ error: { code: "not_found", message: "차이를 찾을 수 없습니다" } }, { status: 404 });
  }
  try {
    assertValidTransition(current.status as DiffStatus, parsed.status);
  } catch (e) {
    if (e instanceof InvalidTransitionError) {
      return NextResponse.json({ error: { code: "invalid_transition", message: "허용되지 않은 변경입니다" } }, { status: 400 });
    }
    throw e;
  }
  // 읽은 상태를 기대값으로 넘긴다 — 그 사이 다른 요청이 바꿨으면 0행(409).
  const changed = await repo.updateStatus(id, parsed.status, current.status as DiffStatus);
  if (!changed) {
    return NextResponse.json(
      { error: { code: "conflict", message: "그새 상태가 바뀌었어요. 다시 시도해 주세요" } },
      { status: 409 },
    );
  }
  return new NextResponse(null, { status: 204 });
}

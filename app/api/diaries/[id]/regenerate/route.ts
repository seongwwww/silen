import { NextResponse } from "next/server";
import { createServerSupabase } from "@/lib/repositories/supabase";
import { createDiaryRepository } from "@/lib/repositories/diaryRepository";

/** 재생성 요청만 남긴다. 다음 run-diary가 1회 소비하고 비운다(자동 재생성 아님). */
export async function POST(
  _request: Request,
  ctx: { params: Promise<{ id: string }> },
) {
  const { id } = await ctx.params;
  const supabase = await createServerSupabase();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) {
    return NextResponse.json(
      { error: { code: "unauthorized", message: "세션이 필요합니다" } },
      { status: 401 },
    );
  }
  const ok = await createDiaryRepository(supabase).requestRegenerate(
    id,
    null,
  );
  if (!ok) {
    return NextResponse.json(
      { error: { code: "not_found", message: "일기를 찾을 수 없습니다" } },
      { status: 404 },
    );
  }
  return new NextResponse(null, { status: 204 });
}

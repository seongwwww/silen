import { NextResponse } from "next/server";
import { z } from "zod";
import { createServerSupabase } from "@/lib/repositories/supabase";
import { createDiaryRepository } from "@/lib/repositories/diaryRepository";
import { TONE_INSTRUCTION_MAX_LENGTH } from "@/lib/services/diary";

const bodySchema = z.strictObject({
  toneInstruction: z
    .string()
    .trim()
    .max(TONE_INSTRUCTION_MAX_LENGTH)
    .nullable()
    .optional(),
});

async function parseBody(request: Request): Promise<string | null> {
  const text = await request.text();
  if (!text.trim()) return null;

  const parsed = bodySchema.parse(JSON.parse(text));
  return parsed.toneInstruction || null;
}

/** 재생성 요청만 남긴다. 다음 run-diary가 1회 소비하고 비운다(자동 재생성 아님). */
export async function POST(
  request: Request,
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

  let toneInstruction: string | null;
  try {
    toneInstruction = await parseBody(request);
  } catch {
    return NextResponse.json(
      {
        error: {
          code: "invalid_body",
          message: "요청 형식이 올바르지 않습니다",
        },
      },
      { status: 400 },
    );
  }

  const ok = await createDiaryRepository(supabase).requestRegenerate(
    id,
    toneInstruction,
  );
  if (!ok) {
    return NextResponse.json(
      { error: { code: "not_found", message: "일기를 찾을 수 없습니다" } },
      { status: 404 },
    );
  }
  return new NextResponse(null, { status: 204 });
}

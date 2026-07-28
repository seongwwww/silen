import { NextResponse, type NextRequest } from "next/server";
import { z } from "zod";
import { createServerSupabase } from "@/lib/repositories/supabase";
import { createDiaryRepository } from "@/lib/repositories/diaryRepository";
import {
  assertValidDiaryTransition,
  InvalidDiaryTransitionError,
  type DiaryStatus,
} from "@/lib/services/diary";

const bodySchema = z.object({
  editedText: z.string().max(2000).optional(),
  status: z.enum(["draft", "edited", "confirmed"]),
});

export async function PATCH(
  request: NextRequest,
  ctx: { params: Promise<{ id: string }> },
) {
  const { id } = await ctx.params;
  let parsed;
  try {
    parsed = bodySchema.parse(await request.json());
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

  // 현재 status를 읽어 전이를 검증한다(본인 것만 보임 — RLS).
  const { data: current } = await supabase
    .from("diaries")
    .select("status")
    .eq("id", id)
    .maybeSingle();
  if (!current) {
    return NextResponse.json(
      { error: { code: "not_found", message: "일기를 찾을 수 없습니다" } },
      { status: 404 },
    );
  }
  try {
    assertValidDiaryTransition(
      current.status as DiaryStatus,
      parsed.status,
    );
  } catch (e) {
    if (e instanceof InvalidDiaryTransitionError) {
      return NextResponse.json(
        {
          error: {
            code: "invalid_transition",
            message: "허용되지 않은 변경입니다",
          },
        },
        { status: 400 },
      );
    }
    throw e;
  }

  const repo = createDiaryRepository(supabase);
  // 읽은 상태를 기대값으로 넘긴다 — 그새 바뀌었으면 0행(409).
  const changed =
    parsed.editedText === undefined
      ? await repo.updateStatus(
          id,
          parsed.status,
          current.status as DiaryStatus,
        )
      : await repo.updateDraft(
          id,
          parsed.editedText,
          parsed.status,
          current.status as DiaryStatus,
        );
  if (!changed) {
    return NextResponse.json(
      {
        error: {
          code: "conflict",
          message: "그새 상태가 바뀌었어요. 다시 시도해 주세요",
        },
      },
      { status: 409 },
    );
  }
  return new NextResponse(null, { status: 204 });
}

import { NextResponse, type NextRequest } from "next/server";
import { z } from "zod";
import { createServerSupabase } from "@/lib/repositories/supabase";
import { MemoryLockConflictError } from "@/lib/services/memoryLock";
import { setMemoryLockForSession } from "@/lib/services/memoryLockServer";

const bodySchema = z
  .object({
    isLocked: z.boolean(),
    expected: z.boolean(),
  })
  .refine((body) => body.isLocked !== body.expected);

export async function PATCH(
  request: NextRequest,
  ctx: { params: Promise<{ id: string }> },
) {
  let body: z.infer<typeof bodySchema>;
  try {
    body = bodySchema.parse(await request.json());
  } catch {
    return NextResponse.json(
      { error: { code: "invalid_body", message: "요청 형식을 확인해 주세요" } },
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

  try {
    const { id } = await ctx.params;
    await setMemoryLockForSession(
      supabase,
      id,
      body.isLocked,
      body.expected,
    );
    return NextResponse.json({ isLocked: body.isLocked });
  } catch (error) {
    if (error instanceof MemoryLockConflictError) {
      return NextResponse.json(
        {
          error: {
            code: "conflict",
            message: "잠금 상태가 바뀌었어요. 화면을 새로고침해 주세요",
          },
        },
        { status: 409 },
      );
    }
    return NextResponse.json(
      { error: { code: "server_error", message: "잠금을 바꾸지 못했어요" } },
      { status: 500 },
    );
  }
}

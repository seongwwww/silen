import { NextResponse, type NextRequest } from "next/server";
import { z } from "zod";
import { createServerSupabase } from "@/lib/repositories/supabase";
import { createMemoryRepository } from "@/lib/repositories/memoryRepository";
import { createMemory, EmptyMemoryError, ForeignAssetPathError } from "@/lib/services/memory";

const bodySchema = z.object({
  text: z.string().optional(),
  emotion: z.enum(["good", "neutral", "bad"]).optional(),
  assetPaths: z.array(z.string()).optional(),
  occurredAt: z.string().datetime().optional(),
});

/**
 * 기록 1건을 만든다. 세션이 없으면 익명 세션을 만든다(auth §6) —
 * 기록 시점이 세션을 만드는 유일한 지점이다. 401은 발생하지 않는다.
 */
export async function POST(request: NextRequest) {
  let parsed;
  try {
    parsed = bodySchema.parse(await request.json());
  } catch {
    return NextResponse.json(
      { error: { code: "invalid_body", message: "요청 형식이 올바르지 않습니다" } },
      { status: 400 },
    );
  }

  const supabase = await createServerSupabase();

  // 기록 시점에 익명 세션을 보장한다.
  const {
    data: { user },
  } = await supabase.auth.getUser();
  let userId = user?.id;
  if (!userId) {
    const { data, error } = await supabase.auth.signInAnonymously();
    if (error || !data.user) {
      return NextResponse.json(
        { error: { code: "session_failed", message: "세션 생성 실패" } },
        { status: 500 },
      );
    }
    userId = data.user.id;
  }

  const repo = createMemoryRepository(supabase);

  try {
    const { memoryId } = await createMemory(repo, {
      userId,
      text: parsed.text,
      emotion: parsed.emotion,
      assetPaths: parsed.assetPaths,
      occurredAt: parsed.occurredAt,
    });
    return NextResponse.json({ memoryId }, { status: 201 });
  } catch (err) {
    if (err instanceof EmptyMemoryError) {
      return NextResponse.json(
        { error: { code: "empty_memory", message: "내용이나 사진이 필요합니다" } },
        { status: 400 },
      );
    }
    if (err instanceof ForeignAssetPathError) {
      return NextResponse.json(
        { error: { code: "foreign_asset", message: "본인 사진만 첨부할 수 있습니다" } },
        { status: 400 },
      );
    }
    // 본문·식별 정보를 응답·로그에 싣지 않는다(backend.md).
    return NextResponse.json(
      { error: { code: "server_error", message: "저장에 실패했습니다" } },
      { status: 500 },
    );
  }
}

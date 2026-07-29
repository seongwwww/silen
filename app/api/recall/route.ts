import { NextResponse, type NextRequest } from "next/server";
import { z } from "zod";
import { createServerSupabase } from "@/lib/repositories/supabase";
import {
  InvalidRecallQueryError,
  RECALL_QUERY_MAX,
} from "@/lib/services/recall";
import {
  enqueueRecallForSession,
  pollRecallForSession,
} from "@/lib/services/recallServer";

const postSchema = z.object({
  requestId: z.string().uuid(),
  question: z.string().max(RECALL_QUERY_MAX),
});
const requestIdSchema = z.string().uuid();

async function authenticatedClient() {
  const supabase = await createServerSupabase();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  return user ? supabase : null;
}

export async function POST(request: NextRequest | Request) {
  const supabase = await authenticatedClient();
  if (!supabase) {
    return NextResponse.json(
      { error: { code: "authentication_required", message: "로그인이 필요합니다" } },
      { status: 401 },
    );
  }

  try {
    const body = postSchema.parse(await request.json());
    await enqueueRecallForSession(supabase, body.requestId, body.question);
    return NextResponse.json({ requestId: body.requestId }, { status: 202 });
  } catch (error) {
    if (error instanceof z.ZodError || error instanceof InvalidRecallQueryError) {
      return NextResponse.json(
        { error: { code: "invalid_question", message: "질문을 확인해 주세요" } },
        { status: 400 },
      );
    }
    return NextResponse.json(
      { error: { code: "server_error", message: "질문을 보내지 못했습니다" } },
      { status: 500 },
    );
  }
}

export async function GET(request: NextRequest | Request) {
  const supabase = await authenticatedClient();
  if (!supabase) {
    return NextResponse.json(
      { error: { code: "authentication_required", message: "로그인이 필요합니다" } },
      { status: 401 },
    );
  }
  const parsed = requestIdSchema.safeParse(
    new URL(request.url).searchParams.get("requestId"),
  );
  if (!parsed.success) {
    return NextResponse.json(
      { error: { code: "invalid_request", message: "요청을 확인해 주세요" } },
      { status: 400 },
    );
  }
  try {
    return NextResponse.json(await pollRecallForSession(supabase, parsed.data));
  } catch {
    return NextResponse.json(
      { error: { code: "server_error", message: "결과를 불러오지 못했습니다" } },
      { status: 500 },
    );
  }
}


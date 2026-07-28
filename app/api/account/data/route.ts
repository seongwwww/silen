import { NextResponse } from "next/server";
import { createServerSupabase } from "@/lib/repositories/supabase";
import { requestAccountDataDeletionForSession } from "@/lib/services/accountDeletionServer";

/** 실제 삭제는 하지 않고 재개 가능한 삭제 원장 요청만 만든다. */
export async function DELETE() {
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
    const result = await requestAccountDataDeletionForSession(supabase);
    return NextResponse.json(result, { status: 202 });
  } catch {
    // DB 오류 객체에는 식별 정보가 섞일 수 있어 고정 오류만 응답한다.
    return NextResponse.json(
      {
        error: {
          code: "server_error",
          message: "삭제를 요청하지 못했습니다",
        },
      },
      { status: 500 },
    );
  }
}

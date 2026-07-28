import { NextResponse } from "next/server";
import { createAccountDeletionRepository } from "@/lib/repositories/accountDeletionRepository";
import { createServerSupabase } from "@/lib/repositories/supabase";
import { requestAccountDataDeletion } from "@/lib/services/accountDeletion";

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

  const result = await requestAccountDataDeletion(
    createAccountDeletionRepository(supabase),
  );
  return NextResponse.json(result, { status: 202 });
}

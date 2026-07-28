import { NextResponse, type NextRequest } from "next/server";
import { z } from "zod";
import { createServerSupabase } from "@/lib/repositories/supabase";
import { createUserRepository } from "@/lib/repositories/userRepository";

const bodySchema = z.object({
  tonePreset: z.enum(["담백", "따뜻"]),
});

export async function PATCH(request: NextRequest) {
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
  const ok = await createUserRepository(supabase).updateTonePreset(
    parsed.tonePreset,
  );
  if (!ok) {
    return NextResponse.json(
      { error: { code: "not_found", message: "설정을 찾을 수 없습니다" } },
      { status: 404 },
    );
  }
  return new NextResponse(null, { status: 204 });
}

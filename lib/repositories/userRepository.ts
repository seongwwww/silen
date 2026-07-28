import type { SupabaseClient } from "@supabase/supabase-js";
import type { TonePreset } from "@/lib/services/diary";

/** 세션 클라이언트로 내 설정을 읽고 쓴다. RLS가 소유권을 강제한다. */
export function createUserRepository(client: SupabaseClient) {
  return {
    async findTonePreset(): Promise<TonePreset> {
      const { data, error } = await client
        .from("users")
        .select("style_profile")
        .limit(1);
      if (error) throw error;
      const preset = (
        data?.[0]?.style_profile as { preset?: string } | null
      )?.preset;
      return preset === "따뜻" ? "따뜻" : "담백";
    },

    async updateTonePreset(preset: TonePreset): Promise<boolean> {
      const { data, error } = await client
        .from("users")
        .update({ style_profile: { preset } })
        .select("id");
      if (error) throw error;
      return (data?.length ?? 0) > 0;
    },
  };
}

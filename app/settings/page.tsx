import Link from "next/link";
import { createServerSupabase } from "@/lib/repositories/supabase";
import { createUserRepository } from "@/lib/repositories/userRepository";
import { TonePicker } from "./_components/TonePicker";

export default async function SettingsPage() {
  const supabase = await createServerSupabase();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  const preset = user
    ? await createUserRepository(supabase).findTonePreset()
    : "담백";

  return (
    <main className="mx-auto max-w-md p-4">
      <h1 className="mb-4 text-lg font-medium">설정</h1>
      <h2 className="mb-2 text-[15px]">일기 톤</h2>
      <TonePicker initial={preset} />
      <p className="mt-2 text-xs text-muted-foreground">
        문체만 바뀌어요. 사실은 그대로예요.
      </p>
      <section className="mt-10 border-t pt-6">
        <h2 className="text-[15px] font-medium">화면 테스트</h2>
        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
          프론트 목 데이터로 Daily Wrap과 일기 생성 상태를 확인해요.
        </p>
        <Link
          href="/demo"
          className="mt-3 inline-flex min-h-11 items-center rounded-xl border bg-card px-4 font-medium"
        >
          데모 상태 보기
        </Link>
      </section>
    </main>
  );
}

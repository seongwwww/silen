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
    </main>
  );
}

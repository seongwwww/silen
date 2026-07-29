import { createServerSupabase } from "@/lib/repositories/supabase";
import { createUserRepository } from "@/lib/repositories/userRepository";
import { RecallScreen } from "./_components/RecallScreen";

export default async function RecallPage() {
  const supabase = await createServerSupabase();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  const timeZone = user
    ? await createUserRepository(supabase).findTimeZone()
    : "Asia/Seoul";

  return <RecallScreen timeZone={timeZone} />;
}


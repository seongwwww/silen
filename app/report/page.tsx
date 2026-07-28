import { createServerSupabase } from "@/lib/repositories/supabase";
import { createUserRepository } from "@/lib/repositories/userRepository";
import { createWeeklyRepository } from "@/lib/repositories/weeklyRepository";
import { ReportScreen } from "./_components/ReportScreen";

export default async function ReportPage() {
  const supabase = await createServerSupabase();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  let report = null;
  if (user) {
    const timeZone = await createUserRepository(supabase).findTimeZone();
    report = await createWeeklyRepository(supabase).findLatest(
      user.id,
      timeZone,
    );
  }

  return <ReportScreen report={report} />;
}

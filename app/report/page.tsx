import Link from "next/link";
import { createServerSupabase } from "@/lib/repositories/supabase";
import { createUserRepository } from "@/lib/repositories/userRepository";
import { createWeeklyRepository } from "@/lib/repositories/weeklyRepository";
import { ReportScreen } from "./_components/ReportScreen";
import { DEMO_WEEKLY_REPORT } from "./fixtures";

export default async function ReportPage({
  searchParams,
}: {
  searchParams: Promise<{ demo?: string }>;
}) {
  const { demo } = await searchParams;
  if (demo === "1") {
    return (
      <>
        <div className="sticky top-0 z-40 border-b bg-background/95 px-4 py-3 backdrop-blur">
          <div className="mx-auto flex max-w-md items-center justify-between gap-3">
            <p className="text-xs font-semibold tracking-wide text-muted-foreground">
              FRONTEND MOCK DATA
            </p>
            <Link
              href="/demo"
              className="inline-flex min-h-11 items-center text-sm font-medium underline-offset-4 hover:underline"
            >
              데모로 돌아가기
            </Link>
          </div>
        </div>
        <ReportScreen report={DEMO_WEEKLY_REPORT} />
      </>
    );
  }

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

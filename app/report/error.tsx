"use client";

import { ErrorState } from "@/components/common/StateView";

export default function Error({
  unstable_retry,
}: {
  error: Error & { digest?: string };
  unstable_retry: () => void;
}) {
  return (
    <main className="mx-auto w-full max-w-md px-5 py-10">
      <h1
        aria-label="당신이 몰랐던 이번 주"
        className="pt-4 text-3xl font-semibold tracking-tight"
      >
        당신이 몰랐던
        <br />
        이번 주
      </h1>
      <ErrorState onRetry={unstable_retry} />
    </main>
  );
}

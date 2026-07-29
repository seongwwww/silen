"use client";

import { ErrorState } from "@/components/common/StateView";

export default function Error({
  unstable_retry,
}: {
  error: Error;
  unstable_retry: () => void;
}) {
  return (
    <main className="mx-auto w-full max-w-md px-5 py-10">
      <h1 className="pt-4 text-3xl font-semibold tracking-tight">그거 뭐였지</h1>
      <ErrorState onRetry={unstable_retry} />
    </main>
  );
}

"use client";
import { ErrorState } from "@/components/common/StateView";
export default function Error({
  reset,
}: {
  error: Error;
  reset: () => void;
}) {
  return (
    <main className="mx-auto max-w-md p-4">
      <ErrorState onRetry={reset} />
    </main>
  );
}

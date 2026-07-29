import { LoadingState } from "@/components/common/StateView";

export default function Loading() {
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
      <div className="mt-8">
        <LoadingState />
      </div>
    </main>
  );
}

import { LoadingState } from "@/components/common/StateView";

export default function Loading() {
  return (
    <main className="mx-auto w-full max-w-md px-5 py-10">
      <h1 className="pt-4 text-3xl font-semibold tracking-tight">그거 뭐였지</h1>
      <div className="mt-8">
        <LoadingState />
      </div>
    </main>
  );
}

"use client";

import { useRouter } from "next/navigation";
import { RecordForm } from "./RecordForm";

export function RecordScreen({ question }: { question: string | null }) {
  const router = useRouter();

  return (
    <main className="mx-auto flex min-h-[calc(100svh-3.5rem)] w-full max-w-md flex-col px-5 py-10">
      <header className="mb-8 pt-8">
        <h1 className="text-2xl font-semibold tracking-tight">뭐든 남겨요</h1>
        <p className="mt-2 text-[15px] text-muted-foreground">
          분류도 태그도 필요 없어요
        </p>
      </header>
      <RecordForm
        question={question}
        onSaved={question ? undefined : () => router.push("/")}
      />
    </main>
  );
}

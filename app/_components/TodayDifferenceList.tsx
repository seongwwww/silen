"use client";

import { useState } from "react";
import { toast } from "sonner";
import { ConfirmActions } from "@/components/common/ConfirmActions";
import type { DiffStatus } from "@/lib/services/difference";
import type { TodayDifference } from "@/lib/services/today";

async function updateDifference(
  id: string,
  status: DiffStatus,
): Promise<boolean> {
  try {
    const response = await fetch(`/api/differences/${id}`, {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ status }),
    });
    return response.ok;
  } catch {
    return false;
  }
}

/** 차이 판단 반영. 기본은 실제 PATCH이고, 호출자가 다른 동작을 주입할 수 있다
 * — 이 컴포넌트는 자신이 어디에 쓰이는지 알지 않는다. */
export function TodayDifferenceList({
  items,
  decideDifference = updateDifference,
}: {
  items: TodayDifference[];
  decideDifference?: (id: string, status: DiffStatus) => Promise<boolean>;
}) {
  const [differences, setDifferences] = useState(items);

  async function decide(
    item: TodayDifference,
    status: "confirmed" | "dismissed",
  ) {
    setDifferences((current) =>
      current.filter((difference) => difference.id !== item.id),
    );
    if (await decideDifference(item.id, status)) {
      toast("반영했어요");
      return;
    }
    setDifferences((current) =>
      current.some((difference) => difference.id === item.id)
        ? current
        : [item, ...current],
    );
    toast.error("바꾸지 못했어요. 다시 시도해 주세요.");
  }

  if (differences.length === 0) return null;

  return (
    <section aria-labelledby="today-difference-title" className="mb-8">
      <h2
        id="today-difference-title"
        className="mb-3 text-sm font-medium text-muted-foreground"
      >
        오늘의 다른 점
      </h2>
      <div className="space-y-3">
        {differences.map((item) => (
          <article
            key={item.id}
            className="rounded-2xl border bg-accent px-4 py-4"
          >
            <p className="text-base font-medium leading-relaxed">
              {item.headline}
            </p>
            <div className="mt-4">
              <ConfirmActions
                onConfirm={() => void decide(item, "confirmed")}
                onDismiss={() => void decide(item, "dismissed")}
              />
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

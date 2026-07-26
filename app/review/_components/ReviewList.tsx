"use client";
import { useState } from "react";
import { toast } from "sonner";
import { Card } from "@/components/ui/card";
import { ConfirmActions } from "@/components/common/ConfirmActions";
import type { ReviewItem, DiffStatus } from "@/lib/services/difference";

async function patch(id: string, status: DiffStatus): Promise<boolean> {
  const res = await fetch(`/api/differences/${id}`, {
    method: "PATCH", headers: { "content-type": "application/json" }, body: JSON.stringify({ status }),
  });
  return res.ok;
}

export function ReviewList({ items }: { items: ReviewItem[] }) {
  const [list, setList] = useState(items);
  const restore = (item: ReviewItem) =>
    setList((l) => (l.some((x) => x.id === item.id) ? l : [item, ...l]));

  async function act(item: ReviewItem, status: "confirmed" | "dismissed") {
    setList((l) => l.filter((x) => x.id !== item.id)); // 낙관적 제거
    if (!(await patch(item.id, status))) {
      restore(item);
      toast.error("바꾸지 못했어요. 다시 시도해 주세요.");
      return;
    }
    toast("처리했어요", {
      duration: 5000,
      action: {
        label: "되돌리기",
        onClick: async () => {
          if (await patch(item.id, "candidate")) restore(item);
          else toast.error("되돌리지 못했어요.");
        },
      },
    });
  }

  return (
    <div className="space-y-3">
      {list.map((item) => (
        <Card key={item.id} className="p-4">
          <span className="inline-block rounded-full bg-[var(--success-bg)] px-2.5 py-0.5 text-[12px] text-[var(--success-text)]">오늘의 다른 점</span>
          <p className="mt-2 text-[16px] font-medium">{item.headline}</p>
          {item.evidence.length > 0 && (
            <>
              <p className="mt-2 text-[13px] text-muted-foreground">이 기록에서 찾았어요</p>
              <div className="mb-4 mt-1.5 flex flex-wrap gap-1.5">
                {item.evidence.map((e, i) => (
                  <span key={i} className="rounded-lg border px-2.5 py-1 text-[13px] text-muted-foreground">{e}</span>
                ))}
              </div>
            </>
          )}
          <div className={item.evidence.length > 0 ? "" : "mt-4"}>
            <ConfirmActions onConfirm={() => act(item, "confirmed")} onDismiss={() => act(item, "dismissed")} />
          </div>
        </Card>
      ))}
    </div>
  );
}

"use client";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import type { DiaryStatus } from "@/lib/services/diary";

/** 늦은 메모를 반영하려 다시 만든다(기획서 §6 "다시 만들기 1회").
 * 즉시 반영이 아니라 요청을 남기고 다음 생성이 반영한다.
 * 편집본이면 고친 내용이 사라지므로 한 번 더 확인받는다. */
export function RegenerateButton({
  id,
  status,
}: {
  id: string;
  status: DiaryStatus;
}) {
  const [confirming, setConfirming] = useState(false);
  const [requested, setRequested] = useState(false);
  const [sending, setSending] = useState(false);

  async function send() {
    setSending(true);
    try {
      const res = await fetch(`/api/diaries/${id}/regenerate`, {
        method: "POST",
      });
      if (!res.ok) throw new Error("failed");
      setRequested(true);
      setConfirming(false);
    } finally {
      setSending(false);
    }
  }

  if (requested) {
    return (
      <p className="mt-3 text-[15px] text-muted-foreground">
        다음 일기를 만들 때 반영돼요.
      </p>
    );
  }

  return (
    <div className="mt-3">
      {confirming && (
        <p className="mb-2 text-[15px] text-muted-foreground">
          고친 내용이 사라져요. 그래도 다시 만들까요?
        </p>
      )}
      <Button
        variant="outline"
        className="min-h-11 w-full"
        disabled={sending}
        onClick={() => {
          if (status !== "draft" && !confirming) {
            setConfirming(true);
            return;
          }
          void send();
        }}
      >
        다시 만들기
      </Button>
    </div>
  );
}

"use client";

import { useRef, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";

export function DataDeletionCard() {
  const [confirming, setConfirming] = useState(false);
  const [sending, setSending] = useState(false);
  const [requested, setRequested] = useState(false);
  const inFlight = useRef(false);

  async function requestDeletion() {
    if (inFlight.current) return;
    if (navigator.onLine === false) {
      toast.error("지금은 오프라인이에요. 연결되면 다시 시도해 주세요.");
      return;
    }
    inFlight.current = true;
    setSending(true);
    try {
      const response = await fetch("/api/account/data", {
        method: "DELETE",
      });
      if (!response.ok) throw new Error("failed");
      setRequested(true);
    } catch {
      toast.error("삭제를 요청하지 못했어요. 다시 시도해 주세요.");
    } finally {
      inFlight.current = false;
      setSending(false);
    }
  }

  return (
    <section className="mt-10 rounded-2xl border bg-card p-5">
      <h2 className="font-medium">전체 기록 삭제</h2>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">
        계정은 유지하고 실은에 저장된 기록 데이터만 지워요.
      </p>

      {requested ? (
        <p role="status" className="mt-4 rounded-xl bg-accent px-4 py-3 text-sm">
          삭제 요청을 받았어요. 계정은 그대로 유지돼요.
        </p>
      ) : confirming ? (
        <div className="mt-4">
          <p className="text-sm leading-6 text-[var(--danger-text)]">
            원본 기록·사진·일기·차이·주간 리포트가 삭제됩니다. 계정은
            유지되며, 삭제한 기록은 되돌릴 수 없습니다.
          </p>
          <div className="mt-4 grid grid-cols-2 gap-2">
            <Button
              type="button"
              variant="outline"
              className="min-h-11"
              disabled={sending}
              onClick={() => setConfirming(false)}
            >
              취소
            </Button>
            <Button
              type="button"
              variant="destructive"
              className="min-h-11"
              disabled={sending}
              onClick={() => void requestDeletion()}
            >
              {sending ? "요청하는 중" : "삭제 요청하기"}
            </Button>
          </div>
        </div>
      ) : (
        <Button
          type="button"
          variant="outline"
          className="mt-4 min-h-11 w-full text-[var(--danger-text)]"
          onClick={() => setConfirming(true)}
        >
          전체 기록 삭제
        </Button>
      )}
    </section>
  );
}

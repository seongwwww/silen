"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";

/** 일기 생성 요청. 기본은 실제 API 호출이고, 호출자가 다른 동작을 주입할 수 있다
 * — 이 컴포넌트는 자신이 어디에 쓰이는지(데모인지 아닌지) 알지 않는다. */
export function ManualDiaryButton({
  requestDiary,
}: {
  requestDiary?: () => Promise<void>;
}) {
  const router = useRouter();
  const inFlight = useRef(false);
  const [isCreating, setIsCreating] = useState(false);
  const [requested, setRequested] = useState(false);

  async function createDiary() {
    if (inFlight.current) return;

    if (typeof navigator !== "undefined" && navigator.onLine === false) {
      toast.error("지금은 오프라인이에요. 연결되면 다시 시도해 주세요.");
      return;
    }

    inFlight.current = true;
    setIsCreating(true);

    try {
      if (requestDiary) {
        await requestDiary();
      } else {
        const response = await fetch("/api/diaries/generate", {
          method: "POST",
        });

        if (!response.ok) throw new Error("diary generation failed");
        router.refresh();
      }

      setRequested(true);
      toast("일기 만들기를 요청했어요");
    } catch {
      toast.error("일기를 만들지 못했어요. 다시 시도해 주세요.");
    } finally {
      inFlight.current = false;
      setIsCreating(false);
    }
  }

  return (
    <div>
      <Button
        type="button"
        className="min-h-11 w-full"
        disabled={isCreating || requested}
        aria-live="polite"
        onClick={() => void createDiary()}
      >
        {isCreating
          ? "일기를 준비하고 있어요"
          : requested
            ? "일기 만들기를 요청했어요"
            : "오늘 일기 만들기"}
      </Button>
      {requested && (
        <p role="status" className="mt-2 text-sm text-muted-foreground">
          완성되면 이 화면에서 바로 보여드릴게요.
        </p>
      )}
    </div>
  );
}

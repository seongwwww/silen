"use client";

import { Lock, LockOpen } from "lucide-react";
import { type ReactNode, useState } from "react";
import { toast } from "sonner";
import type { UpdateMemoryLock } from "@/lib/services/memoryLockClient";

export function MemoryLockControl({
  memoryId,
  updateLock,
  children,
  className = "",
}: {
  memoryId: string;
  updateLock: UpdateMemoryLock;
  children: ReactNode;
  className?: string;
}) {
  const [isLocked, setIsLocked] = useState(false);
  const [busy, setBusy] = useState(false);

  async function toggleLock() {
    if (busy) return;
    const next = !isLocked;
    setBusy(true);
    try {
      await updateLock(memoryId, next, isLocked);
      setIsLocked(next);
      toast(next ? "기억을 잠갔어요" : "잠금을 풀었어요");
    } catch {
      toast.error("잠금을 바꾸지 못했어요. 다시 시도해 주세요.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className={`${className} ${
        isLocked ? "border-amber-300/70 bg-amber-50/60 dark:bg-amber-950/20" : ""
      }`}
    >
      {isLocked ? (
        <div className="flex min-h-16 items-center gap-2 text-sm font-medium text-muted-foreground">
          <Lock aria-hidden="true" className="size-4 text-amber-700" />
          <span>잠긴 기억</span>
        </div>
      ) : (
        children
      )}
      <div className="mt-3 border-t border-border/70 pt-2">
        <p className="text-xs leading-5 text-muted-foreground">
          잠근 기억은 검색·일기·차이 찾기에서 빠져요
        </p>
        <button
          type="button"
          disabled={busy}
          onClick={() => void toggleLock()}
          className="mt-1 inline-flex min-h-11 items-center gap-2 rounded-lg px-2 text-sm font-medium text-amber-800 hover:bg-amber-100 disabled:opacity-50 dark:text-amber-300 dark:hover:bg-amber-950/40"
        >
          {isLocked ? (
            <LockOpen aria-hidden="true" className="size-4" />
          ) : (
            <Lock aria-hidden="true" className="size-4" />
          )}
          {busy
            ? isLocked
              ? "푸는 중"
              : "잠그는 중"
            : isLocked
              ? "잠금 풀기"
              : "기억 잠그기"}
        </button>
      </div>
    </div>
  );
}

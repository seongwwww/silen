"use client";

import { useState } from "react";

/** 일기가 무엇을 보고 쓰였는지 펼쳐 볼 수 있게 한다(추적성).
 * 펼친 내용은 사용자 원본이므로 AI 생성물과 시각·라벨로 구분한다(frontend.md). */
export function EvidenceDisclosure({ items }: { items: string[] }) {
  const [open, setOpen] = useState(false);
  if (items.length === 0) return null;

  return (
    <section className="mt-6">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        className="min-h-11 w-full rounded-lg border px-3 text-left text-[15px] text-muted-foreground"
      >
        {open ? "근거 접기" : `무엇을 보고 썼는지 보기 (${items.length})`}
      </button>

      {open && (
        <div className="mt-2 space-y-2">
          <p className="text-xs text-muted-foreground">내가 남긴 기록</p>
          {items.map((text, index) => (
            <p
              key={index}
              className="rounded-lg bg-muted px-3 py-2 text-[15px] whitespace-pre-wrap"
            >
              {text}
            </p>
          ))}
        </div>
      )}
    </section>
  );
}

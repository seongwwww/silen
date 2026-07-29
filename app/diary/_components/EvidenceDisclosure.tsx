"use client";

import { useState } from "react";
import type { DiaryEvidence } from "@/lib/services/diary";

/** 일기가 무엇을 보고 쓰였는지 펼쳐 볼 수 있게 한다(추적성).
 * 펼친 내용은 사용자 원본이므로 AI 생성물과 시각·라벨로 구분한다(frontend.md). */
export function EvidenceDisclosure({ items }: { items: DiaryEvidence[] }) {
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
          {items.map((item, index) => (
            <div key={index} className="rounded-lg bg-muted px-3 py-2">
              {item.text && (
                <p className="text-[15px] whitespace-pre-wrap">{item.text}</p>
              )}
              {item.photoUrl && (
                /* eslint-disable-next-line @next/next/no-img-element --
                   서명 URL은 만료되는 임시 주소라 next/image 최적화 대상이 아니다. */
                <img
                  src={item.photoUrl}
                  alt="이 기록에 붙인 사진"
                  className={`max-h-48 w-auto rounded-md ${item.text ? "mt-2" : ""}`}
                />
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

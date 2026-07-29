"use client";

import type { DiaryView } from "@/lib/services/diary";
import { updateMemoryLockInBrowser } from "@/lib/services/memoryLockClient";
import { EvidenceDisclosure } from "./EvidenceDisclosure";
import { FollowUpCard } from "./FollowUpCard";
import { DiaryEditor } from "./DiaryEditor";
import { RegenerateButton } from "./RegenerateButton";

/** 일기 한 편. AI 생성물임을 라벨·배경으로 밝히고(frontend.md), 근거는 접어 둔다.
 * 사용자가 고친 일기를 '초안'이라 부르지 않는다. */
export function DiaryArticle({ diary }: { diary: DiaryView }) {
  return (
    <article>
      <p className="text-xs text-muted-foreground">{diary.date}</p>

      {diary.oneLine && (
        <h2 className="mt-1 text-lg font-medium">{diary.oneLine}</h2>
      )}

      <div className="mt-3 rounded-xl bg-muted/50 p-4">
        <p className="mb-2 text-xs text-muted-foreground">
          {diary.isEdited ? "내가 고친 일기" : "AI가 쓴 초안"}
        </p>
        <p className="text-[15px] leading-relaxed whitespace-pre-wrap">
          {diary.body}
        </p>
      </div>

      <DiaryEditor
        id={diary.id}
        body={diary.body}
        status={diary.status}
      />
      <RegenerateButton
        id={diary.id}
        status={diary.status}
        initialToneInstruction={diary.toneInstruction}
        initialRequested={diary.regenerateRequested}
        initialReason={diary.regenerateReason}
      />

      {diary.differences.length > 0 && (
        <section className="mt-4">
          <h3 className="mb-1 text-xs text-muted-foreground">오늘 처음</h3>
          <ul className="list-disc space-y-1 pl-5">
            {diary.differences.map((d, i) => (
              <li key={i} className="text-[15px] text-muted-foreground">
                {d}
              </li>
            ))}
          </ul>
        </section>
      )}

      {diary.question && (
        <FollowUpCard
          sectionId={diary.question.sectionId}
          text={diary.question.text}
        />
      )}

      <EvidenceDisclosure
        items={diary.evidence}
        updateLock={updateMemoryLockInBrowser}
      />
    </article>
  );
}

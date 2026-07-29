/** 일기 보기 화면 표시용 타입. 원본(evidence)과 AI 생성물(body 등)을 함께 담되
 * 화면에서 시각적으로 구분한다(frontend.md). */
export interface DiaryView {
  /** 일기 id — PATCH 대상 */
  id: string;
  /** YYYY-MM-DD */
  date: string;
  /** 편집·확정 UI가 쓰는 현재 상태 */
  status: DiaryStatus;
  /** 오늘의 한 문장. 없으면 빈 문자열 */
  oneLine: string;
  /** edited_text가 있으면 그것, 없으면 generated_text */
  body: string;
  /** 일기에 녹아든 확정 차이 */
  differences: string[];
  /** 근거 메모 본문(잠금·삭제·공백 제외) */
  evidence: DiaryEvidence[];
  /** 사용자가 손댄 일기인가(status !== 'draft') */
  isEdited: boolean;
  /** 꼬리 질문(없으면 null). id는 기록 화면 링크에 쓴다 — URL엔 id만 넣는다. */
  question: { sectionId: string; text: string } | null;
  /** 다음 재생성 한 번에 적용할 자유/빠른 톤 주문. */
  toneInstruction: string | null;
  /** 재생성 요청이 저장돼 다음 워커 실행을 기다리는가. */
  regenerateRequested: boolean;
}

/** 근거 한 건. 사진만 있는 기록도 근거다 — 글이 없다고 빼지 않는다. */
export type DiaryEvidence = {
  text: string | null;
  /** Storage 경로. 화면에 쓰려면 서명 URL로 바꿔야 한다. */
  photoPath: string | null;
  photoUrl?: string | null;
};

export type DiaryStatus = "draft" | "edited" | "confirmed";

export class InvalidDiaryTransitionError extends Error {
  constructor() {
    super("허용되지 않은 상태 전이");
    this.name = "InvalidDiaryTransitionError";
  }
}

// 초안을 고치거나 바로 확정하고, 확정은 되돌릴 수 있다.
// draft로는 되돌아가지 않는다 — 사람이 손댄 흔적을 지우지 않는다.
const ALLOWED: Record<DiaryStatus, DiaryStatus[]> = {
  draft: ["edited", "confirmed"],
  edited: ["confirmed"],
  confirmed: ["edited"],
};

export function assertValidDiaryTransition(
  current: DiaryStatus,
  target: DiaryStatus,
): void {
  if (!ALLOWED[current]?.includes(target)) {
    throw new InvalidDiaryTransitionError();
  }
}

export type TonePreset = "담백" | "따뜻";
export const TONE_PRESETS: TonePreset[] = ["담백", "따뜻"];

export type QuickToneOrder = "짧게" | "유머";
export const QUICK_TONE_ORDERS: readonly QuickToneOrder[] = [
  "짧게",
  "유머",
];

/** API와 UI가 함께 쓰는 자유 톤 주문 상한. */
export const TONE_INSTRUCTION_MAX_LENGTH = 160;

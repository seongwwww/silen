/** 일기 보기 화면 표시용 타입. 원본(evidence)과 AI 생성물(body 등)을 함께 담되
 * 화면에서 시각적으로 구분한다(frontend.md). */
export interface DiaryView {
  /** YYYY-MM-DD */
  date: string;
  /** 오늘의 한 문장. 없으면 빈 문자열 */
  oneLine: string;
  /** edited_text가 있으면 그것, 없으면 generated_text */
  body: string;
  /** 일기에 녹아든 확정 차이 */
  differences: string[];
  /** 근거 메모 본문(잠금·삭제·공백 제외) */
  evidence: string[];
  /** 사용자가 손댄 일기인가(status !== 'draft') */
  isEdited: boolean;
  /** 꼬리 질문(없으면 null). id는 기록 화면 링크에 쓴다 — URL엔 id만 넣는다. */
  question: { sectionId: string; text: string } | null;
}

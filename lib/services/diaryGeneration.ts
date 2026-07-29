import { localDateFor } from "@/lib/time/day";

/** DB RPC가 구현하는 일기 생성 큐 포트.
 * user_id는 세션(auth.uid)에서만 얻고 호출자가 전달하지 않는다. */
export interface DiaryGenerationQueuePort {
  enqueue(date: string): Promise<void>;
}

type RequestTodayDiaryInput = {
  now: Date;
  timeZone: string;
};

export type DiaryGenerationRequest = {
  accepted: true;
  /** 사용자 로컬 날짜(YYYY-MM-DD). */
  date: string;
};

/** 사용자 로컬 '오늘'을 계산해 생성 작업을 요청한다.
 * 중복 제거는 DB RPC의 (auth.uid, date, job_type) 계약이 책임진다. */
export async function requestTodayDiary(
  queue: DiaryGenerationQueuePort,
  { now, timeZone }: RequestTodayDiaryInput,
): Promise<DiaryGenerationRequest> {
  const date = localDateFor(now, timeZone);
  await queue.enqueue(date);
  return { accepted: true, date };
}

export type DiffStatus = "candidate" | "confirmed" | "dismissed";

export interface ReviewItem {
  id: string;
  headline: string;
  category: string;
  evidence: string[];
}

export class InvalidTransitionError extends Error {
  constructor() {
    super("허용되지 않은 상태 전이");
    this.name = "InvalidTransitionError";
  }
}

const ALLOWED: Record<DiffStatus, DiffStatus[]> = {
  candidate: ["confirmed", "dismissed"],
  confirmed: ["candidate"],
  dismissed: ["candidate"],
};

/** 확정(candidate→confirmed/dismissed)과 되돌리기(→candidate)만 허용한다. */
export function assertValidTransition(current: DiffStatus, target: DiffStatus): void {
  if (!ALLOWED[current]?.includes(target)) {
    throw new InvalidTransitionError();
  }
}

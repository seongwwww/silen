import { Check, X } from "lucide-react";
import { Button } from "@/components/ui/button";

/** 차이 확정 액션 쌍. 아니에요(왼쪽)·맞아요(오른쪽), 색+아이콘+라벨로 구분(색만 X),
 * min-h 44px(shadcn 기본 h-9 override), 사이 간격으로 오탭 방지. frontend.md 공통. */
export function ConfirmActions({ onConfirm, onDismiss }: { onConfirm: () => void; onDismiss: () => void }) {
  return (
    <div className="flex gap-3">
      <Button variant="outline" className="min-h-11 flex-1" onClick={onDismiss}>
        <X className="size-4 text-[var(--danger-text)]" aria-hidden />아니에요
      </Button>
      <Button
        variant="outline"
        className="min-h-11 flex-1 border-[var(--success-text)] bg-[var(--success-bg)] font-medium text-[var(--success-text)]"
        onClick={onConfirm}>
        <Check className="size-4" aria-hidden />맞아요
      </Button>
    </div>
  );
}

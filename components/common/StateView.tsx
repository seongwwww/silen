/** empty/error/loading 재사용 뷰. 담담한 문구(죄책감·독려 금지). */
export function EmptyState({ message = "확인할 차이가 없어요" }: { message?: string }) {
  return <p className="py-16 text-center text-[15px] text-muted-foreground">{message}</p>;
}
export function ErrorState({ onRetry }: { onRetry?: () => void }) {
  return (
    <div className="py-16 text-center">
      <p className="text-[15px] text-muted-foreground">불러오지 못했어요.</p>
      {onRetry && <button className="mt-2 underline" onClick={onRetry}>다시 시도</button>}
    </div>
  );
}
export function LoadingState() {
  return (
    <div role="status" aria-label="불러오는 중" className="space-y-3 py-4">
      <span className="sr-only">불러오는 중</span>
      <div aria-hidden="true" className="space-y-3">
        {[0, 1, 2].map((i) => <div key={i} className="h-24 animate-pulse rounded-xl border bg-muted/60" />)}
      </div>
    </div>
  );
}

export function ProcessingState({ message = "기록을 묶고 있어요" }: { message?: string }) {
  return (
    <div role="status" className="rounded-2xl border bg-card px-5 py-8 text-center text-[15px] text-muted-foreground">
      {message}
    </div>
  );
}

export function OfflineState() {
  return (
    <p className="rounded-xl border bg-card px-4 py-3 text-center text-sm text-muted-foreground">
      지금은 오프라인이에요.
    </p>
  );
}

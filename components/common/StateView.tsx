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
  return <div className="space-y-3 py-4" aria-hidden="true">
    {[0, 1, 2].map((i) => <div key={i} className="h-24 rounded-xl border" />)}
  </div>;
}

export function DataExportCard() {
  return (
    <section aria-labelledby="data-export-title" className="mt-10 border-t pt-6">
      <h2 id="data-export-title" className="text-[15px] font-medium">
        내 데이터
      </h2>
      <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
        기록과 감정, AI가 만든 차이·일기·주간 리포트를 JSON으로
        내려받아요. 사진 파일은 포함되지 않아요. 파일 정보만 담겨요.
      </p>
      <a
        href="/api/export"
        download
        className="mt-3 inline-flex min-h-11 items-center rounded-xl border bg-card px-4 font-medium"
      >
        기록 JSON 내보내기
      </a>
    </section>
  );
}

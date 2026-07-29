"use client";

import { useState } from "react";

/** 비공개 Storage 서명 URL의 만료를 깨진 이미지로 방치하지 않는다. */
export function EvidencePhoto({
  src,
  className = "",
}: {
  src: string;
  className?: string;
}) {
  const [expired, setExpired] = useState(false);
  if (expired) {
    return (
      <p className="mt-2 text-xs leading-5 text-muted-foreground">
        사진을 다시 보려면 화면을 새로고침해 주세요
      </p>
    );
  }
  return (
    /* eslint-disable-next-line @next/next/no-img-element --
       서명 URL은 만료되는 임시 주소라 next/image 최적화 대상이 아니다. */
    <img
      src={src}
      alt="이 기록에 붙인 사진"
      onError={() => setExpired(true)}
      className={`max-h-48 max-w-full rounded-lg object-contain ${className}`}
    />
  );
}

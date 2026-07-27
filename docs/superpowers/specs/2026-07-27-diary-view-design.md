# 일기 보기 화면(`/diary`) 설계 스펙

> 상태: 확정(브레인스토밍 승인). 다음 단계: 구현 계획(`docs/superpowers/plans/2026-07-27-diary-view.md`).
> 성격: **읽기 전용 프론트 슬라이스.** 스키마 변경·API 라우트·워커 변경 없음.

## 1. 문제

파이프라인이 일기를 만들지만 **볼 화면이 없다.** 기록(`/`)과 확인(`/review`)은 있는데 끝단 산출물이 사용자에게 도달하지 않는다. 이 화면이 루프를 닫는다.

## 2. 무엇을 보여주나

**가장 최근 일기 하나**를 읽기 전용으로 보여준다. 날짜를 명시한다.

> ⚠️ **"오늘의 일기"가 아니다.** `run-diary`는 **사용자 로컬 어제**를 대상으로 돌기 때문에 가장 최근 일기는 보통 어제 것이다. "오늘"을 기본으로 잡으면 화면이 거의 항상 비어 있게 된다.

구성:

| 요소 | 출처 |
|------|------|
| 오늘의 한 문장 | `diary_sections.section_type='오늘의한문장'` |
| 본문 | `diaries.edited_text` 있으면 그것, 없으면 `generated_text` |
| 녹아든 다른 점 | `diary_sections.section_type='다른점'`의 `content` |
| 근거 메모(접힘) | `diary_sources` → `memories.raw_text` |
| 날짜 | `diaries.date` |

## 3. AI 생성물 ↔ 원본 구분 (frontend.md 필수)

`frontend.md`: *"생성된 일기와 원본 기록을 시각적으로 구분한다(배경/라벨/아이콘). 무엇이 AI 산물인지 항상 알 수 있어야 한다."*

- **일기 본문 영역에 생성물 표식**(라벨 + 배경). 사용자가 편집한 일기(`status`가 `edited`/`confirmed`)면 표식 문구가 달라야 한다 — 편집본을 "AI가 쓴 초안"이라고 하면 거짓이다.
- **펼친 근거 메모는 사용자 원본**임이 명확해야 한다(다른 배경 + 라벨).
- **색만으로 구분하지 않는다** — 라벨을 병행한다(`frontend.md` 접근성).
- **"AI가 발견했다"고 말하지 않는다.** 무엇을 보고 썼는지(근거)를 보여주는 방식으로 신뢰를 준다.

## 4. 근거 메모 노출 규칙 (privacy.md)

- **잠긴(`is_locked`) · 삭제된(`deleted_at`) 메모는 근거에서 제외**한다. 잠근 기억은 노출 경로에서 빠진다는 불변 원칙이 UI에도 적용된다.
- 본문이 비었거나 공백뿐인 메모도 제외한다(보여줄 게 없다).
- 제외는 저장소 계층에서 처리한다(`differenceRepository`의 기존 선례와 동일).

## 5. 상태 처리 (frontend.md 5종)

| 상황 | 표시 |
|------|------|
| 일기 있음 | 일기 |
| 일기 없음 + **메모도 없음** | "아직 쌓인 기록이 없어요" |
| 일기 없음 + **메모는 있음** | **"아직 일기가 만들어지지 않았어요"** |
| 로딩 | `loading.tsx`(`LoadingState`) |
| 에러 | `error.tsx`(`ErrorState` + 재시도) |

**"메모는 있는데 일기가 없다"를 별도 상태로 두는 이유:** 파이프라인이 아직 안 돈 상황이다. 빈 날과 섞으면 사용자가 "내가 기록을 안 했나?"로 오해한다. 정직하게 구분한다.

⚠️ **죄책감 유도 금지(frontend.md):** "일기를 써보세요"·"N일째 비어 있어요" 같은 독려·압박 문구를 쓰지 않는다. 없으면 없다고 담담히 말한다.

현재 `components/common/StateView.tsx`의 `EmptyState`는 `message` prop을 받는다. **미생성 상태는 새 컴포넌트를 만들지 않고 `<EmptyState message="아직 일기가 만들어지지 않았어요" />`로 표현**한다 — 기본 문구만 다른 컴포넌트를 추가하면 verbatim 중복이 된다. `StateView.tsx`는 수정하지 않는다.

## 6. "지금 만들기" 버튼이 없는 이유

`backend.md`: **앱과 워커는 큐·DB로만 통신하고 서로 직접 호출하지 않는다.** 현재 큐(`memory_jobs`)는 추출 전용이고 일기 잡 큐가 없다. 따라서 화면에서 일기 생성을 트리거할 수 없다 — **이번 범위 밖**이다. 화면은 상태를 반영만 한다.

일기 생성은 사람이 `python -m silen_worker run-diary`를 실행하거나 스케줄러가 돈다(`README.md` §4).

## 7. 아키텍처 (`/review` 패턴 그대로)

- `app/diary/page.tsx` — **서버 컴포넌트**. 세션 → 저장소 조회 → 상태 분기.
- `app/diary/loading.tsx` · `app/diary/error.tsx` — 기존 두 줄짜리 패턴.
- `app/diary/_components/DiaryView.tsx` — 일기 본문·다른 점·생성물 표식.
- `app/diary/_components/EvidenceDisclosure.tsx` — 근거 메모 접기(클라이언트).
- `lib/repositories/diaryRepository.ts` — **세션 클라이언트 + RLS**(service_role 금지, 기존 선례와 동일). `diaries`+`diary_sections`+`diary_sources→memories` 조인, 잠금·삭제 필터.
- `lib/services/diary.ts` — 표시용 타입.
- `components/common/StateView.tsx` — **수정 없음.** 기존 `EmptyState`에 문구를 넘겨 쓴다.

**API 라우트 없음**(읽기 전용 서버 컴포넌트로 충분). **스키마 변경 없음.** **워커 변경 없음.**

### 표시용 타입

```ts
type DiaryView = {
  date: string;          // YYYY-MM-DD
  oneLine: string;       // 오늘의 한 문장(없으면 빈 문자열)
  body: string;          // edited_text ?? generated_text
  differences: string[]; // 녹아든 다른 점
  evidence: string[];    // 근거 메모 본문(잠금·삭제 제외)
  isEdited: boolean;     // status가 edited/confirmed → 표식 문구 분기
};
```

저장소는 `findLatest(): Promise<DiaryView | null>`과 `hasAnyMemory(): Promise<boolean>`을 제공한다. 후자는 §5의 두 빈 상태를 가르는 데만 쓴다.

## 8. 접근성·모바일 (frontend.md)

- **터치 타깃 44px 이상** — 접기 토글 버튼에 적용(`ConfirmActions`의 `min-h-11` 선례를 따른다).
- 접기/펼치기 상태를 `aria-expanded`로 알린다(색·아이콘만으로 전달 금지).
- 모바일 우선. 기존 화면과 같은 `mx-auto max-w-md p-4` 컨테이너.

## 9. 테스트

### 9.1 단위 (jsdom, DB 없음)
- 일기 본문·한 문장·다른 점이 보인다.
- **생성물 표식이 있다**, 편집본이면 문구가 다르다.
- 근거는 기본 접혀 있고, 펼치면 원본이 **원본 표식과 함께** 보인다.
- 토글이 `aria-expanded`를 바꾼다.
- 근거가 없으면 접기 UI 자체를 보여주지 않는다.
- 상태 3분기 렌더(일기/빈날/미생성) — 미생성 문구에 독려·압박 표현이 없다.

### 9.2 통합 (실 DB, RLS)
- 저장소가 본인 최신 일기를 섹션·근거와 함께 조회한다.
- **잠금·삭제 메모가 근거에서 빠진다.**
- **타 사용자 일기가 조회되지 않는다**(RLS).
- `edited_text`가 있으면 그것을 본문으로 쓴다.

### 9.3 eval
**해당 없음** — 프롬프트·모델 미변경.

## 10. 범위 밖
- 일기 편집·확정(`edited_text` 쓰기, status 전이) · 날짜 이동·목록 · 공유·내보내기 · 사진.
- "지금 만들기" 버튼(§6 — 큐 필요).
- 워커·스키마·API 라우트 변경.

## 11. 주요 결정 요약
- **가장 최근 일기 하나, 읽기 전용.** "오늘"이 아니라 "최근"인 이유는 파이프라인이 어제를 대상으로 돌기 때문.
- **일기 + 근거 접기.** 추적성을 UI에서 드러내되 화면은 담백하게.
- **생성물/원본 시각 구분 + 라벨 병행**, 잠금·삭제 메모 제외.
- **"메모는 있는데 일기 없음"을 별도 상태로** — 파이프라인 미실행을 정직하게. 죄책감 문구 금지.
- **"지금 만들기" 없음** — 앱↔워커 직접 호출 금지 제약.
- 기존 `/review` 패턴·`StateView`·세션 RLS 저장소를 그대로 따른다.

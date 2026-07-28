# 질문 세션 · 이어 쓰기 구현 계획

> 설계: `docs/superpowers/specs/2026-07-28-question-session-design.md`

## 결정 고정

1. 같은 질문에는 한 세션에서 여러 번 기록할 수 있다.
2. 각 기록은 기존 `POST /api/memories`로 저장되는 독립 메모다.
3. 질문·답변 연결 스키마나 API 필드를 추가하지 않는다.
4. 저장 뒤 질문 맥락은 유지하고 입력·감정만 비운다.
5. 생각 단서는 사용자가 버튼을 눌렀을 때만 보인다.
6. 단서는 고정된 3개를 한 번에 하나씩 순환한다. LLM을 부르지 않는다.
7. 자동 전환·진행률·완료 압박·죄책감 문구를 넣지 않는다.
8. 질문 세션이 아니면 단서·파이프라인 설명을 렌더하지 않는다.
9. 작은 차이는 즉시 발견된다고 약속하지 않는다. 기록이 쌓여 나중의 단서가
   된다고만 설명한다.
10. 모든 조작 버튼은 `min-h-11`로 44px 터치 타깃을 지킨다.
11. URL에는 기존처럼 `section` UUID만 둔다.
12. 스키마·API·워커·저장소·일기 생성 로직은 수정하지 않는다.

## Task 1: 실패 테스트

**Files:** Modify `app/diary/_components/FollowUpCard.test.tsx`,
`app/_components/RecordForm.test.tsx`

1. `FollowUpCard`가 아래 안내를 보여주는 테스트를 추가한다.
   - `"한 번에 다 적지 않아도 괜찮아요."`
   - `"같은 질문에서 여러 번 이어 쓸 수 있어요."`
2. 질문이 있는 `RecordForm`이 아래를 보여주는 테스트를 추가한다.
   - `"이 질문에서 이어 쓰는 중"`
   - 반복 기록 안내
   - `"이렇게 남긴 기록도 쌓여, 나중에 작은 차이를 찾는 단서가 돼요."`
3. `"다른 각도로 떠올려보기"`를 누르면 첫 단서가 나타나고, 다시 누르면
   다음 단서가 나타나는 테스트를 추가한다.
4. 질문이 없으면 생각 단서 버튼이 없는 테스트를 추가한다.
5. 질문 세션에서 두 번 저장해도 질문이 남고 POST가 두 번 호출되는 테스트를
   추가한다.
6. 해당 테스트를 실행해 실패를 확인한다.

```powershell
npx vitest run app/diary/_components/FollowUpCard.test.tsx app/_components/RecordForm.test.tsx
```

## Task 2: 최소 구현

**Files:** Modify `app/diary/_components/FollowUpCard.tsx`,
`app/_components/RecordForm.tsx`

1. `FollowUpCard` 질문 링크 아래에 반복 기록 안내를 추가한다.
2. `RecordForm`에 세션 전용 `QUESTION_CUES` 3개와 cue index state를 둔다.
3. 질문 맥락을 라벨·질문·반복 기록 안내의 묶음으로 렌더한다.
4. 사용자 클릭으로만 단서를 펼치고 다음 클릭에 다음 단서로 순환한다.
5. 단서에 `aria-live="polite"`를 적용한다.
6. 질문 세션에서만 작은 차이 단서 설명을 보여준다.
7. 질문 세션 저장 성공 메시지만
   `"기록했어요. 더 떠오르면 이어 적어도 돼요."`로 바꾼다.
8. 테스트를 통과시킨다.

## Task 3: 회귀 검사

```powershell
npx vitest run
npm run lint
npm run build
```

기준선: 프론트 단위 59건 + 새 테스트.

## Task 4: 상태 기록

`HANDOFF.md`의 현재 활성 작업과 상태에 설계·계획, 변경 파일, 검증 결과,
막힘과 다음 시작점을 기록한다. push·merge는 하지 않는다.

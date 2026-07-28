# ADR-0003 — Daily Wrap과 수동 일기 생성 요청

- 상태: 채택
- 날짜: 2026-07-28

## 배경

데모에서 Day 0 보상인 일기를 사용자가 웹에서 직접 요청하고, 실제 완료 뒤에는
`Daily Wrap` 도착 경험으로 보여줄 필요가 생겼다. 기존에는 첫 일기 생성 요청 경로와
잡 상태 원장이 없고, CLI `run-diary`를 사람이 실행해야 했다.

Next.js가 Python/LLM을 직접 실행하면 저장소의 2런타임 경계를 깨고, 요청 직후
`생성 중`이나 `완료`를 표시하면 실제 상태를 추측하게 된다.

## 결정

1. `Daily Wrap`은 새 산출물 타입이 아니라 기존 `diaries`의 사용자-facing 도착
   상태다. `diaries`와 필수 섹션 저장이 끝난 뒤에만 “오늘의 일기가 도착했어요”를
   표시한다.
2. `diary_generation_requests`를 `(user_id, date)` 유니크 원장으로 둔다.
   상태는 `queued → processing → done | failed`이며 워커 claim 시점에만
   `processing`을 기록한다.
3. 인증 사용자는 security-definer RPC
   `request_diary_generation(target_date)`만 호출한다. RPC가 `auth.uid()`와 사용자
   타임존의 오늘 날짜, 활성 메모 존재, 중복 요청을 검증한다.
4. 별도 런타임 직접 호출이나 새 큐를 만들지 않고 기존 pgmq `memory_jobs`에
   `job_type='diary'` 메시지를 넣는다. Python `run-pending`이 타입을 분기해 일기를
   생성하고 요청 원장을 갱신한다.
5. `/demo`는 프론트 목 데이터만 사용한다. 실제 데이터·API를 건드리지 않으며
   quiet/available/closing/discovery/requested/processing/arrived/failed 상태를
   선택해 확인한다.

## 문구 원칙

- 시간만으로 하루가 끝났다고 단정하지 않고 “오늘을 정리할 시간이에요”라고 제안한다.
- 요청 직후에는 “일기 만들기를 요청했어요”, 실제 claim 뒤에만
  “오늘 기록을 한 편으로 묶고 있어요”라고 한다.
- `Daily Wrap` 도착은 `DAILY WRAP` 라벨과 “오늘의 일기가 도착했어요”로 표현한다.
- 의미 있는 차이는 detector와 narration을 통과한 실제 후보 문장만 사용하고,
  `first_occurrence`는 Daily Wrap 발견 신호에서 제외한다.

## 결과와 제약

- 첫 일기도 웹에서 멱등하게 요청할 수 있고, 재시도 상한 뒤 실패 상태를 복구 UI에
  사용할 수 있다.
- 기존 `memory_jobs`가 두 작업 타입을 운반하므로 소비자는 반드시 `job_type`을
  분기해야 한다. 향후 처리량이나 우선순위 요구가 생기면 전용 큐로 분리한다.
- 마이그레이션은 up/down을 함께 작성하되 AI가 적용하지 않는다. 사람의 staging
  dry-run과 적용 전에는 실제 수동 생성 API가 동작하지 않는다.
- OS 푸시·이메일 알림과 야간 스케줄러는 여전히 베타 운영 게이트다.

# 테스트 규칙

Definition of Done = **lint + typecheck + unit + integration + eval 전부 통과.**

## 계층

- **Unit** — detector 통계 로직(z-score·first-occurrence·freq-shift), 시간/타임존 유틸, 순수 함수. LLM 없이 deterministic.
- **Integration** — 기록→탐지→서술→일기 파이프라인, 큐 멱등성, 삭제 연쇄(DB+Storage+embedding+index), user 스코프 격리.
- **Eval** — LLM 서술 품질(ai-evals.md 골든셋). 별도 게이트.
- **E2E(선택)** — 핵심 사용자 흐름(첫 기록 5초, 밤 일기, 7일 리포트).

## 필수 회귀 시나리오 (실은 특화)

- 같은 날짜 일기 **중복 생성 안 됨**(멱등).
- 타 사용자 embedding이 검색에 **절대 안 섞임**.
- 삭제 후 Storage·pgvector·인덱스에 **잔존 없음**.
- 타임존 경계에서 전날 메모가 오늘 일기에 **안 새어듦**.
- detector에 없는 해석이 LLM 일기에 **추가되지 않음**.
- 재시도된 큐 작업이 **중복 레코드 안 만듦**.
- 빈 날에 **억지 생성 안 함**.

## 방식

- TDD 우선: 실패 테스트 → 최소 구현 → 리팩터. 테스트 통과 지점마다 작은 commit.
- 버그 수정 시 **재현 테스트를 먼저** 추가(systematic-debugging).
- 외부 의존(LLM·STT)은 계약 기반 목/스텁. eval만 실제 모델 사용.
- 커버리지는 목적이 아니라 신뢰의 지표 — 위 필수 시나리오는 100% 커버.

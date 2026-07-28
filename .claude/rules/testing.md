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
- **통합 테스트는 DB를 소유하지 않는다.** 자기가 만든 것만 만들고·지우고·단언한다.
  전역 사용자 삭제, 전역 `purge_queue`, "큐 전체가 비었다" 같은 전역 상태 단언을
  쓰지 않는다.
- 테스트 사용자 정리는 Auth 계정 삭제로 끝내지 않는다. FK 밖에 있는 pgmq
  대기열·아카이브, `deletions` 원장, Storage 사용자 폴더를 `user_id`로 먼저
  정리한 뒤 계정을 삭제한다.
- 큐를 소비하는 통합 테스트는 `process_pending(only_user_id=...)`로 자기 사용자만
  claim·처리한다. 다른 사용자의 `read_ct`·visibility timeout도 바꾸면 안 된다.
  큐 상태 단언은 visibility timeout을 바꾸는 `pgmq.read` 대신 큐 테이블을 직접
  조회한다. 큐 자체의 전달 의미를 검사할 때는 테스트 전용 임시 큐를 쓴다.
- 공유 Mailpit 사서함 전체를 비우지 않는다. 테스트마다 고유한 수신 주소를 쓰고
  그 주소의 메일만 조회한다.

# Git 규칙

히스토리는 영구 기록이다. 로그보다 지우기 어려우므로 프라이버시·경계 원칙이 커밋에도 그대로 적용된다.

## 커밋 메시지

- 형식: `<type>(<scope>): <한국어 요약>` — type·scope는 영문 소문자, 요약은 한국어, 50자 내외. 마침표 없음.
- type: `feat` `fix` `docs` `refactor` `test` `perf` `chore` `revert`
- scope(선택): `detector` `worker` `api` `db` `ui` `eval` `privacy` `auth`
- 본문은 **무엇을·왜**. 어떻게는 코드가 말한다. 72자 줄바꿈.
- ADR·이슈 참조는 본문 마지막 줄에(`ADR-0002`, `#12`).
- Claude가 작성한 커밋은 `Co-Authored-By: Claude ...` 트레일러를 남긴다.

## 프라이버시 (필수)

- **사용자 기록 본문·일기 텍스트를 커밋 메시지·브랜치명·fixture 파일명에 넣지 않는다.** backend.md의 로깅 금지 원칙이 git history에도 적용되며, 히스토리는 사실상 되돌릴 수 없다.
- 버그 재현 케이스는 원문 대신 **fixture ID·dimension·통계값**으로 기술한다.
- `.env`·DB 덤프·실사용자 데이터는 커밋하지 않는다. 스테이징 전 `git status` 확인.

## 커밋 단위

- **하나의 커밋 = 하나의 논리적 변경 + 그 시점에 테스트가 통과하는 상태.** TDD 사이클마다 작게 커밋(testing.md).
- 리팩터링과 동작 변경을 **같은 커밋에 섞지 않는다.** 리뷰가 무엇이 바뀌었는지 분리할 수 있어야 한다.
- **detector 변경과 프롬프트 변경을 같은 커밋에 섞지 않는다.** "탐지=통계, 서술=LLM" 경계가 히스토리에도 남아야 eval 회귀의 원인을 이분 탐색할 수 있다.
- 마이그레이션은 **up/down을 같은 커밋에.** down 없는 마이그레이션 커밋 금지(database.md).
- expand/backfill/contract는 **단계마다 별도 커밋.** 각 커밋이 독립적으로 배포 가능해야 한다.
- ADR은 그 결정을 구현하는 커밋보다 **먼저** 들어간다.

안티패턴: `WIP` · 하루치 몰아서 한 커밋 · `fix typo` 연발 · 무관한 파일 동반 스테이징.

## 브랜치

- 기본 브랜치 `main`. 기능 작업은 worktree로 분리(ADR-0001).
- 네이밍: `feat/<topic>` `fix/<topic>` `docs/<topic>` — 영문 kebab-case.
- 종료는 `/superpowers:finishing-a-development-branch`.

## 금지

- `main`에 **force push 금지.** 히스토리 재작성은 공유 전 로컬 브랜치에서만.
- **`--no-verify` 금지.** Hook(lint·eval)이 막으면 원인을 고친다. 우회하지 않는다.
- **커밋·push는 사람이 요청할 때만.** Claude가 임의로 하지 않는다(CLAUDE.md 안전 가드).

# ADR-0001: 초기 스택·워크플로·거버넌스

- 상태: 채택
- 날짜: 2026-07-22
- 관련: docs/planning/서비스_기획서.md, docs/design/ERD.mermaid

## 맥락

"실은"은 개인 기록을 다루는 프라이버시 민감 제품이며, 핵심 차별점은 "탐지=통계, 서술=LLM" 파이프라인이다. AI가 그럴듯하지만 틀린 결과를 만드는 위험이 크므로, 스택뿐 아니라 개발 워크플로·규칙 거버넌스를 처음부터 고정할 필요가 있다.

## 검토한 선택지

**기술 스택**
1. 단일 Next.js(통계까지 JS) — 운영 단순, 그러나 통계/ML 구현 번거로움.
2. **Next.js + Python 워커** — 통계·AI는 Python(numpy/scipy/pandas), 앱·API는 Next.js.

**워크플로 스킬**
1. Superpowers 주축 — 요구사항 인터뷰·계획·worktree·TDD·리뷰·병합 결정 일괄.
2. Matt Pocock Skills — grill→spec→tickets→implement. Superpowers와 TDD/리뷰 절차 중복.
3. 전부 설치(ECC 등) — 규칙 충돌·컨텍스트 증가.

**규칙 거버넌스** (Claude Code 공식 가이드)
- 항상 적용 = CLAUDE.md + .claude/rules/, 절차 = Skill, 강제 검사 = Hook.

## 결정

- 스택: **Next.js + Python 워커** + PostgreSQL(pgvector/PostGIS) + Supabase.
- 주 워크플로: **Superpowers**. 프론트 품질은 공식 **frontend-design**. ECC는 PostgreSQL·Python·eval·security 부분만 참고. Matt Pocock/ECC 전체·Ralph(광범위)·Caveman·Taste 기본판은 상시 채택하지 않음.
- 거버넌스: CLAUDE.md(불변 원칙, 200줄 이하) + `.claude/rules/*`(도메인별) + ADR(중요 결정) + Hook(eval·lint 강제).
- 안전 가드: 삭제·마이그레이션·배포·production 접근은 Claude 자동 실행 금지. 롤백은 Git(worktree/commit), `/rewind`는 로컬 편집 복구만.

## 결과

- 긍정: 통계/AI 구현이 자연스럽고, AI 오생성 위험을 리뷰·eval 게이트로 방어. 규칙이 코드 생성에 항상 주입됨.
- 감수 비용: Next.js↔Python 두 런타임 운영. 큐/멱등성 설계 필요.
- 후속: (1) ERD 설계 리뷰 게이트 — difference_evidence, diary_sources 조인 테이블, polymorphic embeddings 무결성, deletion ledger 확정(ADR-0002 예정). (2) eval 골든셋 뼈대 W1.

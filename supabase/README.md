# Supabase 로컬

## 명령

- `npx supabase start` — 로컬 스택 기동 (Docker 필요)
- `npx supabase stop` — 중지
- `npx supabase migration new <name>` — 마이그레이션 생성
- `npx supabase db reset` — 초기화 후 마이그레이션 전체 재적용

로컬 DB URL: `postgresql://postgres:postgres@127.0.0.1:54322/postgres`

## down 스크립트 규약

Supabase CLI에는 down 마이그레이션 개념이 없다. `database.md`가 요구하는
보상 전략은 `migrations/down/<같은-타임스탬프>_<같은-이름>.down.sql`로 보관한다.

- **자동 실행되지 않는다.** 롤백은 사람이 검토 후 실행한다.
- up 마이그레이션을 추가하면 down도 **같은 커밋에** 넣는다(git.md).
- 적용 전 staging에서 dry-run 한다. production 적용은 사람이 실행한다.

`migrations/down/`은 CLI가 마이그레이션으로 오인하지 않도록 하위 디렉터리에 둔다.

# Supabase 로컬

## 명령

- `npx supabase start` — 로컬 스택 기동 (Docker 필요)
- `npx supabase stop` — 중지
- `npx supabase migration new <name>` — 마이그레이션 생성
- `npx supabase db reset` — 초기화 후 마이그레이션 전체 재적용

로컬 DB URL: `postgresql://postgres:postgres@127.0.0.1:54322/postgres`

**`db reset` 뒤 auth 요청이 502를 내면** Kong↔GoTrue 라우팅이 컨테이너
재시작으로 깨진 것이다. `npx supabase stop && npx supabase start`로 전체를
다시 띄우면 복구된다. 통합 테스트가 `signInAnonymously`에서 502로 무더기
실패하면 이 경우다.

## down 스크립트 규약

Supabase CLI에는 down 마이그레이션 개념이 없다. `database.md`가 요구하는
보상 전략은 `migrations/down/<같은-타임스탬프>_<같은-이름>.down.sql`로 보관한다.

- **자동 실행되지 않는다.** 롤백은 사람이 검토 후 실행한다.
- up 마이그레이션을 추가하면 down도 **같은 커밋에** 넣는다(git.md).
- 적용 전 staging에서 dry-run 한다. production 적용은 사람이 실행한다.

`migrations/down/`은 CLI가 마이그레이션으로 오인하지 않도록 하위 디렉터리에 둔다.

## 인증

- 익명 로그인이 켜져 있다(`config.toml`의 `enable_anonymous_sign_ins`).
  익명 사용자는 `authenticated` 역할을 받는다(`anon`이 아니다).
- 이메일 변경에 확인이 필요하다(`enable_confirmations = true`). 끄면 익명
  사용자가 남의 주소를 자기 계정에 등록할 수 있다.
- 메일은 Mailpit(`http://127.0.0.1:54324`)으로 간다. 실제 발송되지 않는다.
  통합 테스트는 공유 사서함 전체를 비우지 않고 UUID 기반 수신 주소의 메일만
  조회한다.
- RLS 정책은 소유자 직접과 부모 경유 EXISTS 두 형태뿐이다. 새 테이블을
  추가하면 둘 중 하나를 골라 정책을 함께 넣는다. 정책 없이 RLS만 켜면
  그 테이블은 앱에서 전혀 보이지 않는다.
- `postgres`가 만든 테이블은 역할 권한이 자동 부여되지 않는다. 새 테이블에는
  `authenticated`(CRUD)·`service_role`(ALL) GRANT를 함께 넣는다. `anon`에는
  주지 않는다.

## Storage

- 비공개 버킷 `memories`. 경로 규약 `{user_id}/{uuid}.{ext}`.
- `storage.objects` 정책은 테이블 RLS와 같은 원리다 — 최상위 폴더가 소유자.
  `authenticated`는 자기 폴더만 CRUD, `update`는 없음(원본 불변).
- 사진은 클라이언트가 직접 업로드하고, 서버는 경로의 본인 폴더 여부를
  검증한 뒤 `assets` 행을 만든다. `assets` RLS는 부모 메모 소유권만 보고
  파일 소유권은 안 보므로, 이 경로 검증이 교차 사용자 파일 누출의
  유일한 방어선이다.

## 큐 (pgmq)

- 비동기 큐는 pgmq. 큐 `memory_jobs`, 메시지 `{memory_id, user_id}`.
- 메모 insert AFTER 트리거가 적재한다. in-DB라 메모 커밋과 같은
  트랜잭션 — 유령·유실 잡이 없다. 메시지엔 본문을 싣지 않는다.
- 워커는 특권 역할(로컬 postgres)로 psycopg 직접 접속해 RLS를 우회하므로,
  워커 쿼리가 user_id 필터를 지키는 것이 유일한 격리 방어선이다.
- 새 잡을 추가하면 이 큐를 재사용하고, 처리는 멱등(자연키 upsert)해야 한다.
- 큐는 전역이다. 통합 테스트는 `purge_queue`로 비우지 않고
  `process_pending(only_user_id=...)`로 자기 잡만 claim·처리한다. 남의 `read_ct`와
  visibility timeout도 바꾸지 않는다. 큐 상태 단언은 `pgmq.read` 대신 큐 테이블을
  직접 조회하고, 전달 의미 테스트는 임시 큐를 쓴다.
- 테스트 사용자를 지울 때는 FK cascade 밖의 대기·아카이브 메시지와 삭제 원장,
  Storage 사용자 폴더를 `user_id`로 먼저 지운다.

## 엔티티

- 워커가 메모 텍스트에서 4종(person·place·activity·thing)을 추출해
  `entities`·`memory_entities`를 채운다. relation_type은 `'mentioned'`
  (met/visited/did로 단정하지 않는다 — 과잉해석 금지).
- 추출 name이 원문에 없으면 폐기한다(환각 0%). 추출자이지 해석자가 아니다.
- 고아 entity는 `memory_entities` AFTER DELETE 트리거(`delete_orphan_entity`)로
  즉시 삭제한다 — 링크가 사라진 타인 이름이 남지 않게(삭제 완전성).
- 추출은 Vertex AI Gemini + ADC로 호출한다(env는 루트 `.env.example` 참고).
  본문은 로그·APM에 남기지 않는다(ID·카운트만).

## 차이 검출(detector)

- 워커가 `detect_day(user_id, date)`로 그날 언급된 엔티티를 통계 규칙으로 분류해
  `differences(status=candidate)`를 채운다. **탐지=통계, LLM 없음.**
- 규칙은 first_occurrence(전체 이력 첫 등장), freq_shift(연속·재등장),
  absence(평소 기록되던 엔티티의 **기록상 부재**), 감정 valence z-score다.
- 달력 경과일이 아니라 과거 활성 기록일을 기준으로 놀라움(bits)을 계산하고,
  기각 학습을 반영해 하루 최대 3개만 서술한다. 빈 날에는 부재를 만들지 않는다.
- first_occurrence는 저장하되 일일 카드 랭킹·서술에서는 제외하고 일기의
  "오늘 처음" 목록에서만 사용한다.
- 하루 경계는 사용자 로컬 자정(users.timezone + time.local_date_for).
- 엔티티 차이는 `(user,date,entity,method)`, 감정축은
  `(user,date,dimension,method)` 부분 unique로 멱등 upsert한다.

## 차이 서술(narration)

- 워커가 `differences`(candidate)를 담백한 카드 텍스트로 서술해
  `difference_narrations`(difference당 1건, unique)에 저장한다.
- 입력은 구조화 사실만(엔티티명·통계 근거). **메모 본문은 전송하지 않는다.**
- 가드레일이 엔티티명 정합·조언/인과 블록리스트·길이를 검사해 통과분만 저장.
- 서술은 사용자에게 **읽기 전용**(쓰기는 워커). difference 삭제 시 cascade.

## 일기 생성(diary)

- 워커가 `generate_diary(user_id, date)`로 그날 메모(raw_text)와
  **기각하지 않은 intact 차이**(candidate·confirmed)를 담백한 하루 일기로 엮어
  `diaries`(하루 1건, unique)+`diary_sections`(오늘의한문장·본문·다른점)+
  `diary_sources`(메모 근거)에 저장한다. dismissed·stale은 제외한다.
- 사용자 설정의 기본 톤(담백·따뜻)과 일기별 1회 톤 주문을 프롬프트에 반영하되,
  문체만 바꾸고 사실·근거 가드레일은 그대로 적용한다.
- **하루 1건 멱등·자동 재생성 금지.** 사용자가 남긴 재생성 요청만 상태와 무관하게
  새 초안으로 바꾸고 편집본을 비운 뒤 요청을 소비한다. 요청 없는 force는 draft만 갱신한다.
- 빈 날(메모 0)은 일기를 만들지 않는다. 가드레일이 근거 정합(used⊆입력)·조언/인과와
  **기록 범위 표현**을 검사해 통과분만 저장한다. 차이를 생활 전체의 사실로 승격한
  출력은 status와 관계없이 폐기한다.
- 본문엔 `freq_shift`(반복·재등장)와 `zscore`(감정 기록 변화)를 녹인다.
  `first_occurrence`(처음 등장)는 `다른점` 섹션(= 화면의 "오늘 처음")이 담당한다.
- 꼬리 질문은 하루 최대 1건(`section_type='질문'`). 처음 등장한 사람>장소>활동
  중 하나에만 묻고, 대상이 없으면 묻지 않는다. 답변은 따로 저장하지 않는다 —
  사용자가 남기는 새 기록이 곧 답이다.

## 주간 리포트

- `run-weekly`가 사용자 첫 활성 기록일을 기준으로 막 끝난 7일 블록만 집계한다.
- 가장 많이 기록한 것·이번 블록의 첫 등장·감정 차이의 세 슬롯을
  `weekly_report_highlights`에 저장한다. 모든 하이라이트는 본인
  `difference_id`와 intact 근거를 가져야 한다.
- 같은 블록 재실행은 기존 리포트와 슬롯을 멱등 갱신한다.

## 내보내기·전체 삭제

- `/api/export`는 세션 사용자 그래프를 JSON으로 내려주며 사진 바이너리·OCR·
  전사 본문은 포함하지 않는다. 모든 하위 행은 본인 부모 ID로 다시 제한한다.
- 전체 삭제 요청 RPC는 `auth.uid()`를 대상 ID로 고정한다. 실제 삭제 워커는
  Storage → 리포트 → 일기 → 차이/파생 → 원본 순서로 재개 가능하게 처리하고
  마지막에 DB·Storage 잔존을 검증한다. 계정과 삭제 원장은 유지한다.

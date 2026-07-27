# 파이프라인 트리거(CLI 엔트리포인트) 설계 스펙

> 상태: 확정(브레인스토밍 승인). 다음 단계: 구현 계획(`docs/superpowers/plans/2026-07-27-pipeline-trigger.md`).
> 성격: **새 도메인 로직 없음.** 이미 있는 워커 함수 4개를 실제로 구동 가능하게 만드는 **운영 배선 계층**이다.

## 1. 문제

워커 진입점 4개가 전부 "호출 가능한 함수"일 뿐이고 **아무도 부르지 않는다.**

| 함수 | 위치 | 현재 |
|------|------|------|
| `process_pending(limit, extractor)` | `tasks/process.py` | 큐 소비(엔티티 추출) — 호출자 없음 |
| `detect_day(conn, user_id, date_iso)` | `tasks/detect.py` | 차이 검출 — 호출자 없음 |
| `narrate_difference(conn, difference_id, narrator)` | `tasks/narrate.py` | 차이 서술 — 호출자 없음 |
| `generate_diary(conn, user_id, date_iso, force, writer)` | `tasks/write_diary.py` | 일기 생성 — 호출자 없음 |

CLI·`__main__`·console_scripts가 **전혀 없어** `python -c "..."` 외에 실행 경로가 없다. 그래서 기록 화면으로 메모가 쌓여도 **차이·일기가 생성되지 않는다.**

## 2. 접근 — CLI + 외부 스케줄러 위임

명령줄 진입점을 만들고, **주기 실행은 OS 스케줄러(Windows 작업 스케줄러 / cron)에 맡긴다.**

상주 데몬을 만들지 않는 이유: 배포 환경이 없어 검증이 불가능하고, 프로세스 관리·재시작·타임존별 스케줄링이 붙는다. 스케줄링은 코드가 아니라 **운영 결정**이다. CLI만 있으면 로컬에서 즉시 진짜 파이프라인을 돌려볼 수 있다(지금 불가능한 것).

## 3. 명령 3개

```
python -m silen_worker run-pending    # 큐 소비 → 엔티티 추출
python -m silen_worker run-daily      # detect → narrate (차이 카드 준비)
python -m silen_worker run-diary      # 일기 생성 (확정 차이 반영)
```

### 3.1 왜 `run-daily`와 `run-diary`가 분리되는가

`generate_diary`는 **`status='confirmed'` 차이만** 쓴다(`fetch_confirmed_differences`). 차이는 `candidate`로 생성되고 **확정은 사람이 확인 UI에서** 한다(맞아요/아니에요).

따라서 `detect → narrate → diary`를 한 번에 돌리면 사용자가 확정할 틈이 없어 **일기에 "다른 점"이 하나도 안 들어간다.** 명령을 나눠 사람의 확정을 사이에 둔다:

```
run-daily (자정 이후)  →  사람이 확인 UI에서 확정  →  run-diary (그날 밤)
```

## 4. 재실행 안전 — 이 기능의 핵심

**문제:** `narrate_difference`는 기존 서술 존재를 확인하지 않고 **매번 LLM을 호출**한다. `detect_day`는 멱등(upsert)이지만 매 실행마다 **모든** difference id를 반환하므로 그대로 흘러간다. 사람이 한 번 부를 땐 무해했지만, 스케줄러가 반복 호출하면 **매 실행마다 전체 재서술 = 반복 과금**이다.

**해결:** `narrate_difference`에 `skip_if_exists: bool = True`를 추가한다.
- 기존 narration이 있으면 **LLM을 부르지 않고** 그 narration id를 반환.
- 명시적 "다시 만들기"는 `skip_if_exists=False`.
- 기본값이 `True`라 **모든 호출자가 자동으로 보호**된다.

**결과:** 스케줄러가 아무리 자주 돌아도 **새 차이에만 비용이 발생**한다.

나머지는 이미 멱등: `detect_day`(부분 unique upsert) · `generate_diary`(하루 1건, 자동 재생성 금지) · `process_pending`(큐 소비 + 자연키 upsert).

## 5. 대상 선택

- **인자 없으면 전체 사용자 × 각자 로컬 "어제"** 를 처리한다.
- `--user <uuid>` / `--date <YYYY-MM-DD>` 로 좁힐 수 있다(디버깅·재실행).
- 기준 날짜가 "어제"인 이유: 자정이 지나야 그 하루가 완결된다. 배치는 사용자 로컬 자정 이후에 도는 것을 전제한다.
- 사용자별 로컬 날짜는 `users.timezone` + `time.local_date_for`로 계산한다(하루 경계 단일 출처).
- `run-pending`은 큐 기반이라 사용자 무관 — 큐가 빌 때까지 배치 반복(drain), 무한 루프 방지 상한 있음.

**운영 유의:** `run-daily`와 `run-diary`가 **같은 날(로컬)** 안에서 돌아야 같은 대상을 가리킨다. `run-daily`를 00:30에, `run-diary`를 같은 날 밤에 돌리면 둘 다 "어제"(= 완결된 그 하루)를 대상으로 한다.

**`run-diary`는 `force=False`로 호출한다.** 이미 일기가 있으면 덮어쓰지 않는다(자동 재생성 금지). 스케줄러가 반복 호출해도 안전하고, 사용자가 편집한 일기(`edited`/`confirmed`)는 보존된다. 명시적 재생성이 필요하면 `--force` 플래그로만 가능하게 한다.

## 6. 에러 처리·종료 코드·로깅

- **사용자 단위 격리**: 한 사용자 처리가 실패해도 나머지를 계속 처리한다. 한 명의 LLM 오류가 전체 배치를 멈추면 안 된다.
- **종료 코드**: 전부 성공 `0`, 실패가 하나라도 있으면 `1`(스케줄러가 감지 가능). 인자 오류는 argparse 기본(`2`).
- **로깅**: 구조화(JSON 한 줄). **사용자 기록 본문·일기 텍스트를 절대 남기지 않는다** — `user_id`·카운트·id·소요시간만(backend.md·privacy.md).
- LLM 예외는 해당 사용자 단위에서 잡아 집계하고 다음 사용자로 넘어간다.

## 7. 아키텍처

- `worker/src/silen_worker/cli.py` — argparse + 오케스트레이션. **도메인 로직 없음**, 기존 `tasks/*` 함수를 부르기만 한다.
- `worker/src/silen_worker/__main__.py` — `python -m silen_worker` 진입점.
- `worker/pyproject.toml` — `[project.scripts] silen-worker = "silen_worker.cli:main"`.
- `worker/src/silen_worker/db.py`(수정) — `fetch_active_users`, `fetch_narration_id` 추가.
- `worker/src/silen_worker/tasks/narrate.py`(수정) — `skip_if_exists` 파라미터.

**테스트 가능성:** 각 명령은 주입 가능한 함수로 두고(`run_daily(conn, targets, narrator=None)`), `main()`은 인자 파싱·DB 연결만 한다. 스텁 주입으로 LLM 없이 검증한다.

`process_pending`이 `conn`을 받지 않고 자체 `connect()`하는 불일치는 **그대로 둔다**(병합된 코드 회귀 위험, 이 기능의 목적과 무관).

## 8. 테스트

### 8.1 단위 (DB·LLM 없음)
- 사용자 로컬 "어제" 계산(타임존별, `now` 주입).
- 인자 파싱(`--user`·`--date`·기본값).
- 실패 집계 → 종료 코드 매핑.

### 8.2 통합 (실 DB, 스텁 LLM)
- `run-daily`가 detect→narrate 체인을 수행하고 narration을 남긴다.
- **핵심 회귀 — 두 번 돌려도 LLM 호출은 1회**(스텁 호출 카운트로 검증). 재실행 과금 방지의 증거.
- `run-diary`가 confirmed 차이를 반영해 일기를 만든다. confirmed가 없으면 메모만으로 만든다.
- 한 사용자 실패가 다른 사용자 처리를 막지 않는다(스텁이 특정 user에서 예외).
- user 스코프 격리(타 사용자 데이터 안 섞임).

### 8.3 eval
**해당 없음.** 이 기능은 프롬프트·모델을 건드리지 않는다(배선만). 기존 eval 3종은 그대로 게이트로 남는다.

## 9. 스케줄 등록

`README.md`에 등록 예시를 문서화한다(Windows 작업 스케줄러 / cron).
**실제 등록은 사람이 실행한다** — 운영·배포성 작업은 AI 자동 실행 금지(CLAUDE.md 안전 가드).

## 10. 범위 밖

- 상주 워커 데몬 · `--watch` 폴링 루프.
- 사용자별 `diary_time` 기반 정밀 스케줄(지금은 외부 스케줄러의 단순 주기 실행).
- 실패 알림·모니터링·메트릭.
- `process_pending`의 `conn` 인터페이스 통일.
- 새 도메인 로직·스키마 변경(없음).

## 11. 주요 결정 요약

- **CLI + 외부 스케줄러 위임**(상주 데몬 아님) — 배포 환경 부재, 스케줄링은 운영 결정.
- **`run-daily` / `run-diary` 분리** — 사이에 사람의 확정이 들어가야 일기가 차이를 녹인다.
- **`skip_if_exists=True` 기본값** — 반복 과금 차단. 기존 함수를 수정하지만 모든 호출자를 보호한다.
- **전체 사용자 × 로컬 어제 자동 순회**, `--user`/`--date`로 좁히기 가능.
- **사용자 단위 실패 격리 + exit 1 집계**, 본문 미로깅.
- **스케줄 실제 등록은 사람이.**

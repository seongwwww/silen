-- RLS 정책. 형태는 둘뿐이다 — 소유자 직접, 부모 경유 EXISTS.
-- 형태를 늘리지 않는 것이 검토 가능성을 지킨다.
--
-- (select auth.uid())로 감싸는 것은 Postgres가 행마다 재평가하지
-- 않고 한 번만 계산하게 하기 위함이다.

-- ── 소유자 직접 ────────────────────────────────────────────────
create policy "본인 프로필만" on public.users
  for all to authenticated
  using (id = (select auth.uid()))
  with check (id = (select auth.uid()));

create policy "본인 데이터만" on public.memories
  for all to authenticated
  using (user_id = (select auth.uid()))
  with check (user_id = (select auth.uid()));

create policy "본인 데이터만" on public.differences
  for all to authenticated
  using (user_id = (select auth.uid()))
  with check (user_id = (select auth.uid()));

create policy "본인 데이터만" on public.diaries
  for all to authenticated
  using (user_id = (select auth.uid()))
  with check (user_id = (select auth.uid()));

create policy "본인 데이터만" on public.entities
  for all to authenticated
  using (user_id = (select auth.uid()))
  with check (user_id = (select auth.uid()));

create policy "본인 데이터만" on public.signals
  for all to authenticated
  using (user_id = (select auth.uid()))
  with check (user_id = (select auth.uid()));

create policy "본인 데이터만" on public.baselines
  for all to authenticated
  using (user_id = (select auth.uid()))
  with check (user_id = (select auth.uid()));

create policy "본인 데이터만" on public.weekly_reports
  for all to authenticated
  using (user_id = (select auth.uid()))
  with check (user_id = (select auth.uid()));

create policy "본인 데이터만" on public.consents
  for all to authenticated
  using (user_id = (select auth.uid()))
  with check (user_id = (select auth.uid()));

-- ── 부모 경유 EXISTS ───────────────────────────────────────────
-- 소유자가 부모 한 곳에만 존재하므로 부모와 자식의 소유자가
-- 어긋나는 상황이 원천적으로 불가능하다.

create policy "부모 소유자만" on public.assets
  for all to authenticated
  using (exists (
    select 1 from public.memories m
     where m.id = memory_id and m.user_id = (select auth.uid())
  ));

create policy "부모 소유자만" on public.emotions
  for all to authenticated
  using (exists (
    select 1 from public.memories m
     where m.id = memory_id and m.user_id = (select auth.uid())
  ));

create policy "부모 소유자만" on public.memory_entities
  for all to authenticated
  using (exists (
    select 1 from public.memories m
     where m.id = memory_id and m.user_id = (select auth.uid())
  ));

create policy "부모 소유자만" on public.relations
  for all to authenticated
  using (exists (
    select 1 from public.entities e
     where e.id = source_entity_id and e.user_id = (select auth.uid())
  ));

create policy "부모 소유자만" on public.difference_evidence
  for all to authenticated
  using (exists (
    select 1 from public.differences d
     where d.id = difference_id and d.user_id = (select auth.uid())
  ));

create policy "부모 소유자만" on public.diary_sources
  for all to authenticated
  using (exists (
    select 1 from public.diaries di
     where di.id = diary_id and di.user_id = (select auth.uid())
  ));

create policy "부모 소유자만" on public.diary_sections
  for all to authenticated
  using (exists (
    select 1 from public.diaries di
     where di.id = diary_id and di.user_id = (select auth.uid())
  ));

create policy "부모 소유자만" on public.weekly_report_highlights
  for all to authenticated
  using (exists (
    select 1 from public.weekly_reports w
     where w.id = report_id and w.user_id = (select auth.uid())
  ));

-- ── deletions — 읽기 전용 ──────────────────────────────────────
-- insert/update/delete 정책을 만들지 않는다. 정책이 없으면 차단된다.
-- 사용자가 steps_done을 위조하면 실제로 지워지지 않은 단계가
-- 완료로 표시되어 삭제 완전성이 무너진다.
-- 쓰기는 Route Handler와 워커가 service_role로 수행한다.
create policy "본인 삭제 진행만 조회" on public.deletions
  for select to authenticated
  using (user_id = (select auth.uid()));

-- 꼬리 질문은 일기에 딸린 섹션이다. 새 테이블을 만들지 않고
-- diary_sections에 종류를 하나 추가한다. difference_id로 근거 차이와 연결된다.
alter table public.diary_sections
  drop constraint diary_sections_section_type_check;
alter table public.diary_sections
  add constraint diary_sections_section_type_check
  check (section_type in ('오늘의한문장','본문','다른점','성취','질문'));

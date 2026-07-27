-- 되돌리면 기존 '질문' 행이 제약 위반이라 실패할 수 있다(의도).
alter table public.diary_sections
  drop constraint diary_sections_section_type_check;
alter table public.diary_sections
  add constraint diary_sections_section_type_check
  check (section_type in ('오늘의한문장','본문','다른점','성취'));

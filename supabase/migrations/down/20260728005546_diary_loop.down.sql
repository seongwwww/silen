alter table public.diaries
  drop column if exists regenerate_requested_at,
  drop column if exists tone_instruction;

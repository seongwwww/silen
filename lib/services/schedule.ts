export function formatDiaryHour(hour: number): string {
  if (hour === 0) return "자정";
  if (hour < 6) return `새벽 ${hour}시`;
  if (hour < 12) return `오전 ${hour}시`;
  if (hour === 12) return "낮 12시";
  if (hour < 18) return `오후 ${hour - 12}시`;
  return `밤 ${hour - 12}시`;
}

export function diaryScheduleMessage(hour: number): string {
  return `오늘 ${formatDiaryHour(hour)}에 묶어드릴게요`;
}

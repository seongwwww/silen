"""탐지 튜닝 상수 한곳. 골든 단위 테스트로 검증·튜닝한다(spec §3.3)."""

WINDOW_DAYS = 28          # freq_shift 관찰 창
STREAK_MIN = 2            # 연속 등장 최소 일수
REEMERGENCE_GAP_MIN = 7   # 재등장으로 볼 최소 공백(일)

FIRST_OCCURRENCE_CONFIDENCE = 1.0
STREAK_CONFIDENCE_SPAN = 6.0        # (streak_len-1)/SPAN, 7일=1.0
REEMERGENCE_CONFIDENCE_SPAN = float(WINDOW_DAYS)  # gap/WINDOW, 28일=1.0

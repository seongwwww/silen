"""차이 서술 골든셋 러너 (ai-evals.md: 환각·감정 승격·조언 혼입·근거 정합·단정 금지).

실 Gemini 원시 출력(raw)과 guardrail 통과분(kept)을 모두 검사한다. eval의 목적은
모델/프롬프트 회귀를 잡는 것 — guardrail은 사후에 걸러주므로 kept만 보면 항상
통과라 모델을 못 잰다. 그래서 조언/인과·엔티티명 정합은 raw에서 검사한다.

CI 게이트: 케이스 하나라도 실패하면 종료 코드 1.

실행 (실 Vertex, 비용 발생):
    $env:GOOGLE_GENAI_USE_VERTEXAI = "true"
    $env:GOOGLE_CLOUD_PROJECT = "..."
    $env:GOOGLE_CLOUD_LOCATION = "global"
    worker\\.venv\\Scripts\\python.exe evals/narration/run.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from silen_worker.narration.constants import FORBIDDEN_PHRASES
from silen_worker.narration.gemini import GeminiNarrator
from silen_worker.narration.service import NarrationInput, guardrail

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

FIXTURES_PATH = Path(__file__).parent / "fixtures.json"


def _facts(case: dict) -> NarrationInput:
    return NarrationInput(
        difference_id="eval", user_id="eval",
        entity_name=case["entity_name"], entity_type=case["entity_type"],
        detection_method=case["detection_method"], description=case["description"],
        date_iso=case["date_iso"],
    )


def run_case(case: dict, narrator: GeminiNarrator) -> tuple[bool, list[str]]:
    facts = _facts(case)
    raw = narrator.narrate(facts)
    failures: list[str] = []

    headline = (raw.get("headline") or "").strip()
    body = (raw.get("body") or "").strip()
    evidence = (raw.get("evidence_text") or "").strip()
    blob = f"{headline} {body} {evidence}"

    # 조언·인과·응원(모델 원시 출력 기준 — guardrail 사후 제거와 무관하게 모델을 잰다).
    hit = [p for p in FORBIDDEN_PHRASES if p in blob]
    if hit:
        failures.append(f"조언/인과/응원 표현 혼입: {hit}")

    # 엔티티명 정합.
    if case.get("must_include_entity") and case["entity_name"] not in f"{headline} {body}":
        failures.append(f"엔티티명 누락: '{case['entity_name']}'")

    # 빈 필드.
    if not headline or not body or not evidence:
        failures.append("빈 필드")

    # guardrail이 실제로 통과시키는지(정상 케이스는 저장 가능해야 한다).
    if not failures and guardrail(raw, facts) is None:
        failures.append("정상 출력인데 guardrail 탈락(길이 등 확인)")

    return (not failures, failures)


def main() -> int:
    fixtures = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
    narrator = GeminiNarrator()

    n_pass = 0
    print("=== 차이 서술 골든셋 결과 ===")
    for case in fixtures["cases"]:
        passed, failures = run_case(case, narrator)
        n_pass += 1 if passed else 0
        print(f"[{'PASS' if passed else 'FAIL'}] {case['name']}")
        for f in failures:
            print(f"    - {f}")

    total = len(fixtures["cases"])
    print(f"\n케이스: {n_pass}/{total} 통과")
    if n_pass < total:
        print("결과: FAIL — 게이트 실패, 종료 코드 1")
        return 1
    print("결과: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())

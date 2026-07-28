"""일기 생성 골든셋 러너 (ai-evals.md: 환각·감정 승격·조언·근거 정합·평범한날).

실 Gemini 원시 출력(raw)을 검사한다(모델/프롬프트 회귀 게이트).
자동 게이트: 조언·인과·응원(블록리스트)·근거 정합(used ⊆ 입력)·빈필드.
환각(입력 밖 사실)·감정 승격은 결정적 검사가 어려워 자동 게이트가 아니다 —
생성된 one_line·body를 케이스별로 출력해 사람이 검토한다(각 케이스 reason 참고).
guardrail 통과 여부도 부가 확인.

CI 게이트: 케이스 하나라도 실패하면 종료 코드 1.

실행 (실 Vertex, 비용):
    $env:GOOGLE_GENAI_USE_VERTEXAI = "true"
    $env:GOOGLE_CLOUD_PROJECT = "..."
    $env:GOOGLE_CLOUD_LOCATION = "global"
    worker\\.venv\\Scripts\\python.exe evals/diary/run.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from silen_worker.diary.constants import META_PHRASES
from silen_worker.diary.gemini import GeminiDiaryWriter
from silen_worker.diary.service import DiaryDifference, DiaryInput, DiaryMemory, guardrail
from silen_worker.narration.constants import FORBIDDEN_PHRASES

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

FIXTURES_PATH = Path(__file__).parent / "fixtures.json"


def _facts(
    case: dict,
    tone_preset: str = "담백",
    tone_instruction: str | None = None,
) -> DiaryInput:
    return DiaryInput(
        date_iso="2026-07-24", user_id="eval",
        memories=[DiaryMemory(mid, text) for mid, text in case["memories"]],
        differences=[DiaryDifference(did, h, name) for did, h, name in case["differences"]],
        tone_preset=tone_preset,
        tone_instruction=tone_instruction,
    )


def validate(raw: dict, facts: DiaryInput) -> list[str]:
    failures: list[str] = []

    one_line = str(raw.get("one_line") or "").strip()
    body = str(raw.get("body") or "").strip()
    blob = f"{one_line} {body}"

    hit = [p for p in FORBIDDEN_PHRASES if p in blob]
    if hit:
        failures.append(f"조언/인과/응원 혼입: {hit}")
    meta_hit = [p for p in META_PHRASES if p in blob]
    if meta_hit:
        failures.append(f"메타 서술 혼입: {meta_hit}")
    if blob.count("처음") > 1:
        failures.append(f"'처음' 반복 {blob.count('처음')}회 — 나열은 recap이 담당한다")
    if not one_line or not body:
        failures.append("빈 필드")

    used_mem = [str(x) for x in (raw.get("used_memory_ids") or [])]
    used_diff = [str(x) for x in (raw.get("used_difference_ids") or [])]
    input_mem = {m.memory_id for m in facts.memories}
    input_diff = {d.difference_id for d in facts.differences}
    if not set(used_mem) <= input_mem:
        failures.append(f"근거 정합 위반(메모): {used_mem} ⊄ {sorted(input_mem)}")
    if not set(used_diff) <= input_diff:
        failures.append(f"근거 정합 위반(차이): {used_diff} ⊄ {sorted(input_diff)}")

    if not failures and guardrail(raw, facts) is None:
        failures.append("정상 출력인데 guardrail 탈락(길이 등 확인)")

    return failures


def run_case(
    case: dict, writer: GeminiDiaryWriter
) -> tuple[bool, list[str], dict]:
    facts = _facts(case)
    raw = writer.write(facts)
    failures = validate(raw, facts)
    return (not failures, failures, raw)


def run_tone_case(
    case: dict, writer: GeminiDiaryWriter
) -> tuple[bool, list[str], dict[str, dict]]:
    raws: dict[str, dict] = {}
    failures: list[str] = []
    used_by_tone: dict[str, tuple[list[str], list[str]]] = {}
    variants = [("담백", "담백", None), ("따뜻", "따뜻", None)]
    variants.extend(
        (f"주문:{instruction}", "담백", instruction)
        for instruction in case.get("tone_instructions", [])
    )
    for label, tone, instruction in variants:
        facts = _facts(case, tone, instruction)
        raw = writer.write(facts)
        raws[label] = raw
        failures.extend(f"{label}: {failure}" for failure in validate(raw, facts))
        used_by_tone[label] = (
            sorted(str(x) for x in (raw.get("used_memory_ids") or [])),
            sorted(str(x) for x in (raw.get("used_difference_ids") or [])),
        )
    baseline = used_by_tone["담백"]
    for label, used in used_by_tone.items():
        if used != baseline:
            failures.append(
                "톤에 따라 메모·차이 근거 집합이 달라짐: "
                f"담백={baseline}, {label}={used}"
            )
    return (not failures, failures, raws)


def main() -> int:
    fixtures = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
    writer = GeminiDiaryWriter()

    n_pass = 0
    print("=== 일기 생성 골든셋 결과 ===")
    for case in fixtures["cases"]:
        if case.get("tone_invariance"):
            passed, failures, raws = run_tone_case(case, writer)
            n_pass += 1 if passed else 0
            print(f"[{'PASS' if passed else 'FAIL'}] {case['name']}  ({case.get('reason', '')})")
            for tone, raw in raws.items():
                print(f"    {tone} one_line: {str(raw.get('one_line') or '').strip()}")
                print(f"    {tone} body: {str(raw.get('body') or '').strip()}")
            for f in failures:
                print(f"    - {f}")
            continue

        passed, failures, raw = run_case(case, writer)
        n_pass += 1 if passed else 0
        print(f"[{'PASS' if passed else 'FAIL'}] {case['name']}  ({case.get('reason', '')})")
        print(f"    one_line: {str(raw.get('one_line') or '').strip()}")
        print(f"    body: {str(raw.get('body') or '').strip()}")
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

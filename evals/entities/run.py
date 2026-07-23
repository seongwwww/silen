"""엔티티 추출 골든셋 러너 (ai-evals.md 필수 케이스: 환각 유혹·빈 텍스트·조사·
보수적 병합·4종 분류).

실 Vertex Gemini(GeminiExtractor)로 추출한 원시 후보(candidates)와, 그것을
guardrail에 통과시킨 결과(kept)를 모두 검사한다.

핵심 설계: 이 eval의 목적은 **모델/프롬프트 회귀를 잡는 것**이다(ai-evals.md).
guardrail(worker/src/silen_worker/extraction/service.py)은 원문에 없는 name을
무조건 폐기하므로, kept만 검사하면 환각율은 항상 0%가 되어 모델을 전혀
측정하지 못한다("가드레일을 측정하는 것이지 모델을 측정하는 게 아니다").
그래서:

- **환각율(모델, 가드레일 전)** 은 candidates(원시, guardrail 이전)에 대해
  집계한다. 이것이 헤드라인 지표이며 0이 아닐 수 있다.
- **must_not_contain**(환각 유혹 폐기 확인)도 candidates(원시)를 검사한다.
  guardrail이 사후에 지워주더라도, 모델이 애초에 "지어내지 마라"를 어기고
  금지된 이름을 뱉었다면 그 자체로 실패해야 하기 때문이다.
- **must_contain / expected_count_max / distinct_names** 는 kept(최종 저장
  결과, 하류에서 실제로 쓰이는 값)에 대해 검사한다.

LLM 출력은 실행마다 달라질 수 있으므로 완전일치가 아니라 다음 견고한 부분
검사만 한다:

- must_contain: 특정 (type, name)이 kept에 반드시 있어야 한다.
- must_not_contain: 특정 name이 원시 candidates에 있으면 안 된다(모델이
  "지어내지 마라"를 어기고 확장/환각했는지 확인 — guardrail이 나중에
  지우는지 여부와 무관하게 검사).
- expected_count_max: kept 개수 상한(빈 날 억지 생성 방지).
- distinct_names: 여러 (type, name)이 서로 뭉개지지 않고 각각 kept에
  정확한 타입으로 남아야 한다(과병합 방지 + 오타입 오탐 방지).

추가로 guardrail 자체가 회귀했는지 독립적으로 재확인한다: kept의 모든
name이 실제로 원문 text의 부분 문자열인지 검사한다(항상 0%여야 함 —
0이 아니면 guardrail 자체의 버그).

CI 게이트: 케이스 하나라도 실패하면 종료 코드 1.

실행 (실 Vertex 호출, 비용 발생):
    $env:GOOGLE_GENAI_USE_VERTEXAI = "true"
    $env:GOOGLE_CLOUD_PROJECT = "..."
    $env:GOOGLE_CLOUD_LOCATION = "global"
    worker\\.venv\\Scripts\\python.exe evals/entities/run.py
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

from silen_worker.extraction.gemini import GeminiExtractor
from silen_worker.extraction.service import ExtractedEntity, guardrail, normalize_name

# 콘솔 코덱(cp949 등)에 상관없이 출력이 게이트를 죽이지 않게 UTF-8로 고정.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

FIXTURES_PATH = Path(__file__).parent / "fixtures.json"


@dataclass
class CaseResult:
    name: str
    passed: bool
    failures: list[str]
    candidates: list[dict]
    kept: list[ExtractedEntity]
    raw_hallucinated: list[dict]
    kept_hallucinated: list[ExtractedEntity]


def _raw_name(candidate: dict) -> str | None:
    """원시 후보에서 유효한(문자열·비공백) name을 뽑는다. 아니면 None."""
    name = candidate.get("name")
    if not isinstance(name, str):
        return None
    name = name.strip()
    return name or None


def _check_must_contain(kept: list[ExtractedEntity], expected: list[dict]) -> list[str]:
    failures = []
    for item in expected:
        etype, ename = item["type"], item["name"]
        norm = normalize_name(ename)
        if not any(e.type == etype and e.normalized_name == norm for e in kept):
            failures.append(f"must_contain 누락: {etype}/{ename}")
    return failures


def _check_must_not_contain(candidates: list[dict], forbidden: list[str]) -> list[str]:
    """모델의 원시 출력(가드레일 이전)에 금지된 이름이 있는지 검사한다.
    guardrail이 사후에 지워주는지 여부와 무관하게, 모델이 "지어내지 마라"를
    어겼다는 사실 자체를 잡아야 한다 — 그래서 kept가 아니라 candidates를 본다."""
    failures = []
    raw_named = [(c.get("type"), name, normalize_name(name)) for c in candidates if (name := _raw_name(c)) is not None]
    for bad in forbidden:
        norm = normalize_name(bad)
        hits = [(t, n) for (t, n, nn) in raw_named if nn == norm]
        if hits:
            failures.append(f"must_not_contain 위반: '{bad}' 가 모델 원시 출력(가드레일 전)에 존재 {hits}")
    return failures


def _check_expected_count_max(kept: list[ExtractedEntity], max_count: int) -> list[str]:
    if len(kept) > max_count:
        return [f"expected_count_max 위반: kept={len(kept)} > {max_count} ({kept})"]
    return []


def _check_distinct_names(kept: list[ExtractedEntity], expected: list[dict]) -> list[str]:
    """이름뿐 아니라 type도 맞아야 한다 — 다른 타입으로 잘못 추출된 동명 매치가
    통과하지 않도록(예: '민수'가 person이 아니라 place로 나와도 이름만 보면
    통과해버리는 오탐을 막는다)."""
    missing = []
    for item in expected:
        etype, ename = item["type"], item["name"]
        norm = normalize_name(ename)
        if not any(e.type == etype and e.normalized_name == norm for e in kept):
            missing.append(f"{etype}/{ename}")
    if missing:
        return [f"distinct_names 누락(과병합 또는 오타입 의심): {missing} (kept={kept})"]
    return []


def run_case(case: dict, extractor: GeminiExtractor) -> CaseResult:
    text = case["text"]
    candidates = extractor.extract(text)
    kept = guardrail(candidates, text)

    failures: list[str] = []
    if "must_contain" in case:
        failures += _check_must_contain(kept, case["must_contain"])
    if "must_not_contain" in case:
        failures += _check_must_not_contain(candidates, case["must_not_contain"])
    if "expected_count_max" in case:
        failures += _check_expected_count_max(kept, case["expected_count_max"])
    if "distinct_names" in case:
        failures += _check_distinct_names(kept, case["distinct_names"])

    # 모델 환각율 집계용: 가드레일 이전 원시 후보 중 원문에 없는 name들.
    # 이것이 실제 모델 환각(headline 지표) — kept 기준으로는 절대 0이 아니게
    # 잡을 수 없으므로 반드시 candidates에서 계산한다.
    raw_hallucinated = [
        c for c in candidates if (name := _raw_name(c)) is not None and name not in text
    ]

    # guardrail 자체 회귀 확인(참고용): kept를 통과한 name이 실제로 원문의
    # 부분 문자열인지 재확인한다. 정상이라면 언제나 빈 리스트여야 한다.
    kept_hallucinated = [e for e in kept if e.name not in text]
    if kept_hallucinated:
        failures.append(f"환각(가드레일 회귀 의심): {kept_hallucinated}")

    return CaseResult(
        name=case["name"],
        passed=not failures,
        failures=failures,
        candidates=candidates,
        kept=kept,
        raw_hallucinated=raw_hallucinated,
        kept_hallucinated=kept_hallucinated,
    )


def main() -> int:
    fixtures = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
    extractor = GeminiExtractor()

    results = [run_case(case, extractor) for case in fixtures["cases"]]

    total_raw_named = sum(
        sum(1 for c in r.candidates if _raw_name(c) is not None) for r in results
    )
    total_raw_hallucinated = sum(len(r.raw_hallucinated) for r in results)
    model_hallucination_rate = (
        (total_raw_hallucinated / total_raw_named) if total_raw_named else 0.0
    )

    total_kept = sum(len(r.kept) for r in results)
    total_kept_hallucinated = sum(len(r.kept_hallucinated) for r in results)
    guardrail_hallucination_rate = (
        (total_kept_hallucinated / total_kept) if total_kept else 0.0
    )

    print("=== 엔티티 추출 골든셋 결과 ===")
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        kept_repr = [(e.type, e.name) for e in r.kept]
        print(f"[{status}] {r.name} — kept={kept_repr}")
        if r.raw_hallucinated:
            print(f"    (참고) 원시 후보 중 원문에 없는 항목: {r.raw_hallucinated}")
        for f in r.failures:
            print(f"    - {f}")

    n_pass = sum(1 for r in results if r.passed)
    print()
    print(f"케이스: {n_pass}/{len(results)} 통과")
    print(
        "모델 환각율(가드레일 전): "
        f"{model_hallucination_rate:.1%} ({total_raw_hallucinated}/{total_raw_named})"
    )
    print(
        "  (참고) 가드레일이 위 환각 후보를 걸러낸 뒤 남은 kept 기준 환각율: "
        f"{guardrail_hallucination_rate:.1%} ({total_kept_hallucinated}/{total_kept}) "
        "— 항상 0%여야 하며, 0이 아니면 guardrail 자체의 회귀"
    )

    if n_pass < len(results):
        print("결과: FAIL — 게이트 실패, 종료 코드 1")
        return 1
    print("결과: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())

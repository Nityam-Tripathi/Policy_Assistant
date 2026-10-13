from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from policy_assistant import ask


def citation_key(citation: dict[str, str]) -> tuple[str, str]:
    return (citation["document"], citation["clause"])


def score_case(case: dict[str, Any]) -> dict[str, Any]:
    got = ask(case["question"], case.get("as_of_date"))
    expected_citations = {tuple(c) for c in case["expected_citations"]}
    got_citations = {citation_key(c) for c in got["citations"]}

    status_ok = got["status"] == case["expected_status"]
    citations_ok = expected_citations.issubset(got_citations)
    answer_norm = got["answer"].lower().replace(",", "")
    tokens_ok = all(token.lower().replace(",", "") in answer_norm for token in case.get("must_contain", []))
    has_expected_answer = bool(case.get("expected_answer"))

    passed = status_ok and citations_ok and tokens_ok and has_expected_answer

    return {
        "id": case["id"],
        "category": case.get("category", "standard"),
        "status": "PASS" if passed else "FAIL",
        "status_ok": status_ok,
        "citations_ok": citations_ok,
        "answer_ok": tokens_ok,
        "has_expected_answer": has_expected_answer,
        "expected_status": case["expected_status"],
        "got_status": got["status"],
        "answer": got["answer"],
        "expected_answer": case.get("expected_answer", ""),
    }


def main() -> int:
    cases = json.loads(Path("eval.json").read_text(encoding="utf-8"))
    rows = [score_case(case) for case in cases]

    print(f"{'ID':<28} {'CATEGORY':<28} {'RESULT':<8} {'STATUS':<8} {'CITES':<8} {'ANSWER':<8}")
    print("=" * 96)
    for row in rows:
        print(
            f"{row['id']:<28} {row['category']:<28} {row['status']:<8} "
            f"{str(row['status_ok']):<8} {str(row['citations_ok']):<8} {str(row['answer_ok']):<8}"
        )
        if row["status"] != "PASS":
            print(f"  FAILED: expected status={row['expected_status']}, got status={row['got_status']}")
            print(f"  Got citations match: {row['citations_ok']}")
            print(f"  Answer text check: {row['answer_ok']}")
            print(f"  Got answer: {row['answer']}")
            print(f"  Expected answer: {row['expected_answer']}")
            print("-" * 96)

    passed = sum(1 for row in rows if row["status"] == "PASS")
    print("=" * 96)
    print(f"Evaluation Summary: {passed}/{len(rows)} passed")
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())

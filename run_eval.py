from __future__ import annotations

import json
from pathlib import Path

from policy_assistant import ask


def citation_key(citation: dict) -> tuple[str, str]:
    return (citation["document"], citation["clause"])


def score_case(case: dict) -> dict:
    got = ask(case["question"], case.get("as_of_date"))
    expected_citations = {tuple(c) for c in case["expected_citations"]}
    got_citations = {citation_key(c) for c in got["citations"]}
    status_ok = got["status"] == case["expected_status"]
    citations_ok = expected_citations.issubset(got_citations)
    answer_ok = all(token.lower() in got["answer"].lower() for token in case.get("must_contain", []))
    return {
        "id": case["id"],
        "status": "PASS" if status_ok and citations_ok and answer_ok else "FAIL",
        "status_ok": status_ok,
        "citations_ok": citations_ok,
        "answer_ok": answer_ok,
        "expected_status": case["expected_status"],
        "got_status": got["status"],
        "answer": got["answer"],
    }


def main() -> int:
    cases = json.loads(Path("eval.json").read_text(encoding="utf-8"))
    rows = [score_case(case) for case in cases]
    print(f"{'ID':<8} {'RESULT':<6} {'STATUS':<6} {'CITES':<6} {'ANSWER':<6}")
    print("-" * 40)
    for row in rows:
        print(
            f"{row['id']:<8} {row['status']:<6} "
            f"{str(row['status_ok']):<6} {str(row['citations_ok']):<6} {str(row['answer_ok']):<6}"
        )
        if row["status"] != "PASS":
            print(f"  expected status: {row['expected_status']}; got: {row['got_status']}")
            print(f"  answer: {row['answer']}")
    passed = sum(1 for row in rows if row["status"] == "PASS")
    print("-" * 40)
    print(f"Score: {passed}/{len(rows)}")
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())


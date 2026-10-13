# AI-2 Policy Assistant: The Policy That Changed

A grounded, deterministic policy question-answering assistant over conflicting and superseded merchant policy documents.

---

## Quickstart

Requires Python 3.10+ with **no external dependencies** (zero API keys required, works fully offline).

### Run Test Suite

```bash
python run_eval.py
```

### Programmatic Usage

```python
from policy_assistant import ask

# 1. Standard question with date
result = ask(
    "A large merchant (above Rs.10 lakh monthly) receives a Rs.4,000 UPI payment. What MDR and GST do they pay?",
    "2026-08-15"
)
print(result)
# Returns:
# {
#   'status': 'CONFLICT_RESOLVED',
#   'answer': 'For a UPI payment of Rs.4000, MDR is Rs.20 and GST is Rs.3.60. Total fee including GST is Rs.23.60.',
#   'citations': [
#     {'document': 'policy_master_v1.md', 'clause': '2.2'},
#     {'document': 'circular_2026_08_amendment.md', 'clause': 'C'},
#     {'document': 'policy_master_v1.md', 'clause': '2.4'}
#   ],
#   'resolution': 'Circular C replaces the old single Rs.15 UPI cap with a Rs.25 cap for merchants above Rs.10 lakh from 01 Aug 2026.'
# }

# 2. Date in question text (as_of_date omitted)
print(ask("A merchant refunds a customer 3 hours after the sale on 5 Sep 2026. Do they get the MDR back?"))

# 3. Default date (defaults to 15 August 2026 per assignment specification)
print(ask("When does a small merchant receive UPI money?"))
```

---

## Return Contract

The `ask(question, as_of_date=None)` function returns a JSON-compatible dictionary:

- **`status`**:
  - `ANSWERED`: Question answered directly from active policy without conflict.
  - `CONFLICT_RESOLVED`: Policy conflict, circular amendment, or stale FAQ resolved with controlling authority.
  - `CANNOT_ANSWER`: Question falls outside policy coverage, is ungrounded, or omits necessary facts.
- **`answer`**: Clear, grounded natural language answer.
- **`citations`**: List of objects `{"document": "<filename>", "clause": "<clause>"}`. Never invents clause numbers.
- **`resolution`** *(optional)*: Explanation of how the conflict was resolved (present when status is `CONFLICT_RESOLVED`).

---

## Key Features & Policy Reasoning

1. **Date-Dependent Reasoning**:
   - Master Document effective 01 Jan 2026.
   - Circular Amendments A, B, C, E effective 01 Aug 2026.
   - Circular Amendment D (deleting Clause 3.3 24-hour refund fee reversal) effective 01 Sep 2026.
   - Flexible date parsing supports ISO `YYYY-MM-DD`, `DD Mon YYYY` (e.g. `15 Aug 2026`), and embedded in-question dates.
2. **Deterministic Arithmetic**:
   - Fees, caps, and 18% GST calculated using Python's `Decimal` module with `ROUND_HALF_UP` rounding.
3. **Traps & Cross-Reference Handling**:
   - **Q3 Limit Trap**: Large merchant receiving ₹1,50,000 exceeds standard UPI per-transaction limit (Clause 4.1). Identifies that only Capital Markets/Insurance merchants with enhanced KYC (Clauses 4.2 & 4.4) may accept this amount, calculating the capped fee of ₹25 + ₹4.50 GST = ₹29.50.
   - **Card MDR Grounding**: Policy Section 2 only defines UPI MDR. Queries asking for card MDR return `CANNOT_ANSWER` rather than guessing.
   - **Stale FAQ Override**: FAQ statement of "no fee cap" is identified as stale and overridden by Master Clause 2.3 and Circular C.
   - **Account Closure Prerequisite**: Highlights the mandatory 30-day written notice (Clause 5.1) alongside the 10-day settlement release (Clause 5.2).

---

## What Works & What Doesn't

### What Works
- Answers all required scenario questions (Q1–Q8) accurately and with real citations.
- Correctly switches outcomes based on effective dates (e.g. 20 Aug vs 5 Sep for refunds).
- Passes all 16 test cases in `eval.json`, including 6 adversarial edge cases.
- Operates 100% offline with zero dependencies.

### What Does Not Work
- Does not compute calendar payout dates for "10 working days" because bank holiday calendars are not in the documents.
- Does not infer volume when missing, nor does it resolve ambiguity in how monthly volume is calculated for borderline merchants.
- Does not track multi-account identity across split UPI transactions.

---

## Evaluation

- **`eval.json`**: 16 test cases containing `id`, `question`, `as_of_date`, `category`, `expected_status`, `expected_answer`, `expected_citations`, and `must_contain`.
- **`run_eval.py`**: Automated test harness validating status, citation subset matching, and token inclusion.

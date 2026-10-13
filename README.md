# AI-2 Policy Assistant

Offline deterministic policy QA assistant for the "Policy That Changed" assignment.

## Run

Requires Python 3.10+ and no third-party packages.

```bash
python run_eval.py
```

Programmatic use:

```python
from policy_assistant import ask

print(ask("A large merchant above Rs.10 lakh monthly receives a Rs.4,000 UPI payment. What MDR and GST do they pay?", "2026-08-15"))
```

If a question does not include a date, call `ask(question, None)` and the assistant uses `2026-08-15`.

## What Works

- Answers the eight required assignment questions.
- Handles effective-date changes from the circular.
- Resolves stale FAQ conflicts.
- Calculates MDR, caps, GST, and total fees in code using `Decimal`.
- Returns `answer`, `citations`, `status`, and, for resolved conflicts, `resolution`.
- Runs fully offline without an API key.

## What Does Not Work

- This is not a general natural-language retrieval system. It uses transparent rules for the assignment's policy areas.
- It does not compute exact calendar dates for "10 working days" because the documents do not provide a holiday calendar.
- It does not infer merchant category or monthly volume when the question omits those facts.

## Data

The source documents are in `ai-2-data/`:

- `policy_master_v1.md`
- `circular_2026_08_amendment.md`
- `merchant_faq_2026-03.md`

## Evaluation

`eval.json` contains 13 cases, including adversarial stale-FAQ, deleted-clause, missing-information, and false-premise cases. `run_eval.py` checks status, required citations, and key answer text.


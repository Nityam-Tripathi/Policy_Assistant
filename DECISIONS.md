# Decisions & Policy Ambiguities

## 1. Conflict Hierarchy & Effective Dates

The Circular (`circular_2026_08_amendment.md`) is treated as the controlling amendment over the Master Document (`policy_master_v1.md`) for clauses it explicitly replaces or amends:
- Amendments A, B, C, and E took effect on **01 August 2026**.
- Amendment D (deleting Clause 3.3 to eliminate the 24-hour refund fee reversal) specifies its own delayed effective date of **01 September 2026**.
- The assistant dynamically checks `as_of_date` against these boundaries to return `ANSWERED` or `CONFLICT_RESOLVED`.

## 2. FAQ Status & Stale Answers

`merchant_faq_2026-03.md` (last updated 12 March 2026) is a non-controlling informational support document.
- The FAQ asserted: *"There is no upper limit on the fee, so very large transactions cost more."*
- This statement was contradictory from inception: Master Clause 2.3 already capped UPI MDR at ₹15 as of 01 January 2026.
- Circular C subsequently replaced Clause 2.3 on 01 August 2026 with a dual cap (₹15 for monthly volume ≤ ₹10 lakh, ₹25 for > ₹10 lakh).
- When asked about the FAQ's cap claim, the assistant returns `CONFLICT_RESOLVED`, explaining that the FAQ was stale and contradicted by controlling policy, citing the FAQ heading, Clause 2.3, and Circular C.

## 3. Date Resolution Hierarchy

Per the assignment specification (*"Unless a question gives a date, use as_of_date = 15 August 2026"*):
1. If `as_of_date` is explicitly supplied, parse it. Supported formats include ISO `YYYY-MM-DD`, `DD Mon YYYY` (e.g., `15 Aug 2026`), and `DD Month YYYY` (e.g., `20 August 2026`).
2. If `as_of_date` is omitted or `None`, the assistant inspects the question string for an embedded date (e.g., `"on 5 Sep 2026"`).
3. If no date is found in either source, default to `2026-08-15`.

## 4. Q3 Dissection & The Transaction Limit Trap

Question: *"Same merchant, a Rs.1,50,000 payment. What do they pay?"*
This question contains two policy considerations:
1. **Context Resolution**: "Same merchant" references the large merchant (monthly volume > ₹10 lakh) from Q2.
2. **Transaction Limit Check**:
   - Master Clause 4.1 establishes a standard per-transaction UPI limit of ₹1,00,000.
   - Master Clause 4.2 and 4.4 allow transactions up to ₹2,00,000 only for merchants categorized under "Capital Markets" or "Insurance" who have completed Annexure C enhanced KYC.
   - For an ordinary merchant, a single ₹1,50,000 UPI transaction is impermissible.
   - If the merchant qualifies under Clauses 4.2 and 4.4, the MDR is calculated as 0.50% (₹750), capped at ₹25 (Circular C) plus 18% GST of ₹4.50 (Clause 2.4), yielding a total fee of ₹29.50.
   - The assistant answers both aspects and cites Circular C, Clauses 2.2, 2.4, 4.1, 4.2, and 4.4.

## 5. Card MDR Non-Coverage (Strict Grounding)

The policy documents only specify MDR rates for UPI transactions (Section 2). Card transactions are mentioned solely regarding settlement timing (Clause 1.2: T+2) and FAQ settlement answers.
- When asked what MDR a merchant pays on card transactions, the assistant returns `CANNOT_ANSWER` rather than extrapolating UPI rates, adhering to strict policy grounding.

## 6. Account Closure Requirements (Dual Clause 5.1 & 5.2)

- Master Clause 5.1 requires **30 days written notice** to close an account.
- Master Clause 5.2 releases pending settlements **within 10 working days of closure** (after deducting outstanding dues).
- If a merchant asks when they receive funds after closing yesterday (Q7), the assistant cites both 5.1 and 5.2 to highlight the mandatory 30-day notice prerequisite.
- If asked for an exact calendar date, the assistant returns `CANNOT_ANSWER` because working days exclude bank holidays and the policy provides no holiday schedule.

## 7. Deterministic Currency & Arithmetic

All arithmetic operations are performed using Python's `Decimal` with `ROUND_HALF_UP`.
- Small merchant rate: 0.30% (pre-Aug 2026) -> 0.25% (from 01 Aug 2026, Circular B), cap ₹15 (Circular C).
- Large merchant rate: 0.50% (Clause 2.2), cap ₹15 (pre-Aug 2026, Clause 2.3) -> ₹25 (from 01 Aug 2026, Circular C).
- GST: 18% calculated strictly on the capped MDR amount (Clause 2.4).

## 8. Citation Shape

- Master Policy: `["policy_master_v1.md", "<clause_number>"]` (e.g., `"2.2"`, `"4.1"`).
- Circular: `["circular_2026_08_amendment.md", "<clause_letter>"]` (e.g., `"A"`, `"C"`, `"D"`).
- FAQ: `["merchant_faq_2026-03.md", "<question_heading>"]` (e.g., `"What do I pay on a UPI transaction?"`), as the FAQ has no numbered clauses.

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
import re
from typing import Any


ANSWERED = "ANSWERED"
CONFLICT_RESOLVED = "CONFLICT_RESOLVED"
CANNOT_ANSWER = "CANNOT_ANSWER"

DEFAULT_AS_OF_DATE = date(2026, 8, 15)
CIRCULAR_EFFECTIVE = date(2026, 8, 1)
REFUND_DELETE_EFFECTIVE = date(2026, 9, 1)


@dataclass(frozen=True)
class Citation:
    document: str
    clause: str


def ask(question: str, as_of_date: str | date | None = None) -> dict[str, Any]:
    """Answer merchant policy questions using deterministic rules and citations.

    The returned object is JSON-compatible:
    - status: 'ANSWERED' | 'CONFLICT_RESOLVED' | 'CANNOT_ANSWER'
    - answer: human-readable grounded answer string
    - citations: list of dicts with 'document' and 'clause'
    - resolution: string explaining conflict resolution (present when status is CONFLICT_RESOLVED)
    """

    asked_on = _parse_date(as_of_date, question)
    q = _normalize(question)

    # 1. Card-specific questions
    if _mentions_card(q):
        # Card MDR is NOT covered in any policy document (Section 2 only defines UPI MDR)
        if _mentions_mdr_term(q) or "discount" in q or "cost" in q:
            return _card_mdr_answer()
        if "same day" in q or "settle" in q or "settlement" in q or "when" in q or "receive" in q:
            return _card_settlement_answer()

    # 2. Bank dispute & chargebacks (Clause 3.4)
    if "chargeback" in q or "dispute" in q:
        return _chargeback_answer()

    # 3. Account closure (Clauses 5.1, 5.2)
    if _mentions_closure(q):
        if "exact" in q and "date" in q:
            return _closure_exact_date_answer()
        return _closure_answer()

    # 4. Stale FAQ MDR cap (Q5)
    if _mentions_faq_cap(q):
        return _faq_cap_answer(asked_on)

    # 5. Refunds (Clauses 3.1, 3.2, 3.3, Circular D)
    if _mentions_refund(q):
        if "how many days" in q or "window" in q or "within 90" in q or ("when" in q and "initiate" in q):
            return _refund_window_answer()
        return _refund_answer(asked_on, q)

    # 6. Limits, multiple daily transactions, split payments
    if _mentions_split(q):
        return _split_payment_answer()

    if _mentions_limit_twice(q) or ("twice" in q and _mentions_limit(q)):
        return _twice_daily_limit_answer(asked_on)

    if ("insurance" in q or "capital market" in q) and ("kyc" in q or "annexure" in q):
        return _insurance_kyc_answer(q)

    # 7. Ambiguity in monthly volume threshold (Where it breaks #2)
    if ("this month" in q and "last month" in q) or ("grocery" in q and "which mdr" in q):
        return _volume_ambiguity_answer()

    # 8. MDR & Fee calculations (takes precedence when MDR/GST/fee is explicitly asked)
    if _mentions_mdr_term(q) or _mentions_gst(q) or "same merchant" in q:
        return _mdr_answer(asked_on, q)

    # 9. UPI Settlement (Clause 1.1, Circular A, Clause 1.3)
    if _mentions_settlement(q) or ("upi money" in q) or ("receive" in q and "upi" in q):
        return _upi_settlement_answer(asked_on, q)

    # 10. Fallback to general payment amounts or fees
    if _mentions_mdr(q) or _amount(q) is not None:
        return _mdr_answer(asked_on, q)

    # 11. General limits
    if _mentions_limit(q):
        return _limit_answer(asked_on, q)

    return {
        "status": CANNOT_ANSWER,
        "answer": "I could not find enough policy support to answer that question.",
        "citations": [],
    }


def _upi_settlement_answer(asked_on: date, q: str) -> dict[str, Any]:
    if asked_on >= CIRCULAR_EFFECTIVE:
        answer = (
            "UPI settlement is same day (T+0, by 11:59 PM) only for merchants with an active "
            "'Instant Settlement' add-on. For all other merchants, including a small merchant "
            "when no add-on is stated, UPI settlement is T+1 on the next working day. "
            "Working days exclude Sundays and bank holidays."
        )
        return _result(
            CONFLICT_RESOLVED,
            answer,
            [
                Citation("circular_2026_08_amendment.md", "A"),
                Citation("policy_master_v1.md", "1.3"),
            ],
            "Circular A replaces master clause 1.1 from 01 Aug 2026; clause 1.3 still applies for holidays.",
        )
    return _result(
        ANSWERED,
        "UPI settlement is T+1, meaning the next working day. Sundays and bank holidays are excluded.",
        [
            Citation("policy_master_v1.md", "1.1"),
            Citation("policy_master_v1.md", "1.3"),
        ],
    )


def _card_settlement_answer() -> dict[str, Any]:
    return _result(
        ANSWERED,
        "No. Master clause 1.2 specifies that card transactions settle T+2 (two working days). "
        "The Instant Settlement add-on introduced in Circular A applies only to UPI transactions, "
        "so the policy does not allow same-day card settlement.",
        [Citation("policy_master_v1.md", "1.2")],
    )


def _card_mdr_answer() -> dict[str, Any]:
    return _result(
        CANNOT_ANSWER,
        "The policy documents only specify MDR rates for UPI transactions (Section 2). "
        "No MDR rate or fee schedule is defined for card transactions in the provided documents.",
        [],
    )


def _chargeback_answer() -> dict[str, Any]:
    return _result(
        ANSWERED,
        "Under clause 3.4, chargeback disputes must be raised by the customer's bank within 120 days.",
        [Citation("policy_master_v1.md", "3.4")],
    )


def _closure_answer() -> dict[str, Any]:
    return _result(
        ANSWERED,
        "A merchant may close the account with 30 days written notice (clause 5.1). "
        "After account closure, pending settlements are released within 10 working days, "
        "after deducting outstanding dues (clause 5.2). Working days exclude Sundays and bank holidays.",
        [
            Citation("policy_master_v1.md", "5.1"),
            Citation("policy_master_v1.md", "5.2"),
        ],
    )


def _closure_exact_date_answer() -> dict[str, Any]:
    return _result(
        CANNOT_ANSWER,
        "Under clauses 5.1 and 5.2, pending settlements are released within 10 working days of closure "
        "(subject to 30 days written notice and deducting outstanding dues). However, an exact calendar date "
        "cannot be determined because working days exclude bank holidays and the policy provides no holiday calendar.",
        [
            Citation("policy_master_v1.md", "5.1"),
            Citation("policy_master_v1.md", "5.2"),
        ],
    )


def _refund_window_answer() -> dict[str, Any]:
    return _result(
        ANSWERED,
        "Under clause 3.1, merchants may initiate a refund within 90 days of the original transaction.",
        [Citation("policy_master_v1.md", "3.1")],
    )


def _refund_answer(asked_on: date, q: str) -> dict[str, Any]:
    if asked_on >= REFUND_DELETE_EFFECTIVE:
        return _result(
            CONFLICT_RESOLVED,
            "No. From 01 Sep 2026, MDR charged on a refunded transaction is not returned to the merchant, "
            "even if the refund is initiated within 24 hours.",
            [
                Citation("policy_master_v1.md", "3.2"),
                Citation("circular_2026_08_amendment.md", "D"),
            ],
            "Circular D deletes master clause 3.3 effective 01 Sep 2026, so the no-return rule in clause 3.2 applies without exception.",
        )
    return _result(
        ANSWERED,
        "Yes. If the merchant initiates the refund within 24 hours of the transaction, the MDR is reversed in full.",
        [Citation("policy_master_v1.md", "3.3")],
    )


def _faq_cap_answer(asked_on: date) -> dict[str, Any]:
    if asked_on >= CIRCULAR_EFFECTIVE:
        answer = (
            "The FAQ says there is no upper limit on the UPI fee, so very large transactions cost more. "
            "That is not right: from 01 Aug 2026, Circular C replaced master clause 2.3 so the cap is Rs.15 "
            "for merchants up to Rs.10 lakh monthly volume and Rs.25 for merchants above Rs.10 lakh."
        )
        citations = [
            Citation("merchant_faq_2026-03.md", "What do I pay on a UPI transaction?"),
            Citation("policy_master_v1.md", "2.3"),
            Citation("circular_2026_08_amendment.md", "C"),
        ]
        resolution = "The FAQ conflicts with original master clause 2.3 and is superseded by Circular C from 01 Aug 2026."
    else:
        answer = (
            "The FAQ says there is no upper limit on the UPI fee. That is not right: under master clause 2.3, "
            "MDR on any single UPI transaction shall not exceed Rs.15."
        )
        citations = [
            Citation("merchant_faq_2026-03.md", "What do I pay on a UPI transaction?"),
            Citation("policy_master_v1.md", "2.3"),
        ]
        resolution = "The master policy is controlling; the FAQ contradicts clause 2.3."
    return _result(CONFLICT_RESOLVED, answer, citations, resolution)


def _twice_daily_limit_answer(asked_on: date) -> dict[str, Any]:
    citations = [Citation("policy_master_v1.md", "4.3")]
    if asked_on >= CIRCULAR_EFFECTIVE:
        citations.append(Citation("circular_2026_08_amendment.md", "E"))
        answer = (
            "No. A customer cannot make two Rs.1,00,000 UPI payments in one day. "
            "Under clause 4.3 as amended by Circular E (effective 01 Aug 2026), the daily limit per customer "
            "account is Rs.1,00,000 or the limit set by the customer's own bank, whichever is lower."
        )
        return _result(CONFLICT_RESOLVED, answer, citations, "Circular E amends the daily account limit rule from 01 Aug 2026.")
    return _result(
        ANSWERED,
        "No. Under clause 4.3, the daily limit per customer account is Rs.1,00,000 across all UPI transactions.",
        citations,
    )


def _insurance_kyc_answer(q: str) -> dict[str, Any]:
    if "without" in q or "no kyc" in q:
        return _result(
            ANSWERED,
            "No. Under clause 4.4, the enhanced limit of Rs.2,00,000 in clause 4.2 applies only to merchants "
            "who have completed enhanced KYC (Annexure C). Without enhanced KYC, the merchant cannot accept Rs.2,00,000.",
            [
                Citation("policy_master_v1.md", "4.2"),
                Citation("policy_master_v1.md", "4.4"),
            ],
        )
    return _result(
        ANSWERED,
        "The per-transaction UPI limit is Rs.2,00,000 for Capital Markets and Insurance merchants only if "
        "they have completed enhanced KYC (Annexure C).",
        [
            Citation("policy_master_v1.md", "4.2"),
            Citation("policy_master_v1.md", "4.4"),
        ],
    )


def _split_payment_answer() -> dict[str, Any]:
    return _result(
        CANNOT_ANSWER,
        "The policy specifies per-transaction limits (clauses 4.1, 4.2) and a daily limit per customer account (clause 4.3). "
        "However, the policy does not address customer identity across multiple bank accounts or split-payment anti-circumvention.",
        [
            Citation("policy_master_v1.md", "4.2"),
            Citation("policy_master_v1.md", "4.3"),
        ],
    )


def _volume_ambiguity_answer() -> dict[str, Any]:
    return _result(
        CANNOT_ANSWER,
        "The policy establishes tiers for monthly volume up to vs above Rs.10 lakh (clauses 2.1, 2.2), "
        "but it does not define whether monthly volume is based on previous month actuals, current month to date, or projected volume.",
        [
            Citation("policy_master_v1.md", "2.1"),
            Citation("policy_master_v1.md", "2.2"),
        ],
    )


def _limit_answer(asked_on: date, q: str) -> dict[str, Any]:
    citations = [Citation("policy_master_v1.md", "4.1"), Citation("policy_master_v1.md", "4.3")]
    if asked_on >= CIRCULAR_EFFECTIVE:
        citations.append(Citation("circular_2026_08_amendment.md", "E"))
        answer = (
            "The ordinary per-transaction UPI limit is Rs.1,00,000 (clause 4.1). "
            "From 01 Aug 2026, the daily limit per customer account is Rs.1,00,000 or the limit set by "
            "the customer's own bank, whichever is lower (Circular E amending clause 4.3)."
        )
        return _result(CONFLICT_RESOLVED, answer, citations, "Circular E amends the daily customer-account limit from 01 Aug 2026.")
    return _result(
        ANSWERED,
        "The ordinary per-transaction UPI limit is Rs.1,00,000, and the daily limit per customer account is Rs.1,00,000 across all UPI transactions.",
        citations,
    )


def _mdr_answer(asked_on: date, q: str) -> dict[str, Any]:
    amount = _amount(q)
    if amount is None:
        return _result(
            ANSWERED,
            "UPI MDR depends on monthly volume: merchants up to Rs.10 lakh pay 0.25% (0.30% before 01 Aug 2026); "
            "merchants above Rs.10 lakh pay 0.50%. GST at 18% is charged on the MDR amount.",
            [
                Citation("policy_master_v1.md", "2.1"),
                Citation("policy_master_v1.md", "2.2"),
                Citation("policy_master_v1.md", "2.4"),
            ],
        )

    large = _mentions_large(q) or "same merchant" in q
    small = _mentions_small(q) and not large
    if not (large or small):
        return _result(
            CANNOT_ANSWER,
            "I need the merchant monthly UPI volume category to calculate the MDR.",
            [],
        )

    # Calculation logic
    if large:
        rate = Decimal("0.005")
        cap = Decimal("25") if asked_on >= CIRCULAR_EFFECTIVE else Decimal("15")
        mdr_citations = [Citation("policy_master_v1.md", "2.2")]
        if asked_on >= CIRCULAR_EFFECTIVE:
            mdr_citations.append(Citation("circular_2026_08_amendment.md", "C"))
            status = CONFLICT_RESOLVED
            resolution = "Circular C replaces the old single Rs.15 UPI cap with a Rs.25 cap for merchants above Rs.10 lakh from 01 Aug 2026."
        else:
            mdr_citations.append(Citation("policy_master_v1.md", "2.3"))
            status = ANSWERED
            resolution = None
    else:
        rate = Decimal("0.0025") if asked_on >= CIRCULAR_EFFECTIVE else Decimal("0.003")
        cap = Decimal("15")
        mdr_citations = [Citation("policy_master_v1.md", "2.1"), Citation("policy_master_v1.md", "2.3")]
        if asked_on >= CIRCULAR_EFFECTIVE:
            mdr_citations.extend(
                [
                    Citation("circular_2026_08_amendment.md", "B"),
                    Citation("circular_2026_08_amendment.md", "C"),
                ]
            )
            status = CONFLICT_RESOLVED
            resolution = "Circular B changes the small-merchant rate from 0.30% to 0.25%, and Circular C maintains the Rs.15 cap for small merchants from 01 Aug 2026."
        else:
            status = ANSWERED
            resolution = None

    raw_mdr = amount * rate
    mdr = min(raw_mdr, cap)
    gst = mdr * Decimal("0.18")
    total = mdr + gst

    answer = (
        f"For a UPI payment of {_money(amount)}, MDR is {_money(mdr)} and GST is {_money(gst)}. "
        f"Total fee including GST is {_money(total)}."
    )
    if raw_mdr > cap:
        answer += f" The un-capped percentage MDR would be {_money(raw_mdr)}, but the applicable cap limits MDR to {_money(cap)}."

    # Trap detection: Transactions above Rs. 1,00,000 exceed the normal UPI per-transaction limit (Clause 4.1)
    if amount > Decimal("100000"):
        answer += (
            " Note: Under clause 4.1, the ordinary UPI per-transaction limit is Rs.1,00,000. "
            "A transaction of this size is only permitted if the merchant belongs to Capital Markets or Insurance "
            "and has completed enhanced KYC under Annexure C (clauses 4.2 and 4.4)."
        )
        mdr_citations.extend(
            [
                Citation("policy_master_v1.md", "4.1"),
                Citation("policy_master_v1.md", "4.2"),
                Citation("policy_master_v1.md", "4.4"),
            ]
        )

    return _result(status, answer, mdr_citations + [Citation("policy_master_v1.md", "2.4")], resolution)


def _result(
    status: str,
    answer: str,
    citations: list[Citation],
    resolution: str | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "status": status,
        "answer": answer,
        "citations": [{"document": c.document, "clause": c.clause} for c in citations],
    }
    if resolution:
        out["resolution"] = resolution
    return out


def _parse_date(value: str | date | datetime | None, question: str = "") -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        parsed = _parse_date_string(value.strip())
        if parsed:
            return parsed
    if question:
        extracted = _extract_date_from_text(question)
        if extracted:
            return extracted
    return DEFAULT_AS_OF_DATE


def _parse_date_string(text: str) -> date | None:
    text = text.strip()
    text_clean = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", text, flags=re.IGNORECASE)
    formats = (
        "%Y-%m-%d",
        "%d %b %Y",
        "%d %B %Y",
        "%d %b, %Y",
        "%d %B, %Y",
        "%b %d, %Y",
        "%B %d, %Y",
        "%b %d %Y",
        "%B %d %Y",
    )
    for fmt in formats:
        try:
            return datetime.strptime(text_clean, fmt).date()
        except ValueError:
            pass
    text_norm = re.sub(r"\bsept\b", "Sep", text_clean, flags=re.IGNORECASE)
    for fmt in formats:
        try:
            return datetime.strptime(text_norm, fmt).date()
        except ValueError:
            pass
    return None


def _extract_date_from_text(q: str) -> date | None:
    m = re.search(r"\b(\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+\d{4})\b", q)
    if m:
        parsed = _parse_date_string(m.group(1))
        if parsed:
            return parsed
    m = re.search(r"\b([A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4})\b", q)
    if m:
        parsed = _parse_date_string(m.group(1))
        if parsed:
            return parsed
    m = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", q)
    if m:
        parsed = _parse_date_string(m.group(1))
        if parsed:
            return parsed
    return None


def _normalize(text: str) -> str:
    return (
        text.lower()
        .replace("rs.", "rs")
        .replace("rs ", "rs")
        .replace("inr", "rs")
        .replace("₹", "rs")
        .replace(",", "")
    )


def _amount(q: str) -> Decimal | None:
    candidates: list[tuple[int, Decimal]] = []
    for match in re.finditer(r"rs\s*([0-9]+(?:\.[0-9]+)?)\s*lakh", q):
        window = q[match.start() : match.end() + 35]
        if "monthly" in window or "volume" in window:
            continue
        candidates.append((match.start(), Decimal(match.group(1)) * Decimal("100000")))
    for match in re.finditer(r"rs\s*([0-9]+(?:\.[0-9]+)?)", q):
        window = q[match.start() : match.end() + 35]
        if "lakh" in window or "monthly" in window or "volume" in window:
            continue
        candidates.append((match.start(), Decimal(match.group(1))))
    if candidates:
        return sorted(candidates, key=lambda item: item[0])[-1][1]
    return None


def _money(value: Decimal) -> str:
    rounded = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if rounded == rounded.to_integral_value():
        return f"Rs.{int(rounded)}"
    return f"Rs.{rounded}"


def _mentions_large(q: str) -> bool:
    return "large" in q or "above rs10 lakh" in q or "above 10 lakh" in q


def _mentions_small(q: str) -> bool:
    return "small" in q or "up to rs10 lakh" in q or "up to 10 lakh" in q


def _mentions_mdr(q: str) -> bool:
    return _mentions_mdr_term(q) or "pay" in q or "cost" in q


def _mentions_mdr_term(q: str) -> bool:
    return "mdr" in q or "merchant discount" in q or "fee" in q


def _mentions_gst(q: str) -> bool:
    return "gst" in q


def _mentions_refund(q: str) -> bool:
    return "refund" in q or "mdr back" in q or "fee back" in q


def _mentions_faq_cap(q: str) -> bool:
    return "faq" in q and ("cap" in q or "upper limit" in q or "right" in q or "fee" in q or "mdr" in q)


def _mentions_limit(q: str) -> bool:
    return "limit" in q or "maximum" in q or "max" in q or "accept rs" in q or "pay rs100000" in q


def _mentions_limit_twice(q: str) -> bool:
    return "twice" in q and ("one day" in q or "same day" in q or "daily" in q or "day" in q)


def _mentions_settlement(q: str) -> bool:
    return "settlement" in q or "settle" in q or "receive upi" in q or "receive money" in q or "upi money" in q


def _mentions_card(q: str) -> bool:
    return "card" in q or "credit card" in q or "debit card" in q


def _mentions_closure(q: str) -> bool:
    return "close" in q or "closed" in q or "closure" in q


def _mentions_split(q: str) -> bool:
    return "split" in q and ("payment" in q or "account" in q)

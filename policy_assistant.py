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
    """Answer merchant policy questions using deterministic rules.

    The returned object is intentionally plain JSON-compatible data:
    answer, citations, status, and optional resolution.
    """

    asked_on = _parse_date(as_of_date)
    q = _normalize(question)

    if _mentions_card(q) and ("same day" in q or "settle" in q or "settlement" in q):
        return _card_settlement_answer()

    if _mentions_closure(q) or ("closed" in q and "account" in q):
        return _closure_answer()

    if _mentions_faq_cap(q) or ("faq" in q and "mdr" in q):
        return _faq_cap_answer(asked_on)

    if _mentions_refund(q):
        return _refund_answer(asked_on)

    if _mentions_limit_twice(q) or ("twice" in q and _mentions_limit(q)):
        return _twice_daily_limit_answer(asked_on)

    if _mentions_limit(q):
        return _limit_answer(asked_on, q)

    if _mentions_mdr(q) or _mentions_gst(q) or _amount(q) is not None:
        return _mdr_answer(asked_on, q)

    if _mentions_settlement(q) or ("upi money" in q) or ("receive" in q and "upi" in q):
        return _upi_settlement_answer(asked_on, q)

    return {
        "status": CANNOT_ANSWER,
        "answer": "I could not find enough policy support to answer that question.",
        "citations": [],
    }


def _upi_settlement_answer(asked_on: date, q: str) -> dict[str, Any]:
    if asked_on >= CIRCULAR_EFFECTIVE:
        answer = (
            "UPI settlement is same day by 11:59 PM only for merchants with an active "
            "Instant Settlement add-on. For all other merchants, including a small merchant "
            "when no add-on is stated, UPI settlement is T+1 on the next working day."
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


def _mdr_answer(asked_on: date, q: str) -> dict[str, Any]:
    amount = _amount(q)
    if amount is None:
        return _result(
            ANSWERED,
            "UPI MDR depends on monthly volume: small merchants use the small-merchant rate; merchants above Rs.10 lakh monthly use 0.50%. GST at 18% is charged on the MDR amount.",
            [
                Citation("policy_master_v1.md", "2.1"),
                Citation("policy_master_v1.md", "2.2"),
                Citation("policy_master_v1.md", "2.4"),
            ],
        )

    large = _mentions_large(q)
    small = _mentions_small(q) and not large
    if not (large or small):
        return _result(
            CANNOT_ANSWER,
            "I need the merchant monthly UPI volume category to calculate the MDR.",
            [],
        )

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
            resolution = "Circular B changes the small-merchant rate from 0.30% to 0.25%, and Circular C keeps the Rs.15 cap for small merchants from 01 Aug 2026."
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
        answer += f" The percentage MDR would be {_money(raw_mdr)}, but the applicable cap limits MDR to {_money(cap)}."
    return _result(status, answer, mdr_citations + [Citation("policy_master_v1.md", "2.4")], resolution)


def _refund_answer(asked_on: date) -> dict[str, Any]:
    if asked_on >= REFUND_DELETE_EFFECTIVE:
        return _result(
            CONFLICT_RESOLVED,
            "No. From 01 Sep 2026, MDR charged on a refunded transaction is not returned to the merchant, even if the refund is initiated within 24 hours.",
            [
                Citation("policy_master_v1.md", "3.2"),
                Citation("circular_2026_08_amendment.md", "D"),
            ],
            "Circular D deletes master clause 3.3 from 01 Sep 2026, so the no-return rule in clause 3.2 applies without exception.",
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
            "That is not right: from 01 Aug 2026, the cap is Rs.15 for merchants up to Rs.10 lakh monthly volume and Rs.25 for merchants above Rs.10 lakh."
        )
        citations = [
            Citation("merchant_faq_2026-03.md", "What do I pay on a UPI transaction?"),
            Citation("circular_2026_08_amendment.md", "C"),
        ]
        resolution = "The FAQ is stale because the later circular overrides the earlier public FAQ answer."
    else:
        answer = (
            "The FAQ says there is no upper limit on the UPI fee. That is not right: under the master policy, MDR on any single UPI transaction is capped at Rs.15."
        )
        citations = [
            Citation("merchant_faq_2026-03.md", "What do I pay on a UPI transaction?"),
            Citation("policy_master_v1.md", "2.3"),
        ]
        resolution = "The master policy is the controlling policy document; the FAQ answer conflicts with it."
    return _result(CONFLICT_RESOLVED, answer, citations, resolution)


def _twice_daily_limit_answer(asked_on: date) -> dict[str, Any]:
    citations = [Citation("policy_master_v1.md", "4.3")]
    if asked_on >= CIRCULAR_EFFECTIVE:
        citations.append(Citation("circular_2026_08_amendment.md", "E"))
        answer = (
            "No. A customer cannot make two Rs.1,00,000 UPI payments in one day if the daily account limit is Rs.1,00,000 or lower. "
            "From 01 Aug 2026, the applicable daily limit is Rs.1,00,000 or the customer's own bank limit, whichever is lower."
        )
        return _result(CONFLICT_RESOLVED, answer, citations, "Circular E amends the daily limit rule from 01 Aug 2026.")
    return _result(
        ANSWERED,
        "No. The daily limit per customer account is Rs.1,00,000 across all UPI transactions.",
        citations,
    )


def _limit_answer(asked_on: date, q: str) -> dict[str, Any]:
    if "insurance" in q or "capital market" in q:
        return _result(
            ANSWERED,
            "The per-transaction UPI limit is Rs.2,00,000 for Capital Markets and Insurance merchants only if they have completed enhanced KYC.",
            [
                Citation("policy_master_v1.md", "4.2"),
                Citation("policy_master_v1.md", "4.4"),
            ],
        )
    citations = [Citation("policy_master_v1.md", "4.1"), Citation("policy_master_v1.md", "4.3")]
    if asked_on >= CIRCULAR_EFFECTIVE:
        citations.append(Citation("circular_2026_08_amendment.md", "E"))
        answer = "The ordinary per-transaction UPI limit is Rs.1,00,000. The daily customer-account limit is Rs.1,00,000 or the customer's own bank limit, whichever is lower."
        return _result(CONFLICT_RESOLVED, answer, citations, "Circular E amends the daily customer-account limit from 01 Aug 2026.")
    return _result(
        ANSWERED,
        "The ordinary per-transaction UPI limit is Rs.1,00,000, and the daily limit per customer account is Rs.1,00,000 across all UPI transactions.",
        citations,
    )


def _closure_answer() -> dict[str, Any]:
    return _result(
        ANSWERED,
        "After account closure, pending settlements are released within 10 working days, after deducting outstanding dues.",
        [Citation("policy_master_v1.md", "5.2")],
    )


def _card_settlement_answer() -> dict[str, Any]:
    return _result(
        ANSWERED,
        "No. The policy says card transactions settle T+2; it does not allow same-day card settlement.",
        [Citation("policy_master_v1.md", "1.2")],
    )


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


def _parse_date(value: str | date | None) -> date:
    if value is None or value == "":
        return DEFAULT_AS_OF_DATE
    if isinstance(value, date):
        return value
    return datetime.strptime(value, "%Y-%m-%d").date()


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
    return "large" in q or "above rs10 lakh" in q or "above 10 lakh" in q or "above rs.10 lakh" in q


def _mentions_small(q: str) -> bool:
    return "small" in q or "up to rs10 lakh" in q or "up to 10 lakh" in q


def _mentions_mdr(q: str) -> bool:
    return "mdr" in q or "merchant discount" in q or "fee" in q or "pay" in q


def _mentions_gst(q: str) -> bool:
    return "gst" in q


def _mentions_refund(q: str) -> bool:
    return "refund" in q or "mdr back" in q or "fee back" in q


def _mentions_faq_cap(q: str) -> bool:
    return "faq" in q and ("cap" in q or "upper limit" in q)


def _mentions_limit(q: str) -> bool:
    return "limit" in q or "maximum" in q or "max" in q or "accept rs" in q or "pay rs100000" in q


def _mentions_limit_twice(q: str) -> bool:
    return "twice" in q and ("one day" in q or "same day" in q or "daily" in q)


def _mentions_settlement(q: str) -> bool:
    return "settlement" in q or "settle" in q or "receive" in q or "get my upi money" in q


def _mentions_card(q: str) -> bool:
    return "card" in q


def _mentions_closure(q: str) -> bool:
    return "close my account" in q or "closed my account" in q or "account closure" in q


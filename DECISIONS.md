# Decisions

## Conflict Order

I treat the circular as the controlling document for clauses it explicitly amends, from the effective date of each amendment. Circular D has its own effective date of 01 Sep 2026; the rest of the circular applies from 01 Aug 2026.

## FAQ Authority

The FAQ is treated as a helpful but non-controlling support document. When it disagrees with the master policy or circular, the assistant reports the conflict and uses the policy/circular as authority.

## Default Date

The assignment says to use 15 Aug 2026 unless the question gives a date. The public `ask(question, as_of_date)` function therefore defaults to 2026-08-15 when `as_of_date` is missing.

## Settlement Question Ambiguity

For "When does a small merchant receive UPI money?" after 01 Aug 2026, the circular introduces an Instant Settlement add-on. If the question does not mention that add-on, I answer both branches and state that the ordinary/default case remains T+1.

## Refund Timing

Before 01 Sep 2026, a refund within 24 hours gets full MDR reversal under master clause 3.3. From 01 Sep 2026, circular D deletes clause 3.3, so clause 3.2 applies without exception.

## MDR Arithmetic

MDR and GST are calculated with Python `Decimal`, not guessed. GST is 18% of MDR after applying the cap, because master clause 2.4 says GST is charged on the MDR amount and is not part of the cap.

## Missing Merchant Volume

If a question asks for MDR on a UPI payment but does not say whether the merchant is small or above Rs.10 lakh monthly volume, the assistant returns `CANNOT_ANSWER`.

## Citation Shape

Clause citations are document name plus clause letter/number. FAQ citations use the FAQ question heading because the FAQ has no numbered clauses.


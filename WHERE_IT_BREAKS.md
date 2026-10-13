# Where It Breaks

Three questions the system gets wrong or shouldn't be trusted with, and why:

### 1. "Exactly what date will I receive pending settlements if I close on 28 August 2026?"
- **Why it breaks / shouldn't be trusted**:
  Under Clauses 5.1 and 5.2, pending settlements are released within 10 working days of account closure (subject to 30 days written notice and deducting outstanding dues). Under Clauses 1.1 and 1.3, working days exclude Sundays and bank holidays. Because the policy documents do not supply a national or regional bank holiday calendar, any assistant that attempts to return a specific calendar day (e.g. "08 September 2026") would be guessing and ungrounded.
- **System behavior**: Returns `CANNOT_ANSWER` explaining the 10 working day rule and the missing bank holiday calendar, citing Clauses 5.1 and 5.2.

### 2. "I am a grocery merchant with Rs.9.5 lakh volume this month and Rs.11 lakh last month. Which MDR applies?"
- **Why it breaks / shouldn't be trusted**:
  Clauses 2.1 and 2.2 partition UPI MDR rates based on whether monthly volume is "up to ₹10 lakh" or "above ₹10 lakh". However, the documents fail to define how monthly volume is calculated: does it evaluate the previous calendar month's actuals, trailing 30-day cumulative volume, or the current month's projected run-rate? For merchants hovering near the boundary, this ambiguity cannot be resolved from the text alone.
- **System behavior**: Returns `CANNOT_ANSWER` stating that the policy leaves the monthly volume assessment methodology undefined, citing Clauses 2.1 and 2.2.

### 3. "Can a customer split a Rs.2,00,000 insurance payment into two UPI payments from two different bank accounts?"
- **Why it breaks / shouldn't be trusted**:
  Clause 4.1 limits single UPI transactions to ₹1,00,000 (with an exception up to ₹2,00,000 for Insurance/Capital Markets merchants with enhanced KYC under Clauses 4.2 and 4.4). Clause 4.3 (and Circular E) caps daily payments at ₹1,00,000 "per customer account". The documents do not specify whether the daily cap applies per unique person/PAN or strictly per bank account, nor do they define split-transaction anti-circumvention rules.
- **System behavior**: Returns `CANNOT_ANSWER` explaining that while per-transaction and per-account limits are defined, multi-account identity aggregation is not covered in the policy, citing Clauses 4.2 and 4.3.

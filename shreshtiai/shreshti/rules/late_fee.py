"""GST late fee and interest calculator — deterministic, no LLM.

Late fee (CGST Act s.47, as rationalised by notification): for GSTR-1 and
GSTR-3B, Rs 50 per day of delay (Rs 25 CGST + Rs 25 SGST), or Rs 20 per day
for a nil return, capped by aggregate annual turnover (AATO):
    AATO <= 1.5 crore      -> cap Rs 2,000 per return
    1.5 crore - 5 crore    -> cap Rs 5,000
    above 5 crore          -> cap Rs 10,000
    nil return (any AATO)  -> cap Rs 500

Interest (CGST Act s.50): 18% per annum on tax paid late, for the days of delay.

Figures as of November 2026. The deadline agent shows the "rule as of" date with
every number, and the knowledge base is re-checked when notifications change.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

RULE_AS_OF = date(2026, 11, 18)
CRORE = 10_000_000


@dataclass
class LateFeeResult:
    days_late: int
    late_fee: float
    interest: float
    total: float
    cap_applied: bool
    rule: str = "CGST Act, 2017 — s.47 (late fee) and s.50 (interest)"


def _cap(aato: float, nil_return: bool) -> int:
    if nil_return:
        return 500
    if aato <= 1.5 * CRORE:
        return 2_000
    if aato <= 5 * CRORE:
        return 5_000
    return 10_000


def compute_late_fee(
    due: date,
    filed: date,
    aato: float,
    tax_paid_late: float = 0.0,
    nil_return: bool = False,
) -> LateFeeResult:
    days = max((filed - due).days, 0)
    per_day = 20 if nil_return else 50
    raw_fee = days * per_day
    cap = _cap(aato, nil_return)
    fee = min(raw_fee, cap)
    interest = round(tax_paid_late * 0.18 * days / 365, 2)
    return LateFeeResult(days, float(fee), interest, round(fee + interest, 2), raw_fee > cap)

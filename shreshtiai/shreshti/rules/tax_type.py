"""Intra-state vs inter-state tax type check — deterministic.

Rule (IGST Act s.7 and s.8, simplified for goods): when the supplier's state
and the place of supply are the same, the invoice should charge CGST + SGST/UTGST;
when they differ, it should charge IGST. Charging the wrong type means the tax
has to be paid again under the right head, and the buyer's ITC is at risk.

Edge cases (SEZ supplies, exports, specific services with special
place-of-supply rules) are returned as NEEDS_REVIEW, never guessed.
"""
from __future__ import annotations

from dataclasses import dataclass

COMPLIANT = "COMPLIANT"
NON_COMPLIANT = "NON_COMPLIANT"
NEEDS_REVIEW = "NEEDS_REVIEW"


@dataclass
class TaxTypeFinding:
    verdict: str
    expected: str | None
    message: str
    rule: str = "IGST Act, 2017 — sections 7 and 8 (inter-state vs intra-state supply)"


def check_tax_type(
    supplier_state_code: str,
    place_of_supply_code: str,
    cgst: float,
    sgst: float,
    igst: float,
    special_case: bool = False,
) -> TaxTypeFinding:
    if special_case:
        return TaxTypeFinding(NEEDS_REVIEW, None, "SEZ, export or special place-of-supply case: route to human review.")

    intra = supplier_state_code == place_of_supply_code
    charged_split = cgst > 0 or sgst > 0
    charged_igst = igst > 0

    if charged_split and charged_igst:
        return TaxTypeFinding(NON_COMPLIANT, "IGST only" if not intra else "CGST + SGST only",
                              "Invoice charges both IGST and CGST/SGST on the same supply.")
    if intra:
        if charged_igst:
            return TaxTypeFinding(NON_COMPLIANT, "CGST + SGST",
                                  "Supplier and place of supply are in the same state, so CGST + SGST applies, not IGST.")
        if charged_split and abs(cgst - sgst) > 0.01:
            return TaxTypeFinding(NON_COMPLIANT, "CGST = SGST",
                                  f"CGST ({cgst:.2f}) and SGST ({sgst:.2f}) should be equal halves.")
        return TaxTypeFinding(COMPLIANT, "CGST + SGST", "Intra-state supply taxed as CGST + SGST.")
    if charged_split:
        return TaxTypeFinding(NON_COMPLIANT, "IGST",
                              "Supplier and place of supply are in different states, so IGST applies, not CGST + SGST.")
    return TaxTypeFinding(COMPLIANT, "IGST", "Inter-state supply taxed as IGST.")

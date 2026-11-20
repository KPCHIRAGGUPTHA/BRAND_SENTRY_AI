"""GSTIN validation — deterministic, no LLM.

A GSTIN has 15 characters:
    2  state code (01-38)
    10 PAN of the business
    1  entity number for that PAN in the state (1-9, A-Z)
    1  'Z' by default
    1  check character (mod-36 checksum over the first 14)

ShreshtiAI's rule-check agent calls this before any retrieval, so a bad
GSTIN is caught by code, never "judged" by a model.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_CHARSET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_PATTERN = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")

# State / UT codes used in GSTINs (CBIC state code list).
STATE_CODES = {
    "01": "Jammu and Kashmir", "02": "Himachal Pradesh", "03": "Punjab",
    "04": "Chandigarh", "05": "Uttarakhand", "06": "Haryana", "07": "Delhi",
    "08": "Rajasthan", "09": "Uttar Pradesh", "10": "Bihar", "11": "Sikkim",
    "12": "Arunachal Pradesh", "13": "Nagaland", "14": "Manipur",
    "15": "Mizoram", "16": "Tripura", "17": "Meghalaya", "18": "Assam",
    "19": "West Bengal", "20": "Jharkhand", "21": "Odisha",
    "22": "Chhattisgarh", "23": "Madhya Pradesh", "24": "Gujarat",
    "26": "Dadra and Nagar Haveli and Daman and Diu", "27": "Maharashtra",
    "29": "Karnataka", "30": "Goa", "31": "Lakshadweep", "32": "Kerala",
    "33": "Tamil Nadu", "34": "Puducherry", "35": "Andaman and Nicobar Islands",
    "36": "Telangana", "37": "Andhra Pradesh", "38": "Ladakh",
    "97": "Other Territory", "99": "Centre Jurisdiction",
}


def checksum_char(first14: str) -> str:
    """Return the expected 15th character for the first 14 characters."""
    total = 0
    for i, ch in enumerate(first14):
        product = _CHARSET.index(ch) * (1 if i % 2 == 0 else 2)
        total += product // 36 + product % 36
    return _CHARSET[(36 - total % 36) % 36]


@dataclass
class GstinResult:
    gstin: str
    valid: bool
    state_code: str | None = None
    state: str | None = None
    pan: str | None = None
    errors: list[str] = field(default_factory=list)


def validate_gstin(raw: str) -> GstinResult:
    """Validate format, state code and checksum. Never raises on bad input."""
    gstin = (raw or "").strip().upper()
    result = GstinResult(gstin=gstin, valid=False)

    if len(gstin) != 15:
        result.errors.append(f"GSTIN must be 15 characters, got {len(gstin)}.")
        return result
    if not _PATTERN.match(gstin):
        result.errors.append("GSTIN format is invalid (expected 2 digits + PAN + entity + 'Z' + check).")
        return result

    result.state_code = gstin[:2]
    result.pan = gstin[2:12]
    result.state = STATE_CODES.get(result.state_code)
    if result.state is None:
        result.errors.append(f"Unknown state code {result.state_code}.")

    expected = checksum_char(gstin[:14])
    if gstin[14] != expected:
        result.errors.append(f"Checksum mismatch: last character should be {expected}, found {gstin[14]}.")

    result.valid = not result.errors
    return result

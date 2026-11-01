"""
Guideline Directive Analysis for BrandSentry AI.

Reads the rules out of retrieved guideline text instead of relying on phrases known in
advance, so it works for any uploaded document:

PROHIBITION   "must not", "do not", "is not proof": a claim doing this is CONTRADICTED,
              a claim denying it is SUPPORTED, and a claim asserting the "unless" exception
              is INSUFFICIENT_EVIDENCE because self-reported approval is not documentary proof.
REQUIREMENT   "X must Y": a claim restating it is SUPPORTED, a claim denying it is CONTRADICTED.
RECOMMENDATION "avoid X": a claim saying it avoids X is SUPPORTED; otherwise no verdict.

Matching requires every part of a rule to appear in the claim. When unsure, analyze()
returns None and the caller falls back to its conservative default.
"""
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

SUPPORTED = "SUPPORTED"
CONTRADICTED = "CONTRADICTED"
INSUFFICIENT = "INSUFFICIENT_EVIDENCE"

_STOP_WORDS = frozenset({
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "by", "with", "that", "this",
    "these", "those", "is", "are", "be", "been", "being", "was", "were", "as", "at", "it", "its",
    "their", "our", "your", "we", "they", "you", "any", "all", "every", "each", "such", "has",
    "have", "had", "will", "can", "may", "must", "should", "shall", "when", "where", "than",
    "from", "under", "product", "products", "marketing", "material", "materials", "claim",
    "claims", "statement", "imply", "implies", "state", "states", "describe", "describes",
    "promise", "promises", "use", "uses", "used", "using", "say", "says", "not", "never",
    "do", "does", "alone", "specific", "like", "there", "about",
})

_CANONICAL = {
    "result": "outcome", "results": "outcome",
    "prove": "proof", "proves": "proof", "proven": "proof",
    "zero": "no",
}

_DISEASE_TERMS = frozenset({
    "arthritis", "asthma", "cancer", "covid", "dementia", "depression", "diabetes", "flu",
    "hypertension", "illness", "infection", "influenza", "psoriasis", "alzheimer", "alzheimers",
})

_REGULATORY_RE = re.compile(r"\b(hipaa|gdpr|soc\s?2|pci(?:[\s-]dss)?|iso\s?-?\d{4,5}|fda|fedramp|ccpa)\b", re.I)

_PROHIBITION_RE = re.compile(r"\b(must\s+not|must\s+never|shall\s+not|may\s+not|do\s+not|cannot|never)\b", re.I)
_DENIAL_RE = re.compile(r"\bis\s+not\s+(proof|sufficient|enough|a\s+guarantee)\b", re.I)
_REQUIREMENT_RE = re.compile(r"\b(must|shall|is\s+required\s+to|are\s+required\s+to)\b(?!\s+(?:not|never)\b)", re.I)
_RECOMMENDATION_RE = re.compile(r"\b(avoid|refrain\s+from)\b", re.I)
_CONDITIONAL_RE = re.compile(r"\bmust\s+be\s+(?:[\w,\s-]{0,30}\s)?(?:supported|substantiated|documented|verified|approved)\b", re.I)
_SCOPE_END_RE = re.compile(r"\b(unless|when|if|rather\s+than|except)\b", re.I)
_QUOTED_RE = re.compile(r"[“\"]([^”\"]{2,60})[”\"]|(?<![\w])'([^']{2,60})'(?![\w])")
_LIST_SPLIT_RE = re.compile(r"\s*,\s*(?:and\s+|or\s+)?|\s+(?:and|or)\s+", re.I)
_DETERMINER_RE = re.compile(r"\s(?:a|an|the)\s", re.I)
_NEGATOR_RE = re.compile(
    r"\b(not|never|no|cannot|can't|don't|doesn't|won't|isn't|aren't|without|avoids?|avoiding|"
    r"refrains?|refraining|fails?|failing|omits?|omitting|hides?|hiding)\b",
    re.I,
)
_CLAUSE_BOUNDARY_RE = re.compile(r"\b(?:and|but|while|although|though|because)\b|[;:]")
_EXCEPTION_ASSERTION_RE = re.compile(
    r"\b(approved|approval|sign-?off|authori[sz]ed|authori[sz]ation|substantiated|verified|"
    r"documented|documentation|records?|ledgers?|demonstrates?)\b",
    re.I,
)
# Oral approval and stale records cannot meet a documentary exception, so the prohibition stands.
_UNMET_EXCEPTION_RE = re.compile(
    r"\b(oral|orally|verbal|verbally|informal|informally|expired|outdated|legacy|years\s+ago|never\s+updated)\b",
    re.I,
)
_INJECTION_RE = re.compile(
    r"\b(ignore|disregard)\s+(?:all\s+)?(?:(?:previous|prior|above)\s+)?instructions\b|\bsystem\s+override\b",
    re.I,
)


@dataclass
class Directive:
    """One rule read from a guideline sentence."""
    kind: str
    statement: str
    passage: Dict[str, Any]
    scope: List[Set[str]] = field(default_factory=list)
    subject: List[Set[str]] = field(default_factory=list)
    quoted_terms: List[str] = field(default_factory=list)
    exception: str = ""


@dataclass
class DirectiveMatch:
    """The verdict a directive implies for a claim, with the guideline sentence behind it."""
    verdict: str
    statement: str
    passage: Dict[str, Any]
    explanation: str
    cite: bool = True


def is_prompt_injection(claim_text: str) -> bool:
    """True when the claim tries to instruct the reviewer rather than assert anything."""
    return bool(_INJECTION_RE.search(claim_text))


def _normalize_quotes(text: str) -> str:
    return text.replace("’", "'").replace("‘", "'")


def _stem(word: str) -> str:
    word = _CANONICAL.get(word, word)
    if word in _DISEASE_TERMS:
        return "disease"
    for suffix in ("ing", "ed", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


def _same(a: str, b: str) -> bool:
    if a == b:
        return True
    prefix = 0
    for x, y in zip(a, b):
        if x != y:
            break
        prefix += 1
    return prefix >= 6


def _tokens(text: str) -> List[str]:
    """Content words, stemmed. Keeps 'no' because 'has no risks' depends on it."""
    words = re.findall(r"[a-z0-9]+", _normalize_quotes(text).lower())
    result = []
    for word in words:
        if word == "no":
            result.append("no")
        elif word in _STOP_WORDS or len(word) < 2 or (word.endswith("ly") and len(word) > 4):
            continue
        else:
            result.append(_stem(word))
    return result


def _claim_tokens(claim_text: str) -> List[str]:
    tokens = _tokens(claim_text)
    if _REGULATORY_RE.search(claim_text):
        tokens.append("regulatory")
    return tokens


def _slots(text: str) -> List[Set[str]]:
    """
    Turns a rule phrase into slots the claim must fill; each slot is a set of alternatives.
    'cures, treats, or prevents a disease' gives {cure, treat, prevent}, {disease}.
    """
    items = [i for i in _LIST_SPLIT_RE.split(text.strip()) if i.strip()]
    if len(items) < 2:
        return [{t} for t in _tokens(text)]

    first = _tokens(items[0])
    last = _tokens(items[-1])
    slots: List[Set[str]] = [{t} for t in first[:-1]]
    alternatives: Set[str] = set(first[-1:])
    for item in items[1:-1]:
        alternatives.update(_tokens(item))
    alternatives.update(last[:1])
    if alternatives:
        slots.append(alternatives)
    if _DETERMINER_RE.search(" " + items[-1]):
        slots.extend({t} for t in last[1:])
    return slots


def _fills(slots: List[Set[str]], tokens: List[str]) -> bool:
    return bool(slots) and all(any(_same(alt, t) for alt in slot for t in tokens) for slot in slots)


def _quoted_terms(text: str) -> List[str]:
    terms = []
    for match in _QUOTED_RE.finditer(text):
        term = (match.group(1) or match.group(2) or "").strip().lower()
        term = re.sub(r"^the\s+", "", term)
        if term:
            terms.append(term)
    return terms


def _strip_quoted(text: str) -> str:
    return _QUOTED_RE.sub(" ", text)


def parse_directives(statement: str, passage: Dict[str, Any]) -> List[Directive]:
    """Reads the rules in one guideline sentence."""
    directives: List[Directive] = []
    clauses = re.split(r"\s+(?:and|but)\s+(?=must\b)", statement, flags=re.I)
    shared_subject = ""

    for clause in clauses:
        quoted = _quoted_terms(clause)

        denial = _DENIAL_RE.search(clause)
        if denial:
            subject = clause[: denial.start()]
            directives.append(Directive(
                kind="PROHIBITION",
                statement=statement,
                passage=passage,
                scope=_slots(subject) + [{"proof"}],
                quoted_terms=quoted,
            ))
            continue

        # A quoted word such as "never" is an example of a term, not a rule.
        unquoted = _strip_quoted(clause)
        prohibition = _PROHIBITION_RE.search(unquoted)
        if prohibition:
            after = unquoted[prohibition.end():]
            end = _SCOPE_END_RE.search(after)
            scope_text = after[: end.start()] if end else after
            exception = after[end.end():] if end and end.group(1).lower() == "unless" else ""
            directives.append(Directive(
                kind="PROHIBITION",
                statement=statement,
                passage=passage,
                scope=_slots(_strip_quoted(scope_text)),
                quoted_terms=quoted,
                exception=exception,
            ))
            continue

        recommendation = _RECOMMENDATION_RE.search(clause)
        if recommendation:
            after = clause[recommendation.end():]
            end = _SCOPE_END_RE.search(after)
            directives.append(Directive(
                kind="RECOMMENDATION",
                statement=statement,
                passage=passage,
                scope=_slots(after[: end.start()] if end else after),
            ))
            continue

        requirement = _REQUIREMENT_RE.search(clause)
        if requirement:
            subject = clause[: requirement.start()] or shared_subject
            shared_subject = subject
            predicate = clause[requirement.end():]
            end = _SCOPE_END_RE.search(predicate)
            directives.append(Directive(
                kind="REQUIREMENT",
                statement=statement,
                passage=passage,
                subject=_slots(_strip_quoted(subject)),
                scope=_slots(predicate[: end.start()] if end else predicate),
                quoted_terms=quoted,
            ))

    return directives


def _is_denied(claim_text: str, position: int, own_words: Set[str]) -> bool:
    """
    True when an odd number of negators precede `position` in the same clause, so
    'never fails to disclose' reads as positive and '100% safe without side effects'
    is not treated as a denial.
    """
    before = _normalize_quotes(claim_text[:position]).lower()
    boundaries = list(_CLAUSE_BOUNDARY_RE.finditer(before))
    clause = before[boundaries[-1].end():] if boundaries else before
    clause = re.sub(r"\bnot\s+only\b", " ", clause)
    negators = [m.group(1) for m in _NEGATOR_RE.finditer(clause) if m.group(1) not in own_words]
    return len(negators) % 2 == 1


def _first_position(claim_text: str, slots: List[Set[str]]) -> int:
    """Character position of the first claim word that fills any slot."""
    for match in re.finditer(r"[a-z0-9]+", claim_text.lower()):
        stem = _stem(match.group(0))
        if any(_same(alt, stem) for slot in slots for alt in slot):
            return match.start()
    return len(claim_text)


def _exception_asserted(claim_text: str, directive: Directive) -> bool:
    """True when the claim says the rule's 'unless' condition has been met."""
    assertion = _EXCEPTION_ASSERTION_RE.search(claim_text) if directive.exception else None
    if not assertion or _is_denied(claim_text, assertion.start(), set()):
        return False
    return not _UNMET_EXCEPTION_RE.search(claim_text)


def _match_prohibition(claim_text: str, claim_tokens: List[str], d: Directive) -> Optional[DirectiveMatch]:
    lowered = _normalize_quotes(claim_text).lower()
    position = -1
    own_words: Set[str] = set()

    term = next((t for t in d.quoted_terms if t in lowered), None)
    if term:
        position = lowered.index(term)
        own_words = set(re.findall(r"[a-z]+", term))
    elif len(d.scope) >= 2 and len(claim_text.split()) >= 3 and _fills(d.scope, claim_tokens):
        position = _first_position(claim_text, d.scope)
        own_words = {"no"} if any("no" in slot for slot in d.scope) else set()
    else:
        return None

    if _is_denied(claim_text, position, own_words):
        return DirectiveMatch(SUPPORTED, d.statement, d.passage, "Compliant statement aligned with guideline rule")
    if _exception_asserted(claim_text, d):
        return DirectiveMatch(
            INSUFFICIENT, d.statement, d.passage,
            "The claim says the guideline's exception has been met, but self-reported approval is not "
            "documentary proof, so a reviewer must confirm it against the guideline",
        )
    return DirectiveMatch(CONTRADICTED, d.statement, d.passage, "Claim conflicts with guideline rule")


def _match_requirement(claim_text: str, claim_tokens: List[str], d: Directive) -> Optional[DirectiveMatch]:
    if not _fills(d.scope, claim_tokens) or (d.subject and not _fills(d.subject, claim_tokens)):
        return None
    if _is_denied(claim_text, _first_position(claim_text, d.scope), set()):
        return DirectiveMatch(CONTRADICTED, d.statement, d.passage, "Claim admits breaking guideline requirement")

    # A restatement adds no facts of its own; a claim with many extra words asserts more than the rule.
    rule_tokens = _tokens(d.statement)
    covered = [t for t in claim_tokens if any(_same(t, r) for r in rule_tokens)]
    if not claim_tokens or len(covered) / len(claim_tokens) < 0.6:
        return None
    return DirectiveMatch(SUPPORTED, d.statement, d.passage, "Claim restates guideline requirement")


def _match_recommendation(claim_text: str, claim_tokens: List[str], d: Directive) -> Optional[DirectiveMatch]:
    if len(d.scope) < 2 or not _fills(d.scope, claim_tokens):
        return None
    if _is_denied(claim_text, _first_position(claim_text, d.scope), set()):
        return DirectiveMatch(SUPPORTED, d.statement, d.passage, "Compliant statement aligned with guideline rule")
    return None


def analyze(
    claim_text: str,
    statements: List[Tuple[str, Dict[str, Any]]],
) -> Optional[DirectiveMatch]:
    """
    Finds the guideline rule that decides this claim. Prohibitions outrank requirements.
    Returns None when no rule clearly applies.
    """
    claim_tokens = _claim_tokens(claim_text)
    directives = [d for statement, passage in statements for d in parse_directives(statement, passage)]

    def complete_first(items: List[Directive]) -> List[Directive]:
        # Chunk boundaries can cut a sentence; prefer a copy that ends properly.
        return sorted(items, key=lambda d: not d.statement.rstrip().endswith((".", "!", "?")))

    ordered = complete_first(directives)
    for d in ordered:
        if d.kind == "PROHIBITION":
            found = _match_prohibition(claim_text, claim_tokens, d)
            if found:
                return found
    for d in ordered:
        found = None
        if d.kind == "REQUIREMENT":
            found = _match_requirement(claim_text, claim_tokens, d)
        elif d.kind == "RECOMMENDATION":
            found = _match_recommendation(claim_text, claim_tokens, d)
        if found:
            return found
    return None

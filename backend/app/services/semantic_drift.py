"""
Semantic Drift Detection Engine for BrandSentry AI.

Detects when a marketing claim subtly shifts the meaning, strength, scope,
certainty, conditions, temporality, causality, or comparison of an existing
policy or evidence statement.

Taxonomy of Semantic Drift Categories:
--------------------------------------
1. CERTAINTY_SHIFT:
   Modifies qualified epistemic modality ("may", "might", "could", "likely",
   "aims to", "possible") into unconditional certainty ("always", "guaranteed",
   "never", "definitely", "ensures", "proves").

2. SCOPE_EXPANSION:
   Expands a restricted or qualified demographic/audience ("some", "selected",
   "registered", "enterprise", "eligible", "participating") into universal scope
   ("all", "every", "everyone", "all customers", "any user").

3. NUMERICAL_EXAGGERATION:
   Increases percentages, multipliers, performance figures, or metric claims
   beyond the ceiling or range documented in the source evidence.

4. CONDITION_OMISSION:
   Omits critical qualifications, prerequisites, or constraints documented in
   the evidence (e.g. "when unused", "subject to prior approval",
   "under suitable conditions", "with documentation").

5. TEMPORAL_SHIFT:
   Alters documented timeframes, deadlines, durations, or frequency
   (e.g., "within 30 days" -> "instantly" / "lifetime", or duration inflation).

6. CAUSALITY_SHIFT:
   Upgrades an observed correlation or association ("associated with",
   "linked to", "observed in", "suggests") into a definitive causal claim
   ("causes", "leads directly to", "proves", "cures").

7. COMPARISON_SHIFT:
   Strengthens an aligned or competitive comparison ("comparable to", "competitive")
   into an unsubstantiated superlative ("fastest", "outperforms every competitor").

Guiding Principles:
-------------------
- Grounded: Every flagged drift is tied to an explicit phrase in the claim and
  its corresponding phrase in the retrieved source passage.
- Conservative: When evidence is missing, ambiguous, or lacks topic overlap,
  the detector indicates uncertainty rather than manufacturing false findings.
- Explainable: Returns category, severity, claim phrase, source phrase, explanation,
  and a safe suggested correction where possible.
"""

import re
from typing import List, Dict, Any, Optional, Tuple

from backend.app.schemas.review import (
    SemanticDriftIssue,
    SemanticDriftResult,
)



# ---------------------------------------------------------------------------
# Linguistic Markers & Patterns
# ---------------------------------------------------------------------------

# Epistemic Modality (Certainty)
_QUALIFIED_CERTAINTY_PATTERNS = [
    (re.compile(r'\b(may|might|could|can\s+sometimes|possibly|possible|aims?\s+to|seeks?\s+to|likely|potential|potentially)\b', re.IGNORECASE), "qualified possibility"),
    (re.compile(r'\b(under\s+suitable\s+conditions|in\s+certain\s+circumstances|where\s+applicable|as\s+appropriate)\b', re.IGNORECASE), "conditional suitability"),
]

_ABSOLUTE_CERTAINTY_PATTERNS = [
    (re.compile(r'\b(always|guaranteed|guarantees?|definitely|certainly|invariably|without\s+exception|100%|completely|flawlessly|never)\b', re.IGNORECASE), "unconditional certainty"),
    (re.compile(r'\b(ensures?|proves?|promises?)\b', re.IGNORECASE), "definitive outcome"),
]

# Scope
_RESTRICTED_SCOPE_PATTERNS = [
    (re.compile(r'\b(registered|enterprise|participating|eligible|qualified|select|selected|certain|some|specific)\s+(customers?|users?|clients?|accounts?|members?|organizations?|businesses?)\b', re.IGNORECASE), "restricted customer segment"),
    (re.compile(r'\b(registered|enterprise|participating|eligible|qualified|select|selected)\b', re.IGNORECASE), "qualified qualification"),
    (re.compile(r'\b(internal\s+test|pilot\s+group|sample\s+cohort|beta\s+users?|limited\s+trial)\b', re.IGNORECASE), "limited test cohort"),
]

_UNIVERSAL_SCOPE_PATTERNS = [
    (re.compile(r'\b(all|every|any|everyone|everybody|each\s+and\s+every)\s+(customers?|users?|clients?|accounts?|people|organizations?|businesses?)\b', re.IGNORECASE), "universal audience"),
    (re.compile(r'\b(all|every|everyone|everybody|worldwide|globally|universal|universally)\b', re.IGNORECASE), "universal quantifier"),
    (re.compile(r'\bfor\s+every\s+(customer|user|client|person)\b', re.IGNORECASE), "universal scope"),
]

# Conditions / Qualifications
_CONDITION_PATTERNS = [
    (re.compile(r'\b(when|if|provided\s+that|provided|unless|subject\s+to|on\s+condition\s+that|only\s+when|only\s+if)\s+([a-zA-Z0-9\s,\'-]{3,50}?)(?=[,.;]|$)', re.IGNORECASE), "explicit condition"),
    (re.compile(r'\b(unused|unopened|in\s+original\s+packaging|with\s+receipt|with\s+prior\s+approval|with\s+documentation|under\s+suitable\s+conditions|subject\s+to\s+terms)\b', re.IGNORECASE), "material prerequisite"),
]

# Causality
_CORRELATION_PATTERNS = [
    (re.compile(r'\b(associated\s+with|correlated\s+with|linked\s+to|observed\s+in|suggests|indicated\s+in|connected\s+to)\b', re.IGNORECASE), "correlation / association"),
]

_CAUSATION_PATTERNS = [
    (re.compile(r'\b(causes?|leads?\s+directly\s+to|directly\s+results?\s+in|proves?|cures?|eliminates?|prevents?)\b', re.IGNORECASE), "direct causation"),
]

# Comparisons
_QUALIFIED_COMPARISON_PATTERNS = [
    (re.compile(r'\b(comparable\s+to|competitive\s+with|one\s+of\s+the|among\s+the\s+leading)\b', re.IGNORECASE), "qualified comparison"),
]

_SUPERLATIVE_COMPARISON_PATTERNS = [
    (re.compile(r'\b(fastest|best|cheapest|number\s+1|#1|superior\s+to\s+all|outperforms?\s+every|twice\s+as\s+fast|most\s+effective)\b', re.IGNORECASE), "unsupported superlative"),
]

# Numerical
_PERCENT_PATTERN = re.compile(r'(\b\d+(?:\.\d+)?)\s*%', re.IGNORECASE)
_UP_TO_PERCENT_PATTERN = re.compile(r'\b(?:up\s+to|as\s+much\s+as|maximum\s+of)\s+(\d+(?:\.\d+)?)\s*%', re.IGNORECASE)


class SemanticDriftDetector:
    """
    Evaluates semantic drift between a submitted claim and retrieved evidence passages.
    """

    def analyze(
        self,
        claim_text: str,
        retrieved_passages: List[Dict[str, Any]],
    ) -> SemanticDriftResult:
        """
        Analyze a claim against its retrieved evidence passages.

        Args:
            claim_text: The marketing claim text.
            retrieved_passages: List of passage dictionaries from the vector store.

        Returns:
            SemanticDriftResult detailing detected drift issues or uncertainty.
        """
        if not claim_text or not claim_text.strip():
            return SemanticDriftResult(
                detected=False,
                issues=[],
                uncertainty="Claim text is empty; cannot evaluate semantic drift.",
            )

        if not retrieved_passages:
            return SemanticDriftResult(
                detected=False,
                issues=[],
                uncertainty="No evidence passages available to evaluate semantic drift.",
            )

        # Filter passages to those with meaningful similarity / topic overlap
        relevant_passages = [
            p for p in retrieved_passages
            if p.get("similarity_score", 0.0) >= 0.20 or self._has_topic_overlap(claim_text, p.get("text", ""))
        ]

        if not relevant_passages:
            return SemanticDriftResult(
                detected=False,
                issues=[],
                uncertainty="Retrieved evidence lacks sufficient topical overlap to evaluate drift reliably.",
            )

        issues: List[SemanticDriftIssue] = []

        # Analyze each relevant passage and aggregate grounded drift issues
        for passage in relevant_passages:
            passage_text = passage.get("text", "")
            if not passage_text:
                continue

            # 1. CERTAINTY_SHIFT
            self._check_certainty_shift(claim_text, passage_text, issues)

            # 2. SCOPE_EXPANSION
            self._check_scope_expansion(claim_text, passage_text, issues)

            # 3. NUMERICAL_EXAGGERATION
            self._check_numerical_exaggeration(claim_text, passage_text, issues)

            # 4. CONDITION_OMISSION
            self._check_condition_omission(claim_text, passage_text, issues)

            # 5. TEMPORAL_SHIFT
            self._check_temporal_shift(claim_text, passage_text, issues)

            # 6. CAUSALITY_SHIFT
            self._check_causality_shift(claim_text, passage_text, issues)

            # 7. COMPARISON_SHIFT
            self._check_comparison_shift(claim_text, passage_text, issues)

        # Deduplicate issues by (category, claim_phrase)
        deduped_issues: List[SemanticDriftIssue] = []
        seen_keys = set()
        for issue in issues:
            key = (issue.category, issue.claim_phrase.lower().strip())
            if key not in seen_keys:
                seen_keys.add(key)
                deduped_issues.append(issue)

        return SemanticDriftResult(
            detected=len(deduped_issues) > 0,
            issues=deduped_issues,
            uncertainty=None,
        )

    # -----------------------------------------------------------------------
    # Detection Rules
    # -----------------------------------------------------------------------

    def _check_certainty_shift(
        self,
        claim: str,
        passage: str,
        issues: List[SemanticDriftIssue],
    ) -> None:
        """Detect shift from qualified modality ('may', 'could') to absolute certainty ('always')."""
        source_qualified = None
        source_matched_text = None
        for pat, _ in _QUALIFIED_CERTAINTY_PATTERNS:
            m = pat.search(passage)
            if m:
                source_qualified = m.group(0)
                # Find full sentence or clause for source context
                source_matched_text = self._extract_context_window(passage, m.start(), m.end())
                break

        if not source_qualified:
            return

        claim_absolute = None
        for pat, _ in _ABSOLUTE_CERTAINTY_PATTERNS:
            m = pat.search(claim)
            if m:
                claim_absolute = m.group(0)
                break

        if claim_absolute:
            claim_phrase = self._extract_matching_phrase(claim, claim_absolute)
            correction = re.sub(
                rf'\b{re.escape(claim_absolute)}\b',
                source_qualified,
                claim,
                flags=re.IGNORECASE,
            ).strip()

            issues.append(
                SemanticDriftIssue(
                    category="CERTAINTY_SHIFT",
                    severity="HIGH",
                    claim_phrase=claim_phrase,
                    source_phrase=source_matched_text or source_qualified,
                    explanation=(
                        f"The claim upgrades a qualified source possibility ('{source_qualified}') "
                        f"into an unconditional certainty ('{claim_absolute}')."
                    ),
                    suggested_correction=correction if correction != claim else None,
                )
            )

    def _check_scope_expansion(
        self,
        claim: str,
        passage: str,
        issues: List[SemanticDriftIssue],
    ) -> None:
        """Detect expansion from restricted group ('registered customers') to universal ('all customers')."""
        source_restricted = None
        source_phrase = None
        for pat, _ in _RESTRICTED_SCOPE_PATTERNS:
            m = pat.search(passage)
            if m:
                source_restricted = m.group(0)
                source_phrase = self._extract_context_window(passage, m.start(), m.end())
                break

        if not source_restricted:
            return

        claim_universal = None
        for pat, _ in _UNIVERSAL_SCOPE_PATTERNS:
            m = pat.search(claim)
            if m:
                claim_universal = m.group(0)
                break

        if claim_universal:
            claim_phrase = self._extract_matching_phrase(claim, claim_universal)
            correction = re.sub(
                rf'\b{re.escape(claim_universal)}\b',
                source_restricted,
                claim,
                flags=re.IGNORECASE,
            ).strip()

            issues.append(
                SemanticDriftIssue(
                    category="SCOPE_EXPANSION",
                    severity="HIGH",
                    claim_phrase=claim_phrase,
                    source_phrase=source_phrase or source_restricted,
                    explanation=(
                        f"The claim broadens the scope from a restricted audience or condition "
                        f"('{source_restricted}') to a universal application ('{claim_universal}')."
                    ),
                    suggested_correction=correction if correction != claim else None,
                )
            )

    def _check_numerical_exaggeration(
        self,
        claim: str,
        passage: str,
        issues: List[SemanticDriftIssue],
    ) -> None:
        """Detect inflation of percentages, performance figures, or measurable numbers."""
        claim_percents = _PERCENT_PATTERN.findall(claim)
        passage_percents = _PERCENT_PATTERN.findall(passage)

        if not claim_percents or not passage_percents:
            return

        try:
            claim_max = max(float(p) for p in claim_percents)
            passage_max = max(float(p) for p in passage_percents)
        except ValueError:
            return

        # Check for numerical inflation (e.g. 15% in passage vs 85% in claim)
        if claim_max > passage_max:
            # Check if passage specified a ceiling like "up to 15%"
            m_ceiling = _UP_TO_PERCENT_PATTERN.search(passage)
            source_ceiling_str = f"up to {passage_max:.0f}%" if m_ceiling else f"{passage_max:.0f}%"

            claim_phrase = f"{claim_max:.0f}%"
            # Find surrounding words in claim
            m_claim = re.search(rf'(\b\w+\s+)?{re.escape(claim_phrase)}(\s+\w+)?', claim)
            if m_claim:
                claim_phrase = m_claim.group(0).strip()

            source_phrase = self._extract_context_window(passage, passage.lower().find(f"{passage_max:.0f}%"), None)

            correction = re.sub(
                rf'\b{claim_max:.0f}%\b',
                source_ceiling_str,
                claim,
            ).strip()

            issues.append(
                SemanticDriftIssue(
                    category="NUMERICAL_EXAGGERATION",
                    severity="HIGH",
                    claim_phrase=claim_phrase,
                    source_phrase=source_phrase,
                    explanation=(
                        f"The claim states {claim_max:.0f}%, which materially exceeds the evidence baseline "
                        f"of {source_ceiling_str} documented in the source."
                    ),
                    suggested_correction=correction if correction != claim else None,
                )
            )

    def _check_condition_omission(
        self,
        claim: str,
        passage: str,
        issues: List[SemanticDriftIssue],
    ) -> None:
        """Detect omission of critical conditions or prerequisites in the source (e.g. 'when unused')."""
        # Look for explicit condition clauses in the source
        for pat, _ in _CONDITION_PATTERNS:
            for m in pat.finditer(passage):
                condition_text = m.group(0).strip()
                # If key condition words do not appear in the claim
                words = [w.lower() for w in re.findall(r'\b[a-zA-Z]{4,}\b', condition_text)
                         if w.lower() not in {"when", "that", "this", "with", "from", "have", "been"}]
                if not words:
                    continue

                # Check if NONE of the substantive condition words appear in the claim
                matches_in_claim = sum(1 for w in words if re.search(rf'\b{re.escape(w)}\b', claim, re.IGNORECASE))
                if matches_in_claim == 0:
                    # Condition is omitted
                    source_phrase = self._extract_context_window(passage, m.start(), m.end())
                    issues.append(
                        SemanticDriftIssue(
                            category="CONDITION_OMISSION",
                            severity="MEDIUM",
                            claim_phrase=claim.strip(),
                            source_phrase=source_phrase,
                            explanation=(
                                f"The claim omits an essential qualifying condition documented in the evidence: "
                                f"'{condition_text}'."
                            ),
                            suggested_correction=f"{claim.rstrip('.')} {condition_text}.",
                        )
                    )
                    return

    def _check_temporal_shift(
        self,
        claim: str,
        passage: str,
        issues: List[SemanticDriftIssue],
    ) -> None:
        """Detect temporal changes (e.g. 'within 30 days' vs 'instantly' or altered durations)."""
        time_units = r'(?:(?:business|calendar|working)\s+)?(?:days?|weeks?|months?|years?|hours?|minutes?)'
        p_durations = re.findall(rf'(\b\d+\s+{time_units}\b)', passage, re.IGNORECASE)
        c_durations = re.findall(rf'(\b\d+\s+{time_units}\b)', claim, re.IGNORECASE)

        # 1. Different numerical duration
        if p_durations and c_durations:
            p_first = p_durations[0].lower()
            c_first = c_durations[0].lower()
            if p_first != c_first:
                source_phrase = self._extract_context_window(passage, passage.lower().find(p_first), None)
                issues.append(
                    SemanticDriftIssue(
                        category="TEMPORAL_SHIFT",
                        severity="MEDIUM",
                        claim_phrase=c_first,
                        source_phrase=source_phrase,
                        explanation=f"The claim specifies '{c_first}', whereas the evidence specifies '{p_first}'.",
                        suggested_correction=claim.replace(c_durations[0], p_durations[0]),
                    )
                )
                return

        # 2. Source has duration, claim promises 'instant' or 'lifetime'
        if p_durations:
            instant_m = re.search(r'\b(instantly|instant|immediate|immediately|lifetime|forever|24/7)\b', claim, re.IGNORECASE)
            if instant_m:
                source_phrase = self._extract_context_window(passage, passage.lower().find(p_durations[0].lower()), None)
                issues.append(
                    SemanticDriftIssue(
                        category="TEMPORAL_SHIFT",
                        severity="HIGH",
                        claim_phrase=instant_m.group(0),
                        source_phrase=source_phrase,
                        explanation=(
                            f"The claim claims '{instant_m.group(0)}' turnaround/availability, but the policy "
                            f"documents '{p_durations[0]}'."
                        ),
                        suggested_correction=None,
                    )
                )

    def _check_causality_shift(
        self,
        claim: str,
        passage: str,
        issues: List[SemanticDriftIssue],
    ) -> None:
        """Detect shift from association/correlation to proven cause."""
        source_corr = None
        for pat, _ in _CORRELATION_PATTERNS:
            m = pat.search(passage)
            if m:
                source_corr = m.group(0)
                break

        if not source_corr:
            return

        claim_cause = None
        for pat, _ in _CAUSATION_PATTERNS:
            m = pat.search(claim)
            if m:
                claim_cause = m.group(0)
                break

        if claim_cause:
            source_phrase = self._extract_context_window(passage, passage.lower().find(source_corr.lower()), None)
            claim_phrase = self._extract_matching_phrase(claim, claim_cause)
            issues.append(
                SemanticDriftIssue(
                    category="CAUSALITY_SHIFT",
                    severity="HIGH",
                    claim_phrase=claim_phrase,
                    source_phrase=source_phrase,
                    explanation=(
                        f"The claim asserts direct causality ('{claim_cause}'), whereas the evidence "
                        f"establishes only correlation or association ('{source_corr}')."
                    ),
                    suggested_correction=re.sub(
                        rf'\b{re.escape(claim_cause)}\b',
                        source_corr,
                        claim,
                        flags=re.IGNORECASE,
                    ).strip(),
                )
            )

    def _check_comparison_shift(
        self,
        claim: str,
        passage: str,
        issues: List[SemanticDriftIssue],
    ) -> None:
        """Detect shift from balanced comparison to ungrounded superlative."""
        source_comp = None
        for pat, _ in _QUALIFIED_COMPARISON_PATTERNS:
            m = pat.search(passage)
            if m:
                source_comp = m.group(0)
                break

        claim_super = None
        for pat, _ in _SUPERLATIVE_COMPARISON_PATTERNS:
            m = pat.search(claim)
            if m:
                claim_super = m.group(0)
                break

        if claim_super and (source_comp or "compar" in passage.lower() or "compet" in passage.lower()):
            source_phrase = self._extract_context_window(passage, passage.lower().find(source_comp.lower() if source_comp else "compet"), None)
            claim_phrase = self._extract_matching_phrase(claim, claim_super)
            issues.append(
                SemanticDriftIssue(
                    category="COMPARISON_SHIFT",
                    severity="MEDIUM",
                    claim_phrase=claim_phrase,
                    source_phrase=source_phrase,
                    explanation=(
                        f"The claim introduces an aggressive superlative comparison ('{claim_super}') "
                        f"not substantiated by the evidence."
                    ),
                    suggested_correction=None,
                )
            )

    # -----------------------------------------------------------------------
    # Helper Utilities
    # -----------------------------------------------------------------------

    def _has_topic_overlap(self, claim: str, passage: str) -> bool:
        """Checks if there are at least two substantive non-stopword tokens in common."""
        claim_words = {w.lower() for w in re.findall(r'\b[a-zA-Z]{4,}\b', claim)
                       if w.lower() not in {"this", "that", "with", "from", "have", "were", "they", "will", "your", "their"}}
        passage_words = {w.lower() for w in re.findall(r'\b[a-zA-Z]{4,}\b', passage)}
        return len(claim_words.intersection(passage_words)) >= 2

    def _extract_context_window(self, text: str, start: int, end: Optional[int] = None, max_len: int = 150) -> str:
        """Extract a readable sentence or snippet containing the match."""
        if start < 0 or start >= len(text):
            return text[:max_len]

        if end is None:
            end = start + 10

        # Try to find sentence boundaries
        sent_start = max(0, text.rfind('.', 0, start) + 1)
        sent_end = text.find('.', end)
        if sent_end == -1:
            sent_end = len(text)
        else:
            sent_end += 1

        snippet = text[sent_start:sent_end].strip()
        if len(snippet) > max_len:
            snippet = snippet[:max_len] + "..."
        return snippet

    def _extract_matching_phrase(self, text: str, target: str, window_words: int = 3) -> str:
        """Extract surrounding phrase for readability in UI and report."""
        words = text.split()
        target_lower = target.lower()
        idx = -1
        for i, w in enumerate(words):
            if target_lower in w.lower():
                idx = i
                break

        if idx == -1:
            return target

        start = max(0, idx - window_words)
        end = min(len(words), idx + window_words + 1)
        return " ".join(words[start:end])


# Singleton detector instance
semantic_drift_detector = SemanticDriftDetector()

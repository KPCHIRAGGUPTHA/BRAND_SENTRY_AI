"""
Claim Extraction Service for BrandSentry AI — Phase 3.

Converts raw marketing content into discrete, testable claims.

Strategy
--------
Phase 3 uses a **deterministic sentence-splitting** approach:

1. Split the input text on sentence-terminal punctuation (., !, ?) while
   respecting common abbreviations and decimal numbers.
2. For each resulting sentence, detect common coordinating conjunctions
   (``; and``, ``; but``, ``; however``) that join semantically independent
   assertions and split further.
3. Clean up whitespace, normalise punctuation, and discard empty or
   single-word fragments.
4. Assign a stable ``claim-N`` identifier within the review.

Known limitations (documented, not hidden)
------------------------------------------
- Simple sentence splitting does NOT parse grammar.  A compound sentence like
  "Our cream moisturises and firms skin" remains a single claim unless split by
  a conjunction that appears after a semicolon.
- Quoted speech, lists, and parenthetical asides may produce imperfect splits.
- Punctuation inside acronyms (e.g., ``U.S.A.``) can cause over-splitting.
- Multi-clause sentences joined by ``and`` without a semicolon are kept whole.
- This extractor is not a replacement for language-model parsing.  If the
  application is extended with an LLM extractor, that extractor must be
  implemented behind the ``ClaimExtractorBase`` interface and its failures
  must fall back to this deterministic implementation.

A model call is NEVER required for the deterministic path to work.
"""
import re
import logging
from dataclasses import dataclass, field
from typing import List

logger = logging.getLogger(__name__)

# Sentence abbreviations that should NOT trigger a split on their period.
_ABBREVS = frozenset({
    "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "vs", "etc",
    "e.g", "i.e", "fig", "vol", "dept", "approx", "est", "no",
    "st", "ave", "blvd", "co", "corp", "inc", "ltd",
})

# Regex to find candidate sentence-terminal punctuation followed by whitespace
# and an uppercase letter, digit, or quote.
_CANDIDATE_SPLIT_RE = re.compile(r'([.!?]+)\s+(?=[A-Z0-9\"])')

# Secondary split: semicolons followed by coordinating conjunctions
_CONJUNCTION_SPLIT_RE = re.compile(
    r';\s*(and|but|however|yet|moreover|furthermore|additionally|also)\s+',
    re.IGNORECASE,
)

# Minimum characters for a fragment to count as a claim
_MIN_CLAIM_CHARS: int = 8


@dataclass
class ExtractedClaim:
    """A single discrete claim extracted from marketing content."""
    claim_id: str
    claim_text: str
    char_count: int = field(init=False)

    def __post_init__(self):
        self.char_count = len(self.claim_text)


class ClaimExtractor:
    """
    Deterministic sentence-splitting claim extractor.

    This implementation is intentionally simple and testable.  Every
    transformation is deterministic — the same input always produces the
    same output.

    The extractor is stateless and thread-safe.
    """

    def extract(self, content: str) -> List[ExtractedClaim]:
        """
        Splits marketing content into discrete, testable claims.

        Args:
            content: Raw marketing copy (non-empty string).

        Returns:
            List of ``ExtractedClaim`` objects, one per detected assertion.
            The list is always non-empty for non-empty, non-whitespace input.
            Each claim preserves the original wording as closely as possible.

        Raises:
            ValueError: If content is empty or whitespace-only.
        """
        if not content or not content.strip():
            raise ValueError("Marketing content cannot be empty or whitespace-only.")

        raw_sentences = self._split_into_sentences(content.strip())
        claims: List[ExtractedClaim] = []
        claim_index = 0

        for sentence in raw_sentences:
            # Secondary split on conjunction patterns after semicolons
            sub_parts = _CONJUNCTION_SPLIT_RE.split(sentence)
            for part in sub_parts:
                cleaned = self._clean_fragment(part)
                if cleaned and len(cleaned) >= _MIN_CLAIM_CHARS:
                    claim_index += 1
                    claims.append(
                        ExtractedClaim(
                            claim_id=f"claim-{claim_index}",
                            claim_text=cleaned,
                        )
                    )

        if not claims:
            # Fallback: treat entire stripped content as a single claim
            cleaned = self._clean_fragment(content.strip())
            if cleaned:
                claims.append(ExtractedClaim(claim_id="claim-1", claim_text=cleaned))

        logger.debug("Extracted %d claims from %d characters.", len(claims), len(content))
        return claims

    def _split_into_sentences(self, text: str) -> List[str]:
        """
        Split text on terminal punctuation while avoiding common false positives.

        The splitting is conservative: when in doubt, we keep sentences joined
        rather than over-fragment the input.
        """
        # Replace newline-separated paragraphs as sentence boundaries
        text = re.sub(r'\n{2,}', ' . ', text)
        text = re.sub(r'\n', ' ', text)

        sentences: List[str] = []
        last_idx = 0

        for match in _CANDIDATE_SPLIT_RE.finditer(text):
            punct = match.group(1)
            split_pos = match.start() + len(punct)
            # Check the word immediately before the punctuation
            prefix = text[last_idx:match.start()].strip()
            last_word_match = re.search(r'([a-zA-Z]+)$', prefix)
            if last_word_match:
                last_word = last_word_match.group(1).lower()
                if last_word in _ABBREVS:
                    # It's an abbreviation, do not split
                    continue

            # Valid sentence split
            segment = text[last_idx:split_pos].strip()
            if segment:
                sentences.append(segment)
            last_idx = match.end()

        # Append remaining text
        remaining = text[last_idx:].strip()
        if remaining:
            sentences.append(remaining)

        return sentences if sentences else [text]

    @staticmethod
    def _clean_fragment(text: str) -> str:
        """Normalize whitespace and punctuation for a single claim fragment."""
        # Remove leading conjunctions that may appear as split artefacts
        text = re.sub(
            r'^(and|but|yet|however|moreover|furthermore|additionally|also)\b\s*',
            '',
            text,
            flags=re.IGNORECASE,
        ).strip()
        # Collapse multiple spaces
        text = re.sub(r'\s+', ' ', text).strip()
        # Ensure sentence ends with terminal punctuation
        if text and not text[-1] in '.!?':
            text += '.'
        return text


# Module-level singleton
claim_extractor = ClaimExtractor()

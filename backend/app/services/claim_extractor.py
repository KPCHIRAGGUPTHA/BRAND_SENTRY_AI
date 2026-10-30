"""
Claim Extraction Service for BrandSentry AI — Phase 3 & Stage 1 Upgrade.

Converts raw marketing content into discrete, testable claims while rigorously
preserving qualifiers, conditional clauses, negations, numeric bounds, and context.

Capabilities:
------------
1. Multi-line marketing copy and bulleted lists (•, -, *, 1., etc.) are separated into individual claims.
2. Compound sentences joined by coordinating conjunctions (;, and/but/while/whereas with independent clauses)
   are split when both clauses represent independent assertions.
3. Complex numeric claims (percentages, decimals, units) are preserved without false splits.
4. Essential condition qualifiers ("When used...", "Unless approved...", "If applied...")
   are strictly preserved and never silently stripped.
5. Deterministic and thread-safe: same input always produces identical discrete claims.
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
    "st", "ave", "blvd", "co", "corp", "inc", "ltd", "u.s", "usa",
})

# Regex to find candidate sentence-terminal punctuation followed by whitespace
# and an uppercase letter, digit, quote, or bullet.
_CANDIDATE_SPLIT_RE = re.compile(r'([.!?]+)\s+(?=[A-Z0-9\"•\-\*\(])')

# Bullet point markers at line boundaries or after punctuation
_BULLET_PREFIX_RE = re.compile(
    r'(?:^|\n)\s*(?:[•\-\*–—\u2022\u25cf\u25cb\u25aa\u25ab\u25b6]|\(?\d+[\.\)]\s*)\s*',
    re.MULTILINE,
)

# Conjunction split: semicolons followed by coordinating conjunctions, OR
# comma + conjunction when introducing an independent clause with explicit subject
_COMPOUND_CLAUSE_SPLIT_RE = re.compile(
    r'(?:;\s*(?:and|but|however|yet|moreover|furthermore|additionally|also)\s+|'
    r';\s+|'
    r',\s*(?:and|but|while|whereas)\s+(?=(?:our|it|we|they|this|these|the|all|each|every|users|customers|results|formula)\b))',
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
    Enhanced deterministic claim extractor.

    Accurately decomposes compound marketing copy into individual compliance-testable
    claims while preserving conditions, negations, and factual qualifiers.
    """

    def extract(self, content: str) -> List[ExtractedClaim]:
        """
        Splits marketing content into discrete, testable claims.

        Args:
            content: Raw marketing copy (non-empty string).

        Returns:
            List of ExtractedClaim objects, preserving qualifiers and conditions.
        """
        if not content or not content.strip():
            raise ValueError("Marketing content cannot be empty or whitespace-only.")

        raw_segments = self._split_into_segments(content.strip())
        claims: List[ExtractedClaim] = []
        claim_index = 0

        for segment in raw_segments:
            # Compound clause splitting (preserving meaning and independent clauses)
            sub_parts = _COMPOUND_CLAUSE_SPLIT_RE.split(segment)
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

    def _split_into_segments(self, text: str) -> List[str]:
        """
        Splits text on bullet points, newlines, and terminal sentence punctuation,
        avoiding false splits on decimals, abbreviations, or units.
        """
        # Step 1: Pre-process bullet points and numbered list items
        # If text contains bullet points or distinct lines, split on them
        lines = text.splitlines()
        candidate_blocks: List[str] = []
        current_block: List[str] = []

        for line in lines:
            line_str = line.strip()
            if not line_str:
                if current_block:
                    candidate_blocks.append(" ".join(current_block))
                    current_block = []
                continue

            # Check if line begins with a bullet point or numbered item
            is_bullet = bool(re.match(r'^(?:[•\-\*–—\u2022\u25cf\u25cb\u25aa\u25ab\u25b6]|\(?\d+[\.\)]\s*)', line_str))
            if is_bullet:
                if current_block:
                    candidate_blocks.append(" ".join(current_block))
                    current_block = []
                # Strip leading bullet symbol but keep the rest
                cleaned_line = re.sub(r'^(?:[•\-\*–—\u2022\u25cf\u25cb\u25aa\u25ab\u25b6]|\(?\d+[\.\)]\s*)\s*', '', line_str)
                candidate_blocks.append(cleaned_line)
            else:
                current_block.append(line_str)

        if current_block:
            candidate_blocks.append(" ".join(current_block))

        # Step 2: For each block, split on sentence-terminal punctuation
        sentences: List[str] = []
        for block in candidate_blocks:
            norm_block = re.sub(r'\s+', ' ', block).strip()
            if not norm_block:
                continue

            last_idx = 0
            for match in _CANDIDATE_SPLIT_RE.finditer(norm_block):
                punct = match.group(1)
                split_pos = match.start() + len(punct)
                
                # Check preceding word to avoid splitting abbreviations (e.g. "Dr.", "e.g.", "U.S.")
                prefix = norm_block[last_idx:match.start()].strip()
                last_word_match = re.search(r'([a-zA-Z\.]+)$', prefix)
                if last_word_match:
                    last_word = last_word_match.group(1).lower().rstrip('.')
                    if last_word in _ABBREVS:
                        continue

                # Check if preceding character is digit and following is digit (decimal check)
                if match.start() > 0 and match.start() < len(norm_block) - 1:
                    prev_char = norm_block[match.start() - 1]
                    next_char = norm_block[match.end()] if match.end() < len(norm_block) else ''
                    if prev_char.isdigit() and next_char.isdigit():
                        continue

                segment = norm_block[last_idx:split_pos].strip()
                if segment:
                    sentences.append(segment)
                last_idx = match.end()

            remaining = norm_block[last_idx:].strip()
            if remaining:
                sentences.append(remaining)

        return sentences if sentences else [text]

    @staticmethod
    def _clean_fragment(text: str) -> str:
        """
        Normalize whitespace and punctuation for a single claim fragment.
        Preserves conditional qualifiers ('Unless...', 'When...', 'If...').
        """
        # Strip bullet or numbered list artefacts at start
        text = re.sub(r'^[•\-\*–—\u2022\u25cf\u25cb\u25aa\u25ab\u25b6\s]+', '', text).strip()
        text = re.sub(r'^\(?\d+[\.\)]\s*', '', text).strip()

        # Remove leading coordinating conjunctions that appear purely as split artefacts
        text = re.sub(
            r'^(?:and|but|yet|however|moreover|furthermore|additionally|also)\b\s*',
            '',
            text,
            flags=re.IGNORECASE,
        ).strip()

        # Collapse whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        # Ensure sentence ends with terminal punctuation
        if text and not text[-1] in '.!?':
            text += '.'
        return text


# Module-level singleton
claim_extractor = ClaimExtractor()

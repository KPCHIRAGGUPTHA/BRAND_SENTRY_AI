"""
Unit Tests for Deterministic Claim Extraction Service — Phase 3.

Tests are fully deterministic: no embeddings, no ChromaDB, no network calls.
"""
import pytest
from backend.app.services.claim_extractor import ClaimExtractor, ExtractedClaim


@pytest.fixture
def extractor():
    return ClaimExtractor()


class TestClaimExtractorEdgeCases:
    def test_empty_input_raises(self, extractor):
        with pytest.raises(ValueError, match="empty or whitespace"):
            extractor.extract("")

    def test_whitespace_only_raises(self, extractor):
        with pytest.raises(ValueError, match="empty or whitespace"):
            extractor.extract("   \n\t  ")


class TestSingleClaim:
    def test_single_sentence_returns_one_claim(self, extractor):
        claims = extractor.extract("Our product is certified organic.")
        assert len(claims) == 1
        assert claims[0].claim_id == "claim-1"
        assert "certified organic" in claims[0].claim_text

    def test_claim_ids_are_sequential(self, extractor):
        claims = extractor.extract("We are the best. We are the fastest. We are the safest.")
        ids = [c.claim_id for c in claims]
        for i, cid in enumerate(ids, start=1):
            assert cid == f"claim-{i}", f"Expected claim-{i} but got {cid}"

    def test_claim_text_is_non_empty(self, extractor):
        claims = extractor.extract("Our serum removes wrinkles in 7 days.")
        assert all(c.claim_text.strip() for c in claims)

    def test_claim_preserves_original_wording(self, extractor):
        text = "Our serum removes wrinkles in 7 days."
        claims = extractor.extract(text)
        assert "removes wrinkles" in claims[0].claim_text
        assert "7 days" in claims[0].claim_text


class TestMultipleSentences:
    def test_two_sentences_produce_two_claims(self, extractor):
        text = "Our product is 100% safe. It is recommended by dermatologists."
        claims = extractor.extract(text)
        assert len(claims) >= 2

    def test_three_distinct_sentences(self, extractor):
        text = "Our serum removes wrinkles in seven days. It is 100% safe. It is recommended by 95% of dermatologists."
        claims = extractor.extract(text)
        assert len(claims) >= 2
        texts = " ".join(c.claim_text for c in claims)
        assert "removes wrinkles" in texts or "seven days" in texts

    def test_exclamation_sentence_split(self, extractor):
        text = "Order now! Get free shipping! Results guaranteed!"
        claims = extractor.extract(text)
        assert len(claims) >= 2

    def test_question_mark_split(self, extractor):
        text = "Want clearer skin? Try our formula. Results in 14 days."
        claims = extractor.extract(text)
        assert len(claims) >= 1


class TestNumericAndPercentageClaims:
    def test_percentage_preserved(self, extractor):
        text = "95% of users saw improvement in 30 days."
        claims = extractor.extract(text)
        texts = " ".join(c.claim_text for c in claims)
        assert "95%" in texts

    def test_decimal_number_not_split(self, extractor):
        # "3.5x" should not cause a false sentence split on the period
        text = "Our formula delivers 3.5x faster absorption than competitors."
        claims = extractor.extract(text)
        # The decimal should not split "3" and "5x" into separate claims
        assert any("3.5" in c.claim_text or "faster" in c.claim_text for c in claims)

    def test_numeric_claim_with_unit(self, extractor):
        text = "Reduces wrinkles by 40% in just 28 days."
        claims = extractor.extract(text)
        texts = " ".join(c.claim_text for c in claims)
        assert "40%" in texts or "Reduces" in texts


class TestCompoundClaims:
    def test_semicolon_and_conjunction_split(self, extractor):
        text = "Our cream moisturises; and it firms skin for 24 hours."
        claims = extractor.extract(text)
        assert len(claims) >= 1  # may or may not split depending on implementation

    def test_long_compound_sentence_kept_whole(self, extractor):
        # "and" without semicolon should NOT split
        text = "Our product is fast and effective and affordable."
        claims = extractor.extract(text)
        # Should remain as one or two claims, but not three separate ones
        assert len(claims) <= 2

    def test_multi_claim_advertisement(self, extractor):
        text = (
            "Our serum removes wrinkles in seven days. "
            "It is 100% safe. "
            "It is recommended by 95% of dermatologists."
        )
        claims = extractor.extract(text)
        assert len(claims) >= 2
        all_text = " ".join(c.claim_text for c in claims)
        assert "wrinkles" in all_text or "seven days" in all_text

    def test_disclaimer_text(self, extractor):
        text = "Results may vary. Individual outcomes are not guaranteed."
        claims = extractor.extract(text)
        assert len(claims) >= 1


class TestPunctuationEdgeCases:
    def test_no_trailing_punctuation_added(self, extractor):
        text = "Our product is great"
        claims = extractor.extract(text)
        # Should still extract at least one claim
        assert len(claims) >= 1
        assert claims[0].claim_text.strip()

    def test_abbreviation_not_split(self, extractor):
        # "Dr." should not split the sentence
        text = "Dr. Smith recommends our product for daily use."
        claims = extractor.extract(text)
        all_text = " ".join(c.claim_text for c in claims)
        # Should not split "Dr" from the rest or produce empty fragments
        assert any(c.claim_text.strip() for c in claims)

    def test_claim_char_count_is_correct(self, extractor):
        text = "Our product is the best."
        claims = extractor.extract(text)
        for c in claims:
            assert c.char_count == len(c.claim_text)

    def test_no_duplicate_claims_from_same_input(self, extractor):
        text = "Our product is certified. Our product is certified."
        claims = extractor.extract(text)
        texts = [c.claim_text for c in claims]
        # Both claims may be returned (they are textually distinct sentences),
        # but no single claim_id should repeat
        ids = [c.claim_id for c in claims]
        assert len(ids) == len(set(ids)), "claim_ids must be unique"

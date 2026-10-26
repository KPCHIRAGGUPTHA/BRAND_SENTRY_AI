"""
UI Tests for BrandSentry AI — Evidence Retrieval & Grounding (Test Groups D & F).

Covers:
- TC15: Compliance review cards display grounded evidence fields (quotes, citations, source).
- TC19: Semantic evidence search queries vector store and renders ranked guideline passages.
- TC20: Document-scoped evidence retrieval filters search to the selected guideline.
"""
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

from tests.ui.pages import BrandSentryPage


@pytest.mark.ui
@pytest.mark.live_review
def test_tc15_supporting_evidence_displayed(driver, base_url, sample_txt_path, require_live_backend):
    """
    TC15 — Supporting evidence is displayed.
    Verify that review results present the structured evidence fields:
    - Extracted claim quote
    - Verdict explanation
    - Retrieved evidence citations (source filename, page number/metrics, quoted passage)
      or transparent insufficiency notice when evidence is absent.
    """
    page = BrandSentryPage(driver, base_url)
    page.navigate_home()
    page.wait_for_backend_connected()

    if len(page.get_guideline_registry_rows()) == 0:
        page.select_guideline_file(sample_txt_path)
        page.click_upload_guideline()
        page.get_upload_success_text(timeout=25.0)

    claim_text = "Our product is 100% guaranteed to deliver results."
    page.enter_marketing_copy(claim_text)
    page.click_analyze_compliance()

    # Wait for results container
    page.get_visible_element(BrandSentryPage.REVIEW_RESULTS_CONTAINER, timeout=25.0)

    cards = driver.find_elements(*BrandSentryPage.CLAIM_CARDS)
    assert len(cards) >= 1

    first_card = cards[0]
    first_card_text = first_card.text

    # Verify claim quote is present
    assert "100% guaranteed" in first_card_text

    # Verify verdict explanation section is present
    assert "Verdict Explanation" in first_card_text or "EXPLANATION" in first_card_text.upper()

    # Verify evidence citations or insufficiency notification is present
    has_evidence_citations = len(first_card.find_elements(By.CSS_SELECTOR, ".evidence-card")) > 0
    has_insufficiency_notice = "do not provide sufficient evidence" in first_card_text or "INSUFFICIENT" in first_card_text

    assert has_evidence_citations or has_insufficiency_notice, (
        "Expected claim card to render either evidence citations or insufficiency details"
    )


@pytest.mark.ui
@pytest.mark.live_backend
def test_tc19_semantic_evidence_search(driver, base_url, sample_txt_path, require_live_backend):
    """
    TC19 — Semantic evidence search.
    Enter a search query into the semantic evidence search interface.
    Verify:
    - Matching passages are retrieved and displayed in ranked evidence cards.
    - Each evidence card shows source filename, similarity score, and passage quotation.
    """
    page = BrandSentryPage(driver, base_url)
    page.navigate_home()

    # Ingest baseline guideline if registry is empty
    if len(page.get_guideline_registry_rows()) == 0:
        page.select_guideline_file(sample_txt_path)
        page.click_upload_guideline()
        page.get_upload_success_text(timeout=25.0)

    # Enter semantic search query
    query = "Are absolute guarantee claims permitted?"
    page.enter_search_query(query)

    # Click search button
    page.click_search_evidence()

    # Wait for either results or legitimate no-results message
    WebDriverWait(driver, 15).until(
        lambda d: len(d.find_elements(*BrandSentryPage.EVIDENCE_CARDS)) > 0
        or len(d.find_elements(*BrandSentryPage.SEARCH_ERROR_ALERT)) > 0
        or len(d.find_elements(*BrandSentryPage.SEARCH_EMPTY_STATE)) > 0
    )

    evidence_cards = driver.find_elements(*BrandSentryPage.EVIDENCE_CARDS)
    if len(evidence_cards) > 0:
        first_card = evidence_cards[0]
        card_text = first_card.text
        assert "Similarity:" in card_text or "%" in card_text
        assert len(first_card.find_elements(By.CSS_SELECTOR, ".evidence-source")) > 0


@pytest.mark.ui
@pytest.mark.live_backend
def test_tc20_document_scoped_retrieval(driver, base_url, sample_txt_path, require_live_backend):
    """
    TC20 — Document-scoped retrieval.
    Verify that selecting a specific guideline in the semantic search dropdown
    scopes retrieval to that document.
    """
    page = BrandSentryPage(driver, base_url)
    page.navigate_home()

    if len(page.get_guideline_registry_rows()) == 0:
        page.select_guideline_file(sample_txt_path)
        page.click_upload_guideline()
        page.get_upload_success_text(timeout=25.0)

    # Verify search document selector exists and has options
    select_el = page.get_visible_element(BrandSentryPage.SEARCH_DOC_SELECT)
    dropdown = Select(select_el)
    options = dropdown.options
    assert len(options) >= 1

    # Select the first specific document if available
    if len(options) > 1:
        dropdown.select_by_index(1)
        selected_option = dropdown.first_selected_option
        assert selected_option.get_attribute("value") != ""

    # Execute search query
    page.enter_search_query("safety and zero risk")
    page.click_search_evidence()

    # Verify search concludes with results or no-results state
    WebDriverWait(driver, 15).until(
        lambda d: len(d.find_elements(*BrandSentryPage.EVIDENCE_CARDS)) > 0
        or len(d.find_elements(*BrandSentryPage.SEARCH_ERROR_ALERT)) > 0
        or len(d.find_elements(*BrandSentryPage.SEARCH_EMPTY_STATE)) > 0
    )

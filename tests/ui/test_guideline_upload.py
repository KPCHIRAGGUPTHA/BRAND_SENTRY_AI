"""
UI Tests for BrandSentry AI — Guideline Ingestion and Registry (Test Group C).

Covers:
- TC07: Valid TXT guideline upload and indexing in vector store.
- TC08: Valid PDF guideline upload and indexing with PyMuPDF parser.
- TC10: Uploaded guidelines appear in the Document Registry table.
- TC11: Selecting an indexed guideline reflects in the interface and scoping selectors.
"""
import os
import time
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from tests.ui.pages import BrandSentryPage


@pytest.mark.ui
@pytest.mark.live_backend
def test_tc07_valid_txt_guideline_upload(driver, base_url, sample_txt_path, require_live_backend):
    """
    TC07 — Valid TXT guideline upload.
    Upload a valid small test guideline file.
    Verify:
    - File is selected and displayed in upload panel.
    - Application extracts text, chunks content, and indexes into ChromaDB.
    - Application displays success notification with indexed chunk count.
    """
    page = BrandSentryPage(driver, base_url)
    page.navigate_home()

    # Select the valid TXT fixture
    page.select_guideline_file(sample_txt_path)

    # Verify selected file row appears
    upload_btn = page.get_visible_element(BrandSentryPage.UPLOAD_BUTTON)
    assert upload_btn.is_displayed()

    # Click Upload & Index
    page.click_upload_guideline()

    # Wait for success alert
    success_text = page.get_upload_success_text(timeout=25.0)
    assert "Successfully indexed" in success_text
    assert "sample_guideline.txt" in success_text
    assert "ChromaDB" in success_text


@pytest.mark.ui
@pytest.mark.live_backend
def test_tc08_valid_pdf_guideline_upload(driver, base_url, sample_pdf_path, require_live_backend):
    """
    TC08 — Valid PDF guideline upload.
    Upload a small valid PDF test fixture.
    Verify:
    - Application extracts text and reports successful upload and indexing.
    - Success notification indicates parsed chunks.
    """
    page = BrandSentryPage(driver, base_url)
    page.navigate_home()

    # Select the valid PDF fixture
    page.select_guideline_file(sample_pdf_path)

    # Click Upload & Index
    page.click_upload_guideline()

    # Wait for success alert
    success_text = page.get_upload_success_text(timeout=25.0)
    assert "Successfully indexed" in success_text
    assert "sample_guideline.pdf" in success_text


@pytest.mark.ui
@pytest.mark.live_backend
def test_tc10_guideline_registry_populated(driver, base_url, sample_txt_path, require_live_backend):
    """
    TC10 — Guideline registry.
    Verify that uploaded guidelines appear in the document registry table
    with filename, format badge, chunk counts, and indexed status.
    """
    page = BrandSentryPage(driver, base_url)
    page.navigate_home()

    # Ensure at least one guideline is uploaded
    rows = page.get_guideline_registry_rows()
    if len(rows) == 0:
        page.select_guideline_file(sample_txt_path)
        page.click_upload_guideline()
        page.get_upload_success_text(timeout=25.0)

    # Refresh or wait for document registry table
    WebDriverWait(driver, 10).until(
        lambda d: len(d.find_elements(*BrandSentryPage.DOCUMENT_ROWS)) > 0
    )

    rows = page.get_guideline_registry_rows()
    assert len(rows) >= 1, "Expected at least 1 guideline row in registry table"

    # Verify first row contains indexed badge and chunk count
    first_row = rows[0]
    row_text = first_row.text
    assert "Indexed" in row_text
    assert "chunks" in row_text


@pytest.mark.ui
@pytest.mark.live_backend
def test_tc11_guideline_selection_reflected(driver, base_url, sample_txt_path, require_live_backend):
    """
    TC11 — Guideline selection.
    Select an indexed guideline in the registry and verify that
    the selection is highlighted and reflected in scoping selectors.
    """
    page = BrandSentryPage(driver, base_url)
    page.navigate_home()

    # Ensure document rows exist
    rows = page.get_guideline_registry_rows()
    if len(rows) == 0:
        page.select_guideline_file(sample_txt_path)
        page.click_upload_guideline()
        page.get_upload_success_text(timeout=25.0)
        WebDriverWait(driver, 10).until(
            lambda d: len(d.find_elements(*BrandSentryPage.DOCUMENT_ROWS)) > 0
        )
        rows = page.get_guideline_registry_rows()

    # Click the first row to select it
    first_row = rows[0]
    first_row.click()

    # Verify row receives selected style class or action button indicates Selected
    WebDriverWait(driver, 5).until(
        lambda d: "selected-row" in (first_row.get_attribute("class") or "") or "Selected" in first_row.text
    )

    action_btn = first_row.find_element(By.CSS_SELECTOR, "button")
    assert "Selected" in action_btn.text

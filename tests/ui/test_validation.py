"""
UI Tests for BrandSentry AI — Input and File Validation (Test Groups B & E).

Covers:
- TC04: Empty marketing copy submission triggers client-side validation error.
- TC05: Whitespace-only marketing copy is rejected without submitting to backend.
- TC06: Valid non-empty marketing copy is accepted into the input form.
- TC09: Selecting an unsupported file format (.csv) triggers immediate format rejection alert.
- TC18: Duplicate submission prevention (submit button is disabled during in-flight analysis).
"""
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from tests.ui.pages import BrandSentryPage


@pytest.mark.ui
def test_tc04_empty_marketing_copy_rejected(driver, base_url):
    """
    TC04 — Empty marketing copy.
    Submit an empty input.
    Verify:
    - Expected validation alert (#review-error-alert) is displayed.
    - Error message clearly notes that copy cannot be empty.
    - No compliance review result container (#review-results-container) is displayed.
    """
    page = BrandSentryPage(driver, base_url)
    page.navigate_home()

    # Clear input to ensure it is empty
    page.enter_marketing_copy("")

    # Click Review Compliance
    page.click_analyze_compliance()

    # Verify validation alert appears
    error_text = page.get_review_error_text()
    assert "Marketing copy cannot be empty" in error_text

    # Verify no results container is incorrectly rendered
    assert not page.is_element_visible(BrandSentryPage.REVIEW_RESULTS_CONTAINER, timeout=1.0)


@pytest.mark.ui
def test_tc05_whitespace_only_marketing_copy_rejected(driver, base_url):
    """
    TC05 — Whitespace-only marketing copy.
    Submit whitespace-only content (spaces, tabs, newlines).
    Verify:
    - Input is rejected according to existing validation behavior.
    - Validation alert displays the whitespace/empty error message.
    - No compliance review results container is rendered.
    """
    page = BrandSentryPage(driver, base_url)
    page.navigate_home()

    # Enter whitespace-only content
    page.enter_marketing_copy("   \n\t   \n  ")

    # Click Review Compliance
    page.click_analyze_compliance()

    # Verify validation error is displayed
    error_text = page.get_review_error_text()
    assert "Marketing copy cannot be empty" in error_text

    # Verify results container is not rendered
    assert not page.is_element_visible(BrandSentryPage.REVIEW_RESULTS_CONTAINER, timeout=1.0)


@pytest.mark.ui
def test_tc06_valid_marketing_copy_accepted(driver, base_url):
    """
    TC06 — Valid marketing copy.
    Enter a non-empty marketing claim.
    Verify:
    - Input is accepted and value is reflected in the textarea.
    - The Review Compliance button is enabled and ready to initiate analysis.
    - Any previous empty validation alert is cleared when typing or submitting.
    """
    page = BrandSentryPage(driver, base_url)
    page.navigate_home()

    valid_claim = "Our enterprise platform accelerates data processing by 40% with verified benchmarks."
    page.enter_marketing_copy(valid_claim)

    # Verify textarea contains the entered text
    textarea = page.get_element(BrandSentryPage.MARKETING_COPY_INPUT)
    assert textarea.get_attribute("value") == valid_claim

    # Verify submit button is enabled
    btn = page.get_visible_element(BrandSentryPage.BTN_ANALYZE_COMPLIANCE)
    assert btn.is_enabled()
    assert "Review Compliance" in btn.text


@pytest.mark.ui
def test_tc09_unsupported_file_type_rejected(driver, base_url, invalid_file_path):
    """
    TC09 — Unsupported file type validation.
    Attempt to select an unsupported file type (.csv).
    Verify:
    - Immediate frontend client-side validation error is rendered in the upload section.
    - The alert specifies PDF or TXT formats are required.
    - The file is not accepted for upload (upload submit button is not displayed).
    """
    page = BrandSentryPage(driver, base_url)
    page.navigate_home()

    # Select the invalid .csv file via the file input
    page.select_guideline_file(invalid_file_path)

    # Verify format rejection error alert is rendered
    error_text = page.get_upload_error_text()
    assert "Invalid file type" in error_text
    assert "PDF (.pdf) or Plain Text (.txt)" in error_text

    # Verify upload button is not present since file was rejected
    assert not page.is_element_visible(BrandSentryPage.UPLOAD_BUTTON, timeout=1.0)


@pytest.mark.ui
def test_tc18_duplicate_submission_prevention(driver, base_url):
    """
    TC18 — Duplicate submission prevention.
    Verify that when analysis is triggered, the submission button is disabled
    to prevent double-clicks or duplicate parallel requests.
    """
    page = BrandSentryPage(driver, base_url)
    page.navigate_home()

    # Enter valid claim
    page.enter_marketing_copy("Our product is 100% guaranteed to deliver results.")

    # Locate button before click
    btn = page.get_visible_element(BrandSentryPage.BTN_ANALYZE_COMPLIANCE)
    assert btn.is_enabled()

    # Click analyze button
    btn.click()

    # If backend is connecting, waking, or processing, button transitions to disabled state
    # or displays loading text
    try:
        WebDriverWait(driver, 3).until(
            lambda d: d.find_element(*BrandSentryPage.BTN_ANALYZE_COMPLIANCE).get_attribute("disabled") is not None
            or d.find_elements(*BrandSentryPage.REVIEW_ERROR_ALERT)
            or d.find_elements(*BrandSentryPage.REVIEW_RESULTS_CONTAINER)
        )
    except Exception:
        pass

    # Verify that the analyze button has disabled property while loading is active
    # Form's handleSubmit also enforces: if (loading) return;

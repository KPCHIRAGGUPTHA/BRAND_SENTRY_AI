"""
UI test for the judge quick-start: load the sample guideline from the page, then check the four
documented claims and what the page shows for each.
"""
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from tests.ui.pages import BrandSentryPage


def _review(page, driver, claim):
    page.enter_marketing_copy(claim)
    previous = driver.find_elements(By.ID, "review-results-container")
    page.click_analyze_compliance()
    if previous:
        WebDriverWait(driver, 30).until(lambda d: claim in d.find_element(By.ID, "review-results-container").text)
    card = WebDriverWait(driver, 60).until(lambda d: d.find_element(*page.CLAIM_CARDS))
    WebDriverWait(driver, 30).until(lambda d: claim in d.find_element(*page.CLAIM_CARDS).text)
    return driver.find_element(*page.CLAIM_CARDS).text


@pytest.mark.ui
@pytest.mark.live_review
def test_judge_quick_start(driver, base_url, require_live_backend):
    page = BrandSentryPage(driver, base_url)
    page.navigate_home()
    page.wait_for_backend_connected()

    button = page.get_element(page.LOAD_SAMPLE_BUTTON)
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
    button.click()
    assert "ready for review" in page.get_upload_success_text(timeout=120.0)

    logo = _review(page, driver, "Brand logo appears in the top-left corner with a 25px clear buffer margin.")
    assert "SUPPORTED" in logo
    assert "at least 20px clear buffer margin" in logo

    guarantee = _review(page, driver, "Our platform guarantees 100% impenetrable barrier against ransomware.")
    assert "CONTRADICTED" in guarantee
    assert "impossible to hack" in guarantee

    identifier = _review(
        page, driver, "Medical devices distributed under clinical guidelines display registration code 4412-K."
    )
    assert "INSUFFICIENT_EVIDENCE" in identifier
    assert "9845-A" in identifier

    drift = _review(page, driver, "Our software always improves team productivity.")
    assert "CERTAINTY_SHIFT" in drift
    assert "Rewrite" in drift or "rewrite" in drift or "Suggested" in drift

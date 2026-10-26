"""
UI Tests for BrandSentry AI — Homepage and Navigation (Test Group A).

Covers:
- TC01: Homepage loads successfully with header, hero, review form, and guideline interface.
- TC02: Main navigation links route/scroll to respective sections.
- TC03: Compliance review form controls (textarea, submit button, scope selector) are visible.
"""
import pytest
from selenium.webdriver.common.by import By  # type: ignore
from selenium.webdriver.support.ui import WebDriverWait  # type: ignore
from selenium.webdriver.support import expected_conditions as EC  # type: ignore


from tests.ui.pages import BrandSentryPage


@pytest.mark.ui
def test_tc01_homepage_loads_successfully(driver, base_url):
    """
    TC01 — Homepage loads successfully.
    Verify:
    - Frontend loads without fatal errors.
    - BrandSentry AI primary heading is visible in Hero section.
    - The compliance review form container (#review) is present.
    - The guideline upload interface (#guidelines) is present.
    """
    page = BrandSentryPage(driver, base_url)
    page.navigate_home()

    # Verify primary heading
    hero_title = page.get_visible_element(BrandSentryPage.HERO_TITLE)
    assert "BrandSentry AI" in hero_title.text

    # Verify subtitle
    hero_subtitle = page.get_visible_element(BrandSentryPage.HERO_SUBTITLE)
    assert "Brand Compliance Intelligence" in hero_subtitle.text

    # Verify compliance review section presence
    assert page.is_element_present(BrandSentryPage.REVIEW_SECTION)

    # Verify guideline upload section presence
    assert page.is_element_present(BrandSentryPage.GUIDELINES_SECTION)

    # Verify status and architecture section presence
    assert page.is_element_present(BrandSentryPage.STATUS_SECTION)


@pytest.mark.ui
def test_tc02_navigation_works(driver, base_url):
    """
    TC02 — Navigation works.
    Verify that existing header navigation links correctly point to their sections.
    """
    page = BrandSentryPage(driver, base_url)
    page.navigate_home()

    # Check navigation links exist with correct href targets
    nav_targets = [
        (BrandSentryPage.NAV_CLAIM_REVIEW, "#review"),
        (BrandSentryPage.NAV_GUIDELINES, "#guidelines"),
        (BrandSentryPage.NAV_SEARCH, "#search"),
        (BrandSentryPage.NAV_STATUS, "#status"),
    ]

    for locator, expected_hash in nav_targets:
        link = page.get_visible_element(locator)
        href = link.get_attribute("href") or ""
        assert expected_hash in href, f"Expected {expected_hash} in navigation link href, got '{href}'"

    # Verify API Docs external link
    docs_link = page.get_element(BrandSentryPage.NAV_API_DOCS)
    assert docs_link.get_attribute("target") == "_blank"
    assert "/docs" in (docs_link.get_attribute("href") or "")

    # Test clicking navigation link modifies URL hash and scrolls to section
    guidelines_nav = page.get_visible_element(BrandSentryPage.NAV_GUIDELINES)
    guidelines_nav.click()
    WebDriverWait(driver, 5).until(lambda d: "#guidelines" in d.current_url)
    assert "#guidelines" in driver.current_url


@pytest.mark.ui
def test_tc03_compliance_form_is_visible(driver, base_url):
    """
    TC03 — Compliance form is visible.
    Verify:
    - The marketing copy textarea input is visible.
    - The Review Compliance button is visible.
    - The guideline scope selector is present and populated.
    """
    page = BrandSentryPage(driver, base_url)
    page.navigate_home()

    # Marketing copy textarea
    copy_input = page.get_visible_element(BrandSentryPage.MARKETING_COPY_INPUT)
    assert copy_input.is_displayed()
    assert copy_input.is_enabled()

    # Review Compliance submit button
    review_button = page.get_visible_element(BrandSentryPage.BTN_ANALYZE_COMPLIANCE)
    assert review_button.is_displayed()
    assert review_button.is_enabled()
    assert "Review Compliance" in review_button.text

    # Guideline scoping selector
    scope_select = page.get_visible_element(BrandSentryPage.GUIDELINE_SCOPE_SELECT)
    assert scope_select.is_displayed()
    # Ensure default option is "all"
    selected_value = scope_select.get_attribute("value")
    assert selected_value == "all"

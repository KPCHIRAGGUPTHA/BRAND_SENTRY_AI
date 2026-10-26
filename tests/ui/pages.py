"""
Page Object Model and UI Locator Helpers for BrandSentry AI.
Contains all verified DOM element selectors, waiting abstractions,
and interaction helpers.
"""
from typing import List, Optional
from selenium.webdriver.common.by import By  # type: ignore
from selenium.webdriver.remote.webdriver import WebDriver  # type: ignore
from selenium.webdriver.remote.webelement import WebElement  # type: ignore
from selenium.webdriver.support.ui import WebDriverWait, Select  # type: ignore
from selenium.webdriver.support import expected_conditions as EC  # type: ignore
from selenium.common.exceptions import TimeoutException, NoSuchElementException  # type: ignore



class BrandSentryPage:
    """Encapsulates UI interactions and verified element locators for BrandSentry AI."""

    # Header and Navigation
    LOGO_LINK = (By.CSS_SELECTOR, "a.logo-group")
    NAV_CLAIM_REVIEW = (By.CSS_SELECTOR, "nav a[href='#review']")
    NAV_GUIDELINES = (By.CSS_SELECTOR, "nav a[href='#guidelines']")
    NAV_SEARCH = (By.CSS_SELECTOR, "nav a[href='#search']")
    NAV_STATUS = (By.CSS_SELECTOR, "nav a[href='#status']")
    NAV_API_DOCS = (By.CSS_SELECTOR, "nav a[href*='/docs']")

    # Hero Section
    HERO_TITLE = (By.CSS_SELECTOR, "h1.hero-title")
    HERO_SUBTITLE = (By.CSS_SELECTOR, "p.hero-subtitle")

    # Claim Review Section
    REVIEW_SECTION = (By.ID, "review")
    MARKETING_COPY_INPUT = (By.ID, "marketing-copy-input")
    BTN_ANALYZE_COMPLIANCE = (By.ID, "btn-analyze-compliance")
    GUIDELINE_SCOPE_SELECT = (By.ID, "guideline-scope-select")
    REVIEW_ERROR_ALERT = (By.ID, "review-error-alert")
    REVIEW_RESULTS_CONTAINER = (By.ID, "review-results-container")
    SUMMARY_TOTAL_CLAIMS = (By.ID, "summary-total-claims")
    SUMMARY_SUPPORTED_CLAIMS = (By.ID, "summary-supported-claims")
    SUMMARY_CONTRADICTED_CLAIMS = (By.ID, "summary-contradicted-claims")
    SUMMARY_INSUFFICIENT_CLAIMS = (By.ID, "summary-insufficient-claims")
    FILL_SAMPLE_BUTTON = (By.XPATH, "//button[contains(., 'Fill Sample Copy')]")
    CLEAR_COPY_BUTTON = (By.XPATH, "//button[contains(., 'Clear')]")
    CLAIM_CARDS = (By.CSS_SELECTOR, "article[id^='claim-verdict-card-']")

    # Guideline Upload and Explorer Section
    GUIDELINES_SECTION = (By.ID, "guidelines")
    GUIDELINE_FILE_INPUT = (By.ID, "guideline-file-input")
    UPLOAD_DROPZONE = (By.CSS_SELECTOR, "label.upload-dropzone")
    UPLOAD_BUTTON = (By.XPATH, "//button[contains(., 'Upload & Index') or contains(., 'Extracting & Indexing...')]")
    UPLOAD_SUCCESS_ALERT = (By.CSS_SELECTOR, "#guidelines .alert-success")
    UPLOAD_ERROR_ALERT = (By.CSS_SELECTOR, "#guidelines .alert-error")
    DOCUMENT_TABLE = (By.CSS_SELECTOR, "table.document-table")
    DOCUMENT_ROWS = (By.CSS_SELECTOR, "table.document-table tbody tr")

    # Semantic Evidence Search Section
    SEARCH_SECTION = (By.ID, "search")
    SEARCH_DOC_SELECT = (By.ID, "guideline-select")
    QUERY_INPUT = (By.ID, "query-input")
    SEARCH_BUTTON = (By.XPATH, "//section[@id='search']//button[@type='submit']")
    EVIDENCE_CARDS = (By.CSS_SELECTOR, "#search .evidence-card")
    SEARCH_EMPTY_STATE = (By.CSS_SELECTOR, "#search .empty-state")
    SEARCH_ERROR_ALERT = (By.CSS_SELECTOR, "#search .alert-warning")

    # System Status Section
    STATUS_SECTION = (By.ID, "status")
    STATUS_BADGE = (By.CSS_SELECTOR, "#status [id^='status-badge-']")
    STATUS_BADGE_CONNECTED = (By.ID, "status-badge-connected")

    def __init__(self, driver: WebDriver, base_url: str):
        self.driver = driver
        self.base_url = base_url

    def navigate_home(self):
        """Navigate to the base frontend URL and wait for DOM readiness."""
        self.driver.get(self.base_url)
        WebDriverWait(self.driver, 15).until(
            EC.presence_of_element_located(self.HERO_TITLE)
        )

    def wait_for_backend_connected(self, timeout: float = 15.0):
        """Wait for the frontend health check to confirm connected backend status."""
        try:
            WebDriverWait(self.driver, 2.0).until(
                EC.visibility_of_element_located(self.STATUS_BADGE_CONNECTED)
            )
            return
        except TimeoutException:
            pass

        # If not connected yet (e.g. React 18 StrictMode abort), trigger manual check
        try:
            recheck_btn = self.driver.find_element(By.ID, "btn-recheck-health")
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", recheck_btn)
            recheck_btn.click()
        except Exception:
            pass

        WebDriverWait(self.driver, timeout).until(
            EC.visibility_of_element_located(self.STATUS_BADGE_CONNECTED)
        )

    def get_element(self, locator: tuple, timeout: float = 10.0) -> WebElement:
        """Find an element with explicit wait."""
        return WebDriverWait(self.driver, timeout).until(
            EC.presence_of_element_located(locator)
        )

    def get_visible_element(self, locator: tuple, timeout: float = 10.0) -> WebElement:
        """Find an element and wait until it is visible."""
        return WebDriverWait(self.driver, timeout).until(
            EC.visibility_of_element_located(locator)
        )

    def is_element_present(self, locator: tuple, timeout: float = 2.0) -> bool:
        """Check whether an element is present within a brief timeout."""
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located(locator)
            )
            return True
        except TimeoutException:
            return False

    def is_element_visible(self, locator: tuple, timeout: float = 2.0) -> bool:
        """Check whether an element is visible within a brief timeout."""
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.visibility_of_element_located(locator)
            )
            return True
        except TimeoutException:
            return False

    def enter_marketing_copy(self, text: str):
        """Clear and enter text into the marketing copy textarea with React event synchronization."""
        textarea = self.get_visible_element(self.MARKETING_COPY_INPUT)
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", textarea)
        textarea.click()
        self.driver.execute_script(
            """
            var el = arguments[0];
            var value = arguments[1];
            var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value").set;
            nativeInputValueSetter.call(el, value);
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            """,
            textarea,
            text,
        )


    def click_analyze_compliance(self):
        """Click the Review Compliance button."""
        btn = self.get_element(self.BTN_ANALYZE_COMPLIANCE)
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
        WebDriverWait(self.driver, 5).until(EC.element_to_be_clickable(self.BTN_ANALYZE_COMPLIANCE))
        btn.click()

    def get_review_error_text(self, timeout: float = 5.0) -> str:
        """Get the text of the review error alert."""
        alert = self.get_visible_element(self.REVIEW_ERROR_ALERT, timeout=timeout)
        return alert.text.strip()

    def select_guideline_file(self, file_path: str):
        """Send a local file path to the hidden guideline file input."""
        file_input = self.get_element(self.GUIDELINE_FILE_INPUT)
        file_input.send_keys(file_path)

    def click_upload_guideline(self):
        """Click the Upload & Index button."""
        btn = self.get_visible_element(self.UPLOAD_BUTTON, timeout=5.0)
        btn.click()

    def get_upload_success_text(self, timeout: float = 20.0) -> str:
        """Wait for and retrieve the upload success notification."""
        alert = self.get_visible_element(self.UPLOAD_SUCCESS_ALERT, timeout=timeout)
        return alert.text.strip()

    def get_upload_error_text(self, timeout: float = 5.0) -> str:
        """Wait for and retrieve the upload error alert."""
        alert = self.get_visible_element(self.UPLOAD_ERROR_ALERT, timeout=timeout)
        return alert.text.strip()

    def get_guideline_registry_rows(self) -> List[WebElement]:
        """Get all guideline registry rows in the table."""
        return self.driver.find_elements(*self.DOCUMENT_ROWS)

    def enter_search_query(self, query_text: str):
        """Enter a query into the semantic evidence retrieval search input."""
        inp = self.get_visible_element(self.QUERY_INPUT)
        inp.clear()
        inp.send_keys(query_text)

    def click_search_evidence(self):
        """Click the Search Evidence button."""
        btn = self.get_visible_element(self.SEARCH_BUTTON)
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
        btn.click()

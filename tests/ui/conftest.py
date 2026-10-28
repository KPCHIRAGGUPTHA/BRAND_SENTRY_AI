"""
PyTest Configuration and Reusable Selenium WebDriver Fixtures for BrandSentry AI.

Supports:
- Headless and visible Chrome browser execution via BRANDSENTRY_HEADLESS.
- Configurable base URL via BRANDSENTRY_BASE_URL.
- Configurable backend URL via BRANDSENTRY_BACKEND_URL.
- Automatic failure diagnostics: screenshot capture and current page URL logging.
- Reliable browser lifecycle management with guaranteed teardown.
- Live backend availability detection with informative skips when backend is offline.
"""
import os
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Generator

import pytest
import requests
from selenium import webdriver  # type: ignore
from selenium.webdriver.chrome.options import Options


from selenium.webdriver.support.ui import WebDriverWait  # type: ignore
from selenium.common.exceptions import WebDriverException  # type: ignore



logger = logging.getLogger(__name__)

# Directory setup
RESULTS_DIR = Path("test-results")
SCREENSHOTS_DIR = RESULTS_DIR / "screenshots"
PAGE_SOURCE_DIR = RESULTS_DIR / "page_source"


def pytest_configure(config):
    """Ensure artifacts directories exist and markers are registered."""
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    PAGE_SOURCE_DIR.mkdir(parents=True, exist_ok=True)


@pytest.fixture(scope="session")
def base_url() -> str:
    """Return the frontend application base URL from environment or default."""
    return os.getenv("BRANDSENTRY_BASE_URL", "http://localhost:5173").rstrip("/")


@pytest.fixture(scope="session")
def backend_url() -> str:
    """Return the FastAPI backend service URL from environment or default."""
    return os.getenv("BRANDSENTRY_BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")


@pytest.fixture(scope="session")
def is_headless() -> bool:
    """Determine whether the browser runs in headless mode."""
    val = os.getenv("BRANDSENTRY_HEADLESS", "true").strip().lower()
    return val not in ("0", "false", "no", "off")


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    """Return absolute path to the UI test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def sample_txt_path(fixtures_dir: Path) -> str:
    """Return absolute string path to the valid test TXT guideline."""
    path = fixtures_dir / "sample_guideline.txt"
    assert path.exists(), f"Fixture file not found: {path}"
    return str(path.resolve())


@pytest.fixture(scope="session")
def sample_pdf_path(fixtures_dir: Path) -> str:
    """Return absolute string path to the valid test PDF guideline."""
    path = fixtures_dir / "sample_guideline.pdf"
    assert path.exists(), f"Fixture file not found: {path}"
    return str(path.resolve())


@pytest.fixture(scope="session")
def invalid_file_path(fixtures_dir: Path) -> str:
    """Return absolute string path to an unsupported file format fixture."""
    path = fixtures_dir / "invalid_guideline.csv"
    assert path.exists(), f"Fixture file not found: {path}"
    return str(path.resolve())


@pytest.fixture(scope="session")
def check_backend_health(backend_url: str):
    """Helper to verify if the live backend is reachable and responsive."""
    def _is_healthy() -> bool:
        try:
            resp = requests.get(f"{backend_url}/health", timeout=3.0)
            return resp.status_code == 200 and resp.json().get("status") == "ok"
        except Exception:
            return False
    return _is_healthy


@pytest.fixture(scope="function")
def require_live_backend(check_backend_health, backend_url: str):
    """Skip test if the live FastAPI backend is not running."""
    if not check_backend_health():
        pytest.skip(
            f"Live backend service is not running at {backend_url}. "
            f"Start backend with 'uvicorn backend.app.main:app --port 8000' to run this test."
        )


@pytest.fixture(scope="function")
def driver(is_headless: bool, request) -> Generator[webdriver.Chrome, None, None]:
    """
    Initialize a clean Chrome WebDriver instance with explicit options.
    Guarantees browser termination in teardown even if tests raise exceptions.
    Attaches the active driver to pytest item for failure screenshot capture.
    """
    options = Options()
    if is_headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1440,900")
    options.add_argument("--disable-search-engine-choice-screen")

    chrome_driver = None
    try:
        chrome_driver = webdriver.Chrome(options=options)
        chrome_driver.set_page_load_timeout(30)
    except WebDriverException as exc:
        pytest.fail(
            f"Failed to launch Chrome WebDriver via Selenium Manager: {exc}\n"
            f"Verify that Google Chrome is installed and compatible with your environment."
        )

    # Attach driver to test node for failure hook access
    request.node.driver = chrome_driver

    try:
        yield chrome_driver
    finally:
        if chrome_driver is not None:
            try:
                chrome_driver.quit()
            except Exception as exc:
                logger.warning("Error encountered while closing Chrome WebDriver: %s", exc)


@pytest.fixture(scope="function")
def wait(driver: webdriver.Chrome):
    """Provide a standard explicit wait helper configured for UI interactions."""
    def _make_wait(timeout: float = 12.0) -> WebDriverWait:
        return WebDriverWait(driver, timeout=timeout)
    return _make_wait


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """
    Diagnostics hook: When a test fails in call phase, capture:
    1. Screenshot saved to test-results/screenshots/
    2. HTML source snapshot saved to test-results/page_source/
    3. Current page URL and test name logged to stdout.
    """
    outcome = yield
    report = outcome.get_result()

    if report.when == "call" and report.failed:
        driver = getattr(item, "driver", None)
        if driver is not None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in item.name)
            screenshot_file = SCREENSHOTS_DIR / f"{safe_name}_{timestamp}.png"
            source_file = PAGE_SOURCE_DIR / f"{safe_name}_{timestamp}.html"

            try:
                driver.save_screenshot(str(screenshot_file))
                with open(source_file, "w", encoding="utf-8", errors="replace") as f:
                    f.write(driver.page_source)
                print(f"\n[FAILURE DIAGNOSTIC] Test: {item.name}")
                print(f"[FAILURE DIAGNOSTIC] Current URL: {driver.current_url}")
                print(f"[FAILURE DIAGNOSTIC] Screenshot saved: {screenshot_file}")
                print(f"[FAILURE DIAGNOSTIC] Page source saved: {source_file}")
            except Exception as diag_err:
                print(f"[FAILURE DIAGNOSTIC ERROR] Could not save diagnostic artifacts: {diag_err}")

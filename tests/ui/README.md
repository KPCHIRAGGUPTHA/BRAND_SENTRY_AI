# BrandSentry AI — Selenium UI Browser Automation Framework

End-to-end browser automation testing framework for **BrandSentry AI**, verifying UI workflows, client-side input validations, brand guideline document ingestion, and evidence-grounded marketing claim compliance reviews.

---

## 1. Architecture Overview

```
BrandSentry AI Test Ecosystem
├── PyTest Backend Suite (backend/tests)    --> Unit & RAG algorithm tests (166 tests)
├── Vitest Frontend Suite (frontend/src/test) --> React component & hook tests (12 tests)
└── Selenium UI Suite (tests/ui)             --> Automated Chrome browser E2E workflows (20 TCs)
```

### Components

- **Test Runner**: PyTest with custom fixtures in [conftest.py](conftest.py).
- **Browser Automation**: Selenium WebDriver 4.51+ with built-in **Selenium Manager** (automatic ChromeDriver matching).
- **Page Object Model**: Centralized UI element selectors and action abstractions in [pages.py](pages.py).
- **Failure Diagnostics**: PyTest hook capturing full-page PNG screenshots and HTML DOM snapshots on failure in `test-results/`.
- **Test Group Isolation**: Browser-only smoke/validation tests run independently; RAG verification tests execute when backend is live.

---

## 2. Prerequisites (Windows 11)

1. **Google Chrome**: Stable version 120+ (Tested with Chrome 155).
2. **Python**: 3.10 to 3.14 with virtual environment (`backend/venv`).
3. **Node.js**: v18+ with `npm` (v20+ recommended).

---

## 3. Installation

Activate the virtual environment and install test dependencies:

```powershell
# Using the project's existing virtual environment
.\backend\venv\Scripts\pip.exe install -r tests\ui\requirements.txt
```

Or if virtual environment is activated in your terminal:

```powershell
pip install -r tests\ui\requirements.txt
```

---

## 4. Test Scenarios Implemented

| Group | Test Module | Test Case ID | Description |
|---|---|---|---|
| **A: Homepage** | `test_homepage.py` | `TC01` | Homepage loads successfully (title, form, upload, status) |
| | | `TC02` | Header navigation anchors scroll to respective sections |
| | | `TC03` | Compliance review form controls are visible and enabled |
| **B: Validation** | `test_validation.py` | `TC04` | Empty marketing copy rejected with validation warning |
| | | `TC05` | Whitespace-only copy rejected without submitting |
| | | `TC06` | Valid copy accepted into textarea ready for review |
| | | `TC09` | Unsupported file type (.csv) rejected immediately |
| | | `TC18` | Duplicate submission prevented (submit button disabled during flight) |
| **C: Guideline Ingestion** | `test_guideline_upload.py` | `TC07` | Valid TXT guideline uploaded and indexed into ChromaDB |
| | | `TC08` | Valid PDF guideline uploaded and parsed with PyMuPDF |
| | | `TC10` | Document Registry table populated with chunk counts and status |
| | | `TC11` | Selecting guideline in registry updates UI highlighting and scoping |
| **D: Compliance Review** | `test_claim_review.py` | `TC12` | Review produces `#review-results-container` |
| | | `TC13` | Rendered verdicts belong strictly to `{SUPPORTED, CONTRADICTED, INSUFFICIENT_EVIDENCE}` |
| | | `TC14` | Claim summary counts are consistent (`total = supported + contradicted + insufficient`) |
| | | `TC16` | Graceful failure handling without false success results |
| | | `TC17` | Loading state indicator (`Analyzing Claims...` + spinning icon) verified |
| **E: Evidence Retrieval** | `test_evidence_results.py` | `TC15` | Claim cards present grounded evidence fields, citations, and quotes |
| | | `TC19` | Semantic evidence search queries vector store and displays ranked passages |
| | | `TC20` | Document-scoped retrieval limits query to selected guideline |

---

## 5. Running the Application

### Start the Backend Service (Port 8000)

Open a PowerShell terminal:

```powershell
.\backend\venv\Scripts\python.exe -m uvicorn backend.app.main:app --port 8000
```

Verify backend health at: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

### Start the Frontend Dev Server (Port 5173)

Open a second PowerShell terminal:

```powershell
npm --prefix frontend run dev
```

The application is accessible at: [http://localhost:5173](http://localhost:5173)

---

## 6. Running Browser Automation Tests

### Run All Browser Tests (Default: Headless Mode)

```powershell
.\backend\venv\Scripts\python.exe -m pytest tests/ui -v
```

### Run Only Browser-Only Validation & Smoke Tests

```powershell
.\backend\venv\Scripts\python.exe -m pytest tests/ui -v -m "not live_backend and not live_review"
```

### Run Live Backend & RAG Review Tests

```powershell
.\backend\venv\Scripts\python.exe -m pytest tests/ui -v -m "live_backend or live_review"
```

### Run in Visible Browser Mode (Demonstration Mode)

To watch Chrome launch and execute interactions live on your screen:

```powershell
$env:BRANDSENTRY_HEADLESS="false"
.\backend\venv\Scripts\python.exe -m pytest tests/ui -v
$env:BRANDSENTRY_HEADLESS="true"
```

### Custom Base URL Configuration

If running against a remote deployment or custom port:

```powershell
$env:BRANDSENTRY_BASE_URL="http://localhost:5173"
$env:BRANDSENTRY_BACKEND_URL="http://127.0.0.1:8000"
.\backend\venv\Scripts\python.exe -m pytest tests/ui -v
```

---

## 7. Failure Diagnostics & Artifacts

When any test fails, PyTest hooks in `conftest.py` automatically:
1. Capture a full-page PNG screenshot into `test-results/screenshots/<test_name>_<timestamp>.png`.
2. Capture the active DOM HTML into `test-results/page_source/<test_name>_<timestamp>.html`.
3. Print the failing URL and test metadata to the test execution output.

`test-results/` is included in `.gitignore` to avoid committing local artifacts.

---

## 8. Troubleshooting

### 1. `WebDriverException: ChromeDriver cannot be found`
Selenium 4.51+ includes **Selenium Manager**, which discovers and downloads matching ChromeDriver binaries automatically without third-party tools or manual PATH modifications. Ensure you have network connectivity on the initial test run.

### 2. Live tests skipped (`Live backend service is not running`)
Tests requiring backend vector retrieval (`@pytest.mark.live_backend`, `@pytest.mark.live_review`) automatically verify `GET http://127.0.0.1:8000/health`. If the backend is not running, these tests report an informative skip rather than a false failure. Start the backend with:
```powershell
.\backend\venv\Scripts\python.exe -m uvicorn backend.app.main:app --port 8000
```

### 3. Preserving the Backend Test Suite
The root [pytest.ini](../../pytest.ini) specifies `testpaths = backend/tests`. Running:
```powershell
python -m pytest -q
```
Continues to execute **only** the fast backend unit tests without running browser tests.

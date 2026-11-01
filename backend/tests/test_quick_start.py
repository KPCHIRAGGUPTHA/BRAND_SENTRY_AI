"""
Judge quick-start and cold-start behaviour, tested against a real production-mode server process
with empty storage. Nothing is mocked.
"""
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]

LOGO_CLAIM = "Brand logo appears in the top-left corner with a 25px clear buffer margin."
GUARANTEE_CLAIM = "Our platform guarantees 100% impenetrable barrier against ransomware."
IDENTIFIER_CLAIM = "Medical devices distributed under clinical guidelines display registration code 4412-K."
DRIFT_CLAIM = "Our software always improves team productivity."


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    """Starts the backend as it runs in production, and records every /health response during startup."""
    port = _free_port()
    env = dict(
        os.environ,
        APP_ENV="production",
        DATA_DIR=str(tmp_path_factory.mktemp("quick_start_data")),
        PYTHONPATH=str(ROOT),
    )
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.app.main:app", "--port", str(port), "--log-level", "warning"],
        cwd=ROOT,
        env=env,
    )
    client = httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=120)
    states, slowest = [], 0.0
    try:
        deadline = time.monotonic() + 240
        while time.monotonic() < deadline:
            started = time.monotonic()
            try:
                body = client.get("/health").json()
            except httpx.TransportError:
                time.sleep(0.2)
                continue
            slowest = max(slowest, time.monotonic() - started)
            states.append(body["readiness"])
            if body["readiness"] == "ready":
                break
            time.sleep(0.1)
        else:
            pytest.fail("Backend did not become ready in time")
        yield client, states, slowest
    finally:
        client.close()
        process.terminate()
        process.wait(timeout=30)


def _review(client, content):
    response = client.post("/api/review", json={"content": content})
    assert response.status_code == 200, response.text
    claims = response.json()["claims"]
    assert len(claims) == 1
    assert claims[0]["verdict"] == claims[0]["compliance_verdict"]
    return claims[0]


def test_health_reports_warming_then_ready_and_stays_fast(server):
    _, states, slowest = server
    assert states[0] == "warming"
    assert states[-1] == "ready"
    assert slowest < 2.0, f"/health took {slowest:.2f}s during warm-up"


def test_cold_start_auto_loads_the_sample_guideline(server):
    client, _, _ = server
    documents = client.get("/api/guidelines").json()["documents"]
    assert [d["status"] for d in documents] == ["indexed"]
    assert "Marketing_Compliance" in documents[0]["filename"]


def test_load_sample_is_a_no_op_when_already_loaded(server):
    client, _, _ = server
    before = client.get("/api/guidelines").json()["total"]
    response = client.post("/api/guidelines/load-sample")
    assert response.status_code == 200
    assert "already loaded" in response.json()["message"]
    assert client.get("/api/guidelines").json()["total"] == before == 1


def test_quick_start_logo_margin_is_supported_from_section_11(server):
    claim = _review(server[0], LOGO_CLAIM)
    assert claim["verdict"] == "SUPPORTED"
    assert any("at least 20px clear buffer margin" in e["quote"] for e in claim["evidence"])


def test_quick_start_guarantee_is_contradicted_citing_section_8(server):
    claim = _review(server[0], GUARANTEE_CLAIM)
    assert claim["verdict"] == "CONTRADICTED"
    assert any("impossible to hack" in e["quote"] for e in claim["evidence"])


def test_quick_start_wrong_identifier_is_insufficient(server):
    claim = _review(server[0], IDENTIFIER_CLAIM)
    assert claim["verdict"] == "INSUFFICIENT_EVIDENCE"
    assert "9845-A" in claim["explanation"]


def test_quick_start_certainty_drift_offers_a_rewrite(server):
    drift = _review(server[0], DRIFT_CLAIM)["semantic_drift"]
    issues = [i for i in drift["issues"] if i["category"] == "CERTAINTY_SHIFT"]
    assert issues, drift
    assert issues[0]["suggested_correction"]

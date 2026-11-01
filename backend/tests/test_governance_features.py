"""
Reviewer state machine, integrity stamp, revision diff and image measurements. API behaviour is
tested against a real server process with temporary storage.
"""
import io
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import fitz
import httpx
import pytest
from PIL import Image, ImageDraw

from backend.app.services import visual_checks

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = dict(
        os.environ,
        APP_ENV="development",
        DATA_DIR=str(tmp_path_factory.mktemp("governance_data")),
        PYTHONPATH=str(ROOT),
    )
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.app.main:app", "--port", str(port), "--log-level", "warning"],
        cwd=ROOT,
        env=env,
    )
    http = httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=120)
    try:
        for _ in range(600):
            try:
                http.get("/health")
                break
            except httpx.TransportError:
                time.sleep(0.2)
        http.post("/api/guidelines/load-sample").raise_for_status()
        yield http
    finally:
        http.close()
        process.terminate()
        process.wait(timeout=30)


def _new_review(client, content):
    response = client.post("/api/review", json={"content": content})
    response.raise_for_status()
    return response.json()["review_id"]


def _move(client, review_id, to_state, justification="Checked against the guideline."):
    return client.post(
        f"/api/reviews/{review_id}/transition",
        json={"to_state": to_state, "justification": justification, "reviewer": "qa"},
    )


def test_new_review_starts_as_draft_with_no_history(client):
    review = client.get(f"/api/reviews/{_new_review(client, 'Our product is 100% safe.')}").json()
    assert review["review_state"] == "DRAFT"
    assert review["state_history"] == []
    assert review["allowed_transitions"] == ["UNDER_REVIEW"]


def test_full_lifecycle_is_recorded(client):
    review_id = _new_review(client, "Our product is 100% safe.")
    for state in ("UNDER_REVIEW", "FLAGGED", "LEGAL_ESCALATED", "APPROVED"):
        assert _move(client, review_id, state).status_code == 200
    review = client.get(f"/api/reviews/{review_id}").json()
    assert review["review_state"] == "APPROVED"
    assert [h["to_state"] for h in review["state_history"]] == ["UNDER_REVIEW", "FLAGGED", "LEGAL_ESCALATED", "APPROVED"]
    assert review["allowed_transitions"] == []


@pytest.mark.parametrize("justification", ["", "   "])
def test_justification_is_mandatory(client, justification):
    review_id = _new_review(client, "Our office is open on weekdays.")
    assert _move(client, review_id, "UNDER_REVIEW", justification).status_code == 422
    assert client.get(f"/api/reviews/{review_id}").json()["review_state"] == "DRAFT"


def test_states_cannot_be_skipped(client):
    review_id = _new_review(client, "Our office is open on weekdays.")
    assert _move(client, review_id, "APPROVED").status_code == 409


def test_contradicted_review_cannot_skip_legal(client):
    review_id = _new_review(client, "Our product is 100% safe.")
    assert _move(client, review_id, "UNDER_REVIEW").status_code == 200
    assert _move(client, review_id, "APPROVED").status_code == 409


def test_review_with_no_contradictions_can_be_approved_directly(client):
    review_id = _new_review(client, "Our office is open on weekdays.")
    assert _move(client, review_id, "UNDER_REVIEW").status_code == 200
    assert _move(client, review_id, "APPROVED").status_code == 200


def test_unknown_review_returns_404(client):
    assert _move(client, "no-such-review", "UNDER_REVIEW").status_code == 404


def test_pdf_has_full_integrity_hash_and_is_not_called_signed(client):
    review_id = _new_review(client, "Our product is 100% safe.")
    review = client.get(f"/api/reviews/{review_id}").json()
    assert len(review["integrity_hash"]) == 64

    pdf = client.get(f"/api/reviews/{review_id}/export", params={"format": "pdf"})
    pdf.raise_for_status()
    text = " ".join(page.get_text() for page in fitz.open(stream=pdf.content, filetype="pdf"))
    text = "".join(text.split())
    assert review["integrity_hash"] in text
    assert "notadigitalsignature" in text.lower()


def test_integrity_hash_ignores_workflow_state(client):
    review_id = _new_review(client, "Our product is 100% safe.")
    before = client.get(f"/api/reviews/{review_id}").json()["integrity_hash"]
    _move(client, review_id, "UNDER_REVIEW")
    assert client.get(f"/api/reviews/{review_id}").json()["integrity_hash"] == before


def _upload(client, text):
    response = client.post(
        "/api/guidelines/upload",
        files={"file": ("diff_policy.txt", text.encode("utf-8"), "text/plain")},
    )
    response.raise_for_status()


def test_revision_diff_lists_added_and_removed_sentences(client):
    _upload(client, "Discounts cannot exceed 50%. Logos need a clear margin. Testimonials must be genuine.")
    _upload(client, "Discounts cannot exceed 40%. Logos need a clear margin. Testimonials must be genuine.")
    versions = [v for v in client.get("/api/guidelines/versions/list").json() if v["filename"] == "diff_policy.txt"]
    versions.sort(key=lambda v: v["version_label"])
    assert len(versions) == 2

    diff = client.get(f"/api/guidelines/versions/{versions[0]['version_id']}/diff/{versions[1]['version_id']}").json()
    assert diff["removed"] == ["Discounts cannot exceed 50%."]
    assert diff["added"] == ["Discounts cannot exceed 40%."]
    assert diff["unchanged_count"] == 2


def test_revision_diff_unknown_version_returns_404(client):
    assert client.get("/api/guidelines/versions/ver-x/diff/ver-y").status_code == 404


def _banner():
    image = Image.new("RGB", (400, 200), (255, 255, 255))
    ImageDraw.Draw(image).rectangle((24, 30, 123, 79), fill=(200, 0, 0))
    return image


def test_content_margins_are_measured_from_pixels():
    assert visual_checks.content_margins(_banner()) == {"left": 24, "top": 30, "right": 276, "bottom": 120}


def test_blank_image_has_no_margins():
    assert visual_checks.content_margins(Image.new("RGB", (50, 50), (9, 9, 9))) is None


def test_dominant_colors_are_measured_from_pixels():
    colors = visual_checks.dominant_colors(_banner())
    assert colors[0]["hex"] == "#FFFFFF"
    assert 0.9 < colors[0]["share"] < 0.95
    assert sum(c["share"] for c in colors) == pytest.approx(1.0, abs=0.01)


def test_contrast_ratio_matches_wcag_extremes():
    assert visual_checks.contrast_ratio(0, 255) == 21.0
    assert visual_checks.contrast_ratio(128, 128) == 1.0


def test_text_measurements_use_word_boxes():
    image = Image.new("RGB", (100, 40), (255, 255, 255))
    ImageDraw.Draw(image).rectangle((10, 10, 20, 20), fill=(0, 0, 0))
    result = visual_checks.text_measurements(image, [{"bbox": [5, 5, 30, 16]}])
    assert result["lowest_text_contrast"] == 21.0
    assert result["smallest_text_px"] == 16
    assert result["smallest_text_approx_pt"] == 12.0


def test_measurements_say_they_do_not_identify_the_logo():
    assert "do not identify the logo" in visual_checks.measure(io.BytesIO and _banner())["note"]

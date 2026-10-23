"""
Automated Acceptance Test Suite for PRD Version 2.0:
AI Chest X-ray Analysis Chatbot with Login, Interactive Image Viewer and Analysis History.
Verifies FR-01 through FR-13 and Section 13 Acceptance Criteria (1–17).
"""
import io
import os
import sys
import tempfile
import pytest
from PIL import Image

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app import create_app
from models import db, User, Analysis, ChatMessage


@pytest.fixture
def client():
    db_fd, db_path = tempfile.mkstemp(suffix=".sqlite")
    upload_dir = tempfile.mkdtemp(prefix="cxr_uploads_")
    sample_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static", "samples"))

    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
        "UPLOAD_FOLDER": upload_dir,
        "SAMPLE_FOLDER": sample_dir,
        "SECRET_KEY": "test-secret-key",
    })

    with app.app_context():
        db.create_all()

    with app.test_client() as test_client:
        yield test_client

    with app.app_context():
        db.session.remove()
        db.engine.dispose()

    os.close(db_fd)
    if os.path.exists(db_path):
        os.unlink(db_path)


def create_dummy_xray_bytes(fmt="PNG", size=(256, 256)) -> io.BytesIO:
    img = Image.new("L", size, color=95)
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    buf.seek(0)
    return buf


def test_registration_login_logout_and_invalid_credentials(client):
    """AC 1 & AC 2: Users can register, log in, and log out; invalid credentials and duplicate emails are rejected."""
    # Register User A
    res = client.post("/register", data={
        "name": "Alice Radiologist",
        "email": "alice@example.edu",
        "password": "SecurePassword123",
        "confirm_password": "SecurePassword123",
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b"Alice Radiologist" in res.data

    # Logout
    res = client.get("/logout", follow_redirects=True)
    assert res.status_code == 200
    assert b"securely logged out" in res.data

    # Duplicate email registration rejected
    res = client.post("/register", data={
        "name": "Alice Duplicate",
        "email": "alice@example.edu",
        "password": "AnotherPassword123",
        "confirm_password": "AnotherPassword123",
    })
    assert res.status_code == 409
    assert b"already exists" in res.data

    # Invalid password rejected
    res = client.post("/login", data={
        "email": "alice@example.edu",
        "password": "WrongPassword",
    })
    assert res.status_code == 401
    assert b"Invalid email address or password" in res.data

    # Valid login succeeds
    res = client.post("/login", data={
        "email": "alice@example.edu",
        "password": "SecurePassword123",
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b"Upload Chest X-ray for Analysis" in res.data


def test_health_and_disabled_public_demo_access(client):
    app = client.application
    app.config["ENABLE_DEMO_ACCESS"] = False

    health = client.get("/healthz")
    assert health.status_code == 200
    assert health.get_json() == {"status": "ok"}

    assert client.get("/demo-login").status_code == 404
    response = client.post("/login", data={
        "email": "unregistered@example.edu",
        "password": "Password123!",
    })
    assert response.status_code == 401
    with app.app_context():
        assert User.query.filter_by(email="unregistered@example.edu").first() is None


def test_upload_validation_and_error_handling(client):
    """AC 3 & AC 16: Rejects unsupported/corrupted files and inference failures without saving incomplete records."""
    client.post("/register", data={
        "name": "Upload Tester",
        "email": "uploader@example.edu",
        "password": "Password123!",
        "confirm_password": "Password123!",
    })

    # Unsupported file extension (.txt)
    bad_file = (io.BytesIO(b"not an xray"), "notes.txt")
    res = client.post("/api/analyze", data={"xray_image": bad_file}, content_type="multipart/form-data")
    assert res.status_code == 400
    assert "Unsupported file format" in res.get_json()["error"]

    # Corrupted image header with .png extension
    corrupt_file = (io.BytesIO(b"corrupted binary payload"), "broken.png")
    res = client.post("/api/analyze", data={"xray_image": corrupt_file}, content_type="multipart/form-data")
    assert res.status_code == 400
    assert "Invalid or corrupted" in res.get_json()["error"]

    # Simulated inference failure does not create a database record (FR-13)
    valid_img = (create_dummy_xray_bytes(), "chest_study.png")
    res = client.post(
        "/api/analyze",
        data={"xray_image": valid_img, "simulate_inference_error": "1"},
        content_type="multipart/form-data",
    )
    assert res.status_code == 502
    status_data = client.get("/api/schema-status").get_json()
    assert status_data["user_analyses_count"] == 0


def test_full_analysis_viewer_chatbot_reopen_and_delete(client):
    """
    AC 4..13 & AC 17:
    - Generates structured AI report draft
    - Renders Panel A (Uploaded Image + Zoom Slider + Hover-to-Zoom Loupe) and Panel B (Scrollable Report)
    - Contextual chatbot answers questions grounded in the report
    - Reopens saved analysis without re-running inference
    - Deletes analysis with confirmation and removes stored files
    """
    client.post("/register", data={
        "name": "Clinical Student",
        "email": "student@example.edu",
        "password": "Password123!",
        "confirm_password": "Password123!",
    })

    # Upload chest X-ray
    xray_buf = create_dummy_xray_bytes(fmt="PNG", size=(512, 512))
    res = client.post(
        "/api/analyze",
        data={"xray_image": (xray_buf, "rll_pneumonia_case.png")},
        content_type="multipart/form-data",
    )
    assert res.status_code == 201
    payload = res.get_json()
    assert payload["status"] == "completed"
    analysis_id = payload["analysis"]["analysis_id"]

    # Open side-by-side workspace for this analysis
    page = client.get(f"/analysis/{analysis_id}")
    assert page.status_code == 200
    html = page.data.decode("utf-8")

    # Verify Panel A & Panel B side-by-side elements + Zoom Slider + Hover-to-Zoom Loupe + Medical Safety Notice
    assert "Panel A — Chest X-ray Inspection Viewer" in html
    assert "Panel B — Chest X-ray Report" in html
    assert 'id="xrayZoomSlider"' in html
    assert 'id="hoverZoomLoupe"' in html
    assert "This report is AI-assisted and for informational support only." in html

    # Verify Contextual Chatbot (FR-07)
    for question in [
        "Explain this report in simple English.",
        "What does opacity mean?",
        "Summarize the report.",
        "What limitations should I understand?",
    ]:
        chat_res = client.post(f"/api/analysis/{analysis_id}/chat", json={"message": question})
        assert chat_res.status_code == 200
        chat_json = chat_res.get_json()
        assert chat_json["assistant_message"]["role"] == "assistant"
        assert len(chat_json["assistant_message"]["message_text"]) > 40

    # Reopen saved analysis via JSON endpoint and verify inference_triggered is False (FR-11)
    reopen_res = client.get(f"/api/analysis/{analysis_id}")
    assert reopen_res.status_code == 200
    reopen_json = reopen_res.get_json()
    assert reopen_json["inference_triggered"] is False
    assert len(reopen_json["analysis"]["messages"]) == 9  # 1 greeting + 4 Q&A pairs

    # Delete analysis (FR-12)
    del_res = client.post(
        f"/api/analysis/{analysis_id}/delete",
        headers={"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"},
    )
    assert del_res.status_code == 200
    assert del_res.get_json()["status"] == "deleted"

    # Confirm record is gone
    missing_res = client.get(f"/api/analysis/{analysis_id}")
    assert missing_res.status_code == 404


def test_cross_user_isolation(client):
    """AC 14: Prevents User B from viewing, chatting on, fetching image for, or deleting User A's analysis."""
    # Register User A and create an analysis
    client.post("/register", data={
        "name": "User One",
        "email": "user1@example.edu",
        "password": "Password123!",
        "confirm_password": "Password123!",
    })
    res = client.post(
        "/api/analyze",
        data={"xray_image": (create_dummy_xray_bytes(), "user1_xray.png")},
        content_type="multipart/form-data",
    )
    user1_analysis_id = res.get_json()["analysis"]["analysis_id"]
    client.get("/logout")

    # Register User B
    client.post("/register", data={
        "name": "User Two",
        "email": "user2@example.edu",
        "password": "Password123!",
        "confirm_password": "Password123!",
    })

    # User B attempts to access User A's analysis page, image, API, chat, and delete
    assert client.get(f"/analysis/{user1_analysis_id}").status_code == 403
    assert client.get(f"/analysis/{user1_analysis_id}/image").status_code == 403
    assert client.get(f"/api/analysis/{user1_analysis_id}").status_code == 403
    assert client.post(f"/api/analysis/{user1_analysis_id}/chat", json={"message": "Hello"}).status_code == 403
    assert client.post(f"/api/analysis/{user1_analysis_id}/delete").status_code == 403

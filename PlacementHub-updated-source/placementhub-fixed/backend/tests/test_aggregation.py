"""Tests for the scraping & aggregation pipeline, scam detector, and Excel student import."""
import io
from types import SimpleNamespace
import pytest
from app.aggregation.connectors import SerperGreenhouseConnector
from app.aggregation.scam_detector import assess_opportunity_risk
from app.models import Vacancy, Student, Department, db
from tests.conftest import Api


def test_greenhouse_search_only_returns_https_urls_from_allowed_hosts(monkeypatch):
    results = {
        "organic": [
            {"title": "Allowed", "link": "https://boards.greenhouse.io/acme/jobs/1"},
            {"title": "Allowed alternate", "link": "https://job-boards.greenhouse.io/acme/jobs/2"},
            {"title": "HTTP", "link": "http://boards.greenhouse.io/acme/jobs/3"},
            {"title": "Lookalike host", "link": "https://boards.greenhouse.io.attacker.test/jobs/4"},
            {"title": "Private IP", "link": "https://127.0.0.1/boards.greenhouse.io/jobs/5"},
        ]
    }
    monkeypatch.setattr(
        "app.aggregation.connectors.requests.post",
        lambda *args, **kwargs: SimpleNamespace(status_code=200, json=lambda: results),
    )
    connector = SerperGreenhouseConnector(api_key="test-key")

    links = connector.search_links()

    assert [item["title"] for item in links] == ["Allowed", "Allowed alternate"]


def test_greenhouse_detail_fetch_does_not_follow_redirects(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return SimpleNamespace(status_code=302, text="")

    monkeypatch.setattr("app.aggregation.connectors.requests.get", fake_get)
    connector = SerperGreenhouseConnector(api_key="test-key")

    with pytest.raises(ValueError, match="allowed HTTPS host"):
        connector.extract_details("Job", "https://boards.greenhouse.io.attacker.test/jobs/1")

    connector.extract_details("Job", "https://boards.greenhouse.io/acme/jobs/1")
    assert calls[0][1]["allow_redirects"] is False


def test_scam_detector_flags_fees():
    """Opportunities demanding registration fees or security deposits must be flagged High Risk."""
    job = {
        "title": "Data Entry Internship - Immediate Joining",
        "description": "Candidates must deposit a mandatory security deposit of Rs. 1500 before offer letter release. Send receipt to Telegram @fastjobs.",
        "company": "Tech Fast Ltd",
        "source_url": "https://bit.ly/fast-jobs-apply",
        "ctc_lpa": 3.0,
    }

    res = assess_opportunity_risk(job)
    assert res["risk_level"] == "High Risk"
    assert res["risk_score"] >= 40
    assert any("Monetary demand" in flag for flag in res["risk_flags"])
    assert any("suspicious redirect" in flag.lower() for flag in res["risk_flags"])


def test_scam_detector_allows_legitimate():
    """Legitimate enterprise job listings should pass as Low Risk."""
    job = {
        "title": "Associate Software Engineer - Full Stack",
        "description": "We are seeking a Software Engineer proficient in React, Python, and SQL to join our Enterprise Cloud team in Bengaluru. Requires B.Tech/M.Tech with strong data structures knowledge.",
        "company": "Infosys Limited",
        "source_url": "https://boards.greenhouse.io/infosys/jobs/123456",
        "ctc_lpa": 6.5,
        "from_verified_ats": True,
    }

    res = assess_opportunity_risk(job)
    assert res["risk_level"] == "Low Risk"
    assert res["risk_score"] < 20
    assert len(res["risk_flags"]) == 0


def test_excel_import_endpoint_validation(client, world):
    """Excel import endpoint rejects malformed rows and accepts valid rows."""
    from openpyxl import Workbook

    api = Api(client)
    r = api.login("sa@x.edu", "super_admin")
    assert r.status_code == 200

    wb = Workbook()
    ws = wb.active
    ws.title = "Students"
    # Headers
    ws.append(["Roll No", "Full Name", "Email", "Phone", "Department Code", "Batch", "CGPA", "Active Backlogs", "Skills"])
    # Valid row for FIN department
    ws.append(["FIN9901", "Aarav Sharma", "aarav.test@placementhub.edu", "9876543210", "FIN", "2024-2026", 8.85, 0, "Python, SQL"])
    # Row with missing name
    ws.append(["FIN9902", "", "incomplete@test.com", "9876543211", "FIN", "2024-2026", 7.5, 0, "Java"])

    bio = io.BytesIO()
    wb.save(bio)
    bio.seek(0)

    # Dry-run validation
    headers = api._h()
    res = client.post(
        "/api/students/import",
        headers=headers,
        data={"file": (bio, "test_import.xlsx"), "dryRun": "true"},
        content_type="multipart/form-data"
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["dryRun"] is True
    assert data["totalRows"] == 2
    assert data["imported"] == 1
    assert len(data["errors"]) == 1
    assert data["errors"][0]["row"] == 3

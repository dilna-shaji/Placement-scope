"""Tests for the scraping & aggregation pipeline, scam detector, and Excel student import."""
import io
import pytest
from app.aggregation.scam_detector import assess_opportunity_risk
from app.models import Vacancy, Student, Department, db
from tests.conftest import Api


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


def test_aggregation_run_history_and_summary_endpoints(client, world):
    """Regression: AggregationRun used a column named `query`, which shadowed Model.query, so
    GET /api/aggregation/runs and /api/aggregation/summary (and the Opportunity Collection page) returned 500."""
    api = Api(client)
    assert api.login("sa@x.edu", "super_admin").status_code == 200

    # Run the pipeline once so there is a recorded run (offline: falls back to the curated feed).
    res = api.post("/api/aggregation/run", json={"source": "All Sources", "query": "python intern"})
    assert res.status_code == 200, res.get_data(as_text=True)

    runs = api.get("/api/aggregation/runs")
    assert runs.status_code == 200
    items = runs.get_json()["items"]
    assert len(items) == 1
    # The public JSON key must stay "query" (the frontend reads it), even though the model attribute is renamed.
    assert items[0]["query"] == "python intern"
    assert "searchQuery" not in items[0]

    summary = api.get("/api/aggregation/summary")
    assert summary.status_code == 200
    assert summary.get_json()["lastRun"]["query"] == "python intern"

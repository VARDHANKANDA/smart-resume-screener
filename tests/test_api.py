import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database.connection import init_db

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_database():
    init_db()

def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_create_text_resume():
    payload = {
        "text": """John Developer
        Email: john.dev@test.com
        Skills: Python, FastAPI, Docker, PostgreSQL, Redis
        Experience:
        Backend Engineer at CodeCorp (2020 - Present) - Developed REST APIs.
        Education:
        B.S. in Computer Science from State University
        """,
        "candidate_name": "John Developer",
        "filename": "john_test.txt"
    }
    response = client.post("/resumes/text", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "John Developer"
    assert data["email"] == "john.dev@test.com"
    assert "Python" in data["skills"]
    assert len(data["experience"]) >= 1

def test_create_job_and_match():
    # 1. Create a candidate
    cand_res = client.post("/resumes/text", json={
        "text": "Alice Engineer\nEmail: alice@test.com\nSkills: Python, FastAPI, PostgreSQL, Docker\nExperience:\nBackend Dev at CloudWorks 2021-Present\nEducation:\nB.Tech CS",
        "candidate_name": "Alice Engineer"
    })
    assert cand_res.status_code == 201
    cand_id = cand_res.json()["id"]

    # 2. Create a job
    job_payload = {
        "title": "Python Backend Engineer",
        "description": "We are seeking a Python Backend Engineer with FastAPI, PostgreSQL, and Docker skills."
    }
    job_res = client.post("/jobs", json=job_payload)
    assert job_res.status_code == 201
    job_id = job_res.json()["id"]

    # 3. Match candidates against the job
    match_res = client.post(f"/jobs/{job_id}/match", json={"candidate_ids": [cand_id]})
    assert match_res.status_code == 200
    results_data = match_res.json()
    assert results_data["total_candidates_evaluated"] >= 1
    assert len(results_data["results"]) >= 1

    top_candidate = results_data["results"][0]
    assert top_candidate["match_score"] > 0
    assert top_candidate["recommendation"] in ["Strong Match", "Potential Match", "Weak Match"]
    assert len(top_candidate["justification"]) > 0

    # 4. Fetch results via GET endpoint
    get_results_res = client.get(f"/jobs/{job_id}/results")
    assert get_results_res.status_code == 200
    assert len(get_results_res.json()["results"]) >= 1

def test_invalid_resume_text():
    response = client.post("/resumes/text", json={"text": "too short"})
    assert response.status_code in [400, 422]

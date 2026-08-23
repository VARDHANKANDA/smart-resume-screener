import io
import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database.connection import init_db

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_database():
    init_db()

def test_duplicate_detection_and_pool_clearing():
    unique_suffix = uuid.uuid4().hex[:8]
    email = f"recruiter_{unique_suffix}@techfirm.com"
    pwd = "StrongPassword2026!"

    reg_res = client.post("/auth/register", json={
        "full_name": "Test Recruiter",
        "email": email,
        "password": pwd,
        "confirm_password": pwd
    })
    token = reg_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Setup workspace
    client.post("/workspace/setup", json={"name": "TechFirm Talent"}, headers=headers)

    resume_text = "Ravi Kumar\nEmail: ravi.kumar@example.com\nSkills: Python, Django, PostgreSQL\nExperience:\nPython Dev at InnoSoft (2020-Present)\nEducation:\nB.Tech"

    # 1. Upload candidate
    res1 = client.post("/resumes/text", json={
        "text": resume_text,
        "candidate_name": "Ravi Kumar"
    }, headers=headers)
    assert res1.status_code == 201

    # 2. Upload duplicate resume (same text/hash) -> should return 409 Conflict
    res2 = client.post("/resumes/text", json={
        "text": resume_text,
        "candidate_name": "Ravi Kumar"
    }, headers=headers)
    assert res2.status_code == 409
    assert "already been added" in res2.json()["detail"].lower()

    # 3. Upload another candidate with same email -> should return 409 Conflict
    res3 = client.post("/resumes/text", json={
        "text": "Ravi Different Text\nEmail: ravi.kumar@example.com\nSkills: Python, AWS\nExperience:\nEngineer\nEducation:\nB.S.",
        "candidate_name": "Ravi Kumar Variant"
    }, headers=headers)
    assert res3.status_code == 409

    # 4. Verify candidate count is exactly 1
    cands = client.get("/resumes", headers=headers).json()
    assert len(cands) == 1

    # 5. Clear Candidate Pool
    clear_res = client.delete("/resumes", headers=headers)
    assert clear_res.status_code == 200

    # 6. Verify candidate count is 0
    cands_empty = client.get("/resumes", headers=headers).json()
    assert len(cands_empty) == 0

def test_bulk_resume_upload():
    unique_suffix = uuid.uuid4().hex[:8]
    email = f"bulk_recruiter_{unique_suffix}@batchcorp.com"
    pwd = "StrongPassword2026!"

    reg_res = client.post("/auth/register", json={
        "full_name": "Bulk Recruiter",
        "email": email,
        "password": pwd,
        "confirm_password": pwd
    })
    token = reg_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    client.post("/workspace/setup", json={"name": "BatchCorp Recruiting"}, headers=headers)

    # Prepare multiple file payloads
    file1_content = b"Candidate Alpha\nEmail: alpha@test.com\nSkills: Python, FastAPI\nExperience:\nDev at Alpha\nEducation:\nB.Tech"
    file2_content = b"Candidate Beta\nEmail: beta@test.com\nSkills: React, TypeScript\nExperience:\nDev at Beta\nEducation:\nB.S."
    file3_content = b"Too short"  # Should fail due to length
    file4_content = b"Candidate Alpha\nEmail: alpha@test.com\nSkills: Python, FastAPI\nExperience:\nDev at Alpha\nEducation:\nB.Tech"  # Duplicate of file 1

    files = [
        ("files", ("alpha.txt", io.BytesIO(file1_content), "text/plain")),
        ("files", ("beta.txt", io.BytesIO(file2_content), "text/plain")),
        ("files", ("short.txt", io.BytesIO(file3_content), "text/plain")),
        ("files", ("alpha_dup.txt", io.BytesIO(file4_content), "text/plain")),
    ]

    bulk_res = client.post("/resumes/bulk", files=files, headers=headers)
    assert bulk_res.status_code == 200
    data = bulk_res.json()
    assert data["total_files"] == 4
    assert data["success_count"] == 2
    assert data["duplicate_count"] == 1
    assert data["failed_count"] == 1

    # Verify candidates pool in database
    pool = client.get("/resumes", headers=headers).json()
    assert len(pool) == 2

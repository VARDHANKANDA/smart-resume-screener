import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database.connection import init_db

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_database():
    init_db()

def test_workspace_lifecycle_and_team_collaboration():
    unique_suffix = uuid.uuid4().hex[:8]
    email_owner = f"owner_{unique_suffix}@acmecorp.com"
    email_member = f"member_{unique_suffix}@acmecorp.com"
    pwd = "SecurePassword123!"

    # 1. Register Owner
    owner_reg = client.post("/auth/register", json={
        "full_name": "Alice Owner",
        "email": email_owner,
        "password": pwd,
        "confirm_password": pwd,
        "job_title": "Head of Talent"
    })
    assert owner_reg.status_code == 201
    owner_token = owner_reg.json()["access_token"]
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    # 2. Register Member user
    member_reg = client.post("/auth/register", json={
        "full_name": "Bob Recruiter",
        "email": email_member,
        "password": pwd,
        "confirm_password": pwd,
        "job_title": "Technical Recruiter"
    })
    assert member_reg.status_code == 201
    member_token = member_reg.json()["access_token"]
    member_headers = {"Authorization": f"Bearer {member_token}"}

    # 3. Owner sets up workspace
    ws_res = client.post("/workspace/setup", json={
        "name": "Acme Talent Hub",
        "job_title": "Head of Talent"
    }, headers=owner_headers)
    assert ws_res.status_code == 201
    ws_data = ws_res.json()
    assert ws_data["name"] == "Acme Talent Hub"
    assert ws_data["role"] == "owner"
    assert len(ws_data["members"]) == 1

    # 4. Owner updates profile
    prof_res = client.put("/auth/me", json={
        "full_name": "Alice M. Owner",
        "job_title": "Director of Talent Acquisition"
    }, headers=owner_headers)
    assert prof_res.status_code == 200
    assert prof_res.json()["full_name"] == "Alice M. Owner"
    assert prof_res.json()["job_title"] == "Director of Talent Acquisition"

    # 5. Owner invites Member to workspace
    add_mem_res = client.post("/workspace/members", json={
        "email": email_member,
        "role": "member"
    }, headers=owner_headers)
    assert add_mem_res.status_code == 200
    members = add_mem_res.json()
    assert len(members) == 2
    emails = [m["email"] for m in members]
    assert email_member in emails

    # 6. Owner uploads a candidate in workspace
    cand_res = client.post("/resumes/text", json={
        "text": "Jane Dev Candidate\nEmail: jane.dev@example.com\nSkills: Python, FastAPI, Docker\nExperience:\nBackend Dev at StarTech (2021-Present)\nEducation:\nB.Tech in CS",
        "candidate_name": "Jane Dev Candidate"
    }, headers=owner_headers)
    assert cand_res.status_code == 201
    cand_id = cand_res.json()["id"]

    # 7. Member accesses the shared candidate pool in the workspace
    member_cands_res = client.get("/resumes", headers=member_headers)
    assert member_cands_res.status_code == 200
    member_cands = member_cands_res.json()
    assert any(c["id"] == cand_id for c in member_cands)

    # 8. Member can delete candidate from workspace
    del_res = client.delete(f"/resumes/{cand_id}", headers=member_headers)
    assert del_res.status_code == 200

    # 9. Verify candidate pool is now empty
    cands_after_del = client.get("/resumes", headers=owner_headers).json()
    assert len(cands_after_del) == 0

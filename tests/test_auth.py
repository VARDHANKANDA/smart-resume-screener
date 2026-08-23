import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database.connection import init_db, get_db_cursor

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_database():
    init_db()

def test_user_registration_and_login_flow():
    unique_suffix = uuid.uuid4().hex[:8]
    email = f"recruit_{unique_suffix}@example.com"
    password = "SecretPassword123"

    # 1. Register new user
    reg_payload = {
        "full_name": "Recruiter Lead",
        "email": email,
        "password": password,
        "confirm_password": password
    }
    reg_res = client.post("/auth/register", json=reg_payload)
    assert reg_res.status_code == 201
    reg_data = reg_res.json()
    assert "access_token" in reg_data
    assert reg_data["user"]["email"] == email.lower()
    assert reg_data["user"]["full_name"] == "Recruiter Lead"
    token = reg_data["access_token"]

    # 2. Duplicate registration should fail
    dup_res = client.post("/auth/register", json=reg_payload)
    assert dup_res.status_code == 400
    assert "already exists" in dup_res.json()["detail"].lower()

    # 3. Fetch profile /auth/me with valid token
    headers = {"Authorization": f"Bearer {token}"}
    me_res = client.get("/auth/me", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["email"] == email.lower()

    # 4. Fetch profile /auth/me without token should fail
    unauth_res = client.get("/auth/me")
    assert unauth_res.status_code == 401

    # 5. Login with invalid password
    bad_login_res = client.post("/auth/login", json={"email": email, "password": "WrongPassword!"})
    assert bad_login_res.status_code == 401

    # 6. Login with valid password
    login_res = client.post("/auth/login", json={"email": email, "password": password})
    assert login_res.status_code == 200
    login_data = login_res.json()
    assert "access_token" in login_data
    new_token = login_data["access_token"]

    # 7. Logout
    logout_res = client.post("/auth/logout", headers={"Authorization": f"Bearer {new_token}"})
    assert logout_res.status_code == 200

    # 8. Token should now be invalid
    after_logout_res = client.get("/auth/me", headers={"Authorization": f"Bearer {new_token}"})
    assert after_logout_res.status_code == 401

def test_user_data_isolation():
    unique_suffix = uuid.uuid4().hex[:8]
    email_a = f"user_a_{unique_suffix}@example.com"
    email_b = f"user_b_{unique_suffix}@example.com"

    # Register User A
    user_a_res = client.post("/auth/register", json={
        "full_name": "User Alpha",
        "email": email_a,
        "password": "PasswordA123",
        "confirm_password": "PasswordA123"
    })
    assert user_a_res.status_code == 201
    token_a = user_a_res.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Register User B
    user_b_res = client.post("/auth/register", json={
        "full_name": "User Beta",
        "email": email_b,
        "password": "PasswordB123",
        "confirm_password": "PasswordB123"
    })
    assert user_b_res.status_code == 201
    token_b = user_b_res.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # User A uploads a candidate
    cand_a_res = client.post("/resumes/text", json={
        "text": "Alpha Candidate\nEmail: alpha@test.com\nSkills: Python, FastAPI\nExperience:\nEngineer at AlphaCorp\nEducation:\nB.Tech",
        "candidate_name": "Alpha Candidate"
    }, headers=headers_a)
    assert cand_a_res.status_code == 201
    cand_a_id = cand_a_res.json()["id"]

    # User B creates a candidate
    cand_b_res = client.post("/resumes/text", json={
        "text": "Beta Candidate\nEmail: beta@test.com\nSkills: React, Node.js\nExperience:\nDev at BetaCorp\nEducation:\nB.S.",
        "candidate_name": "Beta Candidate"
    }, headers=headers_b)
    assert cand_b_res.status_code == 201

    # User A lists candidates -> sees Alpha Candidate
    cands_a = client.get("/resumes", headers=headers_a).json()
    cands_a_names = [c["name"] for c in cands_a]
    assert "Alpha Candidate" in cands_a_names

    # User B cannot access Candidate A by ID
    b_access_a = client.get(f"/resumes/{cand_a_id}", headers=headers_b)
    assert b_access_a.status_code == 404

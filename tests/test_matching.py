import pytest
from app.schemas.schemas import LLMMatchOutput
from app.services.llm_matcher import compute_deterministic_evaluation, clean_json_string
from app.services.job_parser import parse_job_description

def test_clean_json_string():
    raw_with_markdown = "```json\n{\"match_score\": 85, \"recommendation\": \"Strong Match\"}\n```"
    cleaned = clean_json_string(raw_with_markdown)
    assert cleaned == "{\"match_score\": 85, \"recommendation\": \"Strong Match\"}"

def test_llm_output_schema_validation():
    valid_data = {
        "match_score": 85,
        "recommendation": "Strong Match",
        "matched_skills": ["Python", "FastAPI"],
        "missing_skills": ["Kubernetes"],
        "experience_assessment": "Solid background in backend development.",
        "strengths": ["FastAPI mastery"],
        "concerns": ["Missing Kubernetes"],
        "justification": "Candidate closely fits the requirements."
    }
    model = LLMMatchOutput(**valid_data)
    assert model.match_score == 85
    assert model.recommendation == "Strong Match"
    assert len(model.matched_skills) == 2

def test_llm_score_clamping():
    data = {
        "match_score": 120, # Out of range
        "recommendation": "Strong Match",
        "matched_skills": [],
        "missing_skills": [],
        "experience_assessment": "",
        "strengths": [],
        "concerns": [],
        "justification": "Clamped test."
    }
    model = LLMMatchOutput(**data)
    assert model.match_score == 100

def test_job_parser_skill_extraction():
    job_text = """
    Required:
    - 3+ years experience with Python, FastAPI, and PostgreSQL
    Preferred:
    - Docker, Kubernetes, AWS
    """
    job = parse_job_description(job_text, title="Backend Developer")
    assert "Python" in job["required_skills"]
    assert "FastAPI" in job["required_skills"]
    assert "Docker" in job["preferred_skills"] or "Docker" in job["required_skills"]

def test_deterministic_evaluation_strong_match():
    candidate = {
        "name": "Aarav Sharma",
        "skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "Redis", "AWS"],
        "experience": [{"role": "Backend Engineer", "company": "RazorScale Tech", "duration": "2020 - Present"}],
        "education": [{"degree": "B.Tech Computer Science", "institution": "IIT Bombay"}],
        "raw_text": "Senior Backend Engineer with Python and FastAPI experience."
    }
    job = {
        "title": "Senior Backend Engineer",
        "description": "Looking for Python, FastAPI, Docker, and PostgreSQL developer.",
        "required_skills": ["Python", "FastAPI", "PostgreSQL"],
        "preferred_skills": ["Docker", "Redis"]
    }
    eval_result = compute_deterministic_evaluation(candidate, job)
    assert eval_result.match_score >= 75
    assert eval_result.recommendation == "Strong Match"
    assert "Python" in eval_result.matched_skills

def test_deterministic_evaluation_weak_match():
    candidate = {
        "name": "Rohan Verma",
        "skills": ["Excel", "SEO", "Tableau"],
        "experience": [{"role": "SEO Specialist", "company": "UrbanScale Media", "duration": "2021 - 2023"}],
        "education": [{"degree": "B.A. Communications", "institution": "Delhi University"}],
        "raw_text": "Digital marketing and search engine optimization professional."
    }
    job = {
        "title": "Senior Backend Engineer",
        "description": "Requires Python, FastAPI, Docker, and PostgreSQL.",
        "required_skills": ["Python", "FastAPI", "PostgreSQL"],
        "preferred_skills": ["Docker", "Kubernetes"]
    }
    eval_result = compute_deterministic_evaluation(candidate, job)
    assert eval_result.match_score < 50
    assert eval_result.recommendation == "Weak Match"
    assert len(eval_result.missing_skills) > 0

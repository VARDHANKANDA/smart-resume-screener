import pytest
from app.services.resume_parser import (
    extract_email,
    extract_name,
    extract_skills,
    extract_experience,
    extract_education,
    parse_resume
)
from app.services.pdf_parser import extract_text_from_pdf, PDFParsingError

SAMPLE_RAW_RESUME = """Aarav Sharma
Email: aarav.sharma@example.com | Phone: +91-98765-43210
Bengaluru, Karnataka, India

PROFESSIONAL SUMMARY
Senior Software Developer with 6 years experience in Python, FastAPI, Docker, and PostgreSQL.

SKILLS
Python, FastAPI, Docker, PostgreSQL, Redis, Pytest, Git, Kubernetes

EXPERIENCE
Lead Backend Developer | RazorScale Tech | 2021 - Present
- Designed microservices architecture and scaled FastAPI REST APIs.
- Maintained PostgreSQL database and Redis caching layer.

Software Engineer | CodeCraft Solutions | 2018 - 2021
- Built cloud pipelines using Docker and Python.

EDUCATION
Bachelor of Technology in Computer Science
Indian Institute of Technology | 2014 - 2018
"""

def test_extract_email():
    email = extract_email(SAMPLE_RAW_RESUME)
    assert email == "aarav.sharma@example.com"

def test_extract_name():
    name = extract_name(SAMPLE_RAW_RESUME)
    assert name == "Aarav Sharma"

def test_extract_skills():
    skills = extract_skills(SAMPLE_RAW_RESUME)
    assert "Python" in skills
    assert "FastAPI" in skills
    assert "Docker" in skills
    assert "PostgreSQL" in skills
    assert "Redis" in skills
    assert "Kubernetes" in skills

def test_extract_experience():
    exp = extract_experience(SAMPLE_RAW_RESUME)
    assert len(exp) >= 1
    assert any("Lead Backend Developer" in (e.get("role") or "") for e in exp)

def test_extract_education():
    edu = extract_education(SAMPLE_RAW_RESUME)
    assert len(edu) >= 1
    assert any("Bachelor of Technology" in (e.get("degree") or "") for e in edu)

def test_parse_resume_complete():
    result = parse_resume(SAMPLE_RAW_RESUME, filename="aarav_resume.pdf")
    assert result["name"] == "Aarav Sharma"
    assert result["email"] == "aarav.sharma@example.com"
    assert "Python" in result["skills"]
    assert len(result["experience"]) >= 1
    assert len(result["education"]) >= 1
    assert result["source_filename"] == "aarav_resume.pdf"

def test_empty_resume_handling():
    with pytest.raises(PDFParsingError):
        extract_text_from_pdf(b"")

def test_invalid_pdf_bytes():
    with pytest.raises(PDFParsingError):
        extract_text_from_pdf(b"Not a real PDF header or content")

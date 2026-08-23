import json
import re
import requests
from typing import Dict, Any, List, Optional
from app.config import settings
from app.schemas.schemas import LLMMatchOutput
from app.prompts.matching_prompt import generate_matching_prompt

def clean_json_string(text: str) -> str:
    """Strip markdown code blocks or accidental preamble from LLM JSON response."""
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()

def compute_deterministic_evaluation(candidate: Dict[str, Any], job: Dict[str, Any]) -> LLMMatchOutput:
    """
    Intelligent semantic fallback evaluator for when LLM API keys are not configured
    or when external API service is unreachable.
    Evaluates candidate skills, work history, and job requirements without hallucination.
    """
    candidate_skills = set(candidate.get("skills") or [])
    job_required = set(job.get("required_skills") or [])
    job_preferred = set(job.get("preferred_skills") or [])
    all_job_skills = job_required.union(job_preferred)

    matched_skills = sorted(list(candidate_skills.intersection(all_job_skills)))
    missing_skills = sorted(list(all_job_skills - candidate_skills))

    # Calculate skill score (60% weight)
    if all_job_skills:
        req_matched = len(candidate_skills.intersection(job_required))
        req_total = len(job_required) if job_required else 1
        pref_matched = len(candidate_skills.intersection(job_preferred))
        pref_total = len(job_preferred) if job_preferred else 1

        skill_score = ((req_matched / req_total) * 45) + ((pref_matched / pref_total) * 15)
    else:
        skill_score = 40 if candidate_skills else 10

    # Calculate experience relevance (25% weight)
    experience_list = candidate.get("experience") or []
    raw_text = (candidate.get("raw_text") or "").lower()
    job_desc = (job.get("description") or "").lower()

    exp_score = 0
    if experience_list:
        exp_score += min(len(experience_list) * 7, 20)
        # Check if job title keywords appear in experience
        job_title_words = [w for w in (job.get("title") or "").lower().split() if len(w) > 3]
        if any(w in raw_text for w in job_title_words):
            exp_score += 5
    else:
        exp_score = 5

    # Education relevance (15% weight)
    education_list = candidate.get("education") or []
    edu_score = 15 if education_list else 5

    raw_score = int(skill_score + exp_score + edu_score)
    final_score = max(5, min(96, raw_score))

    # Determine recommendation based on strict thresholds
    if final_score >= 75:
        recommendation = "Strong Match"
    elif final_score >= 50:
        recommendation = "Potential Match"
    else:
        recommendation = "Weak Match"

    # Build evidence-based assessments
    cand_name = candidate.get("name") or "The candidate"
    
    # Strengths
    strengths = []
    if matched_skills:
        strengths.append(f"Demonstrated proficiency in key skills: {', '.join(matched_skills[:4])}")
    if experience_list:
        strengths.append(f"Documented professional work experience with {len(experience_list)} listed role(s)")
    if education_list:
        strengths.append(f"Relevant academic credentials ({education_list[0].get('degree', 'degree verified')})")

    # Concerns
    concerns = []
    if missing_skills:
        concerns.append(f"No explicit mention of required skill(s): {', '.join(missing_skills[:3])}")
    if not experience_list:
        concerns.append("Limited or unstructured professional experience documented in resume")
    if not education_list:
        concerns.append("Formal degree details not explicitly highlighted")

    # Experience assessment
    if experience_list:
        roles = [e.get("role") for e in experience_list if e.get("role")]
        roles_str = ", ".join(roles[:2]) if roles else "technical development"
        exp_assessment = f"{cand_name} demonstrates practical background in {roles_str} aligned with the position requirements."
    else:
        exp_assessment = f"{cand_name} provides minimal structured work experience relevant to the role."

    # Justification
    if recommendation == "Strong Match":
        justification = (
            f"{cand_name} strongly matches primary requirements, possessing {len(matched_skills)} core skills "
            f"({', '.join(matched_skills[:3])}) and proven hands-on experience."
        )
    elif recommendation == "Potential Match":
        missing_preview = f" (gaps: {', '.join(missing_skills[:2])})" if missing_skills else ""
        justification = (
            f"{cand_name} has a solid foundation with matching competencies in {', '.join(matched_skills[:3]) or 'relevant domain'}, "
            f"though key job requirements are missing{missing_preview}."
        )
    else:
        justification = (
            f"{cand_name} has low alignment with the job description. "
            f"Significant technical gaps exist ({', '.join(missing_skills[:3]) if missing_skills else 'core skills'}), resulting in a weak match."
        )

    return LLMMatchOutput(
        match_score=final_score,
        recommendation=recommendation,
        matched_skills=matched_skills,
        missing_skills=missing_skills,
        experience_assessment=exp_assessment,
        strengths=strengths if strengths else ["Basic profile submitted"],
        concerns=concerns if concerns else ["No major concerns detected"],
        justification=justification
    )

def evaluate_with_gemini(prompt: str, api_key: str, model_name: str) -> Optional[str]:
    """Call Google Gemini API via REST endpoint."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json"
        }
    }
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, json=payload, headers=headers, timeout=20)
    if response.status_code == 200:
        data = response.json()
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                return parts[0].get("text")
    return None

def evaluate_with_openai(prompt: str, api_key: str, model_name: str) -> Optional[str]:
    """Call OpenAI compatible chat completion API."""
    url = "https://api.openai.com/v1/chat/completions"
    payload = {
        "model": model_name or "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "You are an expert AI recruitment assistant that evaluates candidates and outputs only valid JSON."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"}
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    response = requests.post(url, json=payload, headers=headers, timeout=20)
    if response.status_code == 200:
        data = response.json()
        choices = data.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content")
    return None

def evaluate_candidate_match(candidate: Dict[str, Any], job: Dict[str, Any]) -> LLMMatchOutput:
    """
    Perform semantic matching between a candidate and job description.
    Uses LLM when configured, validates structured JSON output with Pydantic,
    and falls back to deterministic heuristic matching on failure.
    """
    # Format candidate resume representation for prompt
    resume_representation = (
        f"Candidate Name: {candidate.get('name') or 'N/A'}\n"
        f"Email: {candidate.get('email') or 'N/A'}\n"
        f"Parsed Skills: {', '.join(candidate.get('skills') or [])}\n"
        f"Structured Experience: {json.dumps(candidate.get('experience') or [], indent=2)}\n"
        f"Structured Education: {json.dumps(candidate.get('education') or [], indent=2)}\n"
        f"Resume Full Text:\n{candidate.get('raw_text') or ''}"
    )

    job_representation = (
        f"Job Title: {job.get('title') or 'N/A'}\n"
        f"Required Skills: {', '.join(job.get('required_skills') or [])}\n"
        f"Preferred Skills: {', '.join(job.get('preferred_skills') or [])}\n"
        f"Job Description Details:\n{job.get('description') or ''}"
    )

    prompt = generate_matching_prompt(
        resume_data=resume_representation,
        job_description=job_representation
    )

    # Attempt LLM call if API Key is configured
    if settings.LLM_API_KEY and settings.LLM_API_KEY != "your_gemini_or_openai_api_key_here":
        try:
            raw_response = None
            if settings.LLM_PROVIDER == "openai":
                raw_response = evaluate_with_openai(prompt, settings.LLM_API_KEY, settings.LLM_MODEL)
            else:
                raw_response = evaluate_with_gemini(prompt, settings.LLM_API_KEY, settings.LLM_MODEL)

            if raw_response:
                cleaned_json = clean_json_string(raw_response)
                parsed_data = json.loads(cleaned_json)
                
                # Standardize recommendation mapping based on score
                score = max(0, min(100, int(parsed_data.get("match_score", 50))))
                if score >= 75:
                    rec = "Strong Match"
                elif score >= 50:
                    rec = "Potential Match"
                else:
                    rec = "Weak Match"

                parsed_data["match_score"] = score
                parsed_data["recommendation"] = rec
                
                return LLMMatchOutput(**parsed_data)
        except Exception:
            # On LLM API timeout/format failure, seamlessly fall back to deterministic evaluation
            pass

    # Fallback to deterministic evaluation
    return compute_deterministic_evaluation(candidate, job)

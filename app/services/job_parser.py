import re
from typing import Dict, List, Any
from app.services.resume_parser import extract_skills

def parse_job_description(description: str, title: str = None) -> Dict[str, Any]:
    """
    Analyze job description text to extract required and preferred skills.
    """
    req_pattern = re.compile(
        r"(?:REQUIRED|REQUIREMENTS|MUST\s+HAVE|MINIMUM\s+QUALIFICATIONS|WHAT\s+YOU'LL\s+NEED)[\s\S]*?(?=(?:PREFERRED|NICE\s+TO\s+HAVE|BONUS|PERKS|BENEFITS|ABOUT\s+US|$))",
        re.IGNORECASE
    )
    pref_pattern = re.compile(
        r"(?:PREFERRED|NICE\s+TO\s+HAVE|BONUS|GOOD\s+TO\s+HAVE|PLUS)[\s\S]*?(?=(?:PERKS|BENEFITS|ABOUT\s+US|$))",
        re.IGNORECASE
    )

    req_match = req_pattern.search(description)
    pref_match = pref_pattern.search(description)

    all_skills = extract_skills(description)

    if req_match:
        required_skills = extract_skills(req_match.group(0))
    else:
        required_skills = all_skills[:int(len(all_skills) * 0.75)] if all_skills else []

    if pref_match:
        preferred_skills = extract_skills(pref_match.group(0))
    else:
        preferred_skills = [s for s in all_skills if s not in required_skills]

    # If splitting resulted in empty required skills but all_skills exists, assign all_skills to required
    if not required_skills and all_skills:
        required_skills = all_skills
        preferred_skills = []

    return {
        "title": title or "Software Engineering Position",
        "description": description.strip(),
        "required_skills": required_skills,
        "preferred_skills": preferred_skills,
        "all_skills": all_skills
    }

import re
from typing import Dict, List, Any, Optional

# Predefined comprehensive skill taxonomy with regex boundaries
SKILLS_TAXONOMY = [
    # Languages
    "Python", "Java", "JavaScript", "TypeScript", "C++", "C#", "Go", "Golang", "Rust", "Ruby",
    "PHP", "Swift", "Kotlin", "SQL", "HTML", "HTML5", "CSS", "CSS3", "R", "Scala", "Bash", "Shell",
    # Backend Frameworks & Tech
    "FastAPI", "Django", "Flask", "Express.js", "Express", "NestJS", "Spring Boot", "Spring",
    "Node.js", "REST APIs", "RESTful APIs", "REST", "GraphQL", "gRPC", "WebSockets", "Microservices",
    # Frontend Frameworks & Libraries
    "React", "React.js", "Next.js", "Vue", "Vue.js", "Angular", "Svelte", "Redux", "Tailwind CSS",
    "TailwindCSS", "Bootstrap", "Sass", "Webpack", "Vite",
    # Databases & Storage
    "PostgreSQL", "Postgres", "MySQL", "SQLite", "MongoDB", "Redis", "Elasticsearch",
    "Cassandra", "DynamoDB", "Firebase", "Supabase", "Oracle",
    # Cloud & DevOps
    "AWS", "Amazon Web Services", "Azure", "GCP", "Google Cloud", "Google Cloud Platform",
    "Docker", "Kubernetes", "K8s", "Terraform", "Ansible", "CI/CD", "Jenkins", "GitHub Actions",
    "GitLab CI", "Linux", "Nginx", "Apache", "Helm", "Prometheus", "Grafana",
    # Data, AI & ML
    "Machine Learning", "Deep Learning", "NLP", "Natural Language Processing", "Computer Vision",
    "LLM", "LLMs", "Large Language Models", "PyTorch", "TensorFlow", "Keras", "Scikit-Learn",
    "Pandas", "NumPy", "OpenCV", "LangChain", "Hugging Face", "Data Analysis", "Data Science",
    # Messaging & Async
    "Kafka", "Apache Kafka", "RabbitMQ", "Celery", "BullMQ",
    # Tools & Methodologies
    "Git", "GitHub", "GitLab", "Bitbucket", "Jira", "Postman", "Swagger", "OpenAPI",
    "Pytest", "Unit Testing", "TDD", "Agile", "Scrum", "OAuth", "JWT",
    # Analytics & Business
    "Excel", "Power BI", "Tableau", "SEO", "Market Research", "Product Management"
]

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")

DEGREE_PATTERNS = [
    r"Bachelor of Technology|B\.?\s*Tech",
    r"Bachelor of Engineering|B\.?\s*E\.?",
    r"Bachelor of Science|B\.?\s*S\.?|B\.?\s*Sc\.?",
    r"Bachelor of Arts|B\.?\s*A\.?",
    r"Bachelor of Computer Applications|BCA",
    r"Master of Technology|M\.?\s*Tech",
    r"Master of Engineering|M\.?\s*E\.?",
    r"Master of Science|M\.?\s*S\.?|M\.?\s*Sc\.?",
    r"Master of Computer Applications|MCA",
    r"Master of Business Administration|MBA",
    r"Doctor of Philosophy|Ph\.?D\.?",
    r"Associate Degree|Diploma"
]

def extract_email(text: str) -> Optional[str]:
    """Extract first valid email address from text."""
    matches = EMAIL_REGEX.findall(text)
    if matches:
        return matches[0].strip()
    return None

def extract_name(text: str) -> Optional[str]:
    """Extract candidate name from header of the resume."""
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if not lines:
        return None

    bad_keywords = {
        "resume", "curriculum", "vitae", "cv", "page", "profile", "contact",
        "email", "phone", "summary", "objective", "experience", "education",
        "skills", "projects", "portfolio", "github", "linkedin", "http", "www"
    }

    for line in lines[:6]:
        cleaned = re.sub(r"[^a-zA-Z\s]", "", line).strip()
        words = cleaned.split()
        if 2 <= len(words) <= 4:
            if not any(word.lower() in bad_keywords for word in words):
                if all(len(w) > 1 and (w[0].isupper() or w.isalpha()) for w in words):
                    return " ".join(words)

    first_line_clean = re.sub(r"[^a-zA-Z\s]", "", lines[0]).strip()
    words = first_line_clean.split()
    if 1 <= len(words) <= 3 and not any(w.lower() in bad_keywords for w in words):
        return first_line_clean

    return None

def extract_skills(text: str) -> List[str]:
    """Extract skills matching the skills taxonomy with case-insensitive boundary search."""
    found_skills = set()
    normalized_text = f" {text} "
    
    for skill in SKILLS_TAXONOMY:
        escaped_skill = re.escape(skill)
        pattern = rf"(?i)(?<![\w\.-]){escaped_skill}(?![\w\.-])"
        if re.search(pattern, normalized_text):
            canonical = skill
            if skill in ["Postgres", "PostgreSQL"]:
                canonical = "PostgreSQL"
            elif skill in ["Golang", "Go"]:
                canonical = "Go"
            elif skill in ["K8s", "Kubernetes"]:
                canonical = "Kubernetes"
            elif skill in ["Amazon Web Services", "AWS"]:
                canonical = "AWS"
            elif skill in ["Google Cloud Platform", "GCP", "Google Cloud"]:
                canonical = "GCP"
            elif skill in ["React.js", "React"]:
                canonical = "React"
            elif skill in ["Vue.js", "Vue"]:
                canonical = "Vue"
            elif skill in ["RESTful APIs", "REST APIs", "REST"]:
                canonical = "REST APIs"
            elif skill in ["Tailwind CSS", "TailwindCSS"]:
                canonical = "TailwindCSS"
            elif skill in ["LLMs", "Large Language Models", "LLM"]:
                canonical = "LLMs"
            found_skills.add(canonical)

    return sorted(list(found_skills))

def extract_experience(text: str) -> List[Dict[str, Any]]:
    """Extract structured work experience from resume text."""
    experiences: List[Dict[str, Any]] = []
    
    # Strictly match section heading on standalone line
    section_pattern = re.compile(
        r"(?:^|\n)\s*(?:WORK\s+EXPERIENCE|PROFESSIONAL\s+EXPERIENCE|EMPLOYMENT\s+HISTORY|EXPERIENCE|WORK\s+HISTORY)\s*(?::|\n|\r|$)",
        re.IGNORECASE
    )
    next_section_pattern = re.compile(
        r"(?:^|\n)\s*(?:EDUCATION|ACADEMIC\s+BACKGROUND|SKILLS|PROJECTS|CERTIFICATIONS|PUBLICATIONS|AWARDS|INTERESTS|DECLARATION)\s*(?::|\n|\r|$)",
        re.IGNORECASE
    )

    matches = list(section_pattern.finditer(text))
    if not matches:
        exp_text = text
    else:
        start_idx = matches[0].end()
        remaining_text = text[start_idx:]
        next_match = next_section_pattern.search(remaining_text)
        if next_match:
            exp_text = remaining_text[:next_match.start()].strip()
        else:
            exp_text = remaining_text.strip()

    date_regex = re.compile(
        r"((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?|\d{4})\s*(?:-|–|to)\s*(?:Present|Current|\d{4}|Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?\s*\d{4}?))",
        re.IGNORECASE
    )

    lines = [l.strip() for l in exp_text.split("\n") if l.strip()]
    current_entry: Optional[Dict[str, Any]] = None

    role_keywords = [
        "developer", "engineer", "lead", "architect", "manager", "intern", "consultant",
        "specialist", "analyst", "administrator", "designer", "officer", "assistant", "associate"
    ]

    for line in lines:
        date_match = date_regex.search(line)
        has_role = any(rk in line.lower() for rk in role_keywords)
        
        if date_match or has_role:
            if current_entry:
                experiences.append(current_entry)
            
            duration = date_match.group(1).strip() if date_match else None
            line_without_date = date_regex.sub("", line).strip(" -–,|")
            
            parts = [p.strip() for p in re.split(r"\||–|-| at |,|@", line_without_date) if p.strip()]
            role = parts[0] if parts else line_without_date
            company = parts[1] if len(parts) > 1 else None

            current_entry = {
                "role": role if role else "Software Engineer",
                "company": company,
                "duration": duration,
                "description": ""
            }
        else:
            if current_entry:
                if current_entry["description"]:
                    current_entry["description"] += " " + line
                else:
                    current_entry["description"] = line

    if current_entry:
        experiences.append(current_entry)

    # Clean descriptions
    for exp in experiences:
        if exp["description"]:
            exp["description"] = exp["description"][:500].strip()

    return experiences

def extract_education(text: str) -> List[Dict[str, Any]]:
    """Extract education details from resume text."""
    education_list: List[Dict[str, Any]] = []

    section_pattern = re.compile(r"(?:^|\n)\s*(?:EDUCATION|ACADEMIC\s+BACKGROUND|ACADEMICS|QUALIFICATIONS)\s*(?::|\n|\r|$)", re.IGNORECASE)
    next_section_pattern = re.compile(r"(?:^|\n)\s*(?:WORK\s+EXPERIENCE|EXPERIENCE|SKILLS|PROJECTS|CERTIFICATIONS)\s*(?::|\n|\r|$)", re.IGNORECASE)

    matches = list(section_pattern.finditer(text))
    if matches:
        start_idx = matches[0].end()
        remaining = text[start_idx:]
        next_m = next_section_pattern.search(remaining)
        edu_text = remaining[:next_m.start()].strip() if next_m else remaining.strip()
    else:
        edu_text = text

    combined_degree_regex = re.compile("|".join(DEGREE_PATTERNS), re.IGNORECASE)
    institution_regex = re.compile(r"([A-Za-z\s]+(?:University|Institute|College|Academy|School)[A-Za-z\s]*)", re.IGNORECASE)

    degree_matches = list(combined_degree_regex.finditer(edu_text))
    inst_matches = list(institution_regex.finditer(edu_text))

    if degree_matches:
        for i, deg_match in enumerate(degree_matches):
            degree_str = deg_match.group(0).strip()
            institution_str = None
            if i < len(inst_matches):
                institution_str = inst_matches[i].group(0).strip()
            elif inst_matches:
                institution_str = inst_matches[0].group(0).strip()

            education_list.append({
                "degree": degree_str,
                "institution": institution_str
            })
    elif inst_matches:
        for inst_match in inst_matches[:2]:
            education_list.append({
                "degree": "Higher Education Degree",
                "institution": inst_match.group(0).strip()
            })

    return education_list

def parse_resume(raw_text: str, filename: Optional[str] = None, candidate_name: Optional[str] = None) -> Dict[str, Any]:
    cleaned_text = raw_text.strip()
    extracted_name = candidate_name or extract_name(cleaned_text)
    extracted_email = extract_email(cleaned_text)
    extracted_skills = extract_skills(cleaned_text)
    extracted_exp = extract_experience(cleaned_text)
    extracted_edu = extract_education(cleaned_text)

    return {
        "name": extracted_name,
        "email": extracted_email,
        "source_filename": filename or "resume.txt",
        "skills": extracted_skills,
        "experience": extracted_exp,
        "education": extracted_edu,
        "raw_text": cleaned_text
    }

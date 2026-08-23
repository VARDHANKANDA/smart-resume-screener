from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field, EmailStr, field_validator

# --- Auth & User Schemas ---
class UserRegister(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100, description="Full Name of the user")
    email: str = Field(..., min_length=5, max_length=255, description="Valid email address")
    password: str = Field(..., min_length=6, max_length=128, description="Password (at least 6 characters)")
    confirm_password: Optional[str] = Field(None, description="Confirmation password")
    job_title: Optional[str] = Field("", description="Optional user role or job title")

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        clean = v.strip().lower()
        if "@" not in clean or "." not in clean.split("@")[-1]:
            raise ValueError("Invalid email format.")
        return clean

class UserLogin(BaseModel):
    email: str = Field(..., description="Email address")
    password: str = Field(..., description="Password")

    @field_validator("email")
    @classmethod
    def clean_email(cls, v: str) -> str:
        return v.strip().lower()

class UserResponse(BaseModel):
    id: int
    full_name: str
    email: str
    job_title: Optional[str] = ""
    created_at: Optional[str] = None

class UserProfileUpdate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    job_title: Optional[str] = Field("", max_length=100)

class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
    workspace: Optional[Dict[str, Any]] = None

# --- Workspace Schemas ---
class WorkspaceCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="Business / Company Workspace Name")
    job_title: Optional[str] = Field("", description="User's role in the company")

class WorkspaceUpdate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="Updated workspace name")

class WorkspaceMemberResponse(BaseModel):
    user_id: int
    full_name: str
    email: str
    job_title: Optional[str] = ""
    role: str
    joined_at: Optional[str] = None

class WorkspaceResponse(BaseModel):
    id: int
    name: str
    created_by_user_id: Optional[int] = None
    role: Optional[str] = "owner"
    created_at: Optional[str] = None
    members: List[WorkspaceMemberResponse] = Field(default_factory=list)

class AddMemberRequest(BaseModel):
    email: str = Field(..., min_length=5, description="Email of the user to invite / add")
    role: Optional[str] = Field("member", description="Role: 'member' or 'owner'")

# --- Candidate Schemas ---
class ExperienceItem(BaseModel):
    role: Optional[str] = None
    company: Optional[str] = None
    duration: Optional[str] = None
    description: Optional[str] = None

class EducationItem(BaseModel):
    degree: Optional[str] = None
    institution: Optional[str] = None

class TextResumeInput(BaseModel):
    text: str = Field(..., min_length=10, description="Raw text of the resume")
    candidate_name: Optional[str] = Field(None, description="Optional override candidate name")
    filename: Optional[str] = Field("pasted_text_resume.txt", description="Identifier source name")

class CandidateResponse(BaseModel):
    id: int
    workspace_id: Optional[int] = None
    user_id: Optional[int] = None
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    source_filename: Optional[str] = None
    resume_hash: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    experience: List[ExperienceItem] = Field(default_factory=list)
    education: List[EducationItem] = Field(default_factory=list)
    raw_text: Optional[str] = None
    created_at: Optional[str] = None

# --- Bulk Upload Schemas ---
class BulkUploadItemResult(BaseModel):
    filename: str
    status: Literal["success", "duplicate_skipped", "failed"]
    candidate_id: Optional[int] = None
    candidate_name: Optional[str] = None
    message: Optional[str] = None

class BulkResumeUploadResponse(BaseModel):
    total_files: int
    processed_count: int
    success_count: int
    duplicate_count: int
    failed_count: int
    results: List[BulkUploadItemResult]

# --- Job Schemas ---
class JobCreate(BaseModel):
    title: Optional[str] = Field(None, description="Job title")
    description: str = Field(..., min_length=15, description="Full job description")

class JobResponse(BaseModel):
    id: int
    workspace_id: Optional[int] = None
    user_id: Optional[int] = None
    title: Optional[str] = None
    description: str
    required_skills: List[str] = Field(default_factory=list)
    preferred_skills: List[str] = Field(default_factory=list)
    created_at: Optional[str] = None

# --- LLM Match Output Schema ---
class LLMMatchOutput(BaseModel):
    match_score: int = Field(..., description="Match score between 0 and 100")
    recommendation: Literal["Strong Match", "Potential Match", "Weak Match"]
    matched_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    experience_assessment: str = Field("", description="Assessment of candidate's relevant experience")
    strengths: List[str] = Field(default_factory=list)
    concerns: List[str] = Field(default_factory=list)
    justification: str = Field(..., description="Evidence-based reasoning for the score and recommendation")

    @field_validator("match_score", mode="before")
    @classmethod
    def clamp_score(cls, v: Any) -> int:
        try:
            val = int(v)
            return max(0, min(100, val))
        except (ValueError, TypeError):
            return 50

    @field_validator("recommendation", mode="before")
    @classmethod
    def validate_recommendation(cls, v: Any) -> str:
        v_clean = str(v).strip().title()
        if "Strong" in v_clean:
            return "Strong Match"
        elif "Potential" in v_clean:
            return "Potential Match"
        elif "Weak" in v_clean:
            return "Weak Match"
        return "Potential Match"

# --- Match Request & Response Schemas ---
class MatchCandidatesRequest(BaseModel):
    candidate_ids: Optional[List[int]] = Field(None, description="Specific candidate IDs to match. If omitted, matches all candidates in workspace.")

class MatchResultItem(BaseModel):
    id: int
    candidate_id: int
    candidate_name: str
    candidate_email: Optional[str] = None
    candidate_phone: Optional[str] = None
    source_filename: Optional[str] = None
    match_score: int
    recommendation: str
    matched_skills: List[str]
    missing_skills: List[str]
    experience_assessment: str
    strengths: List[str]
    concerns: List[str]
    justification: str
    candidate_skills: List[str] = Field(default_factory=list)
    candidate_experience: List[Dict[str, Any]] = Field(default_factory=list)
    candidate_education: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: Optional[str] = None

class JobMatchResultsResponse(BaseModel):
    job_id: int
    job_title: Optional[str] = None
    total_candidates_evaluated: int
    shortlisted_count: int
    results: List[MatchResultItem]

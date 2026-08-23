from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, status
from app.schemas.schemas import JobCreate, JobResponse
from app.services.job_parser import parse_job_description
from app.database.connection import JobDB
from app.api.auth import get_optional_workspace_context

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def create_job(payload: JobCreate, ctx: Dict[str, Any] = Depends(get_optional_workspace_context)):
    """
    Create a new job description with structured skill requirement extraction scoped to the workspace.
    """
    if not payload.description or len(payload.description.strip()) < 15:
        raise HTTPException(
            status_code=400,
            detail="Job description must be at least 15 characters long."
        )

    parsed = parse_job_description(payload.description, payload.title)
    user_id = ctx["user"]["id"] if ctx["user"] else None
    workspace_id = ctx["workspace_id"]

    job_id = JobDB.create(
        title=parsed["title"],
        description=parsed["description"],
        required_skills=parsed["required_skills"],
        preferred_skills=parsed["preferred_skills"],
        user_id=user_id,
        workspace_id=workspace_id
    )

    saved_job = JobDB.get_by_id(job_id, workspace_id=workspace_id, user_id=user_id)
    if not saved_job:
        raise HTTPException(status_code=500, detail="Failed to save job description.")

    return saved_job


@router.get("", response_model=List[JobResponse])
def get_all_jobs(ctx: Dict[str, Any] = Depends(get_optional_workspace_context)):
    """Retrieve all saved job descriptions for the active workspace."""
    workspace_id = ctx["workspace_id"]
    user_id = ctx["user"]["id"] if ctx["user"] else None
    return JobDB.get_all(workspace_id=workspace_id, user_id=user_id)


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: int, ctx: Dict[str, Any] = Depends(get_optional_workspace_context)):
    """Retrieve a single job description by ID within workspace."""
    workspace_id = ctx["workspace_id"]
    user_id = ctx["user"]["id"] if ctx["user"] else None
    job = JobDB.get_by_id(job_id, workspace_id=workspace_id, user_id=user_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job with ID {job_id} not found.")
    return job


@router.delete("/{job_id}", status_code=status.HTTP_200_OK)
def delete_job(job_id: int, ctx: Dict[str, Any] = Depends(get_optional_workspace_context)):
    """Delete a job description and its matching results within workspace."""
    workspace_id = ctx["workspace_id"]
    user_id = ctx["user"]["id"] if ctx["user"] else None
    
    job = JobDB.get_by_id(job_id, workspace_id=workspace_id, user_id=user_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job with ID {job_id} not found.")
    
    JobDB.delete(job_id, workspace_id=workspace_id, user_id=user_id)
    return {"message": f"Job #{job_id} successfully deleted."}

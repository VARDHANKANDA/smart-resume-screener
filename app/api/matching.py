from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, status
from app.schemas.schemas import MatchCandidatesRequest, JobMatchResultsResponse, MatchResultItem
from app.database.connection import JobDB, CandidateDB, MatchResultDB
from app.services.llm_matcher import evaluate_candidate_match
from app.api.auth import get_optional_workspace_context

router = APIRouter(prefix="/jobs", tags=["Matching"])


@router.post("/{job_id}/match", response_model=JobMatchResultsResponse, status_code=status.HTTP_200_OK)
def match_candidates_for_job(
    job_id: int,
    payload: Optional[MatchCandidatesRequest] = None,
    ctx: Dict[str, Any] = Depends(get_optional_workspace_context)
):
    """
    Run LLM semantic matching for candidates against the given job description.
    Scores, generates evidence-based justifications, and ranks candidates within the workspace.
    """
    user_id = ctx["user"]["id"] if ctx["user"] else None
    workspace_id = ctx["workspace_id"]

    job = JobDB.get_by_id(job_id, workspace_id=workspace_id, user_id=user_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job with ID {job_id} not found.")

    # Determine candidates to evaluate in this workspace
    all_candidates = CandidateDB.get_all(workspace_id=workspace_id, user_id=user_id)
    if not all_candidates:
        raise HTTPException(
            status_code=400,
            detail="No candidates found in your workspace pool. Please upload resumes before matching."
        )

    target_candidates = all_candidates
    if payload and payload.candidate_ids:
        id_set = set(payload.candidate_ids)
        target_candidates = [c for c in all_candidates if c["id"] in id_set]
        if not target_candidates:
            raise HTTPException(
                status_code=400,
                detail="None of the specified candidate IDs were found in your workspace."
            )

    # Evaluate each candidate
    for candidate in target_candidates:
        match_output = evaluate_candidate_match(candidate, job)
        
        # Save evaluation to database
        MatchResultDB.save_result(
            candidate_id=candidate["id"],
            job_id=job_id,
            match_score=match_output.match_score,
            recommendation=match_output.recommendation,
            matched_skills=match_output.matched_skills,
            missing_skills=match_output.missing_skills,
            experience_assessment=match_output.experience_assessment,
            strengths=match_output.strengths,
            concerns=match_output.concerns,
            justification=match_output.justification,
            user_id=user_id,
            workspace_id=workspace_id
        )

    # Fetch ranked results from database
    results = MatchResultDB.get_results_by_job(job_id, workspace_id=workspace_id, user_id=user_id)
    shortlisted_count = sum(1 for r in results if r["recommendation"] == "Strong Match")

    return {
        "job_id": job["id"],
        "job_title": job["title"],
        "total_candidates_evaluated": len(results),
        "shortlisted_count": shortlisted_count,
        "results": results
    }


@router.get("/{job_id}/results", response_model=JobMatchResultsResponse)
def get_job_match_results(job_id: int, ctx: Dict[str, Any] = Depends(get_optional_workspace_context)):
    """
    Retrieve ranked candidate match results for a specific job description in workspace.
    """
    user_id = ctx["user"]["id"] if ctx["user"] else None
    workspace_id = ctx["workspace_id"]

    job = JobDB.get_by_id(job_id, workspace_id=workspace_id, user_id=user_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job with ID {job_id} not found.")

    results = MatchResultDB.get_results_by_job(job_id, workspace_id=workspace_id, user_id=user_id)
    shortlisted_count = sum(1 for r in results if r["recommendation"] == "Strong Match")

    return {
        "job_id": job["id"],
        "job_title": job["title"],
        "total_candidates_evaluated": len(results),
        "shortlisted_count": shortlisted_count,
        "results": results
    }

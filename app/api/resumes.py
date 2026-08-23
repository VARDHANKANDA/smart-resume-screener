import hashlib
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Body, Depends, status
from app.schemas.schemas import CandidateResponse, TextResumeInput, BulkResumeUploadResponse, BulkUploadItemResult
from app.services.pdf_parser import extract_text_from_pdf, PDFParsingError
from app.services.resume_parser import parse_resume
from app.database.connection import CandidateDB
from app.api.auth import get_optional_workspace_context, get_current_workspace_context

router = APIRouter(prefix="/resumes", tags=["Resumes"])


@router.post("", response_model=CandidateResponse, status_code=status.HTTP_201_CREATED)
async def create_resume(
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
    candidate_name: Optional[str] = Form(None),
    ctx: Dict[str, Any] = Depends(get_optional_workspace_context)
):
    """
    Upload and parse a single resume from a PDF file or text form data.
    Checks for duplicates by content hash and email within the workspace.
    """
    raw_text = ""
    filename = "resume.txt"
    resume_hash = ""

    if file:
        filename = file.filename or "uploaded_resume.pdf"
        file_bytes = await file.read()
        
        if not file_bytes:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        # Compute hash of file bytes
        resume_hash = hashlib.sha256(file_bytes).hexdigest()

        if filename.lower().endswith(".pdf"):
            try:
                raw_text = extract_text_from_pdf(file_bytes)
            except PDFParsingError as e:
                raise HTTPException(status_code=400, detail=str(e))
        else:
            try:
                raw_text = file_bytes.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    raw_text = file_bytes.decode("latin-1")
                except Exception:
                    raise HTTPException(status_code=400, detail="Unable to decode resume text file.")
    elif text:
        raw_text = text.strip()
        filename = "pasted_text_resume.txt"
        resume_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
    else:
        raise HTTPException(
            status_code=400,
            detail="Either a PDF file upload or direct resume text must be provided."
        )

    if not raw_text or len(raw_text.strip()) < 15:
        raise HTTPException(
            status_code=400,
            detail="Resume content must contain meaningful text (at least 15 characters)."
        )

    # Perform structured parsing
    parsed_info = parse_resume(raw_text, filename=filename, candidate_name=candidate_name)

    user_id = ctx["user"]["id"] if ctx["user"] else None
    workspace_id = ctx["workspace_id"]

    # Duplicate check in workspace
    if workspace_id:
        existing = CandidateDB.find_duplicate(
            workspace_id=workspace_id,
            resume_hash=resume_hash,
            email=parsed_info.get("email")
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"This resume for '{existing.get('name') or parsed_info.get('name')}' has already been added to your candidate pool."
            )

    # Store in database
    candidate_id = CandidateDB.create(
        name=parsed_info["name"],
        email=parsed_info["email"],
        source_filename=parsed_info["source_filename"],
        skills=parsed_info["skills"],
        experience=parsed_info["experience"],
        education=parsed_info["education"],
        raw_text=parsed_info["raw_text"],
        user_id=user_id,
        workspace_id=workspace_id,
        resume_hash=resume_hash
    )

    saved_candidate = CandidateDB.get_by_id(candidate_id, workspace_id=workspace_id)
    if not saved_candidate:
        raise HTTPException(status_code=500, detail="Failed to save parsed candidate to database.")

    return saved_candidate


@router.post("/text", response_model=CandidateResponse, status_code=status.HTTP_201_CREATED)
def create_text_resume(payload: TextResumeInput, ctx: Dict[str, Any] = Depends(get_optional_workspace_context)):
    """
    JSON endpoint for directly submitting raw text resumes with duplicate detection.
    """
    if not payload.text or len(payload.text.strip()) < 15:
        raise HTTPException(status_code=400, detail="Resume text must contain at least 15 characters.")

    resume_hash = hashlib.sha256(payload.text.strip().encode("utf-8")).hexdigest()
    user_id = ctx["user"]["id"] if ctx["user"] else None
    workspace_id = ctx["workspace_id"]

    parsed_info = parse_resume(
        raw_text=payload.text,
        filename=payload.filename or "pasted_text_resume.txt",
        candidate_name=payload.candidate_name
    )

    # Duplicate check in workspace
    if workspace_id:
        existing = CandidateDB.find_duplicate(
            workspace_id=workspace_id,
            resume_hash=resume_hash,
            email=parsed_info.get("email")
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"This resume for '{existing.get('name') or parsed_info.get('name')}' has already been added to your candidate pool."
            )

    candidate_id = CandidateDB.create(
        name=parsed_info["name"],
        email=parsed_info["email"],
        source_filename=parsed_info["source_filename"],
        skills=parsed_info["skills"],
        experience=parsed_info["experience"],
        education=parsed_info["education"],
        raw_text=parsed_info["raw_text"],
        user_id=user_id,
        workspace_id=workspace_id,
        resume_hash=resume_hash
    )

    saved = CandidateDB.get_by_id(candidate_id, workspace_id=workspace_id)
    if not saved:
        raise HTTPException(status_code=500, detail="Failed to save candidate.")
    return saved


@router.post("/bulk", response_model=BulkResumeUploadResponse, status_code=status.HTTP_200_OK)
async def bulk_upload_resumes(
    files: List[UploadFile] = File(...),
    ctx: Dict[str, Any] = Depends(get_optional_workspace_context)
):
    """
    Bulk upload and process multiple resumes in batch.
    Processes each file independently, isolates errors, detects duplicates, and returns batch summary.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided for bulk upload.")

    user_id = ctx["user"]["id"] if ctx["user"] else None
    workspace_id = ctx["workspace_id"]

    results: List[BulkUploadItemResult] = []
    success_count = 0
    duplicate_count = 0
    failed_count = 0

    for file in files:
        filename = file.filename or "resume.pdf"
        try:
            file_bytes = await file.read()
            if not file_bytes:
                results.append(BulkUploadItemResult(
                    filename=filename,
                    status="failed",
                    message="Empty file."
                ))
                failed_count += 1
                continue

            file_hash = hashlib.sha256(file_bytes).hexdigest()

            # Extract text
            if filename.lower().endswith(".pdf"):
                raw_text = extract_text_from_pdf(file_bytes)
            else:
                try:
                    raw_text = file_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    raw_text = file_bytes.decode("latin-1")

            if not raw_text or len(raw_text.strip()) < 15:
                results.append(BulkUploadItemResult(
                    filename=filename,
                    status="failed",
                    message="File contains insufficient text content."
                ))
                failed_count += 1
                continue

            parsed_info = parse_resume(raw_text, filename=filename)

            # Duplicate check in workspace
            if workspace_id:
                existing = CandidateDB.find_duplicate(
                    workspace_id=workspace_id,
                    resume_hash=file_hash,
                    email=parsed_info.get("email")
                )
                if existing:
                    results.append(BulkUploadItemResult(
                        filename=filename,
                        status="duplicate_skipped",
                        candidate_name=existing.get("name") or parsed_info.get("name"),
                        message="Duplicate resume already exists in workspace."
                    ))
                    duplicate_count += 1
                    continue

            # Store in database
            candidate_id = CandidateDB.create(
                name=parsed_info["name"],
                email=parsed_info["email"],
                source_filename=parsed_info["source_filename"],
                skills=parsed_info["skills"],
                experience=parsed_info["experience"],
                education=parsed_info["education"],
                raw_text=parsed_info["raw_text"],
                user_id=user_id,
                workspace_id=workspace_id,
                resume_hash=file_hash
            )

            results.append(BulkUploadItemResult(
                filename=filename,
                status="success",
                candidate_id=candidate_id,
                candidate_name=parsed_info["name"],
                message="Successfully parsed and ingested."
            ))
            success_count += 1

        except Exception as e:
            results.append(BulkUploadItemResult(
                filename=filename,
                status="failed",
                message=str(e)
            ))
            failed_count += 1

    return BulkResumeUploadResponse(
        total_files=len(files),
        processed_count=len(files),
        success_count=success_count,
        duplicate_count=duplicate_count,
        failed_count=failed_count,
        results=results
    )


@router.get("", response_model=List[CandidateResponse])
def get_all_candidates(ctx: Dict[str, Any] = Depends(get_optional_workspace_context)):
    """Retrieve all parsed candidates stored in the database for the active workspace."""
    workspace_id = ctx["workspace_id"]
    user_id = ctx["user"]["id"] if ctx["user"] else None
    return CandidateDB.get_all(workspace_id=workspace_id, user_id=user_id)


@router.get("/{candidate_id}", response_model=CandidateResponse)
def get_candidate(candidate_id: int, ctx: Dict[str, Any] = Depends(get_optional_workspace_context)):
    """Retrieve detailed candidate information by ID within workspace."""
    workspace_id = ctx["workspace_id"]
    user_id = ctx["user"]["id"] if ctx["user"] else None
    candidate = CandidateDB.get_by_id(candidate_id, workspace_id=workspace_id, user_id=user_id)
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate with ID {candidate_id} not found.")
    return candidate


@router.delete("", status_code=status.HTTP_200_OK)
def clear_all_candidates(ctx: Dict[str, Any] = Depends(get_optional_workspace_context)):
    """Delete all candidate profiles and matching results for the active workspace."""
    workspace_id = ctx["workspace_id"]
    user_id = ctx["user"]["id"] if ctx["user"] else None
    count = CandidateDB.delete_all(workspace_id=workspace_id, user_id=user_id)
    return {"message": f"Successfully deleted {count} candidates from workspace."}


@router.delete("/{candidate_id}", status_code=status.HTTP_200_OK)
def delete_candidate(candidate_id: int, ctx: Dict[str, Any] = Depends(get_optional_workspace_context)):
    """Delete a single candidate and associated matching history within workspace."""
    workspace_id = ctx["workspace_id"]
    user_id = ctx["user"]["id"] if ctx["user"] else None
    
    candidate = CandidateDB.get_by_id(candidate_id, workspace_id=workspace_id, user_id=user_id)
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate with ID {candidate_id} not found in this workspace.")
    
    deleted = CandidateDB.delete(candidate_id, workspace_id=workspace_id, user_id=user_id)
    if not deleted:
        raise HTTPException(status_code=500, detail="Failed to delete candidate.")
    
    return {"message": f"Candidate #{candidate_id} ({candidate.get('name')}) successfully deleted."}

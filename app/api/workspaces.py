from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, Depends, status
from app.schemas.schemas import WorkspaceCreate, WorkspaceUpdate, WorkspaceResponse, WorkspaceMemberResponse, AddMemberRequest
from app.database.connection import WorkspaceDB, UserDB
from app.api.auth import get_current_user, get_current_workspace_context

router = APIRouter(prefix="/workspace", tags=["Workspace"])


@router.get("", response_model=WorkspaceResponse)
def get_current_workspace(ctx: Dict[str, Any] = Depends(get_current_workspace_context)):
    """Retrieve details and member list for the active workspace."""
    workspace = ctx["workspace"]
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active workspace found for this user. Please complete workspace setup."
        )
    
    members = WorkspaceDB.get_members(workspace["id"])
    return {
        "id": workspace["id"],
        "name": workspace["name"],
        "created_by_user_id": workspace["created_by_user_id"],
        "role": workspace.get("role", "member"),
        "created_at": workspace["created_at"],
        "members": members
    }


@router.post("/setup", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
def setup_workspace(payload: WorkspaceCreate, user: Dict[str, Any] = Depends(get_current_user)):
    """Create a new business workspace during onboarding or initial setup."""
    existing_ws = WorkspaceDB.get_user_primary_workspace(user["id"])
    if existing_ws:
        # Update existing workspace name if already exists
        WorkspaceDB.update_workspace_name(existing_ws["id"], payload.name)
        if payload.job_title:
            UserDB.update_profile(user["id"], user["full_name"], payload.job_title)
        ws_id = existing_ws["id"]
    else:
        ws_id = WorkspaceDB.create_workspace(payload.name, user["id"])
        if payload.job_title:
            UserDB.update_profile(user["id"], user["full_name"], payload.job_title)

    ws = WorkspaceDB.get_workspace_by_id(ws_id)
    members = WorkspaceDB.get_members(ws_id)

    return {
        "id": ws["id"],
        "name": ws["name"],
        "created_by_user_id": ws["created_by_user_id"],
        "role": "owner",
        "created_at": ws["created_at"],
        "members": members
    }


@router.put("", response_model=WorkspaceResponse)
def update_workspace(payload: WorkspaceUpdate, ctx: Dict[str, Any] = Depends(get_current_workspace_context)):
    """Update workspace / company name."""
    workspace = ctx["workspace"]
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found.")

    if workspace.get("role") != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only workspace owners can update workspace settings."
        )

    WorkspaceDB.update_workspace_name(workspace["id"], payload.name)
    ws = WorkspaceDB.get_workspace_by_id(workspace["id"])
    members = WorkspaceDB.get_members(workspace["id"])

    return {
        "id": ws["id"],
        "name": ws["name"],
        "created_by_user_id": ws["created_by_user_id"],
        "role": workspace.get("role", "owner"),
        "created_at": ws["created_at"],
        "members": members
    }


@router.post("/members", response_model=List[WorkspaceMemberResponse])
def add_team_member(payload: AddMemberRequest, ctx: Dict[str, Any] = Depends(get_current_workspace_context)):
    """Add a registered user to the company workspace by email."""
    workspace = ctx["workspace"]
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found.")

    if workspace.get("role") != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only workspace owners can invite or add team members."
        )

    target_user = UserDB.get_by_email(payload.email)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No registered user found with email '{payload.email}'. Please ask them to create an account first."
        )

    WorkspaceDB.add_member(workspace["id"], target_user["id"], payload.role or "member")
    return WorkspaceDB.get_members(workspace["id"])


@router.delete("/members/{member_user_id}", response_model=List[WorkspaceMemberResponse])
def remove_team_member(member_user_id: int, ctx: Dict[str, Any] = Depends(get_current_workspace_context)):
    """Remove a team member from the workspace."""
    workspace = ctx["workspace"]
    user = ctx["user"]
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found.")

    if workspace.get("role") != "owner" and user["id"] != member_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only workspace owners can remove team members."
        )

    if member_user_id == workspace["created_by_user_id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove the workspace creator."
        )

    WorkspaceDB.remove_member(workspace["id"], member_user_id)
    return WorkspaceDB.get_members(workspace["id"])

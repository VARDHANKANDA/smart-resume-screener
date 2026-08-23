from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Header, status
from app.schemas.schemas import UserRegister, UserLogin, UserResponse, UserProfileUpdate, AuthTokenResponse
from app.services.auth_service import (
    hash_password,
    verify_password,
    generate_session_token,
    validate_session_token,
    revoke_session_token
)
from app.database.connection import UserDB, WorkspaceDB

router = APIRouter(prefix="/auth", tags=["Authentication"])


def get_token_from_header(authorization: Optional[str] = Header(None)) -> Optional[str]:
    """Extract Bearer token from Authorization header if present."""
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return authorization


def get_current_user(token: Optional[str] = Depends(get_token_from_header)) -> Dict[str, Any]:
    """Dependency: require a valid authenticated user."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    user_id = validate_session_token(token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    user = UserDB.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return user


def get_optional_current_user(token: Optional[str] = Depends(get_token_from_header)) -> Optional[Dict[str, Any]]:
    """Dependency: returns user if valid token present, otherwise None without throwing 401."""
    if not token:
        return None
    user_id = validate_session_token(token)
    if not user_id:
        return None
    return UserDB.get_by_id(user_id)


def get_current_workspace_context(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Dependency: resolves the active workspace for the authenticated user."""
    workspace = WorkspaceDB.get_user_primary_workspace(user["id"])
    return {
        "user": user,
        "workspace": workspace,
        "workspace_id": workspace["id"] if workspace else None
    }


def get_optional_workspace_context(user: Optional[Dict[str, Any]] = Depends(get_optional_current_user)) -> Dict[str, Any]:
    """Dependency: resolves workspace context if authenticated, otherwise returns empty context."""
    if not user:
        return {"user": None, "workspace": None, "workspace_id": None}
    workspace = WorkspaceDB.get_user_primary_workspace(user["id"])
    return {
        "user": user,
        "workspace": workspace,
        "workspace_id": workspace["id"] if workspace else None
    }


@router.post("/register", response_model=AuthTokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister):
    """
    Register a new user account with secure password hashing.
    Rejects duplicate email addresses and returns an access token.
    """
    if payload.confirm_password is not None and payload.password != payload.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match."
        )

    # Check if user already exists
    existing = UserDB.get_by_email(payload.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists."
        )

    pwd_hash, salt = hash_password(payload.password)
    user_id = UserDB.create(
        full_name=payload.full_name,
        email=payload.email,
        password_hash=pwd_hash,
        salt=salt,
        job_title=payload.job_title or ""
    )

    created_user = UserDB.get_by_id(user_id)
    if not created_user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register user."
        )

    token = generate_session_token(user_id, created_user["email"])
    workspace = WorkspaceDB.get_user_primary_workspace(user_id)

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": created_user,
        "workspace": workspace
    }


@router.post("/login", response_model=AuthTokenResponse, status_code=status.HTTP_200_OK)
def login(payload: UserLogin):
    """
    Authenticate a user via email and password, returning an access token and active workspace.
    """
    user_record = UserDB.get_by_email(payload.email)
    if not user_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password."
        )

    if not verify_password(payload.password, user_record["password_hash"], user_record["salt"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password."
        )

    token = generate_session_token(user_record["id"], user_record["email"])
    workspace = WorkspaceDB.get_user_primary_workspace(user_record["id"])

    user_info = {
        "id": user_record["id"],
        "full_name": user_record["full_name"],
        "email": user_record["email"],
        "job_title": user_record.get("job_title", ""),
        "created_at": user_record["created_at"]
    }

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user_info,
        "workspace": workspace
    }


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(token: Optional[str] = Depends(get_token_from_header)):
    """Log out the current user session."""
    if token:
        revoke_session_token(token)
    return {"message": "Successfully logged out."}


@router.get("/me", response_model=Dict[str, Any])
def get_current_user_profile(ctx: Dict[str, Any] = Depends(get_current_workspace_context)):
    """Retrieve profile and active workspace information for currently authenticated user."""
    user = ctx["user"]
    return {
        "id": user["id"],
        "full_name": user["full_name"],
        "email": user["email"],
        "job_title": user.get("job_title", ""),
        "created_at": user.get("created_at"),
        "workspace": ctx["workspace"]
    }


@router.put("/me", response_model=UserResponse)
def update_user_profile(payload: UserProfileUpdate, user: Dict[str, Any] = Depends(get_current_user)):
    """Update authenticated user's personal profile (full name, job title)."""
    UserDB.update_profile(user["id"], payload.full_name, payload.job_title or "")
    updated_user = UserDB.get_by_id(user["id"])
    return updated_user

import sqlite3
import json
import hashlib
from contextlib import contextmanager
from typing import Generator, Any, Dict, List, Optional
from app.config import settings
from app.models.database_models import CREATE_TABLES_SQL, CREATE_INDICES_SQL

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

@contextmanager
def get_db_cursor() -> Generator[sqlite3.Cursor, None, None]:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

def init_db() -> None:
    """Initialize database tables and run lightweight migrations for columns if needed."""
    conn = get_connection()
    try:
        # 1. Create base tables
        conn.executescript(CREATE_TABLES_SQL)
        conn.commit()

        # 2. Check and add columns if migrating an existing database
        cursor = conn.cursor()
        
        # users migrations
        cursor.execute("PRAGMA table_info(users);")
        user_cols = [row["name"] for row in cursor.fetchall()]
        if "job_title" not in user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN job_title TEXT DEFAULT '';")
        if "updated_at" not in user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN updated_at TIMESTAMP;")

        # candidates migrations
        cursor.execute("PRAGMA table_info(candidates);")
        cand_cols = [row["name"] for row in cursor.fetchall()]
        if "workspace_id" not in cand_cols:
            cursor.execute("ALTER TABLE candidates ADD COLUMN workspace_id INTEGER;")
        if "phone" not in cand_cols:
            cursor.execute("ALTER TABLE candidates ADD COLUMN phone TEXT;")
        if "resume_hash" not in cand_cols:
            cursor.execute("ALTER TABLE candidates ADD COLUMN resume_hash TEXT;")

        # jobs migrations
        cursor.execute("PRAGMA table_info(jobs);")
        job_cols = [row["name"] for row in cursor.fetchall()]
        if "workspace_id" not in job_cols:
            cursor.execute("ALTER TABLE jobs ADD COLUMN workspace_id INTEGER;")

        # match_results migrations
        cursor.execute("PRAGMA table_info(match_results);")
        match_cols = [row["name"] for row in cursor.fetchall()]
        if "workspace_id" not in match_cols:
            cursor.execute("ALTER TABLE match_results ADD COLUMN workspace_id INTEGER;")

        conn.commit()

        # 3. Create indices after ensuring all columns exist
        conn.executescript(CREATE_INDICES_SQL)
        conn.commit()
    finally:
        conn.close()


# ================= DATABASE HELPER OPERATIONS =================

class UserDB:
    @staticmethod
    def create(full_name: str, email: str, password_hash: str, salt: str, job_title: str = "") -> int:
        with get_db_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO users (full_name, email, password_hash, salt, job_title)
                VALUES (?, ?, ?, ?, ?)
                """,
                (full_name.strip(), email.strip().lower(), password_hash, salt, job_title.strip())
            )
            return cursor.lastrowid

    @staticmethod
    def get_by_email(email: str) -> Optional[Dict[str, Any]]:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE LOWER(email) = LOWER(?)", (email.strip(),))
            row = cursor.fetchone()
            if row:
                return {
                    "id": row["id"],
                    "full_name": row["full_name"],
                    "email": row["email"],
                    "password_hash": row["password_hash"],
                    "salt": row["salt"],
                    "job_title": row["job_title"] if "job_title" in row.keys() else "",
                    "created_at": row["created_at"]
                }
            return None

    @staticmethod
    def get_by_id(user_id: int) -> Optional[Dict[str, Any]]:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            if row:
                return {
                    "id": row["id"],
                    "full_name": row["full_name"],
                    "email": row["email"],
                    "job_title": row["job_title"] if "job_title" in row.keys() else "",
                    "created_at": row["created_at"]
                }
            return None

    @staticmethod
    def update_profile(user_id: int, full_name: str, job_title: str) -> bool:
        with get_db_cursor() as cursor:
            cursor.execute(
                """
                UPDATE users
                SET full_name = ?, job_title = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (full_name.strip(), job_title.strip(), user_id)
            )
            return cursor.rowcount > 0


class WorkspaceDB:
    @staticmethod
    def create_workspace(name: str, user_id: int) -> int:
        with get_db_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO workspaces (name, created_by_user_id)
                VALUES (?, ?)
                """,
                (name.strip(), user_id)
            )
            workspace_id = cursor.lastrowid

            # Add creator as 'owner'
            cursor.execute(
                """
                INSERT INTO workspace_members (workspace_id, user_id, role)
                VALUES (?, ?, 'owner')
                """,
                (workspace_id, user_id)
            )
            return workspace_id

    @staticmethod
    def get_user_primary_workspace(user_id: int) -> Optional[Dict[str, Any]]:
        with get_db_cursor() as cursor:
            cursor.execute(
                """
                SELECT w.*, wm.role
                FROM workspaces w
                JOIN workspace_members wm ON w.id = wm.workspace_id
                WHERE wm.user_id = ?
                ORDER BY w.created_at ASC
                LIMIT 1
                """,
                (user_id,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    "id": row["id"],
                    "name": row["name"],
                    "created_by_user_id": row["created_by_user_id"],
                    "role": row["role"],
                    "created_at": row["created_at"]
                }
            return None

    @staticmethod
    def get_workspace_by_id(workspace_id: int) -> Optional[Dict[str, Any]]:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT * FROM workspaces WHERE id = ?", (workspace_id,))
            row = cursor.fetchone()
            if row:
                return {
                    "id": row["id"],
                    "name": row["name"],
                    "created_by_user_id": row["created_by_user_id"],
                    "created_at": row["created_at"]
                }
            return None

    @staticmethod
    def update_workspace_name(workspace_id: int, name: str) -> bool:
        with get_db_cursor() as cursor:
            cursor.execute(
                """
                UPDATE workspaces
                SET name = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (name.strip(), workspace_id)
            )
            return cursor.rowcount > 0

    @staticmethod
    def get_members(workspace_id: int) -> List[Dict[str, Any]]:
        with get_db_cursor() as cursor:
            cursor.execute(
                """
                SELECT u.id as user_id, u.full_name, u.email, u.job_title, wm.role, wm.created_at as joined_at
                FROM workspace_members wm
                JOIN users u ON wm.user_id = u.id
                WHERE wm.workspace_id = ?
                ORDER BY wm.role DESC, wm.created_at ASC
                """,
                (workspace_id,)
            )
            rows = cursor.fetchall()
            return [
                {
                    "user_id": row["user_id"],
                    "full_name": row["full_name"],
                    "email": row["email"],
                    "job_title": row["job_title"] or "",
                    "role": row["role"],
                    "joined_at": row["joined_at"]
                }
                for row in rows
            ]

    @staticmethod
    def add_member(workspace_id: int, user_id: int, role: str = "member") -> bool:
        with get_db_cursor() as cursor:
            cursor.execute(
                """
                INSERT OR IGNORE INTO workspace_members (workspace_id, user_id, role)
                VALUES (?, ?, ?)
                """,
                (workspace_id, user_id, role)
            )
            return cursor.rowcount > 0

    @staticmethod
    def remove_member(workspace_id: int, user_id: int) -> bool:
        with get_db_cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM workspace_members
                WHERE workspace_id = ? AND user_id = ?
                """,
                (workspace_id, user_id)
            )
            return cursor.rowcount > 0

    @staticmethod
    def is_user_in_workspace(workspace_id: int, user_id: int) -> bool:
        with get_db_cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM workspace_members WHERE workspace_id = ? AND user_id = ?",
                (workspace_id, user_id)
            )
            return cursor.fetchone() is not None


class CandidateDB:
    @staticmethod
    def compute_hash(text: str) -> str:
        """Compute SHA-256 hash for duplicate detection."""
        return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()

    @staticmethod
    def find_duplicate(workspace_id: Optional[int], resume_hash: Optional[str] = None, email: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Check for existing duplicate candidate in the same workspace."""
        if not workspace_id:
            return None

        with get_db_cursor() as cursor:
            if resume_hash:
                cursor.execute(
                    "SELECT * FROM candidates WHERE workspace_id = ? AND resume_hash = ?",
                    (workspace_id, resume_hash)
                )
                row = cursor.fetchone()
                if row:
                    return CandidateDB._format_row(row)

            if email and email.strip():
                cursor.execute(
                    "SELECT * FROM candidates WHERE workspace_id = ? AND LOWER(email) = LOWER(?)",
                    (workspace_id, email.strip())
                )
                row = cursor.fetchone()
                if row:
                    return CandidateDB._format_row(row)

        return None

    @staticmethod
    def create(name: Optional[str], email: Optional[str], source_filename: Optional[str],
               skills: List[str], experience: List[Dict[str, Any]], education: List[Dict[str, Any]],
               raw_text: str, user_id: Optional[int] = None, workspace_id: Optional[int] = None,
               phone: Optional[str] = None, resume_hash: Optional[str] = None) -> int:
        
        if not resume_hash and raw_text:
            resume_hash = CandidateDB.compute_hash(raw_text)

        with get_db_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO candidates (workspace_id, user_id, name, email, phone, source_filename, resume_hash, skills, experience, education, raw_text)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    workspace_id,
                    user_id,
                    name,
                    email,
                    phone,
                    source_filename,
                    resume_hash,
                    json.dumps(skills),
                    json.dumps(experience),
                    json.dumps(education),
                    raw_text
                )
            )
            return cursor.lastrowid

    @staticmethod
    def get_all(workspace_id: Optional[int] = None, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        with get_db_cursor() as cursor:
            if workspace_id is not None:
                cursor.execute("SELECT * FROM candidates WHERE workspace_id = ? ORDER BY created_at DESC", (workspace_id,))
            elif user_id is not None:
                cursor.execute("SELECT * FROM candidates WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
            else:
                cursor.execute("SELECT * FROM candidates ORDER BY created_at DESC")
            rows = cursor.fetchall()
            return [CandidateDB._format_row(row) for row in rows]

    @staticmethod
    def get_by_id(candidate_id: int, workspace_id: Optional[int] = None, user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        with get_db_cursor() as cursor:
            if workspace_id is not None:
                cursor.execute("SELECT * FROM candidates WHERE id = ? AND workspace_id = ?", (candidate_id, workspace_id))
            elif user_id is not None:
                cursor.execute("SELECT * FROM candidates WHERE id = ? AND user_id = ?", (candidate_id, user_id))
            else:
                cursor.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,))
            row = cursor.fetchone()
            if row:
                return CandidateDB._format_row(row)
            return None

    @staticmethod
    def delete(candidate_id: int, workspace_id: Optional[int] = None, user_id: Optional[int] = None) -> bool:
        with get_db_cursor() as cursor:
            # Delete associated match results first
            if workspace_id is not None:
                cursor.execute("DELETE FROM match_results WHERE candidate_id = ? AND workspace_id = ?", (candidate_id, workspace_id))
                cursor.execute("DELETE FROM candidates WHERE id = ? AND workspace_id = ?", (candidate_id, workspace_id))
            elif user_id is not None:
                cursor.execute("DELETE FROM match_results WHERE candidate_id = ? AND user_id = ?", (candidate_id, user_id))
                cursor.execute("DELETE FROM candidates WHERE id = ? AND user_id = ?", (candidate_id, user_id))
            else:
                cursor.execute("DELETE FROM match_results WHERE candidate_id = ?", (candidate_id,))
                cursor.execute("DELETE FROM candidates WHERE id = ?", (candidate_id,))
            return cursor.rowcount > 0

    @staticmethod
    def delete_all(workspace_id: Optional[int] = None, user_id: Optional[int] = None) -> int:
        with get_db_cursor() as cursor:
            if workspace_id is not None:
                cursor.execute("DELETE FROM match_results WHERE workspace_id = ?", (workspace_id,))
                cursor.execute("DELETE FROM candidates WHERE workspace_id = ?", (workspace_id,))
            elif user_id is not None:
                cursor.execute("DELETE FROM match_results WHERE user_id = ?", (user_id,))
                cursor.execute("DELETE FROM candidates WHERE user_id = ?", (user_id,))
            else:
                cursor.execute("DELETE FROM match_results")
                cursor.execute("DELETE FROM candidates")
            return cursor.rowcount

    @staticmethod
    def _format_row(row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "id": row["id"],
            "workspace_id": row["workspace_id"] if "workspace_id" in row.keys() else None,
            "user_id": row["user_id"] if "user_id" in row.keys() else None,
            "name": row["name"],
            "email": row["email"],
            "phone": row["phone"] if "phone" in row.keys() else None,
            "source_filename": row["source_filename"],
            "resume_hash": row["resume_hash"] if "resume_hash" in row.keys() else None,
            "skills": json.loads(row["skills"]) if row["skills"] else [],
            "experience": json.loads(row["experience"]) if row["experience"] else [],
            "education": json.loads(row["education"]) if row["education"] else [],
            "raw_text": row["raw_text"],
            "created_at": row["created_at"]
        }


class JobDB:
    @staticmethod
    def create(title: Optional[str], description: str, required_skills: List[str], preferred_skills: List[str],
               user_id: Optional[int] = None, workspace_id: Optional[int] = None) -> int:
        with get_db_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO jobs (workspace_id, user_id, title, description, required_skills, preferred_skills)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    workspace_id,
                    user_id,
                    title,
                    description,
                    json.dumps(required_skills),
                    json.dumps(preferred_skills)
                )
            )
            return cursor.lastrowid

    @staticmethod
    def get_all(workspace_id: Optional[int] = None, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        with get_db_cursor() as cursor:
            if workspace_id is not None:
                cursor.execute("SELECT * FROM jobs WHERE workspace_id = ? ORDER BY created_at DESC", (workspace_id,))
            elif user_id is not None:
                cursor.execute("SELECT * FROM jobs WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
            else:
                cursor.execute("SELECT * FROM jobs ORDER BY created_at DESC")
            rows = cursor.fetchall()
            return [JobDB._format_row(row) for row in rows]

    @staticmethod
    def get_by_id(job_id: int, workspace_id: Optional[int] = None, user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        with get_db_cursor() as cursor:
            if workspace_id is not None:
                cursor.execute("SELECT * FROM jobs WHERE id = ? AND workspace_id = ?", (job_id, workspace_id))
            elif user_id is not None:
                cursor.execute("SELECT * FROM jobs WHERE id = ? AND user_id = ?", (job_id, user_id))
            else:
                cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
            row = cursor.fetchone()
            if row:
                return JobDB._format_row(row)
            return None

    @staticmethod
    def delete(job_id: int, workspace_id: Optional[int] = None, user_id: Optional[int] = None) -> bool:
        with get_db_cursor() as cursor:
            if workspace_id is not None:
                cursor.execute("DELETE FROM match_results WHERE job_id = ? AND workspace_id = ?", (job_id, workspace_id))
                cursor.execute("DELETE FROM jobs WHERE id = ? AND workspace_id = ?", (job_id, workspace_id))
            elif user_id is not None:
                cursor.execute("DELETE FROM match_results WHERE job_id = ? AND user_id = ?", (job_id, user_id))
                cursor.execute("DELETE FROM jobs WHERE id = ? AND user_id = ?", (job_id, user_id))
            else:
                cursor.execute("DELETE FROM match_results WHERE job_id = ?", (job_id,))
                cursor.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
            return cursor.rowcount > 0

    @staticmethod
    def _format_row(row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "id": row["id"],
            "workspace_id": row["workspace_id"] if "workspace_id" in row.keys() else None,
            "user_id": row["user_id"] if "user_id" in row.keys() else None,
            "title": row["title"],
            "description": row["description"],
            "required_skills": json.loads(row["required_skills"]) if row["required_skills"] else [],
            "preferred_skills": json.loads(row["preferred_skills"]) if row["preferred_skills"] else [],
            "created_at": row["created_at"]
        }


class MatchResultDB:
    @staticmethod
    def save_result(candidate_id: int, job_id: int, match_score: int, recommendation: str,
                    matched_skills: List[str], missing_skills: List[str], experience_assessment: str,
                    strengths: List[str], concerns: List[str], justification: str,
                    user_id: Optional[int] = None, workspace_id: Optional[int] = None) -> int:
        with get_db_cursor() as cursor:
            # Delete any existing match result for this candidate and job
            cursor.execute(
                "DELETE FROM match_results WHERE candidate_id = ? AND job_id = ?",
                (candidate_id, job_id)
            )
            cursor.execute(
                """
                INSERT INTO match_results (
                    workspace_id, user_id, candidate_id, job_id, match_score, recommendation,
                    matched_skills, missing_skills, experience_assessment,
                    strengths, concerns, justification
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    workspace_id,
                    user_id,
                    candidate_id,
                    job_id,
                    match_score,
                    recommendation,
                    json.dumps(matched_skills),
                    json.dumps(missing_skills),
                    experience_assessment,
                    json.dumps(strengths),
                    json.dumps(concerns),
                    justification
                )
            )
            return cursor.lastrowid

    @staticmethod
    def get_results_by_job(job_id: int, workspace_id: Optional[int] = None, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        with get_db_cursor() as cursor:
            query = """
                SELECT 
                    m.id as match_id,
                    m.workspace_id,
                    m.user_id,
                    m.job_id,
                    m.match_score,
                    m.recommendation,
                    m.matched_skills,
                    m.missing_skills,
                    m.experience_assessment,
                    m.strengths,
                    m.concerns,
                    m.justification,
                    m.created_at as match_created_at,
                    c.id as candidate_id,
                    c.name as candidate_name,
                    c.email as candidate_email,
                    c.phone as candidate_phone,
                    c.source_filename,
                    c.skills as candidate_skills,
                    c.experience as candidate_experience,
                    c.education as candidate_education
                FROM match_results m
                JOIN candidates c ON m.candidate_id = c.id
                WHERE m.job_id = ?
            """
            params: List[Any] = [job_id]
            if workspace_id is not None:
                query += " AND m.workspace_id = ?"
                params.append(workspace_id)
            elif user_id is not None:
                query += " AND m.user_id = ?"
                params.append(user_id)
            query += " ORDER BY m.match_score DESC"

            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            results = []
            for row in rows:
                results.append({
                    "id": row["match_id"],
                    "candidate_id": row["candidate_id"],
                    "candidate_name": row["candidate_name"] or f"Candidate #{row['candidate_id']}",
                    "candidate_email": row["candidate_email"],
                    "candidate_phone": row["candidate_phone"] if "candidate_phone" in row.keys() else None,
                    "source_filename": row["source_filename"],
                    "match_score": row["match_score"],
                    "recommendation": row["recommendation"],
                    "matched_skills": json.loads(row["matched_skills"]) if row["matched_skills"] else [],
                    "missing_skills": json.loads(row["missing_skills"]) if row["missing_skills"] else [],
                    "experience_assessment": row["experience_assessment"],
                    "strengths": json.loads(row["strengths"]) if row["strengths"] else [],
                    "concerns": json.loads(row["concerns"]) if row["concerns"] else [],
                    "justification": row["justification"],
                    "candidate_skills": json.loads(row["candidate_skills"]) if row["candidate_skills"] else [],
                    "candidate_experience": json.loads(row["candidate_experience"]) if row["candidate_experience"] else [],
                    "candidate_education": json.loads(row["candidate_education"]) if row["candidate_education"] else [],
                    "created_at": row["match_created_at"]
                })
            return results

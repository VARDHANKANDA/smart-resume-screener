import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database.connection import init_db
from app.api.auth import router as auth_router
from app.api.workspaces import router as workspaces_router
from app.api.resumes import router as resumes_router
from app.api.jobs import router as jobs_router
from app.api.matching import router as matching_router

BASE_DIR = Path(__file__).resolve().parent.parent

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB tables & run migrations
    init_db()
    yield

app = FastAPI(
    title="Smart Resume Screener API",
    description="Intelligent AI-powered resume screening, structured parsing, candidate ranking system, and SaaS multi-tenant workspaces.",
    version="2.1.0",
    lifespan=lifespan
)

# Enable CORS for local integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(auth_router)
app.include_router(workspaces_router)
app.include_router(resumes_router)
app.include_router(jobs_router)
app.include_router(matching_router)

# Mount Static Files
static_dir = BASE_DIR / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """Serve the single-page frontend application dashboard."""
    template_path = BASE_DIR / "templates" / "index.html"
    if template_path.exists():
        with open(template_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Smart Resume Screener is running. (templates/index.html not found)</h1>")

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "Smart Resume Screener SaaS",
        "llm_provider": settings.LLM_PROVIDER,
        "llm_configured": bool(settings.LLM_API_KEY and settings.LLM_API_KEY != "your_gemini_or_openai_api_key_here")
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)

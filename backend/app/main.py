import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.routes import (
    auth,
    career,
    debate,
    feynman,
    planner,
    profile,
    quiz,
    rag,
    roadmap,
    rooms,
    tutor,
    voice,
)
from app.config import get_settings

settings = get_settings()
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title=settings.app_name,
    description="AI-powered learning platform — tutor, RAG, quizzes, and more.",
    version="1.0.0",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(auth.router, prefix="/api")
app.include_router(tutor.router, prefix="/api")
app.include_router(rag.router, prefix="/api")
app.include_router(quiz.router, prefix="/api")
app.include_router(feynman.router, prefix="/api")
app.include_router(debate.router, prefix="/api")
app.include_router(career.router, prefix="/api")
app.include_router(planner.router, prefix="/api")
app.include_router(roadmap.router, prefix="/api")
app.include_router(voice.router, prefix="/api")
app.include_router(rooms.router, prefix="/api")
app.include_router(profile.router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok", "app": settings.app_name}


# Serve frontend static files
FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

upload_path = Path(settings.upload_dir)
upload_path.mkdir(parents=True, exist_ok=True)

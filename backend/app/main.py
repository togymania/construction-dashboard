"""
Construction Management API - Entry Point
FastAPI application bootstrap.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Enterprise Construction Dashboard Backend",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    """Liveness/readiness probe endpoint."""
    return {
        "status": "ok",
        "service": "construction-api",
        "environment": settings.ENVIRONMENT,
    }


@app.get("/", tags=["Root"])
async def root() -> dict:
    """Root endpoint - API bilgisi."""
    return {
        "message": f"{settings.PROJECT_NAME} v0.1.0",
        "docs": "/docs",
        "health": "/health",
    }

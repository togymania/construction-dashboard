"""Construction Management API -- entry point.

Wires the FastAPI app, mounts the v1 router, and configures CORS from
the comma-separated CORS_ORIGINS env var (so production can whitelist
the Vercel domain without code changes).
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_v1_router
from app.core.config import settings


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Enterprise Construction Dashboard Backend",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS_LIST or ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)


@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    return {
        "status": "ok",
        "service": "construction-api",
        "environment": settings.ENVIRONMENT,
    }


@app.get("/", tags=["Root"])
async def root() -> dict:
    return {
        "message": f"{settings.PROJECT_NAME} v0.1.0",
        "docs": "/docs",
        "api": settings.API_V1_PREFIX,
    }

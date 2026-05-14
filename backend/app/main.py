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


# CORS: in addition to the explicit list, allow any Vercel preview
# subdomain on this project so production + branch deploys both work
# without needing to chase the random hash subdomain in env vars.
_cors_origins = settings.CORS_ORIGINS_LIST or ["http://localhost:3000"]
print(f"[CORS] allow_origins = {_cors_origins}")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=r"https://(monotek|monart)-stroy-pm.*\.vercel\.app",
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

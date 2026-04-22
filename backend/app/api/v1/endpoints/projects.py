"""Projects API endpoints."""
from fastapi import APIRouter, HTTPException

from app.db.seed import MOCK_PROJECTS
from app.schemas.project import ProjectResponse

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.get("", response_model=list[ProjectResponse], summary="List all projects")
async def list_projects() -> list[ProjectResponse]:
    return MOCK_PROJECTS


@router.get("/{project_id}", response_model=ProjectResponse, summary="Get project by ID")
async def get_project(project_id: int) -> ProjectResponse:
    project = next((p for p in MOCK_PROJECTS if p.id == project_id), None)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

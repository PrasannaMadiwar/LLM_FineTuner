from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_current_user, get_project_service
from app.domain.users import User
from app.schemas.projects import (
    ProjectCreateRequest,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdateRequest,
)
from app.services.project_service import ProjectService

router = APIRouter()
ProjectServiceDep = Annotated[ProjectService, Depends(get_project_service)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreateRequest,
    project_service: ProjectServiceDep,
    current_user: CurrentUserDep,
):
    project = await project_service.create_project(
        user_id=current_user.id,
        name=payload.name,
        description=payload.description,
        metadata=payload.metadata,
    )
    return ProjectResponse(project=project)


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    project_service: ProjectServiceDep,
    current_user: CurrentUserDep,
):
    return ProjectListResponse(projects=await project_service.list_projects(current_user.id))


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    project_service: ProjectServiceDep,
    current_user: CurrentUserDep,
):
    try:
        return ProjectResponse(project=await project_service.get_project(current_user.id, project_id))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    payload: ProjectUpdateRequest,
    project_service: ProjectServiceDep,
    current_user: CurrentUserDep,
):
    try:
        project = await project_service.update_project(
            user_id=current_user.id,
            project_id=project_id,
            name=payload.name,
            description=payload.description,
            metadata=payload.metadata,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ProjectResponse(project=project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    project_service: ProjectServiceDep,
    current_user: CurrentUserDep,
):
    try:
        await project_service.delete_project(current_user.id, project_id)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

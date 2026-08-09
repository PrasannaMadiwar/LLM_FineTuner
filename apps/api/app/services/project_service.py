from uuid import UUID

from app.domain.projects import Project
from app.infrastructure.repositories.project_repository import ProjectRepository


class ProjectService:
    def __init__(self, repository: ProjectRepository):
        self._repository = repository

    async def create_project(
        self,
        user_id: UUID,
        name: str,
        description: str | None = None,
        metadata: dict | None = None,
    ) -> Project:
        return await self._repository.create_project(user_id, name, description, metadata)

    async def list_projects(self, user_id: UUID) -> list[Project]:
        return await self._repository.list_projects(user_id)

    async def get_project(self, user_id: UUID, project_id: UUID) -> Project:
        return await self._require_owned_project(user_id, project_id)

    async def update_project(
        self,
        user_id: UUID,
        project_id: UUID,
        name: str | None = None,
        description: str | None = None,
        metadata: dict | None = None,
    ) -> Project:
        await self._require_owned_project(user_id, project_id)
        return await self._repository.update_project(project_id, name, description, metadata)

    async def delete_project(self, user_id: UUID, project_id: UUID) -> None:
        await self._require_owned_project(user_id, project_id)
        await self._repository.delete_project(project_id)

    async def _require_owned_project(self, user_id: UUID, project_id: UUID) -> Project:
        project = await self._repository.get_project(project_id)
        if project is None:
            raise ValueError("Project not found.")
        if project.user_id != user_id:
            raise PermissionError("You do not have access to this project.")
        return project

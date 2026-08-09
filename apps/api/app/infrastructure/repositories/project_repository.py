from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.projects import Project
from app.infrastructure.models.project import ProjectModel


class ProjectRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create_project(
        self,
        user_id: UUID,
        name: str,
        description: str | None = None,
        metadata: dict | None = None,
    ) -> Project:
        now = datetime.now(UTC)
        model = ProjectModel(
            user_id=user_id,
            name=name,
            description=description,
            metadata_json=metadata or {},
            created_at=now,
            updated_at=now,
        )
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return self._to_project(model)

    async def list_projects(self, user_id: UUID) -> list[Project]:
        result = await self._session.execute(
            select(ProjectModel)
            .where(ProjectModel.user_id == user_id)
            .order_by(ProjectModel.created_at.desc())
        )
        return [self._to_project(model) for model in result.scalars().all()]

    async def get_project(self, project_id: UUID) -> Project | None:
        model = await self._session.get(ProjectModel, project_id)
        return self._to_project(model) if model else None

    async def update_project(
        self,
        project_id: UUID,
        name: str | None = None,
        description: str | None = None,
        metadata: dict | None = None,
    ) -> Project:
        model = await self._session.get(ProjectModel, project_id)
        if model is None:
            raise ValueError("Project not found.")
        if name is not None:
            model.name = name
        if description is not None:
            model.description = description
        if metadata is not None:
            model.metadata_json = metadata
        model.updated_at = datetime.now(UTC)
        await self._session.commit()
        await self._session.refresh(model)
        return self._to_project(model)

    async def delete_project(self, project_id: UUID) -> None:
        model = await self._session.get(ProjectModel, project_id)
        if model is None:
            raise ValueError("Project not found.")
        await self._session.delete(model)
        await self._session.commit()

    @staticmethod
    def _to_project(model: ProjectModel) -> Project:
        return Project(
            id=model.id,
            user_id=model.user_id,
            name=model.name,
            description=model.description,
            metadata=model.metadata_json or {},
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

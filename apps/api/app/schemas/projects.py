from pydantic import BaseModel, Field

from app.domain.projects import Project


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    metadata: dict = Field(default_factory=dict)


class ProjectUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    metadata: dict | None = None


class ProjectResponse(BaseModel):
    project: Project


class ProjectListResponse(BaseModel):
    projects: list[Project]

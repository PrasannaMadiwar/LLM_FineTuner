from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user, get_project_service
from app.domain.projects import Project
from app.domain.users import User, UserRole
from app.main import app


class FakeProjectService:
    def __init__(self):
        self.projects = {}

    async def create_project(self, user_id, name, description=None, metadata=None):
        now = datetime.now(UTC)
        project = Project(
            id=uuid4(),
            user_id=user_id,
            name=name,
            description=description,
            metadata=metadata or {},
            created_at=now,
            updated_at=now,
        )
        self.projects[project.id] = project
        return project

    async def list_projects(self, user_id):
        return [project for project in self.projects.values() if project.user_id == user_id]

    async def get_project(self, user_id, project_id):
        project = self.projects.get(project_id)
        if project is None:
            raise ValueError("Project not found.")
        if project.user_id != user_id:
            raise PermissionError("You do not have access to this project.")
        return project

    async def update_project(self, user_id, project_id, name=None, description=None, metadata=None):
        project = await self.get_project(user_id, project_id)
        updated = project.model_copy(
            update={
                "name": name or project.name,
                "description": description if description is not None else project.description,
                "metadata": metadata if metadata is not None else project.metadata,
                "updated_at": datetime.now(UTC),
            }
        )
        self.projects[project_id] = updated
        return updated

    async def delete_project(self, user_id, project_id):
        await self.get_project(user_id, project_id)
        del self.projects[project_id]


def test_project_crud_api():
    service = FakeProjectService()
    user = _user()
    client = _client(service, user)

    created = client.post("/api/v1/projects", json={"name": "Demo", "description": "One"})
    project_id = created.json()["project"]["id"]
    listed = client.get("/api/v1/projects")
    fetched = client.get(f"/api/v1/projects/{project_id}")
    updated = client.patch(f"/api/v1/projects/{project_id}", json={"name": "Renamed"})
    deleted = client.delete(f"/api/v1/projects/{project_id}")
    missing = client.get(f"/api/v1/projects/{project_id}")

    assert created.status_code == 201
    assert listed.status_code == 200
    assert len(listed.json()["projects"]) == 1
    assert fetched.json()["project"]["name"] == "Demo"
    assert updated.json()["project"]["name"] == "Renamed"
    assert deleted.status_code == 204
    assert missing.status_code == 404


def test_project_api_enforces_ownership():
    service = FakeProjectService()
    owner = _user()
    other = _user()
    owner_client = _client(service, owner)
    project_id = owner_client.post("/api/v1/projects", json={"name": "Private"}).json()["project"]["id"]

    other_client = _client(service, other)
    response = other_client.get(f"/api/v1/projects/{project_id}")

    assert response.status_code == 403


def _client(service: FakeProjectService, user: User) -> TestClient:
    app.dependency_overrides.clear()
    app.dependency_overrides[get_project_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def _user() -> User:
    return User(
        id=uuid4(),
        email=f"{uuid4()}@example.com",
        hashed_password="hash",
        role=UserRole.USER,
        is_active=True,
    )

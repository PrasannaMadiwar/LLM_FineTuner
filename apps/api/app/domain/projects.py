from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class Project(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    description: str | None = None
    metadata: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

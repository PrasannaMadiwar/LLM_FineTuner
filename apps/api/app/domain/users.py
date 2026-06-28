from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, EmailStr


class UserRole(StrEnum):
    ADMIN = "admin"
    USER = "user"


class User(BaseModel):
    id: UUID
    email: EmailStr
    hashed_password: str
    role: UserRole
    is_active: bool

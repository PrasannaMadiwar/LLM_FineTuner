from uuid import uuid4

import asyncio

from app.domain.users import User, UserRole
from app.schemas.auth import RegisterRequest
from app.services.auth_service import AuthenticationService


class FakeUserRepository:
    def __init__(self):
        self.users_by_email = {}
        self.users_by_id = {}

    async def get_by_email(self, email):
        return self.users_by_email.get(email)

    async def get_by_id(self, user_id):
        return self.users_by_id.get(user_id)

    async def create(self, email, hashed_password):
        user = User(
            id=uuid4(),
            email=email,
            hashed_password=hashed_password,
            role=UserRole.USER,
            is_active=True,
        )
        self.users_by_email[email] = user
        self.users_by_id[user.id] = user
        return user


def test_register_user_hashes_password():
    repository = FakeUserRepository()
    service = AuthenticationService(repository)

    user = asyncio.run(
        service.register_user(RegisterRequest(email="user@example.com", password="strong-password"))
    )

    assert user.email == "user@example.com"
    assert user.hashed_password != "strong-password"


def test_register_user_rejects_duplicate_email():
    repository = FakeUserRepository()
    service = AuthenticationService(repository)
    payload = RegisterRequest(email="user@example.com", password="strong-password")

    asyncio.run(service.register_user(payload))

    try:
        asyncio.run(service.register_user(payload))
    except ValueError:
        return
    raise AssertionError("Duplicate email should raise ValueError.")


def test_authenticate_user_returns_token_for_valid_password():
    repository = FakeUserRepository()
    service = AuthenticationService(repository)
    asyncio.run(
        service.register_user(RegisterRequest(email="user@example.com", password="strong-password"))
    )

    token = asyncio.run(service.authenticate_user("user@example.com", "strong-password"))

    assert token is not None
    assert token.token_type == "bearer"
    assert token.access_token

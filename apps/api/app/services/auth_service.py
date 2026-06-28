from app.core.security import create_access_token, hash_password, verify_password
from app.infrastructure.repositories.user_repository import UserRepository
from app.schemas.auth import RegisterRequest, TokenResponse


class AuthenticationService:
    def __init__(self, user_repository: UserRepository):
        self._user_repository = user_repository

    async def register_user(self, payload: RegisterRequest):
        existing_user = await self._user_repository.get_by_email(payload.email)
        if existing_user is not None:
            raise ValueError("A user with this email already exists.")
        return await self._user_repository.create(
            email=payload.email,
            hashed_password=hash_password(payload.password),
        )

    async def authenticate_user(self, email: str, password: str) -> TokenResponse | None:
        user = await self._user_repository.get_by_email(email)
        if user is None or not verify_password(password, user.hashed_password):
            return None
        return TokenResponse(access_token=create_access_token(user.id))

    async def get_user_by_id(self, user_id):
        return await self._user_repository.get_by_id(user_id)

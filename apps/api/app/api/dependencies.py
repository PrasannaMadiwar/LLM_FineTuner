from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import create_redis_client
from app.core.config import get_settings
from app.core.database import get_session
from app.core.security import decode_access_token
from app.domain.gpu import GPUProviderName
from app.domain.users import User, UserRole
from app.infrastructure.cache.mapping_cache import MappingCache
from app.infrastructure.datasets.demo_provider import DemoDatasetProvider
from app.infrastructure.datasets.github_provider import GitHubDatasetProvider
from app.infrastructure.datasets.huggingface_provider import HuggingFaceDatasetProvider
from app.infrastructure.datasets.kaggle_provider import KaggleDatasetProvider
from app.infrastructure.gpu.factory import create_gpu_provider
from app.infrastructure.llm.openai_provider import OpenAIProvider
from app.infrastructure.repositories.dataset_repository import DatasetRepository
from app.infrastructure.repositories.gpu_repository import GPURepository
from app.infrastructure.repositories.project_repository import ProjectRepository
from app.infrastructure.repositories.training_job_repository import TrainingJobRepository
from app.infrastructure.repositories.user_repository import UserRepository
from app.schemas.auth import TokenPayload
from app.services.auth_service import AuthenticationService
from app.services.dataset_converter_service import DatasetConverterService
from app.services.dataset_service import DatasetService
from app.services.dataset_validation_service import DatasetValidationService
from app.services.gpu_service import GPUService
from app.services.model_registry import ModelRegistry
from app.services.project_service import ProjectService
from app.services.semantic_mapping_service import SemanticMappingService
from app.services.template_loader import TemplateLoader
from app.services.training_service import TrainingService
from app.services.training_state_machine import TrainingStateMachine
from app.services.training_task_dispatcher import TrainingTaskDispatcher

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_session():
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


def get_user_repository(
    session: SessionDep,
) -> UserRepository:
    return UserRepository(session)


def get_authentication_service(
    user_repository: Annotated[UserRepository, Depends(get_user_repository)],
) -> AuthenticationService:
    return AuthenticationService(user_repository)


def get_dataset_repository(
    session: SessionDep,
) -> DatasetRepository:
    return DatasetRepository(session)


def get_gpu_repository(
    session: SessionDep,
) -> GPURepository:
    return GPURepository(session)


def get_project_repository(
    session: SessionDep,
) -> ProjectRepository:
    return ProjectRepository(session)


def get_training_job_repository(
    session: SessionDep,
) -> TrainingJobRepository:
    return TrainingJobRepository(session)


def get_model_registry() -> ModelRegistry:
    return ModelRegistry()


def get_template_loader() -> TemplateLoader:
    return TemplateLoader()


def get_training_state_machine() -> TrainingStateMachine:
    return TrainingStateMachine()


def get_training_task_dispatcher() -> TrainingTaskDispatcher:
    return TrainingTaskDispatcher()


def get_training_service(
    repository: Annotated[TrainingJobRepository, Depends(get_training_job_repository)],
    model_registry: Annotated[ModelRegistry, Depends(get_model_registry)],
    template_loader: Annotated[TemplateLoader, Depends(get_template_loader)],
    state_machine: Annotated[TrainingStateMachine, Depends(get_training_state_machine)],
    task_dispatcher: Annotated[TrainingTaskDispatcher, Depends(get_training_task_dispatcher)],
) -> TrainingService:
    return TrainingService(
        repository=repository,
        model_registry=model_registry,
        template_loader=template_loader,
        state_machine=state_machine,
        task_dispatcher=task_dispatcher,
    )


def get_semantic_mapping_service(
    dataset_repository: Annotated[DatasetRepository, Depends(get_dataset_repository)],
) -> SemanticMappingService:
    settings = get_settings()
    return SemanticMappingService(
        dataset_repository,
        OpenAIProvider(
            api_key=settings.llm_semantic_mapping_api_key or settings.openai_api_key,
            base_url=settings.llm_semantic_mapping_url or "https://api.openai.com/v1",
            model=settings.openai_model,
        ),
        MappingCache(create_redis_client(), settings.mapping_cache_ttl_seconds),
    )


def get_dataset_converter_service() -> DatasetConverterService:
    return DatasetConverterService()


def get_dataset_validation_service() -> DatasetValidationService:
    return DatasetValidationService()


def get_dataset_service(
    dataset_repository: Annotated[DatasetRepository, Depends(get_dataset_repository)],
    semantic_mapping_service: Annotated[SemanticMappingService, Depends(get_semantic_mapping_service)],
    converter_service: Annotated[DatasetConverterService, Depends(get_dataset_converter_service)],
    validation_service: Annotated[DatasetValidationService, Depends(get_dataset_validation_service)],
) -> DatasetService:
    return DatasetService(
        repository=dataset_repository,
        providers=[
            DemoDatasetProvider(),
            HuggingFaceDatasetProvider(),
            KaggleDatasetProvider(),
            GitHubDatasetProvider(),
        ],
        semantic_mapping_service=semantic_mapping_service,
        converter_service=converter_service,
        validation_service=validation_service,
    )


def get_gpu_service(
    gpu_repository: Annotated[GPURepository, Depends(get_gpu_repository)],
) -> GPUService:
    settings = get_settings()
    try:
        provider_name = GPUProviderName(settings.gpu_provider)
        provider = create_gpu_provider(provider_name)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"GPU provider '{settings.gpu_provider}' is not implemented.",
        ) from exc
    return GPUService(
        repository=gpu_repository,
        provider=provider,
        provider_name=provider_name,
    )


def get_project_service(
    project_repository: Annotated[ProjectRepository, Depends(get_project_repository)],
) -> ProjectService:
    return ProjectService(project_repository)


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    auth_service: Annotated[AuthenticationService, Depends(get_authentication_service)],
) -> User:
    payload_data = decode_access_token(token)
    if payload_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = TokenPayload(**payload_data)
    user = await auth_service.get_user_by_id(payload.sub)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive or missing user.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_role(*allowed_roles: UserRole):
    async def dependency(current_user: Annotated[User, Depends(get_current_user)]) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions.",
            )
        return current_user

    return dependency

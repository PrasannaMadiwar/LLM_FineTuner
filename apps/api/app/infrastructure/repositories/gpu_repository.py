from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.gpu import GPUEvent, GPUEventType, GPUInstance, GPUInstanceStatus, GPUProviderName
from app.infrastructure.models.gpu import GPUEventModel, GPUInstanceModel


class GPURepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create_instance(
        self,
        user_id: UUID,
        provider: GPUProviderName,
        status: GPUInstanceStatus,
        project_id: UUID | None = None,
        gpu_type: str | None = None,
        metadata: dict | None = None,
    ) -> GPUInstance:
        model = GPUInstanceModel(
            provider=provider.value,
            status=status.value,
            user_id=user_id,
            project_id=project_id,
            gpu_type=gpu_type,
            metadata_json=metadata or {},
        )
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return self._to_instance(model)

    async def get_instance(self, instance_id: UUID) -> GPUInstance | None:
        model = await self._session.get(GPUInstanceModel, instance_id)
        return self._to_instance(model) if model else None

    async def list_instances(self, user_id: UUID) -> list[GPUInstance]:
        result = await self._session.execute(
            select(GPUInstanceModel)
            .where(GPUInstanceModel.user_id == user_id)
            .order_by(GPUInstanceModel.created_at.desc())
        )
        return [self._to_instance(model) for model in result.scalars().all()]

    async def update_instance(
        self,
        instance_id: UUID,
        status: GPUInstanceStatus | None = None,
        provider_instance_id: str | None = None,
        endpoint_url: str | None = None,
        metadata: dict | None = None,
        terminated_at: datetime | None = None,
    ) -> GPUInstance:
        model = await self._session.get(GPUInstanceModel, instance_id)
        if model is None:
            raise ValueError("GPU instance not found.")
        if status is not None:
            model.status = status.value
        if provider_instance_id is not None:
            model.provider_instance_id = provider_instance_id
        if endpoint_url is not None:
            model.endpoint_url = endpoint_url
        if metadata is not None:
            model.metadata_json = metadata
        if terminated_at is not None:
            model.terminated_at = terminated_at
        model.updated_at = datetime.now(UTC)
        await self._session.commit()
        await self._session.refresh(model)
        return self._to_instance(model)

    async def add_event(
        self,
        user_id: UUID,
        event_type: GPUEventType,
        message: str,
        gpu_instance_id: UUID | None = None,
        metadata: dict | None = None,
    ) -> GPUEvent:
        model = GPUEventModel(
            gpu_instance_id=gpu_instance_id,
            user_id=user_id,
            event_type=event_type.value,
            message=message,
            metadata_json=metadata or {},
        )
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return self._to_event(model)

    @staticmethod
    def _to_instance(model: GPUInstanceModel) -> GPUInstance:
        return GPUInstance(
            id=model.id,
            provider=GPUProviderName(model.provider),
            provider_instance_id=model.provider_instance_id,
            status=GPUInstanceStatus(model.status),
            user_id=model.user_id,
            project_id=model.project_id,
            gpu_type=model.gpu_type,
            endpoint_url=model.endpoint_url,
            cost_estimate=model.cost_estimate,
            metadata=model.metadata_json or {},
            created_at=model.created_at,
            updated_at=model.updated_at,
            terminated_at=model.terminated_at,
        )

    @staticmethod
    def _to_event(model: GPUEventModel) -> GPUEvent:
        return GPUEvent(
            id=model.id,
            gpu_instance_id=model.gpu_instance_id,
            user_id=model.user_id,
            event_type=GPUEventType(model.event_type),
            message=model.message,
            metadata=model.metadata_json or {},
            created_at=model.created_at,
        )

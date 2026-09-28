from app.domain.gpu import GPUProviderName
from app.infrastructure.gpu.base import GPUProvider
from app.infrastructure.gpu.local_docker_provider import LocalDockerProvider
from app.infrastructure.gpu.runpod_provider import RunPodProvider


def create_gpu_provider(provider_name: GPUProviderName) -> GPUProvider:
    """Return the provider selected by GPU_PROVIDER; the rest of the pipeline is identical."""
    if provider_name == GPUProviderName.RUNPOD:
        return RunPodProvider()
    if provider_name == GPUProviderName.LOCAL:
        return LocalDockerProvider()
    raise ValueError(f"GPU provider '{provider_name}' is not implemented.")

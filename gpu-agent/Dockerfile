# CUDA 12.8 is the minimum toolkit with kernels for Blackwell GPUs (RTX 50xx, B100/B200)
# and still runs on older data-center GPUs such as the A100, so one image serves both.
# Ubuntu 24.04 ships a stable Python 3.12; 22.04's python3.11 is a 3.11.0 release
# candidate on which Triton's compiler segfaults.
FROM nvidia/cuda:12.8.1-runtime-ubuntu24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=10 \
    PIP_RESUME_RETRIES=10 \
    PATH=/opt/venv/bin:$PATH \
    PORT=8001 \
    WORKSPACE_PATH=/workspace \
    LOG_PATH=/workspace/logs \
    CHECKPOINT_PATH=/workspace/checkpoints \
    OUTPUT_PATH=/workspace/outputs \
    TEMP_PATH=/workspace/temp \
    HF_HOME=/opt/hf-cache

# python3-dev and build-essential are needed at runtime: Triton compiles small
# C helpers against the Python headers the first time Unsloth kernels run.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 \
        python3-dev \
        python3-venv \
        build-essential \
        git \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv /opt/venv \
    && pip install --upgrade pip setuptools wheel

WORKDIR /opt/gpu-agent

ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cu128
RUN pip install --index-url ${TORCH_INDEX_URL} torch torchvision \
    && pip freeze | grep -E '^(torch|torchvision)==' > /opt/torch-constraints.txt

COPY requirements.txt requirements-train.txt ./
RUN pip install -c /opt/torch-constraints.txt -r requirements-train.txt -r requirements.txt

# Compiled GPU kernels live next to the model cache so a new container per job
# reuses them instead of recompiling for minutes before the first step.
ENV TRITON_CACHE_DIR=/opt/hf-cache/triton \
    TORCHINDUCTOR_CACHE_DIR=/opt/hf-cache/inductor

COPY app ./app
COPY templates ./templates

# Fixed UID: the workspace and model-cache volumes outlive the image, so the owner must not
# change between base images (Ubuntu 24.04 already uses 1000 for its "ubuntu" user).
RUN useradd --uid 1001 --create-home --shell /bin/bash agent \
    && mkdir -p /workspace/dataset /workspace/configs /workspace/templates /workspace/outputs \
        /workspace/checkpoints /workspace/logs /workspace/artifacts /workspace/cache /workspace/temp \
        /opt/hf-cache \
    && cp -r /opt/gpu-agent/templates/* /workspace/templates/ \
    && chown -R agent:agent /workspace /opt/gpu-agent /opt/hf-cache

USER agent
EXPOSE 8001

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]

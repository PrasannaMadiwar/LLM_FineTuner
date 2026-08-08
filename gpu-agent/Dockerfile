FROM nvidia/cuda:12.1.1-cudnn8-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8001
ENV WORKSPACE_PATH=/workspace
ENV LOG_PATH=/workspace/logs
ENV CHECKPOINT_PATH=/workspace/checkpoints
ENV OUTPUT_PATH=/workspace/outputs
ENV TEMP_PATH=/workspace/temp

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3.11 \
        python3.11-venv \
        python3-pip \
        build-essential \
        git \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/gpu-agent

COPY requirements.txt .
RUN python3.11 -m pip install --no-cache-dir --upgrade pip setuptools wheel \
    && FLASH_ATTENTION_SKIP_CUDA_BUILD=TRUE python3.11 -m pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY templates ./templates

RUN useradd --create-home --shell /bin/bash agent \
    && mkdir -p /workspace/dataset /workspace/configs /workspace/templates /workspace/outputs \
        /workspace/checkpoints /workspace/logs /workspace/artifacts /workspace/cache /workspace/temp \
    && cp -r /opt/gpu-agent/templates/* /workspace/templates/ \
    && chown -R agent:agent /workspace /opt/gpu-agent

USER agent
EXPOSE 8001

CMD ["sh", "-c", "python3.11 -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]

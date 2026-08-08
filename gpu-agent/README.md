# GPU Runtime Agent

FastAPI control agent that runs inside every GPU pod. The platform backend talks to this
agent instead of using SSH for normal operations.

## Responsibilities

- Create and validate `/workspace` runtime directories.
- Accept streaming uploads for datasets, configs, and templates.
- Execute only approved training templates.
- Capture stdout and stderr logs.
- Report health, disk, RAM, VRAM, CUDA, and PyTorch details.
- List and download artifacts.
- Provide compatibility endpoints used by the backend `RunPodProvider`.

## API

- `GET /health`
- `POST /upload?remote_path=dataset/train.jsonl`
- `PUT /files?path=dataset/train.jsonl`
- `GET /files?path=dataset/train.jsonl`
- `POST /train`
- `POST /cancel/{training_id}`
- `GET /status/{training_id}`
- `GET /logs/{training_id}`
- `GET /logs`
- `GET /artifacts/{training_id}`
- `POST /download/{training_id}?path=artifacts/{training_id}/model.txt`
- `POST /commands`
- `POST /cleanup`

## Environment

- `WORKSPACE_PATH`, default `/workspace`
- `DATASET_PATH`, default `/workspace/dataset`
- `CONFIG_PATH`, default `/workspace/configs`
- `TEMPLATE_PATH`, default `/workspace/templates`
- `OUTPUT_PATH`, default `/workspace/outputs`
- `CHECKPOINT_PATH`, default `/workspace/checkpoints`
- `LOG_PATH`, default `/workspace/logs`
- `ARTIFACT_PATH`, default `/workspace/artifacts`
- `CACHE_PATH`, default `/workspace/cache`
- `TEMP_PATH`, default `/workspace/temp`
- `PORT`, default `8001`
- `MAX_UPLOAD_BYTES`, default `10737418240`

## Build

```powershell
docker build -t llm-fine-tuner-gpu-agent:latest gpu-agent
```

The image includes CUDA-compatible PyTorch, Unsloth, Transformers, TRL, PEFT,
Datasets, Accelerate, Flash Attention, FastAPI, and Uvicorn.

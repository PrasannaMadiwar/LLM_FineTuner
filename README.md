# LLM Fine-Tuner

A web workspace for preparing instruction datasets, launching LoRA fine-tuning jobs on a GPU, watching progress, and collecting the trained adapter.

GPU access goes through a pluggable `GPUProvider`. Two providers are implemented:

- **`local`**: runs the GPU runtime agent in Docker on your own NVIDIA GPU (for demos and testing).
- **`runpod`**: runs the same agent on a RunPod pod.

See [docs/DESIGN.md](docs/DESIGN.md) for the provider abstraction, state machines, dataset pipeline, and security boundaries.

## Status

| Area | State |
|---|---|
| Local GPU, end to end | Verified. 4 completed jobs on an RTX 5050 Laptop GPU (8 GB) training `unsloth/Qwen2.5-1.5B-Instruct` for 1 epoch. Built-in demo dataset: 527 examples, 66 steps, 137 s wall clock. `yahma/alpaca-cleaned` capped at 2,000 rows: 250 steps, 345–564 s. The LoRA adapter was retrieved each time. |
| RunPod, end to end | **Not yet verified.** 3 earlier attempts failed at pod creation with HTTP 400 because `gpuTypeIds: ["A100"]` is not a valid RunPod GPU type ID. The payload is fixed and passes RunPod's schema validation, but no pod has been created with it yet. |
| Tests | API: 292 tests, 74% line coverage. GPU agent: 88 tests, 83%. CI runs both ([ci.yml](.github/workflows/ci.yml)). |
| Render deployment | `render.yaml` defines 3 services. The two public hostnames currently return `404` with `x-render-routing: no-server` (not deployed). |

## Architecture

```mermaid
flowchart LR
    B[Browser] --> W[Next.js web<br/>apps/web]
    W -->|JWT| A[FastAPI API<br/>apps/api]
    A --> P[(PostgreSQL)]
    A --> R[(Redis)]
    A -->|enqueue job| R
    R --> K[Celery worker<br/>same codebase as API]
    K --> P
    K --> G{{GPUProvider}}
    G -->|GPU_PROVIDER=local| L[Docker on this machine]
    G -->|GPU_PROVIDER=runpod| RP[RunPod pod]
    L --> AG[GPU runtime agent<br/>gpu-agent/]
    RP --> AG
    K -->|GPU_AGENT_TOKEN<br/>upload, /train, /status, artifacts| AG
    A -->|dataset metadata & rows| HF[Hugging Face / Kaggle / GitHub]
```

The API never trains anything itself. Queuing a job dispatches a Celery task. The worker creates a GPU instance through the provider, uploads the normalized dataset and a config to the agent, starts an approved training template, polls until the run finishes, stores metrics, checkpoints, and artifacts, and terminates the instance.

## Setup (local GPU)

Prerequisites: Docker Desktop with WSL 2 GPU support, an NVIDIA GPU with 8 GB+ VRAM, Node.js 20+, Python 3.12+.

Check that Docker can see the GPU:

```powershell
docker run --rm --gpus all nvidia/cuda:12.8.1-base-ubuntu24.04 nvidia-smi
```

Then:

```powershell
copy .env.example .env
docker build -t llm-finetuner-gpu-agent:local gpu-agent   # large; first build takes a while
docker compose up --build
```

| Service | URL |
|---|---|
| Web app | http://localhost:13000 |
| API | http://localhost:18000 |
| PostgreSQL | localhost:15432 |
| Redis | localhost:16379 |

First run: register an account, open **Fine-Tune**, click **Use built-in demo dataset**, pick **Qwen2.5 1.5B Instruct**, and start the job. The job page shows status, logs, loss, ETA, checkpoints, and artifacts. The first run also downloads the model into the `llm-finetuner-hf-cache` volume.

The image uses CUDA 12.8, which RTX 50-series (Blackwell) GPUs require.

### Using RunPod instead

```env
GPU_PROVIDER=runpod
RUNPOD_API_KEY=...
RUNPOD_TEMPLATE_ID=...      # template whose image runs gpu-agent and exposes RUNPOD_AGENT_PORT
RUNPOD_DEFAULT_GPU=A100    # alias for "NVIDIA A100 80GB PCIe", "NVIDIA A100-SXM4-80GB"; full gpuTypeIds also work
RUNPOD_AGENT_PORT=8001
RUNPOD_CLOUD_TYPE=SECURE    # Secure Cloud always gives the pod a public HTTP proxy
GPU_AGENT_TOKEN=...         # same value on the API and the worker; injected into each pod
```

The pod image must be built from the current `gpu-agent/Dockerfile` (CUDA 12.8, Ubuntu 24.04). The agent is reached through `https://<pod-id>-8001.proxy.runpod.net`.

RunPod pods are billable. Set spending limits before queueing jobs.

### Key environment variables

| Variable | Purpose |
|---|---|
| `GPU_PROVIDER` | `local` or `runpod` |
| `JWT_SECRET_KEY` | Signs user tokens. Must be at least 32 bytes. Replace the example value anywhere shared. |
| `GPU_AGENT_TOKEN` | Bearer token between the worker and the agent. Required: the agent refuses to start without it, and the RunPod provider refuses to rent a pod without it. |
| `DATASET_MAX_ROWS` | Caps rows per normalized dataset (2000 in `.env.example`) |
| `LOG_LEVEL` | API and worker log level (default `INFO`) |

## Sample request and response

Log in, then create a job for a dataset you have already normalized:

```http
POST /api/v1/auth/login
Content-Type: application/x-www-form-urlencoded

username=you@example.com&password=your-password
```

```json
{ "access_token": "eyJhbGciOiJIUzI1NiIs...", "token_type": "bearer" }
```

```http
POST /api/v1/training/jobs
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
Content-Type: application/json

{
  "config": {
    "model_key": "qwen2.5-1.5b",
    "dataset_id": "builtin/edi-demo",
    "normalized_dataset_path": "/app/storage/datasets/<user-id>/default/demo/builtin_edi-demo/train.jsonl",
    "epochs": 1
  }
}
```

`201 Created`:

```json
{
  "job": {
    "id": "982d27d2-163f-4253-bc67-958fca02f1ce",
    "user_id": "e990f204-0bb3-4d58-b49c-51d9e085eb2a",
    "project_id": null,
    "status": "created",
    "model_key": "qwen2.5-1.5b",
    "model_id": "unsloth/Qwen2.5-1.5B-Instruct",
    "template_name": "qwen",
    "training_config": {
      "model_key": "qwen2.5-1.5b",
      "dataset_id": "builtin/edi-demo",
      "normalized_dataset_path": "/app/storage/datasets/<user-id>/default/demo/builtin_edi-demo/train.jsonl",
      "output_dir": null,
      "epochs": 1,
      "learning_rate": 0.0002,
      "batch_size": 2,
      "gradient_accumulation_steps": 4,
      "lora_rank": 16,
      "lora_alpha": null,
      "max_sequence_length": 2048,
      "load_in_4bit": true,
      "extra": {}
    },
    "dataset_id": "builtin/edi-demo",
    "normalized_dataset_path": "/app/storage/datasets/<user-id>/default/demo/builtin_edi-demo/train.jsonl",
    "gpu_instance_id": null,
    "error_message": null,
    "created_at": "2026-10-17T20:19:03.780308Z",
    "updated_at": "2026-10-17T20:19:03.780308Z",
    "queued_at": null,
    "started_at": null,
    "completed_at": null
  }
}
```

Then `POST /api/v1/training/jobs/{id}/queue` to start training, and poll `GET /api/v1/training/jobs/{id}`. Without a valid token, every job route returns `401`. A job owned by someone else returns `403` (or `404` for metrics, checkpoints, and artifacts).

## API surface

**Backend** (`/api/v1`, 36 routes, plus an unauthenticated `GET /health` at the root):

| Area | Routes |
|---|---|
| Health | `GET /health`, `GET /ready` (database and Redis) |
| Auth | `POST /auth/register`, `POST /auth/login`, `GET /auth/me` |
| Datasets | `GET /datasets/search`, `GET /datasets/info/{id}`, `GET /datasets/preview/{id}`, `POST /datasets/analyze`, `POST /datasets/normalize` |
| Projects | `POST /projects`, `GET /projects`, `GET/PATCH/DELETE /projects/{id}` |
| GPU | `POST /gpu/create`, `GET /gpu`, `GET /gpu/{id}`, `POST /gpu/{id}/terminate`, `POST /gpu/{id}/execute`, `POST /gpu/{id}/upload`, `GET /gpu/{id}/logs`, `GET /gpu/{id}/health` |
| Training | `GET /training/models`, `GET /training/templates`, `POST /training/jobs`, `GET /training/jobs`, `GET /training/jobs/{id}`, `POST /training/jobs/{id}/queue`, `POST /training/jobs/{id}/cancel`, `POST /training/jobs/{id}/resume`, `GET /training/jobs/{id}/events`, `GET /training/jobs/{id}/metrics`, `GET /training/jobs/{id}/checkpoints/latest`, `GET /training/jobs/{id}/artifacts`, `GET /training/jobs/{id}/artifacts/{artifact_id}` |

**GPU runtime agent** (13 endpoints, all require `GPU_AGENT_TOKEN`): `GET /health`, `POST /upload`, `PUT /files`, `GET /files`, `POST /train`, `GET /status/{id}`, `POST /cancel/{id}`, `GET /logs/{id}`, `GET /logs`, `GET /artifacts/{id}`, `POST /download/{id}`, `POST /commands`, `POST /cleanup`.

## Logging

The API and worker write one JSON object per line to stdout. Every line has `timestamp`, `level`, `logger`, `message`, and `job_id`. `job_id` is filled for requests under `/training/jobs/{id}`, for everything the worker does while running a job, and for every job state transition. Otherwise it is `null`.

```json
{"timestamp": "2026-10-17T20:15:34.383290+00:00", "level": "INFO", "logger": "uvicorn.access", "message": "127.0.0.1:64934 - \"GET /api/v1/training/jobs/0b7c3b9e-1111-4222-8333-944455556666 HTTP/1.1\" 401", "job_id": "0b7c3b9e-1111-4222-8333-944455556666"}
```

## Tests

```powershell
cd apps/api;   python -m pip install -e ".[dev]"; python -m pytest --cov=app
cd gpu-agent;  python -m pip install -r requirements.txt httpx pytest pytest-cov; python -m pytest --cov=app
```

No GPU is needed. GPU lifecycle tests use a fake `GPUProvider`, and agent templates run in dry-run mode.

## Troubleshooting

| Symptom | Check |
|---|---|
| Web app doesn't load | Use http://localhost:13000 with Compose. Run `docker compose logs web --tail 100`. |
| `/api/v1/ready` reports `unavailable` | Inside Compose, use the hosts `postgres` and `redis`, not `localhost`. |
| GPU agent image not found | `docker build -t llm-finetuner-gpu-agent:local gpu-agent` |
| Docker can't attach the GPU | Update the NVIDIA driver, enable the WSL 2 backend, restart Docker Desktop. Use a CUDA 12.8 image on RTX 50-series GPUs. |
| "Local GPU already in use" | Only one local agent runs at a time: `docker ps --filter "label=llm-finetuner.managed=true"`, then `docker rm -f <id>`. |
| RunPod create fails | `docker compose logs worker --tail 200`. Check the API key, template ID, GPU availability in your region, the exposed agent port, and quota or billing. |

## Deployment

`render.yaml` and [RENDER_DEPLOY.md](RENDER_DEPLOY.md) describe a three-service Render deployment (API, web, Celery worker). Never use the `local` provider on a public host: it mounts the Docker socket, which gives control of the host.

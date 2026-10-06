# LLM Fine-Tuner

A browser-based fine-tuning workspace for preparing instruction datasets, launching LoRA training jobs, watching live progress, and collecting adapter artifacts.

The project can be run with two GPU options:

- **Remote GPU provider:** the main production path. RunPod is implemented today, and the provider interface is designed so other GPU providers can be added later.
- **Local GPU testing provider:** runs the same GPU agent on your own NVIDIA laptop or desktop GPU through Docker. This was added for MVP testing and demos, and is suitable for an RTX 5060 8 GB class machine.

## What You Get

- Next.js web app for dataset selection, normalization, job creation, logs, metrics, checkpoints, and artifacts.
- FastAPI backend with authentication, dataset services, GPU orchestration, and training job APIs.
- Celery worker for asynchronous training.
- Local PostgreSQL and Redis through Docker Compose.
- GPU Runtime Agent container that performs the actual training work.
- Provider switch using `GPU_PROVIDER`. Use `runpod` for the remote provider or `local` for laptop/desktop GPU testing.

## Architecture

```text
Browser
  -> Next.js web app
  -> FastAPI API
    -> PostgreSQL
    -> Redis / Celery broker
    -> Celery worker
      -> GPU provider
        -> remote GPU provider, or
        -> local Docker GPU agent for testing
```

The backend talks to a provider-agnostic `GPUProvider` interface. The training pipeline is the same whether the GPU agent is running on a remote provider or locally for testing.

## Prerequisites

Install these before starting:

- Git
- Docker Desktop
- Node.js 20+
- Python 3.12+
- NVIDIA driver
- NVIDIA GPU with 8 GB+ VRAM for local training
- Docker Desktop WSL 2 backend with GPU support enabled

Check Docker GPU access:

```powershell
docker run --rm --gpus all nvidia/cuda:12.8.1-base-ubuntu24.04 nvidia-smi
```

If this does not show your GPU, fix Docker/NVIDIA GPU support before running training jobs.

## Quick Start: Local GPU Testing MVP

From the project root:

```powershell
git clone <repo-url>
cd LLM_FineTuner
copy .env.example .env
```

Build the GPU agent image. This is large and can take time on the first run.

```powershell
docker build -t llm-finetuner-gpu-agent:local gpu-agent
```

Start the full app:

```powershell
docker compose up --build
```

Open:

```text
http://localhost:13000
```

The API is available at:

```text
http://localhost:18000
```

Docker Compose also starts:

- PostgreSQL at `localhost:15432`
- Redis at `localhost:16379`
- API container
- Celery worker
- Web container

## First Training Run

1. Open `http://localhost:13000`.
2. Register a local account.
3. Go to **Fine-Tune**.
4. Click **Use built-in demo dataset** for the fastest offline test.
5. Select **Qwen2.5 1.5B Instruct** for an 8 GB GPU.
6. Start the job.
7. Watch the job page for status, logs, loss, ETA, checkpoints, and artifacts.

The built-in demo dataset goes through the same normalize, validate, train, checkpoint, and artifact flow as remote datasets. In Docker Compose, `DATASET_MAX_ROWS=2000` keeps MVP runs short.

On an RTX 50-series laptop GPU with 8 GB VRAM, expect the first run to take longer because the model is downloaded and cached. Later runs reuse the Docker volume cache.

## Environment Configuration

Copy `.env.example` to `.env` and edit only what you need.

Important local defaults:

```env
GPU_PROVIDER=local
LOCAL_GPU_IMAGE=llm-finetuner-gpu-agent:local
DATASET_MAX_ROWS=2000
LOCAL_DATABASE_URL=postgresql+asyncpg://llm_finetuner:llm_finetuner_password@postgres:5432/llm_finetuner
LOCAL_REDIS_URL=redis://redis:6379/0
NEXT_PUBLIC_API_BASE_URL=http://localhost:18000/api/v1
```

Important security values:

```env
JWT_SECRET_KEY=change-me-in-production-use-at-least-32-bytes
GPU_AGENT_TOKEN=change-me-runtime-agent-token
```

For local-only testing, the example values are acceptable. For any shared or public deployment, replace them.

## GPU Provider Options

The application is built around a provider abstraction:

- `GPU_PROVIDER=runpod` uses the remote GPU provider path. This is the main intended path for production and shared deployments.
- `GPU_PROVIDER=local` uses this machine's NVIDIA GPU through Docker. This is for testing, demos, and MVP validation before spending money on remote GPUs.

Other remote GPU providers can be added by implementing the same `GPUProvider` interface used by RunPod and the local Docker provider.

## Local GPU Testing Provider

The local testing provider starts the GPU Runtime Agent as a Docker container on your machine. It uses the Docker Engine socket mounted into the API and worker containers.

This is intentional for local MVP testing, but it is powerful access. Do not mount the Docker socket on a publicly reachable server.

Local provider behavior:

- One GPU agent container is allowed at a time.
- Training uses Docker GPU access with `--gpus all` equivalent settings.
- Workspace artifacts are stored in the `llm-finetuner-gpu-workspace` Docker volume.
- Hugging Face/model cache is stored in the `llm-finetuner-hf-cache` Docker volume.
- The GPU agent joins the fixed Docker network `llm-finetuner-net`.

Useful local commands:

```powershell
docker compose ps
docker compose logs api --tail 100
docker compose logs worker --tail 100
docker compose logs web --tail 100
```

Stop the stack:

```powershell
docker compose down
```

Stop and remove local DB/cache volumes:

```powershell
docker compose down -v
```

## Remote GPU Provider: RunPod

RunPod is the currently implemented remote provider. To use RunPod instead of the local testing GPU:

```env
GPU_PROVIDER=runpod
RUNPOD_API_KEY=your-runpod-api-key
RUNPOD_TEMPLATE_ID=your-runpod-template-id
RUNPOD_DEFAULT_GPU=A100
RUNPOD_AGENT_PORT=8001
```

Your RunPod template/image must run the GPU Runtime Agent and expose the agent port. The backend expects the agent endpoints such as `/health`, `/files`, `/train`, `/status/{training_id}`, `/cancel/{training_id}`, `/logs`, and `/artifacts/{training_id}`.

Build the agent image for publishing or template use:

```powershell
docker build -t llm-finetuner-gpu-agent:latest gpu-agent
```

RunPod jobs may create billable GPU pods. Confirm your RunPod account, template, GPU type, and spending limits before queueing jobs.

## Development Without Docker

Use this mode when you want to work on the API or web app directly on your machine.

Install dependencies:

```powershell
npm install
python -m venv apps/api/.venv
apps/api/.venv/Scripts/python -m pip install -e apps/api[dev]
```

Run the API:

```powershell
apps/api/.venv/Scripts/python -m uvicorn app.main:app --app-dir apps/api --reload --host 0.0.0.0 --port 18000
```

Run the web app:

```powershell
npm run dev:web
```

For direct local development, point `DATABASE_URL` and `REDIS_URL` at services you can reach from your host. The Docker Compose setup is simpler for most users because it provides PostgreSQL and Redis automatically.

## Health Checks

API health:

```powershell
Invoke-RestMethod http://localhost:18000/api/v1/health
```

Database and Redis readiness:

```powershell
Invoke-RestMethod http://localhost:18000/api/v1/ready
```

Expected readiness result:

```text
database redis
-------- -----
ok       ok
```

## Verification

Backend tests:

```powershell
$env:PYTHONPATH='apps/api'
apps/api/.venv/Scripts/python -m pytest apps/api/tests -q
```

GPU agent tests:

```powershell
$env:PYTHONPATH='gpu-agent'
apps/api/.venv/Scripts/python -m pytest gpu-agent/tests -q
```

Frontend build:

```powershell
npm run build
```

## Main API Areas

Authentication:

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`

Datasets:

- `GET /api/v1/datasets/search?query=...`
- `GET /api/v1/datasets/info/{dataset_id}`
- `GET /api/v1/datasets/preview/{dataset_id}`
- `POST /api/v1/datasets/analyze`
- `POST /api/v1/datasets/normalize`

Training:

- `GET /api/v1/training/models`
- `POST /api/v1/training/jobs`
- `POST /api/v1/training/jobs/{job_id}/queue`
- `POST /api/v1/training/jobs/{job_id}/cancel`
- `GET /api/v1/training/jobs/{job_id}`
- `GET /api/v1/training/jobs/{job_id}/events`
- `GET /api/v1/training/jobs/{job_id}/metrics`
- `GET /api/v1/training/jobs/{job_id}/checkpoints/latest`
- `GET /api/v1/training/jobs/{job_id}/artifacts`

GPU:

- `POST /api/v1/gpu/create`
- `POST /api/v1/gpu/{id}/terminate`
- `GET /api/v1/gpu/{id}`
- `GET /api/v1/gpu`
- `GET /api/v1/gpu/{id}/health`
- `GET /api/v1/gpu/{id}/logs`

## GPU Runtime Agent

The GPU Runtime Agent lives in `gpu-agent/`. It runs inside local GPU containers or RunPod pods and exposes the control API used by the backend.

Important endpoints:

- `GET /health`
- `PUT /files`
- `GET /files`
- `POST /train`
- `POST /cancel/{training_id}`
- `GET /status/{training_id}`
- `GET /logs/{training_id}`
- `GET /logs`
- `GET /artifacts/{training_id}`
- `POST /cleanup`

The Docker image uses CUDA 12.8, which is required for RTX 50-series Blackwell GPUs. Older CUDA 12.1 images can fail on RTX 50-series cards with kernel compatibility errors.

## Troubleshooting

### Web app does not load

Check the containers:

```powershell
docker compose ps
docker compose logs web --tail 100
```

Open `http://localhost:13000`, not `http://localhost:3000`, when using Docker Compose.

### API readiness fails

Check API, PostgreSQL, and Redis:

```powershell
docker compose ps
docker compose logs api --tail 100
Invoke-RestMethod http://localhost:18000/api/v1/ready
```

If you changed database settings, make sure Docker containers use the internal host names `postgres` and `redis`, not `localhost`.

### GPU agent image was not found

Build it:

```powershell
docker build -t llm-finetuner-gpu-agent:local gpu-agent
```

Then restart:

```powershell
docker compose up --build
```

### Docker cannot attach the NVIDIA GPU

Run:

```powershell
docker run --rm --gpus all nvidia/cuda:12.8.1-base-ubuntu24.04 nvidia-smi
```

If that fails:

- Update the NVIDIA driver.
- Enable Docker Desktop WSL 2 backend.
- Restart Docker Desktop.
- Make sure you are using a CUDA 12.8 compatible image for RTX 50-series GPUs.

### Local GPU is already in use

The local provider allows one GPU agent container at a time. Check for existing containers:

```powershell
docker ps --filter "label=llm-finetuner.managed=true"
```

Remove a stuck local agent:

```powershell
docker rm -f <container-name-or-id>
```

### First run is slow

The first training job downloads model weights and builds caches. This can take several minutes. Later jobs reuse the Hugging Face cache volume.

### RunPod create job fails

Check worker logs:

```powershell
docker compose logs worker --tail 200
```

Common causes:

- Invalid `RUNPOD_API_KEY`
- Invalid `RUNPOD_TEMPLATE_ID`
- GPU type unavailable in your RunPod account or region
- Template does not expose the GPU Runtime Agent port
- RunPod account quota or billing issue

## Deployment

Render deployment configuration is included in `render.yaml`.

See [RENDER_DEPLOY.md](RENDER_DEPLOY.md) for production environment variables, Render Blueprint steps, worker requirements, and storage limitations.

For production, do not use the local Docker socket provider. Use a remote GPU provider such as RunPod and managed PostgreSQL/Redis services.

## Notes

- Local GPU mode is intended for MVP development and demos.
- The built-in model for 8 GB GPUs is `Qwen2.5 1.5B Instruct`.
- Larger models such as 7B/8B/9B generally require a larger cloud GPU.
- Training jobs are asynchronous and require the Celery worker to be running.
- Cancelled jobs are recorded in the database and the worker attempts to stop the runtime agent cleanly.

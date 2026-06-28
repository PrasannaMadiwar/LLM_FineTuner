# LLM Fine-Tuner

Commercial SaaS foundation for browser-based fine-tuning workflows.

## Phase 1 Scope

- Next.js frontend shell with TypeScript and TailwindCSS.
- FastAPI backend with configuration management, dependency injection, JWT authentication, PostgreSQL, and Redis providers.
- Docker Compose for local PostgreSQL, Redis, API, and web services.
- No training, GPU orchestration, Celery workers, inference, or artifact pipelines are implemented in this phase.

## Phase 2 Scope: Dataset Intelligence

The backend includes a Dataset Intelligence slice for instruction-tuning dataset discovery,
metadata extraction, semantic mapping, validation, and normalization.

```text
FastAPI routes
  -> DatasetService
    -> Dataset providers: Hugging Face implemented, Kaggle/GitHub adapter contracts prepared
    -> SemanticMappingService -> JSON-only LLM mapping client
    -> DatasetValidationService
    -> DatasetConverterService
    -> DatasetRepository -> PostgreSQL caches/history
```

### Implemented Features

- Dataset search through Hugging Face Hub.
- Provider contracts for Kaggle and GitHub dataset sources.
- Metadata extraction without downloading full datasets.
- First-row dataset previews for sample inspection.
- JSON-only semantic mapping through the OpenAI API.
- Mapping cache stored in PostgreSQL.
- Dataset metadata cache stored in PostgreSQL.
- Normalization history stored in PostgreSQL.
- One generic converter to OpenAI `messages` format.
- Validation reports for empty values, missing prompts, missing assistant responses, duplicate rows, long samples, invalid UTF-8, and unsupported schemas.

### Dataset API

Available routes:

- `GET /api/v1/datasets/search?query=...`
- `GET /api/v1/datasets/info/{dataset_id}`
- `GET /api/v1/datasets/preview/{dataset_id}`
- `POST /api/v1/datasets/analyze`
- `POST /api/v1/datasets/normalize`

Example semantic mapping:

```json
{
  "user": ["instruction", "input"],
  "assistant": "output",
  "system": null,
  "context": []
}
```

Normalized output format:

```json
{
  "messages": [
    {
      "role": "user",
      "content": "..."
    },
    {
      "role": "assistant",
      "content": "..."
    }
  ]
}
```

The Hugging Face provider reads metadata and first rows only. It does not download entire
datasets. Semantic mapping calls OpenAI through the provider-agnostic `LLMProvider`
interface and validates that the response is JSON matching the allowed mapping schema.

### Dataset Tables

Alembic migration `20260628_0002_create_dataset_intelligence_tables.py` creates:

- `dataset_metadata_cache`
- `dataset_mappings`
- `dataset_normalization_history`

## Configuration

Core environment variables:

- `DATABASE_URL`
- `REDIS_URL`
- `JWT_SECRET_KEY`
- `API_CORS_ORIGINS`
- `NEXT_PUBLIC_API_BASE_URL`
- `LLM_SEMANTIC_MAPPING_URL` optional OpenAI-compatible base URL override for semantic mapping
- `LLM_SEMANTIC_MAPPING_API_KEY` optional API key override for semantic mapping
- `OPENAI_API_KEY`
- `OPENAI_MODEL` with default `gpt-4.1`
- `GPU_PROVIDER` currently `runpod`
- `RUNPOD_API_KEY`
- `RUNPOD_TEMPLATE_ID`
- `RUNPOD_DEFAULT_GPU` with default `A100`
- `RUNPOD_VOLUME_SIZE` with default `100`
- `RUNPOD_CONTAINER_DISK` with default `50`
- `RUNPOD_REGION`
- `RUNPOD_AGENT_PORT` with default `8001`
- `GPU_CREATE_TIMEOUT_SECONDS` with default `900`
- `GPU_OPERATION_MAX_RETRIES` with default `3`

## Phase 3 Scope: GPU Orchestration

The backend includes a provider-agnostic GPU orchestration layer for lifecycle management.
It does not implement Unsloth training, inference serving, or workload-specific training logic.

```text
FastAPI routes
  -> GPUService
    -> GPURepository -> PostgreSQL lifecycle/events
    -> GPUProvider interface
      -> RunPodProvider
```

### GPU API

Available routes:

- `POST /api/v1/gpu/create`
- `POST /api/v1/gpu/{id}/terminate`
- `GET /api/v1/gpu/{id}`
- `GET /api/v1/gpu`
- `POST /api/v1/gpu/{id}/execute`
- `POST /api/v1/gpu/{id}/upload`
- `GET /api/v1/gpu/{id}/logs`
- `GET /api/v1/gpu/{id}/health`

All GPU routes require JWT authentication. Users can only access their own GPU instances.

The service exposes generic statuses:

- `pending`
- `starting`
- `running`
- `stopping`
- `stopped`
- `failed`
- `unavailable`

RunPod is the first provider implementation. Business logic depends only on the
`GPUProvider` interface, so AWS, Vast.ai, Lambda Labs, and Google Cloud can be added by
implementing the same interface.

Remote upload, command execution, health checks, downloads, and log streaming are routed
through a generic control-agent HTTP contract exposed by the GPU pod image. This phase adds
the orchestration surface only; it does not add a training container or training script.

### GPU Tables

Alembic migration `20260628_0003_create_gpu_orchestration_tables.py` creates:

- `gpu_instances`
- `training_sessions`
- `gpu_events`

## Local Development

Copy `.env.example` to `.env`, then install dependencies:

```powershell
npm install
python -m venv apps/api/.venv
apps/api/.venv/Scripts/python -m pip install -e apps/api[dev]
```

Run locally:

```powershell
npm run dev:web
apps/api/.venv/Scripts/python -m uvicorn app.main:app --app-dir apps/api --reload
```

Or run the infrastructure with Docker:

```powershell
docker compose up --build
```

API docs are available at `http://localhost:8000/docs`.

## Verification

Backend:

```powershell
apps/api/.venv/Scripts/python -m pytest -q
apps/api/.venv/Scripts/python -m ruff check . --no-cache
apps/api/.venv/Scripts/python -m alembic upgrade head --sql
```

Frontend:

```powershell
npm run build
npm run lint -w apps/web
npm audit --omit=dev
```

Docker:

```powershell
docker compose up -d --no-build
```

The running Compose stack has been verified with PostgreSQL, Redis, API, and web services healthy.
The Dataset Intelligence migration was applied successfully to the running PostgreSQL container.

## Current Non-Goals

- No Unsloth integration.
- No training jobs.
- No inference serving.
- No Celery workers.

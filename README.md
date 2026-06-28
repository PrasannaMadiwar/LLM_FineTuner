# LLM Fine-Tuner

Commercial SaaS foundation for browser-based fine-tuning workflows.

## Phase 1 Scope

- Next.js frontend shell with TypeScript and TailwindCSS.
- FastAPI backend with configuration management, dependency injection, JWT authentication, PostgreSQL, and Redis providers.
- Docker Compose for local PostgreSQL, Redis, API, and web services.
- No training, GPU orchestration, Celery workers, inference, or artifact pipelines are implemented in this phase.

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

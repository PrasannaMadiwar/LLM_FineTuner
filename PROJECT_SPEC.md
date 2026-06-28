# MASTER PROMPT FOR GPT CODEX

You are my Lead Staff Software Engineer, AI Infrastructure Architect, and Technical Lead.

We are building a commercial SaaS platform called **LLM Fine-Tuner**.

The goal is to let users fine-tune open-source LLMs entirely through a web interface without writing code.

This project must be production-quality, scalable, modular, and maintainable.

Never generate quick prototypes.

Never generate duplicate code.

Never violate clean architecture.

Never put business logic inside API routes.

Always separate responsibilities into services.

Whenever implementing a feature:

1. First explain the architecture.
2. List every file you will create or modify.
3. Implement only that feature.
4. Keep the project compiling at every step.
5. Add unit tests.
6. Update API documentation.
7. Update database migrations if required.

Never modify unrelated files.

---

# Product Overview

The platform should support:

* User authentication
* Projects
* Model selection
* Dataset discovery
* Dataset preprocessing
* Automatic semantic mapping
* Dataset normalization
* GPU orchestration
* LLM fine-tuning
* Live training monitoring
* Checkpoint recovery
* Model evaluation
* Chat inference
* Hugging Face publishing
* Artifact downloads

---

# Technology Stack

Frontend

* Next.js
* React
* TypeScript
* TailwindCSS
* Shadcn UI

Backend

* FastAPI
* Python 3.12

Database

* PostgreSQL

Cache

* Redis

Queue

* Celery

Storage

* S3 compatible storage

Containerization

* Docker

Training

* Unsloth
* Transformers
* TRL
* PEFT
* Accelerate

Inference

* vLLM

GPU Providers

Provider interface only.

First implementation:

RunPod.

Future support:

AWS

Lambda Labs

Vast.ai

Google Cloud

No business logic should depend directly on RunPod.

---

# Architecture

Frontend

↓

FastAPI

↓

Application Services

↓

Domain Services

↓

Infrastructure Services

↓

GPU Provider

Use dependency injection.

Follow SOLID principles.

---

# Required Services

Authentication Service

Project Service

Dataset Service

Dataset Cache Service

Semantic Mapping Service

Dataset Converter Service

Dataset Validation Service

Cost Estimator Service

GPU Service

Training Service

Artifact Service

Inference Service

Notification Service

Billing Service

Logging Service

Analytics Service

Every service must be independent.

---

# AI Responsibilities

AI should only perform reasoning tasks.

Examples:

Dataset understanding

Semantic mapping

Hyperparameter suggestions

Error explanations

Training summaries

AI should NEVER:

Write backend code

Generate SQL

Execute shell commands

Control infrastructure directly

Infrastructure must be deterministic.

---

# Dataset Pipeline

1.

Search datasets.

Sources

* Hugging Face
* Kaggle
* GitHub
* User upload

2.

Download metadata only.

3.

Read

* README
* Features
* Column names
* First 10 rows

4.

Check mapping cache.

5.

If cache exists

Use cached mapping.

6.

Else

Ask LLM:

Return ONLY JSON.

Example

{
"user":["instruction","input"],
"assistant":"output",
"system":null,
"context":[]
}

7.

Store mapping.

8.

Generic converter.

Convert every dataset into OpenAI messages format.

9.

Validation.

10.

Save normalized dataset.

GPU must NOT be launched before preprocessing finishes.

---

# Training Pipeline

User chooses model.

Examples

Llama

Qwen

Gemma

Mistral

DeepSeek

Load corresponding Unsloth template.

Never execute notebooks.

Convert notebooks into reusable Python templates.

Replace only configuration values.

Dataset path

Learning rate

Epochs

Batch size

Output directory

LoRA rank

Run train.py.

---

# GPU Workflow

Before GPU launch

Estimate

Training time

Estimated cost

Recommended GPU

VRAM

Token count

Require user confirmation.

Create GPU.

Upload

Dataset

Configuration

Training starts.

Stream logs.

Checkpoint every epoch.

Store artifacts.

Terminate GPU automatically.

---

# Inference

Deploy model separately.

Never reuse training GPU.

Use vLLM.

Allow

Chat

Streaming

Temperature

Top-P

System prompts

History

---

# Artifact Storage

Store

Model

Tokenizer

Logs

Metrics

TensorBoard

Loss curves

Accuracy

LoRA

Merged model

GGUF

Allow download.

Allow Hugging Face upload.

---

# Queue

Training jobs must run inside Celery workers.

FastAPI should never wait for training.

Training must be asynchronous.

---

# Security

JWT authentication.

Role-based permissions.

Signed URLs.

Secrets stored in environment variables.

No arbitrary Python execution.

Validate uploaded datasets.

---

# Logging

Every operation must be logged.

Training

GPU creation

Downloads

Uploads

Inference

Errors

Queue events

---

# Development Rules

Never implement multiple large features at once.

Always build feature by feature.

After every completed feature:

* ensure tests pass
* ensure Docker still works
* ensure API documentation is updated
* ensure typing is correct

Commit-ready code only.

If any requirement is ambiguous, ask before implementing.

Treat this repository as production software.

# Enterprise Agentic RAG (Production, Scalable Pipeline)

A production-grade, enterprise-level RAG system built with **LangGraph**, **Portkey LLM Gateway**, **OpenAI**, and **Jina AI Embeddings/Reranker**. The system distinguishes between technical "True Data" and random "Noisy Data" using semantic re-ranking, history-aware planning, and NeMo Guardrails for input/output safety.

It ships with everything needed to run it for real: a hardened container image, a `docker compose` stack for local validation, GitHub Actions CI/CD, and a full **AWS ECS Fargate** deployment behind an Application Load Balancer with auto-scaling, Secrets Manager, and CloudWatch.

| | |
|---|---|
| **Runtime** | AWS ECS Fargate (`rag-api` + `rag-ui`), ALB ingress, private subnets + NAT |
| **State** | Qdrant Cloud (vectors) · Neon Postgres (LangGraph checkpoints) · Upstash Redis (rate limits) |
| **Pipeline** | GitHub Actions → Amazon ECR → ECS rolling deploy |
| **Observability** | CloudWatch Logs/Metrics · Prometheus `/metrics` · Logfire · LangSmith |

---

## Key Features

- **Agentic Intelligence**: LangGraph for cyclic reasoning, multi-step planning, and conversation memory.
- **Guardrails**: NeMo Guardrails gate blocks off-topic, jailbreak, and injection inputs before any retrieval.
- **LLM Gateway**: Portkey routes all LLM calls with automatic fallback between OpenAI and Anthropic via your configured Portkey virtual providers.
- **Enterprise Search**: Qdrant Cloud for high-performance vector search + Jina AI Reranker API for semantic reranking.
- **Jina AI Embeddings**: `jina-embeddings-v3` (1024-dim) via Jina API, with local `mxbai-embed-large-v1` fallback.
- **Local Document Parsing**: PDF, HTML, TXT, DOCX, PPTX parsed entirely on-device — no external OCR service.
- **Observability**: Full trace nesting with **Pydantic Logfire** and **LangSmith** across every agent node.
- **Metrics**: Prometheus `/metrics` endpoint with custom RAG and guardrails counters.
- **Synchronous `/query`**: The LangGraph pipeline runs directly inside the `/query` endpoint and returns the final answer.
- **API Key & Rate Limiting**: Optional bearer-token auth and Redis-backed (or in-memory) rate limiting.
- **Evaluation Suite**: RAGAS-powered eval pipeline (6 metrics) with a dedicated Streamlit demo app and a headless `evals/run_evals.py` script.
- **Production Deployment**: Single hardened image, non-root container, ECS Fargate services, target-tracking auto-scaling, and a one-command teardown script.

---

## Agent Intelligence Flow

```mermaid
graph TD
    User((User)) --> UI[Streamlit UI]
    UI --> API[FastAPI /query]
    API --> Guard{NeMo Guardrails}
    Guard -->|Blocked| UI
    Guard -->|Pass| Planner{Planner Node}
    Planner -->|Conversational| Responder[Responder Node]
    Planner -->|Technical| Retriever[Retriever Node]
    Retriever --> Reranker[Jina AI Reranker API]
    Reranker --> Responder
    Responder --> UI
    Responder -.-> Memory[(LangGraph Checkpointer — Neon)]
```

---

## Deployment Architecture

```mermaid
graph TD
    Client((Internet)) --> ALB[Application Load Balancer<br/>public subnets]

    subgraph VPC["AWS VPC — 2 Availability Zones"]
        subgraph Public["Public subnets"]
            ALB
            NAT[NAT Gateway]
        end
        subgraph Private["Private subnets"]
            API[ECS Fargate — rag-api<br/>uvicorn :8080<br/>1 vCPU / 2 GB · min 2 / max 10]
            UIS[ECS Fargate — rag-ui<br/>streamlit :8501<br/>0.5 vCPU / 1 GB · min 1 / max 4]
        end
    end

    ALB -->|/ , /query, /health| API
    ALB -->|/ui*| UIS
    UIS --> API
    API --> NAT
    NAT --> Qdrant[(Qdrant Cloud<br/>vectors)]
    NAT --> Neon[(Neon Postgres<br/>checkpoints)]
    NAT --> Redis[(Upstash Redis<br/>rate limits)]
    NAT --> LLM[Portkey Gateway<br/>OpenAI + Anthropic fallback]
    NAT --> Jina[Jina AI<br/>embeddings + reranker]

    API -. secrets .-> SM[AWS Secrets Manager]
    API -. logs .-> CW[CloudWatch Logs<br/>/ecs/rag-api · /ecs/rag-ui]
```

All stateful components live **outside** Fargate, so every ECS task is stateless and horizontally scalable. Both services run the **same image** from ECR — only the container command differs.

---

## Project Structure

```text
├── app/
│   ├── agents/
│   │   └── nodes/       # Planner, Retriever, Responder LangGraph nodes
│   ├── gateway/         # Portkey LLM gateway — primary + Anthropic fallback routing
│   ├── guardrails/      # NeMo Guardrails input/output filtering
│   ├── ingestion/
│   │   ├── chunking/    # Paragraph-based text splitter (1500 char max)
│   │   └── loaders/     # Local parsers — PDF (pypdf), HTML, TXT, DOCX, PPTX
│   ├── services/
│   │   ├── health/      # connection_checker — validates every external dependency
│   │   └── retrieval/   # Jina AI embeddings + Qdrant search + Jina AI reranking
│   ├── config.py        # Centralized environment variable management
│   ├── health.py        # /health and /ready routes
│   └── main.py          # FastAPI entrypoint — guardrails gate + /query endpoint
├── evals/               # RAGAS evaluation suite + Streamlit 3-tab demo
├── ui/                  # Streamlit chat interface with reasoning step transparency
├── tests/               # pytest unit tests (run in CI)
├── .aws/
│   └── task-definitions/  # ECS Fargate task definitions (rag-api.json, rag-ui.json)
├── .github/workflows/
│   ├── ci.yml           # Lint (ruff) + unit tests (pytest)
│   └── cd.yml           # Build → ECR push → ECS deploy
├── scripts/             # AWS provisioning, secrets, teardown, and load-test helpers
├── processed_data/      # Auto-generated — parsed & chunked JSON output per document
├── DATA/                # Sample datasets (True vs Noisy documentation)
├── Dockerfile           # Production image — uv install, non-root user, :8080
├── docker-compose.yml   # Local full-stack validation (api + ui + qdrant)
├── requirements.txt     # Full dev dependencies
└── requirements-prod.txt  # Lean production dependency set
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Orchestration | LangChain + LangGraph |
| LLMs | OpenAI `gpt-5-mini` + Anthropic fallback via **Portkey** gateway |
| Guardrails | NeMo Guardrails |
| Vector DB | Qdrant Cloud |
| Reranking | Jina AI Reranker API (`jina-reranker-v3`) |
| Embeddings | Jina AI `jina-embeddings-v3` (1024-dim) + local mxbai fallback |
| Document Parsing | pypdf + pdfplumber (local, no OCR service) |
| Conversation memory | Neon serverless PostgreSQL (LangGraph checkpointer) |
| Rate limiting | Upstash Redis (in-memory fallback) |
| Observability | Pydantic Logfire + LangSmith + Prometheus + CloudWatch |
| Evaluation | RAGAS + custom Tool Correctness (Jaccard) |
| Container | Docker (`python:3.11-slim-bookworm`, `uv`, non-root) |
| Compute | AWS ECS on Fargate |
| Ingress | AWS Application Load Balancer |
| Registry | Amazon ECR |
| Secrets | AWS Secrets Manager |
| CI/CD | GitHub Actions |
| Load testing | Locust |

---

## API Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness probe — `{"status":"ok"}` |
| `GET` | `/ready` | Readiness — checks Postgres, Redis, Qdrant, LLM gateway, Jina embeddings, Jina reranker |
| `POST` | `/query` | Run the LangGraph RAG pipeline synchronously |
| `GET` | `/graph` | Graph representation of the agent pipeline |
| `GET` | `/metrics` | Prometheus metrics (RAG + guardrails counters) |

---

## Getting Started (Local)

### 1. Install dependencies

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

Copy `.env.example` to `.env` and fill in your keys:

```powershell
copy .env.example .env
```

Key variables:

```env
# OpenAI LLM
OPENAI_API_KEY=

# LLM Gateway (Portkey)
PORTKEY_API_KEY=
PORTKEY_PRIMARY_SLUG=marathon-api
PORTKEY_PRIMARY_MODEL=gpt-5-mini
PORTKEY_FALLBACK_SLUG=anthropic-fallback
PORTKEY_PRIMARY_CONFIG_ID=      # system-generated pc-... ID of the saved Portkey config

# Jina AI Embeddings + Reranker API
JINA_API_KEY=

# Vector DB
QDRANT_API_KEY=
QDRANT_CLUSTER_ENDPOINT=https://your-cluster.cloud.qdrant.io:6333

# Production persistence (Neon) & cache (Upstash Redis)
NEON_DB_URL=postgresql://user:password@host.neon.tech/enterprise_rag?sslmode=require
UPSTASH_REDIS_REST_URL=https://your-db.upstash.io
UPSTASH_REDIS_REST_TOKEN=your-upstash-token

# API safety
RAG_API_KEY=                    # set in production to require bearer auth
RATE_LIMIT_PER_MINUTE=20

# Observability
LOGFIRE_TOKEN=
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=enterprise_rag
LANGSMITH_TRACING=true

# Evals
JUDGE_OPENAI_API_KEY=           # falls back to OPENAI_API_KEY

# Backend (for Streamlit UI)
BACKEND_URL=http://localhost:8000
```

> `PORTKEY_PRIMARY_CONFIG_ID` must be the system-generated `pc-...` ID of a saved Portkey config, not the human-readable slug. Run `python scripts/list_portkey_configs.py` to list yours.

### 3. Run data ingestion

Parses all documents in `DATA/`, chunks them, saves metadata to `processed_data/`, and indexes vectors into Qdrant.

```powershell
python -m app.ingestion.processor DATA --wipe
```

> Pass `--wipe` to drop and recreate the Qdrant collection. Omit it to append to an existing collection. The processor probes the embedding model and creates the collection with the correct dimension (1024, cosine) automatically.

### 4. Launch the app

The `/query` endpoint runs the LangGraph pipeline synchronously. You only need the FastAPI server and (optionally) the Streamlit UI. Redis and Postgres are managed by Upstash and Neon; no local persistence services are required.

> **Tip:** Verify all external connections before starting the server:
> ```bash
> python -m app.services.health.connection_checker
> ```

```powershell
# Terminal 1 — FastAPI backend
uvicorn app.main:app --reload --port 8000

# Terminal 2 — Streamlit UI
streamlit run ui/app.py
```

### 5. Query the API

```powershell
curl -X POST "http://localhost:8000/query" `
  -H "Content-Type: application/json" `
  -d '{"q": "How do I start Redis for a Kubernetes work queue?", "thread_id": "user-1"}'

# Response: {"question": "...", "answer": "...", "thought_process": [...], "status": "...", "sources": [...]}
```

### 6. Run the eval suite

```powershell
# Headless CLI runner (requires backend on :8000)
python -m evals.run_evals

# Or use the Streamlit demo
streamlit run evals/app.py
```

### 7. Run tests locally

```powershell
# Lint + format checks
ruff check app tests evals
ruff format --check app tests evals

# Unit tests
$env:LOGFIRE_IGNORE_NO_CONFIG=1
pytest tests/
```

---

## Run with Docker

`docker-compose.yml` brings up the API, the Streamlit UI, and a local Qdrant instance — the fastest way to validate the exact production image before deploying.

```bash
docker compose up --build

# API    → http://localhost:8000
# UI     → http://localhost:8501
# Qdrant → http://localhost:6333
```

Both `api` and `ui` are built from the same `Dockerfile` and read secrets from your `.env`. To point the stack at the local Qdrant container instead of Qdrant Cloud, override `QDRANT_URL=http://qdrant:6333` in the `api` service environment.

Build and run the production image on its own:

```bash
docker build -t enterprise-rag:local .
docker run --rm -p 8080:8080 --env-file .env enterprise-rag:local
```

**Image hardening**

- `python:3.11-slim-bookworm` base with OS packages patched at build time
- Dependencies installed with [`uv`](https://github.com/astral-sh/uv) in a cached layer, split from the source copy so code-only changes never re-resolve dependencies
- Runs as a non-root `appuser`
- Exposes `:8080` with `--timeout-graceful-shutdown 5` for clean ECS draining

---

## Production Deployment — AWS ECS Fargate

Full step-by-step provisioning commands live in **[`aws.md`](aws.md)**; the design rationale and alternatives live in **[`deployment_plan.md`](deployment_plan.md)**. This section is the overview.

### Services

| Service | Container command | CPU / Memory | Scaling | Responsibility |
|---|---|---|---|---|
| **rag-api** | `uvicorn app.main:app --host 0.0.0.0 --port 8080` | 1024 / 2048 | min 2, max 10 | Public HTTP API and synchronous RAG execution |
| **rag-ui** | `streamlit run ui/app.py --server.port 8501` | 512 / 1024 | min 1, max 4 | End-user chat interface |

### Managed dependencies

| Component | Service | Purpose |
|---|---|---|
| Vectors | Qdrant Cloud | Retrieval index (`enterprise_rag`, 1024-dim, cosine) |
| Postgres | Neon | LangGraph checkpointer / conversation memory |
| Redis | Upstash | FastAPI rate-limit store |
| Secrets | AWS Secrets Manager | API keys, DB URIs, Redis token |
| Ingress | Application Load Balancer | Public access to `rag-api` and `rag-ui` |
| Logs | CloudWatch Logs | `/ecs/rag-api`, `/ecs/rag-ui` |

Keeping all state in managed services means no EFS volumes, no sticky tasks, and no data loss on scale-in.

### Networking

- VPC across **2 Availability Zones** with public and private subnets.
- **Public subnets:** ALB + NAT Gateway.
- **Private subnets:** Fargate tasks only. Outbound traffic to Neon, Upstash, Qdrant Cloud, and the LLM APIs goes through NAT.

| Security group | Inbound | Outbound |
|---|---|---|
| `alb-sg` | 80/443 from the internet | `api-sg`, `ui-sg` |
| `api-sg` | 8080 from `alb-sg` | Internet (Neon, Upstash, Qdrant, LLM APIs) |
| `ui-sg` | 8501 from `alb-sg` | `api-sg` on 8080 |

ALB listener rules forward `/ui*` to the UI target group and everything else to the API target group.

### Configuration

Sensitive values are stored in **AWS Secrets Manager** and injected into the task definitions as `secrets`; non-sensitive values are plain `environment` entries.

**Secrets Manager** — `NEON_DB_URL`, `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN`, `QDRANT_URL`, `QDRANT_API_KEY`, `OPENAI_API_KEY`, `JINA_API_KEY`, `PORTKEY_API_KEY`, `RAG_API_KEY`, `LOGFIRE_TOKEN`, `LANGSMITH_API_KEY`

**Plain environment** — `QDRANT_COLLECTION=enterprise_rag`, `RATE_LIMIT_PER_MINUTE=60`, `PORTKEY_PRIMARY_CONFIG_ID`, `PORTKEY_PRIMARY_SLUG`, `PORTKEY_FALLBACK_SLUG`, `STRICT_STARTUP`, `PYTHONUNBUFFERED=1`

> `STRICT_STARTUP=true` makes the API refuse to boot if any external dependency is unreachable — use it in production, and `false` locally.

Task definition templates live in `.aws/task-definitions/` with `<PLACEHOLDER>` tokens for the image URI, region, backend URL, and every secret ARN. They are rendered at deploy time by the CD workflow, or locally by `scripts/render_task_defs.py`.

### Auto-scaling

`rag-api` uses target-tracking policies on:

- ALB **request count per target** > 1000
- **CPU utilization** > 70%
- **Memory utilization** > 70%

`rag-ui` scales on request count or CPU between 1 and 4 tasks (or stays fixed at 1 if internal-only).

### CI/CD Pipeline

```mermaid
graph LR
    Push[git push<br/>main / deployment] --> CI[CI workflow<br/>ruff + pytest]
    CI -->|success| CD[CD workflow]
    CD --> Build[docker build<br/>tag: git-sha + latest]
    Build --> ECR[(Amazon ECR)]
    ECR --> Render[Render task definitions<br/>inject image URI + secret ARNs]
    Render --> DeployA[ECS deploy rag-api]
    Render --> DeployU[ECS deploy rag-ui]
    DeployA --> Stable[Wait for service stability]
    DeployU --> Stable
```

- **`.github/workflows/ci.yml`** — runs on pushes and PRs to `main`, `features`, `deployment`: `ruff check`, `ruff format --check`, then `pytest tests/` with dummy credentials.
- **`.github/workflows/cd.yml`** — triggered by a **successful CI run** on `main` or `deployment`. Logs in to ECR, builds and pushes the image tagged with the commit SHA and `latest`, renders the task definitions, then deploys `rag-api` and `rag-ui` and waits for each service to stabilize.

#### Required GitHub Actions secrets

Set under **Settings → Secrets and variables → Actions**.

| Secret | Description |
|---|---|
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | IAM credentials with ECS, ECR, and Secrets Manager access |
| `AWS_REGION` | Target region (e.g. `us-east-1`) |
| `ECR_REPOSITORY` | ECR repository name (default `enterprise-rag`) |
| `ECS_CLUSTER` | ECS cluster name (default `rag-cluster`) |
| `ECS_SERVICE_API` / `ECS_SERVICE_UI` | ECS service names (default `rag-api` / `rag-ui`) |
| `BACKEND_URL` | API URL injected into the UI task |
| `NEON_DB_URL_ARN` | Secrets Manager ARN for `NEON_DB_URL` |
| `UPSTASH_REDIS_REST_URL_ARN` | Secrets Manager ARN for `UPSTASH_REDIS_REST_URL` |
| `UPSTASH_REDIS_REST_TOKEN_ARN` | Secrets Manager ARN for `UPSTASH_REDIS_REST_TOKEN` |
| `QDRANT_URL_ARN` | Secrets Manager ARN for `QDRANT_URL` |
| `QDRANT_API_KEY_ARN` | Secrets Manager ARN for `QDRANT_API_KEY` |
| `OPENAI_API_KEY_ARN` | Secrets Manager ARN for `OPENAI_API_KEY` |
| `JINA_API_KEY_ARN` | Secrets Manager ARN for `JINA_API_KEY` |
| `PORTKEY_API_KEY_ARN` | Secrets Manager ARN for `PORTKEY_API_KEY` |
| `RAG_API_KEY_ARN` | Secrets Manager ARN for `RAG_API_KEY` |
| `LOGFIRE_TOKEN_ARN` | Secrets Manager ARN for `LOGFIRE_TOKEN` |
| `LANGSMITH_API_KEY_ARN` | Secrets Manager ARN for `LANGSMITH_API_KEY` |

### Deployment sequence

1. Create the VPC, subnets, IGW, NAT Gateway, route tables, and security groups.
2. Provision Neon Postgres, Upstash Redis, and a Qdrant Cloud cluster; collect the connection strings.
3. Create the ECR repository (with a keep-last-30-images lifecycle policy) and the CloudWatch log groups.
4. Push secrets to Secrets Manager — `python scripts/create_aws_secrets.py` reads them straight from your `.env`.
5. Create `ecsTaskExecutionRole` plus the `rag-api-task-role` / `rag-ui-task-role` task roles and the read-secrets policy.
6. Create the ECS cluster and register both task definitions.
7. Create the ALB, target groups, and listener rules.
8. Create the ECS services and attach the auto-scaling policies.
9. Store the GitHub Actions secrets and push to `main` or `deployment` to trigger CI → CD.
10. Validate the endpoints, then run the ingestion job.

Every command for these steps is in **[`aws.md`](aws.md)**.

### Helper scripts

| Script | Purpose |
|---|---|
| `scripts/aws_deploy_env.sh` | Shared region / naming / CIDR variables sourced by the other scripts |
| `scripts/aws_deploy_state.sh` | Records the IDs of provisioned resources (VPC, subnets, ALB, target groups, task defs) |
| `scripts/create_aws_secrets.py` | Creates Secrets Manager entries from the local `.env` |
| `scripts/aws_secret_arns.sh` | Exports the resulting secret ARNs for task-definition rendering |
| `scripts/render_task_defs.py` | Renders `.aws/task-definitions/*.json` locally using `.env` + secret ARNs |
| `scripts/list_portkey_configs.py` | Lists Portkey saved configs so you can find the `pc-...` config ID |
| `scripts/locustfile.py` | Locust load-test scenario against the deployed ALB endpoint |
| `scripts/destroy_aws_deployment.sh` | Full teardown in dependency-safe order |

### Validate the deployment

```bash
export API_URL="http://<your-alb-dns-name>"

curl -s "${API_URL}/health"
curl -s "${API_URL}/ready"

curl -s -X POST "${API_URL}/query" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your-production-api-key>" \
  -d '{"q":"What is a Kubernetes pod?","thread_id":"aws-test"}'

# Streamlit UI
echo "Open ${API_URL}/ui"
```

Tail the logs and watch service health:

```bash
aws logs tail /ecs/rag-api --follow
aws ecs describe-services --cluster rag-cluster --services rag-api rag-ui
```

### Ingestion in production

Do **not** run ingestion as a long-running ECS service. Use one of:

1. **Fargate one-off task** — `ecs run-task` with `python -m app.ingestion.processor s3://bucket/data --wipe`.
2. **AWS Batch** — for large or scheduled ingestion jobs.
3. **GitHub Actions** — a post-deploy step for small, static datasets.

When sourcing from S3, download the files into the task's ephemeral storage before running the processor.

### Monitoring & alerting

- **CloudWatch Logs** — every service logs to `/ecs/<service>`.
- **CloudWatch Alarms** — `rag-api` 5xx error rate > 1%.
- **Prometheus** — scrape `/metrics` on `rag-api` (Amazon Managed Prometheus or a sidecar).
- **Dashboard metrics** — `/query` p50/p95 latency, guardrails block rate, answer token count.
- **Logfire + LangSmith** — distributed tracing and per-node agent traces, unchanged from local.

### Load testing

```bash
pip install locust
locust -f scripts/locustfile.py --headless -u 50 -r 5 -t 10m \
  --host http://<your-alb-dns-name>
```

### Cost & operational notes

- Fargate is simple to operate but costs more per vCPU than EC2 — consider EC2-backed ECS or EKS for sustained high throughput.
- The NAT Gateway is a fixed hourly cost; it is required for tasks in private subnets to reach the managed services.
- Neon, Upstash, and Qdrant Cloud are usage-priced and remove all database operations overhead.
- Keep `requirements-prod.txt` lean — `streamlit`, `ragas`, `sentence-transformers`, and `deepeval` do not belong in the API image unless needed.
- The Qdrant collection must be 1024-dimensional with cosine distance to match `jina-embeddings-v3`.

### Teardown

```bash
bash scripts/destroy_aws_deployment.sh
```

This removes, in dependency order: auto-scaling targets, ECS services and cluster, task definitions, ALB/listeners/target groups, ECR repository, Secrets Manager entries, IAM roles and policies, CloudWatch log groups, NAT Gateway and Elastic IP, and finally the route tables, subnets, IGW, and VPC. Section 19 of [`aws.md`](aws.md) has the equivalent manual commands.

---

## Documentation

| Document | Contents |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | System architecture, agent graph, ingestion and eval diagrams |
| [`deployment_plan.md`](deployment_plan.md) | AWS deployment design, trade-offs, task definitions, alternatives |
| [`aws.md`](aws.md) | Complete AWS provisioning runbook — every CLI command, in order |
| [`local_testing.md`](local_testing.md) | Local environment setup, ingestion, and feature-by-feature testing |
| [`TESTING.md`](TESTING.md) | Endpoint, guardrails, auth, rate-limit, metrics, and eval test guide |

---

*Built for High-Scale Enterprise Document Intelligence.*

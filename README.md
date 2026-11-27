# AI_SAAS

Two production-grade AI products in one monorepo:

1. **ClauseGuard** — automated RFP / legal contract redliner and analyzer.
2. **Relay Receptionist** — real-time voice receptionist and outbound qualifier.

Both are built as independently deployable services with a shared operational
model: Postgres, Redis, object storage, OpenTelemetry + Langfuse, structured
JSON logs, health/readiness probes, migrations, and Docker images.

> Planning documents live in `docs/roadmaps/` and are intentionally **not
> committed** (see `.gitignore`). This README is the durable architecture
> record.

---

## Repository layout

```
apps/
  contract-redliner/
    api/    FastAPI + async SQLAlchemy + pgvector + arq workers
    web/    Next.js 15 App Router review console
  voice-receptionist/
    api/    FastAPI control plane (tenants, numbers, calls, bookings)
    agent/  LiveKit Agents worker (Deepgram STT / ElevenLabs TTS)
infra/      compose, provisioning, observability config
docs/       architecture notes + local-only roadmaps
```

## Product 1 — ClauseGuard

Upload a multi-page PDF/RFP. The pipeline:

1. Extracts page-aware text and tables (PyMuPDF + pdfplumber, with optional
   LlamaParse/Unstructured adapters).
2. Segments clauses deterministically, then normalizes them with an LLM into a
   typed clause IR with **page + bounding-box citations**.
3. Evaluates each clause against a versioned **company playbook** using a hybrid
   of deterministic patterns and LLM classification.
4. Retrieves precedent with **hybrid search** (Postgres FTS + pgvector, fused
   with Reciprocal Rank Fusion).
5. Produces a downloadable redline package: tracked-changes `.docx`, annotated
   `.pdf`, summary `.pdf`, and `.md`/`.json`.

### Quick start

```bash
cp apps/contract-redliner/api/.env.example apps/contract-redliner/api/.env
cp apps/contract-redliner/web/.env.example apps/contract-redliner/web/.env.local
docker compose -f infra/docker-compose.yml up -d postgres redis minio
cd apps/contract-redliner/api
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn redliner.main:app --reload --port 8000
# worker (separate shell)
arq redliner.services.jobs.WorkerSettings
# web (separate shell)
cd ../web && npm install && npm run dev
```

## Product 2 — Relay Receptionist

A low-latency phone agent for dental clinics, real-estate teams, and local
contractors.

- **Inbound**: Twilio number → LiveKit SIP trunk → LiveKit room → Python agent.
- **Outbound**: `POST /v1/calls/outbound` → Twilio → SIP → agent.
- **Pipeline**: Deepgram streaming STT → LLM with tools → ElevenLabs TTS.
- **Interruptions**: LiveKit turn detection + VAD; barge-in safe.
- **Tools**: `check_availability`, `book_appointment` (DB-enforced no
  double-booking), `send_booking_link` (Twilio SMS), `lookup_knowledge`,
  `take_message`, `transfer_call`, `end_call`.
- **After call**: transcript + recording (S3), summary, CRM webhook, Langfuse
  trace.

### Quick start

```bash
cp apps/voice-receptionist/api/.env.example apps/voice-receptionist/api/.env
cp apps/voice-receptionist/agent/.env.example apps/voice-receptionist/agent/.env
docker compose -f infra/docker-compose.yml up -d postgres redis minio
cd apps/voice-receptionist/api
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]" && alembic upgrade head
uvicorn voice_api.main:app --reload --port 8001
# worker (separate shell)
cd ../agent && pip install -e ".[dev]" && python -m receptionist_agent
```

## Architecture decisions

| Concern | Choice | Why |
|---|---|---|
| API | FastAPI + Pydantic v2 | Async I/O, typed contracts, OpenAPI |
| DB | Postgres 16 + pgvector | FTS + vector in one store, tenant RLS-ready |
| Queue | Redis + arq | Async-native, retries, no extra broker |
| PDF | PyMuPDF + pdfplumber | Fast page-level text, real table extraction |
| LLM | OpenRouter free models by default, OpenAI-compatible fallback | No vendor lock-in; JSON-schema validated |
| Search | FTS + vector + RRF | Keyword precision + semantic recall |
| Voice | LiveKit Agents + Deepgram + ElevenLabs | Sub-500ms turn-taking, barge-in |
| Telephony | Twilio SIP trunk | Programmable inbound/outbound |
| Observability | Langfuse + OTel + JSON logs | Traces per document/call |
| Auth | JWT + API keys, argon2/scrypt | Multi-tenant by default |

## Non-negotiables

- Every AI output carries a **citation** (`page`, `block`, `quote`) or is
  rejected by validation.
- Every redline is **reviewable**: accept/reject persisted, exportable.
- Every call has a **durable record** before the agent confirms an action.
- Booking writes use a **partial unique index**; races return a friendly
  alternative, never a double booking.
- Secrets never reach the browser or the LLM prompt.
- PII redaction + configurable retention on transcripts/recordings.

## Testing

```bash
# API unit + integration
cd apps/contract-redliner/api && pytest
cd ../../voice-receptionist/api && pytest
# Agent unit tests (no LiveKit cloud required)
cd ../agent && pytest
# Web
cd ../../contract-redliner/web && npm run lint && npm run typecheck
```

## Local stack

```bash
make up        # build and start every service (Postgres, Redis, MinIO, APIs, workers, web)
make migrate   # apply both Alembic migrations
make logs      # tail logs
make down      # stop and remove volumes
```

Observability (Langfuse/OTel, Prometheus, Grafana) is behind a compose profile:

```bash
docker compose -f infra/docker-compose.yml --profile observability up -d otel-collector prometheus grafana
```

## Deployment — Vercel Services + Render

The repository can deploy as **one Vercel project with multiple services**, or as
a Render Blueprint. The Vercel path is the lowest-latency option: the browser
talks directly to the FastAPI services, and the LiveKit agent runs as a Vercel
daemon with a private service binding.

### Vercel (recommended)

Import the repo with the default root (the repository root). `vercel.json` defines:

| Service | Type | Public path | Notes |
|---|---|---|---|
| `web` | Next.js | `/(.*)` | Review console |
| `clause-api` | FastAPI | `/api/clause(.*)` | Direct browser uploads, no proxy body limit |
| `relay-api` | FastAPI | `/api/relay(.*)` | Twilio webhooks + agent API |
| `receptionist-agent` | daemon | internal | LiveKit worker, bound to `relay-api` |

The agent declares a service binding:

```json
{ "type": "service", "service": "relay-api", "format": "url", "env": "RELAY_API_URL" }
```

The agent reads `RELAY_API_URL` first and falls back to `CONTROL_PLANE_URL` for
local/Render. Both APIs mount their routers under `/v1` and under their public
prefix (`/api/clause/v1`, `/api/relay/v1`), so the same code works behind Vercel
and Render without path rewriting.

Set these in Vercel (do **not** set `RELAY_API_URL`; Vercel injects it):

| Variable | Value |
|---|---|
| `NEXT_PUBLIC_API_URL` | `/api/clause` |
| `NEXT_PUBLIC_SITE_URL` | `https://<your-vercel-domain>` |
| `CORS_ORIGINS` (clause-api) | `https://<your-vercel-domain>` |
| `INTERNAL_API_TOKEN` (relay-api + agent) | same generated value |
| `DATABASE_URL`, `REDIS_URL` | Vercel/Upstash or your Postgres/Redis |
| `S3_*`, `OPENROUTER_API_KEY`, `TWILIO_*`, `LIVEKIT_*`, `DEEPGRAM_API_KEY`, `ELEVENLABS_API_KEY` | production secrets |

`NEXT_PUBLIC_*` values are inlined at build time. Changing them requires a
Vercel redeploy.

### Render (alternative)

Import the repo as a Blueprint. `render.yaml` creates `clauseguard-api`,
`relay-api`, both workers, the LiveKit agent, Postgres, and Key Value. Set the
same secrets in Render. `preDeployCommand` runs `alembic upgrade head`.

### Post-deploy checklist

- `GET /api/clause/v1/healthz` and `/api/relay/v1/healthz` return `ok`.
- `GET /metrics` returns Prometheus metrics on both APIs.
- Postgres has the `vector` extension (ClauseGuard migration creates it).
- S3/R2 bucket exists and credentials can read/write.
- Twilio webhook URLs point at `https://<domain>/api/relay/v1/webhooks/twilio/...`.
- LiveKit SIP trunk points at the Relay agent daemon/worker.
- Vercel preview deployments get isolated `NEXT_PUBLIC_API_URL` values if needed.

## License

Apache-2.0 (see `LICENSE`).
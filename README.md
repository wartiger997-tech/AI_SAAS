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
| LLM | Provider-abstracted (OpenAI/Anthropic/Gemini) | No lock-in; JSON-schema validated |
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

## Deployment — Vercel + Render

The frontend deploys to Vercel; both APIs, workers, the LiveKit agent, Postgres,
and Redis deploy to Render from the root `render.yaml` Blueprint.

### 1. Render (backend)

1. Push the repo to GitHub.
2. In Render: **New → Blueprint** → select the repo.
3. Fill in every `sync: false` secret (Twilio, LiveKit, Deepgram, ElevenLabs,
   OpenAI, S3/R2, Langfuse).
4. The Blueprint creates:
   - `clauseguard-api` + `clauseguard-worker` + `clauseguard-db` + Redis
   - `relay-api` + `relay-worker` + `relay-agent` + `relay-db` + Redis
5. `initialDeployHook` runs `alembic upgrade head` for both APIs.

### 2. Vercel (frontend)

**Option A — recommended:** import the repo, set **Root Directory** to
`apps/contract-redliner/web`. Vercel detects Next.js and uses
`apps/contract-redliner/web/vercel.json`.

**Option B — repo root:** the root `vercel.json` builds the web app from the
monorepo root.

Set these environment variables in Vercel:

| Variable | Value |
|---|---|
| `NEXT_PUBLIC_API_URL` | `https://clauseguard-api.onrender.com` |
| `NEXT_PUBLIC_SITE_URL` | `https://clauseguard-web.vercel.app` |

Then set `CORS_ORIGINS` on the Render `clauseguard-api` service to the Vercel
URL and redeploy. `NEXT_PUBLIC_*` values are inlined at build time, so changing
them requires a Vercel redeploy.

### 3. Post-deploy checklist

- `GET /healthz` and `/readyz` return `ok` on both APIs.
- Render Postgres has the `vector` extension (ClauseGuard migration creates it).
- S3/R2 bucket exists and credentials can read/write.
- Twilio webhook URLs point at `https://relay-api.onrender.com/v1/webhooks/twilio/...`.
- LiveKit SIP trunk points at the Relay agent worker.
- Vercel preview deployments get their own `NEXT_PUBLIC_API_URL` if you want
  isolated API environments.

## License

Apache-2.0 (see `LICENSE`).
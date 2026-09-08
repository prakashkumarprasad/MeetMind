# MeetMind — AI Meeting Intelligence

> **Turn every meeting into notes, action items, and answers.**

MeetMind is a full-stack AI application that lets teams upload audio and video
recordings of meetings, get them automatically **transcribed**, distilled into
**summaries and action items**, and then **chat with the content** across all of
their meetings via a grounded, source-cited RAG assistant.

This README provides a detailed overview of the entire project: what it does,
how it is architected, every service and endpoint, the data model, how to run it
locally, and how to test it.

---

## Table of Contents

- [Repository](#-repository)
- [Overview](#overview)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [High-Level Architecture](#high-level-architecture)
- [Project Layout](#project-layout)
- [Database Schema](#database-schema)
- [API Endpoints](#api-endpoints)
- [Ingestion & Processing Pipeline](#ingestion--processing-pipeline)
- [RAG / Chat Design](#rag--chat-design)
- [Security Design](#security-design)
- [Getting Started](#getting-started)
- [Production Deployment](#production-deployment)
- [Environment Variables Reference](#environment-variables-reference)
- [Database Migrations](#database-migrations)
- [Testing](#testing)
- [Comments & Code Style Policy](#comments--code-style-policy)
- [Status & Roadmap](#status--roadmap)

---

## 🔗 Repository

**Repository:** `https://github.com/prakashkumarprasad/MeetMind`

The repository is a single monorepo containing two top-level packages:
`backend/` (FastAPI + Celery + PostgreSQL/pgvector) and `frontend/`
(Next.js App Router + React 19 + TypeScript).

---

## Overview

MeetMind solves a common problem: meeting recordings are locked inside audio and
video files. Teams can't search them, skim them, or ask questions about them.

MeetMind's flow is:

1. **Upload** — a user uploads an audio or video recording to their workspace.
   Files go straight to an S3-compatible bucket via a **presigned URL**, so large
   files never touch the API server.
2. **Process (asynchronous)** — a Celery worker downloads the file, converts
   video to audio with `ffmpeg` when needed, transcribes it with `faster-whisper`
   (`medium`, CPU/INT8 in production), chunks and embeds the transcript into
   **pgvector**, and generates a summary + action items with an LLM.
3. **Chat (RAG)** — the user asks natural-language questions. The backend
   retrieves relevant context from the embedded transcript chunks (and stored
   meeting summaries) and the LLM answers with **cited sources** — which meeting
   and which excerpt each answer came from.

It is a **multi-tenant** system: users belong to **workspaces**, and all meetings,
chunks, and chat data are scoped to workspaces with membership checks.

---

## Features

- **AI transcription** — upload audio or video; `faster-whisper` (medium) transcribes
  speech-to-text. The current production worker runs the medium model on CPU with
  INT8 and two CPU threads. Video files are automatically converted to 16 kHz mono
  WAV audio with `ffmpeg` first.
- **Meeting summaries & action items** — each ready meeting has a generated
  prose summary plus actionable items with owner and due date.
- **Chat with your meetings** — an interactive, multi-turn chat UI. Users select
  one or many meetings as context and ask questions; answers are grounded in the
  actual meeting content and include sources.
- **Multi-meeting synthesis** — the model is explicitly prompted to synthesize
  answers across *all* selected meetings, acknowledge meetings with no content,
  and surface conflicting statements rather than silently picking one.
- **Seamless SSO + email auth** — email/password signup+login **and** Google
  OAuth sign-in, with secure refresh-token rotation.
- **Workspace multi-tenancy** — per-user workspaces with role-based membership
  (`owner` / `admin` / `member`).
- **Media-aware processing UI** — while a meeting is being processed, both the
  meeting card and the meeting detail page show a shared progress panel with a
  loading bar, a live step tracker (`validating → converting → transcribing →
  summarizing`), and an amber notice explaining that video meetings take a
  little longer because they are first converted to audio before transcription.
- **Modern dashboard UI** — Next.js App Router with statistics cards, live
  processing-status polling, clickable meeting cards (hand cursor, navigate to
  the detail page while keeping delete separate), a meeting detail view, and a
  chat page.
- **Security-hardened** — CSRF-resistant cookie auth, workspace-level IDOR
  protection, refresh-token reuse detection, and Redis-backed rate limiting.

---

## Tech Stack

### Backend (`backend/` — Python 3.12)
| Layer | Technology |
|---|---|
| Web framework | [FastAPI](https://fastapi.tiangolo.com/) + Uvicorn |
| ORM / migrations | SQLAlchemy 2.x + Alembic |
| Database | PostgreSQL 16 with [pgvector](https://github.com/pgvector/pgvector) (`pgvector/pgvector:pg16`) |
| Cache / broker | Redis (Upstash in prod) |
| Background jobs | Celery 5.x |
| Object storage | AWS S3 or any S3-compatible store (Supabase Storage, MinIO) via `boto3` |
| Transcription | `faster-whisper` (CPU/INT8 in production) + `ffmpeg` for video → audio |
| Embeddings | `sentence-transformers` (`all-MiniLM-L6-v2`, 384-dim) |
| LLM | Groq (default) or Ollama (local) via the `groq` / `httpx` SDKs |
| Auth | `bcrypt` (password hashing) + `PyJWT` (JWT + refresh-token families) |
| Validation | Pydantic v2 + `pydantic-settings` + `email-validator` |

### Frontend (`frontend/` — TypeScript)
| Layer | Technology |
|---|---|
| Framework | [Next.js](https://nextjs.org/) 16 (App Router) + React 19 |
| Language | TypeScript 5 |
| Styling | Tailwind CSS v4 (PostCSS), `class-variance-authority`, `tailwind-merge` |
| State | Zustand (auth store) + TanStack Query (server state/caching) |
| Data fetching | Axios with interceptors (CSRF header + auto token refresh) |
| UI components | Base UI (`@base-ui/react`), Radix scroll-area, `shadcn`, `sonner` (toasts), `lucide-react` (icons) |
| Markdown | `react-markdown` + `remark-gfm` (rendering AI answers) |
| Animation | `framer-motion` |
| Lint | ESLint 9 (`eslint-config-next`) |

---

## High-Level Architecture

```
┌────────────────────────────┐        ┌─────────────────────────────────────┐
│        Frontend            │  HTTPS  │             Backend                │
│   Next.js 16 (App Router)  │◀───────▶│        FastAPI (Uvicorn)           │
│   React 19 + TypeScript    │  /api   │  ┌───────────────────────────────┐ │
│   TanStack Query / Zustand │         │  │  api/v1: auth, meetings,      │ │
└────────────────────────────┘         │  │          chat, workspaces      │ │
                                      │  └───────────────────────────────┘ │
                                      │  ┌───────────────────────────────┐ │
                                      │  │  services: s3, llm            │ │
                                      │  └───────────────────────────────┘ │
                                      └───────────┬────────────────────────┘
                                                  │
                        ┌─────────────────────────┼─────────────────────────┐
                        │ PostgreSQL 16 + pgvector│        Redis            │
                        │ (models, chunks,        │        (rate limits,    │
                        │  embeddings, chat)      │         broker/backend) │
                        └─────────────────────────┴─────────────────────────┘
                                        ▲
                                        │ publish / consume
                        ┌───────────────┴──────────────────────────┐
                        │              Celery Worker              │
                        │  1. transcribe_meeting (faster-whisper,  │
                        │     ffmpeg for video)                     │
                        │  2. embed_meeting (chunk + pgvector)      │
                        │  3. summarize_meeting (LLM + action items)│
                        └──────────────────────────────────────────┘
                                        │
                                        ▼
                        ┌──────────────────────────────────────────────┐
                        │          S3-compatible storage               │
                        │   (presigned upload/download, never exposes  │
                        │    the bucket publicly)                      │
                        └──────────────────────────────────────────────┘
```

Key architectural decisions:

- **Presigned uploads.** Clients upload media directly to S3 using a short-lived
  presigned POST, so the API server never streams large files through itself.
  The server always generates the storage key itself (never trusts client
  filenames) to prevent path/filename injection.
- **Web/worker split.** Celery decouples the heavy ingestion pipeline (whisper,
  embeddings, LLM) from the API so requests stay responsive. In production, the
  FastAPI backend and Celery worker run as separate containers on AWS EC2.
- **pgvector for retrieval.** Transcripts are chunked (~200 words with 30-word
  overlap) and embedded into a `Vector(384)` column for semantic similarity
  search (with a bounded-distance threshold and recency bonus).
- **Summary-first RAG.** When a meeting is explicitly selected by the user, chat
  retrieval treats it as *relevant by definition* and uses its stored summary as
  the primary source instead of running a similarity gate that could drop it.
- **Cookie + bearer auth.** Access tokens are sent as `Authorization: Bearer`;
  refresh tokens live in an HttpOnly, Secure, SameSite cookie and rotate on
  every use.

---

## Project Layout

### Backend

```
backend/
├── alembic/                    # Database migrations
│   └── versions/
│       ├── b3ad46caea01_initial_schema.py
│       ├── 7e9f6f8ab7d9_add_action_items_table.py
│       ├── a1b2c3d4e5f6_add_video_upload_columns.py
│       ├── c2d3e4f5a6b7_add_refresh_token_families_table.py
│       └── e9e4cc5cf7c1_add_chat_sessions_and_chat_messages.py
├── app/
│   ├── main.py                 # FastAPI app, CORS, security headers, routers, /health
│   ├── api/
│   │   ├── deps.py             # get_current_user, get_workspace_membership,
│   │   │                       # require_role, require_xhr_header
│   │   └── v1/                 # Versioned routers
│   │       ├── auth.py         # signup, login, Google, refresh, logout, /me
│   │       ├── meetings.py     # upload request, confirm, list, detail, delete
│   │       ├── chat.py         # RAG chat + sessions/messages + chat-meeting catalog
│   │       └── workspaces.py   # list caller's workspaces
│   ├── core/
│   │   ├── config.py           # pydantic-settings Settings
│   │   ├── security.py         # bcrypt, JWT, refresh-token family helpers
│   │   └── rate_limit.py       # Redis sliding-window rate limiting
│   ├── db/
│   │   ├── base.py             # Declarative Base
│   │   └── session.py          # engine, SessionLocal, get_db dependency
│   ├── models/                 # SQLAlchemy models (see Database Schema)
│   ├── schemas/                # Pydantic request/response models
│   │   ├── auth.py
│   │   ├── meeting.py
│   │   └── chat.py
│   ├── services/
│   │   ├── s3.py               # presigned upload/download, storage keys
│   │   └── llm.py              # summary prompt, RAG prompt builder, Groq/Ollama calls
│   └── workers/                # Celery tasks
│       ├── celery_app.py
│       ├── transcription.py    # transcribe_meeting
│       ├── embedding.py        # embed_meeting
│       └── summarization.py    # summarize_meeting
├── tests/                      # pytest suite (see Testing)
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_auth_security.py
│   ├── test_chat.py
│   ├── test_meetings.py
│   ├── test_record_access.py
│   └── test_workspace_membership.py
├── Dockerfile                  # python:3.12-slim + ffmpeg + non-root user
├── docker-compose.yml          # backend + celery worker
├── docker-compose.test.yml     # isolated pgvector + redis for local tests
├── requirements.txt
├── alembic.ini
├── .env.example
└── .env                        # local secrets (git-ignored)
```

### Frontend (App Router)

```
frontend/
├── app/
│   ├── layout.tsx              # Root layout: Geist fonts + Providers
│   ├── page.tsx                # Public marketing/landing page
│   ├── providers.tsx           # React Query + auth restore + CSRF axios
│   ├── globals.css
│   ├── not-found.tsx
│   ├── (auth)/                 # Auth route group (shared layout)
│   ├── (dashboard)/            # Authenticated route group → PageWrapper
│   │   ├── layout.tsx
│   │   ├── error.tsx           # Error boundary UI
│   │   └── dashboard/
│   │       ├── page.tsx        # Dashboard: stats, upload, recent meetings
│   │       ├── components.tsx  # StatCard, MeetingCard, MeetingProcessingPanel, progress helpers
│   │       ├── upload-dialog.tsx
│   │       ├── chat/page.tsx        # Multi-meeting RAG chat UI
│   │       ├── meetings/page.tsx    # list all meetings
│   │       ├── meetings/[id]/page.tsx  # meeting detail (transcript/summary/AI)
│   │       └── settings/page.tsx
│   ├── login/page.tsx
│   ├── signup/page.tsx
│   ├── contact/page.tsx
│   ├── privacy/page.tsx
│   └── terms/page.tsx
├── components/
│   ├── auth/                   # AuthShell, GoogleSignIn, PasswordInput
│   ├── layout/                 # PageWrapper, Sidebar, index.ts
│   ├── meetings/               # delete-meeting-dialog.tsx
│   ├── ui/                     # badge, button, card, dialog, input, label,
│   │                           # scroll-area, skeleton, textarea
│   ├── legal-section.tsx
│   ├── legal-shell.tsx
│   └── public-footer.tsx
├── lib/
│   ├── api-client.ts           # axios instance + CSRF header + 401 refresh interceptor
│   ├── auth-store.ts           # Zustand auth store
│   ├── csrf.ts                 # CSRF custom header constants
│   ├── use-require-auth.ts     # redirect-if-unauthenticated hook
│   ├── utils.ts                # cn() (tailwind-merge) + date formatting
│   └── hooks/                  # useClickOutside, useDebounce, useLocalStorage,
│                               # useMediaQuery, useOnScreen, usePageTitle, index.ts
└── public/                     # static assets + favicon
```

---

## Database Schema

All PostgreSQL tables (managed with SQLAlchemy + Alembic). UUID primary keys and
timezone-aware timestamps throughout. Definitions in `backend/app/models/`.

| Table | Purpose | Key columns |
|---|---|---|
| `users` | Application users | `email` (unique), `hashed_password`, `google_id` (unique), `full_name` |
| `workspaces` | Multi-tenant containers for meetings | `name` |
| `workspace_members` | User↔workspace membership | `workspace_id`, `user_id`, `role` (`owner`/`admin`/`member`) |
| `meetings` | A single uploaded recording + processing state | `workspace_id`, `owner_id`, `title`, `storage_key`, `original_filename`, `file_size_bytes`, `content_type`, `source_media_type` (`audio`/`video`), `status`, `error_message`, `transcript_text`, `summary_text` |
| `transcript_chunks` | Embeddable chunks of a transcript | `meeting_id`, `workspace_id`, `chunk_text`, `chunk_index`, `embedding` (`Vector(384)`) |
| `action_items` | Extracted action items per meeting | `meeting_id`, `workspace_id`, `description`, `owner`, `due_date` |
| `chat_sessions` | A chat conversation | `workspace_id`, `user_id`, `title` |
| `chat_messages` | Messages within a session | `session_id`, `role` (`user`/`assistant`), `content`, `sources` (JSONB of cited sources) |
| `refresh_token_families` | Server-side rotation/reuse tracking | `user_id`, `family_id` (unique), `revoked`, `last_jti`, `revoked_at` |

Meeting status lifecycle (see Pipeline below):
`pending → transcribing → converting (video only) → validating → summarizing →
ready`, or `failed`.

---

## API Endpoints

All API routes are mounted under the `/api/v1` prefix on the FastAPI app, and
response schemas are enforced with Pydantic. OpenAPI docs are available at
`/docs` when running.

### Auth — `/api/v1/auth/*`
| Method | Path | Description |
|---|---|---|
| POST | `/auth/signup` | Create account + default workspace, return access token, set refresh cookie |
| POST | `/auth/login` | Email/password login (rate-limited, failure-only counting) |
| POST | `/auth/google` | Exchange a Google ID token for a MeetMind session |
| POST | `/auth/refresh` | Rotate refresh token (reuse detection), issue new access token |
| POST | `/auth/logout` | Revoke refresh-token family, clear cookie |
| GET | `/auth/me` | Current user profile |

### Workspaces
| Method | Path | Description |
|---|---|---|
| GET | `/workspaces` | List the caller's workspaces and their role in each |

### Meetings — `/workspaces/{workspace_id}/meetings`
| Method | Path | Description |
|---|---|---|
| POST | `` (empty) | Request a presigned upload; validates type/size, creates `pending` meeting with `source_media_type` (`audio`/`video`) |
| POST | `/{meeting_id}/confirm-upload` | Mark upload complete; enqueue `transcribe_meeting` Celery task |
| GET | `` | List meetings in the workspace |
| GET | `/{meeting_id}` | Meeting detail (transcript, summary, action items, error) |
| DELETE | `/{meeting_id}` | Delete meeting + its S3 object (owner/admin only) |

### Chat — `/workspaces/{workspace_id}/chat`
| Method | Path | Description |
|---|---|---|
| POST | `/messages` | Send a chat message with RAG retrieval; returns answer + sources |
| GET | `/sessions` | List chat sessions (most recent first) |
| GET | `/sessions/{session_id}/messages` | Messages in a session |
| GET | `/meetings` | Catalog of `ready` meetings available as chat context |
| GET | `/meetings/{meeting_id}` | Single meeting for chat context |

### Health
| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness check: `{"status": "ok"}` |

---

## Ingestion & Processing Pipeline

When a user confirms an upload (`confirm-upload`), the backend enqueues the
Celery task `transcribe_meeting`, which chains into the full pipeline:

1. **`transcribe_meeting`** (`workers/transcription.py`)
   - Sets status to `transcribing`, downloads the file from S3.
   - If the source is video (`source_media_type == "video"`), status → `converting`
     and `ffmpeg` extracts the audio track to 16 kHz mono WAV.
   - `faster-whisper` (`medium`) transcribes with the `translate` task (translates
     to English). Production uses CPU inference with INT8 and two CPU threads.
     Status → `validating`.
   - Enqueues `embed_meeting`.
   - On failure: status → `failed` with a friendly `error_message`.

2. **`embed_meeting`** (`workers/embedding.py`)
   - Splits the transcript into ~200-word chunks with 30-word overlap.
   - Embeds each chunk with `sentence-transformers/all-MiniLM-L6-v2` (384-dim)
     and inserts rows into `transcript_chunks` (pgvector `embedding` column).
   - Status → `summarizing`. Enqueues `summarize_meeting`.

3. **`summarize_meeting`** (`workers/summarization.py`)
   - Calls the LLM with a strict JSON-output system prompt asking for a
     `summary` plus `action_items[]` (description, owner, due date).
   - Parses the JSON (with a safe fallback to raw text + no action items if the
     model ignores the format).
   - Persists `summary_text` and `action_items`, sets status → `ready`.
   - On failure: status → `failed`.

These same statuses are surfaced to users through a single shared frontend
component, `MeetingProcessingPanel`, which is used on meeting cards and the meeting
detail page. It renders a loading bar, a step tracker with checkmarks on completed
steps, and a reassurance message explaining that processing can take a few minutes.
For video meetings it also shows an amber notice that the recording is first converted
to audio, which is why video uploads take a little longer.

The dashboard polls the meeting list every 5 s while anything is still in an
in-progress status, so users see live progress.

---

## RAG / Chat Design

`chat.py` powers the question-answering endpoint, and `services/llm.py` builds
the prompts.

**Retrieval strategy (multi-meeting):**

- *Explicitly selected meetings* (from `meeting_ids`) and *title-matched meetings*
  (a title that appears word-boundary in the question) are treated as **in
  scope**. For each one, the stored `summary_text` is the primary source, plus up
  to `TOP_K_CHUNKS` (8) transcript chunks **without a distance threshold** —
  being explicitly selected already proves relevance, so a semantic gate is not
  applied and no silently dropped meeting is possible.
- If the user named/selected nothing, it falls back to a **workspace-wide
  semantic search** over pgvector using cosine distance, with a
  `MAX_RELEVANT_DISTANCE` (0.8) threshold, a global top-k of 8, and a
  recency bonus (30-day half-life) that mildly favors newer meetings.

**Prompt hardening (`llm.py`):**

- A `<selected_meetings>` block lists every user-chosen meeting with its
  processing `status` and is authoritative — the model must answer about the
  whole list, not just whichever has the longest excerpt.
- A `<no_content>` note tells the model to acknowledge meetings that have no
  transcript/summary (still processing, failed, or empty) by name instead of
  claiming they weren't provided or silently omitting them.
- Excerpts are grouped per meeting in the prompt so the model synthesizes across
  distinct sources and explicitly calls out conflicting statements.
- Strict formatting rules: at most one markdown table for multiple meetings
  (Meeting | Date | Key points) plus one "Overall" paragraph, one format per
  message — no duplicated content.
- The system prompt treats excerpts/history as **data, never instructions**
  (prompt-injection defense).

**Sources:** every assistant reply stores the cited `sources` (meeting id/title
+ excerpt) in `chat_messages.sources` (JSONB) and returns them in the response so
the UI can attribute answers.

**Context window:** the transcript/chunk text passed into the prompt is truncated
to `MAX_TRANSCRIPT_CHARACTERS` (20k chars) and history to at most
`MAX_HISTORY_MESSAGES` (12 turns).

---

## Security Design

MeetMind was built with several deliberate security hardening choices:

- **Passwords** hashed with `bcrypt` (12 rounds); a 72-byte limit is enforced.
- **Access tokens** are short-lived JWTs (15 min, HS256) sent as a bearer token.
- **Refresh-token rotation + reuse detection** — each login creates a
  *refresh-token family*; each rotation assigns a new `jti` recorded in the DB.
  Presenting an *older*, already-rotated refresh token revokes the whole family
  (a stolen-token signal). Refresh tokens live in an **HttpOnly, Secure,
  SameSite=None** cookie.
- **CSRF protection** — state-changing cookie-authenticated routes
  (`refresh`, `logout`) require a custom `X-Requested-With: XMLHttpRequest`
  header (`require_xhr_header` dependency). Browsers won't attach custom headers
  cross-origin without a CORS preflight, and the CORS allowlist rejects foreign
  origins, closing the cookie-forgery gap that CORS alone cannot.
- **IDOR prevention** — `get_workspace_membership` returns **404** (not 403)
  when a user isn't a member, so "doesn't exist" and "not yours" are
  indistinguishable, preventing enumeration of valid workspace IDs. Deletion is
  further gated by `owner`/`admin` role checks.
- **Redis rate limiting** — sliding-window counters for signup, login (counts
  only real failures so successful logins don't exhaust the budget), chat, and
  upload requests; failures return `Retry-After`.
- **Storage safety** — upload keys are server-generated UUIDs
  (`audio/<uuid>`), never client-supplied filenames; presigned URLs keep the
  bucket private; a `content-length-range` condition enforces size at S3.
- **Security headers** — `X-Content-Type-Options: nosniff` and
  `X-Frame-Options: DENY` on every response; HSTS in non-development.
- **Prompt injection defense** — the LLM system prompt treats all meeting
  content and history as data, never instructions.

---

## Getting Started

### Prerequisites
- Python 3.12
- Node.js 20+ (Next.js 16)
- Docker (for local Postgres/pgvector + Redis)
- Optional: an NVIDIA GPU can accelerate `faster-whisper`; production currently uses the medium model on CPU/INT8.
- An LLM provider API key (Groq by default; Ollama also supported)

### 1. Backend

```bash
cd backend

# create venv and install
python -m venv .venv
.\.venv\Scripts\activate          # Windows
# source .venv/bin/activate       # macOS / Linux
pip install -r requirements.txt

# configure environment
copy .env.example .env            # then fill in real values (see variable reference)
```

Set up local databases (isolated test infra lives in `docker-compose.test.yml`,
and a normal one in `docker-compose.yml`):

```bash
# isolated pgvector + redis for local dev/tests
docker compose -f docker-compose.test.yml up -d

# run migrations (needs DATABASE_URL in .env)
alembic upgrade head
```

Run the API:

```bash
uvicorn app.main:app --reload
# → http://localhost:8000   (OpenAPI docs at /docs)
```

Run the Celery worker (in a second terminal):

```bash
celery -A app.workers.celery_app worker --loglevel=info --pool=solo
```

### 2. Frontend

```bash
cd frontend
npm install

# configure environment
# NEXT_PUBLIC_API_URL=http://localhost:8000  (see frontend/.env.local)
```

Run the dev server:

```bash
npm run dev
# → http://localhost:3000
```

### 3. Docker (production-style, optional)

```bash
cd backend
docker compose up --build        # starts the API + Celery worker
```

The production Docker image is CPU-oriented: the backend Dockerfile installs the
CPU-only PyTorch wheel because the current EC2 worker does not have a GPU. The worker
uses Celery's `solo` pool to keep memory usage predictable on the small EC2 instance.

---

## Production Deployment

The current production architecture is:

```
Vercel
└── Next.js frontend

AWS EC2
├── Nginx / HTTPS
├── FastAPI backend container
└── Celery worker container
    └── faster-whisper medium (CPU, INT8, 2 CPU threads)

Upstash Redis
└── Celery broker/result backend + rate limiting

S3-compatible storage
└── Meeting recordings uploaded with presigned requests
```

The frontend is deployed through Vercel. The FastAPI backend and Celery worker run
in Docker containers on EC2. The EC2 instance uses an Elastic IP as the stable
deployment target and Nginx terminates HTTPS for the backend.

GitHub Actions runs continuous integration for `main` and `develop`. For `main`,
a successful CI run triggers the CD workflow, which connects to EC2 over SSH, checks
out the exact commit tested by CI, builds the backend image, and recreates both the
API and Celery worker containers.

The deployment workflow uses repository secrets named `EC2_HOST`, `EC2_USER`, and
`EC2_SSH_PRIVATE_KEY_B64`.

---

## Environment Variables Reference

### Backend (`backend/.env`)
| Variable | Required | Default | Description |
|---|---|---|---|
| `ENVIRONMENT` | no | `development` | Toggles HSTS, cookie `secure`/`samesite`, etc. |
| `JWT_SECRET_KEY` | **yes** | — | Secret used to sign JWTs |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | *yes* | — | Google OAuth credentials |
| `GOOGLE_REDIRECT_URI` | no | `http://localhost:3000/api/auth/callback/google` | OAuth redirect |
| `DATABASE_URL` | **yes** | — | e.g. `postgresql+psycopg://postgres:<pw>@<host>:5432/postgres` |
| `REDIS_URL` | **yes** | — | e.g. `rediss://default:<token>@<host>:6379` (TLS) |
| `LLM_PROVIDER` | no | `groq` | `groq` or `ollama` |
| `LLM_API_KEY` | *yes* (groq) | — | Groq API key |
| `LLM_MODEL` | no | `openai/gpt-oss-20b` | Groq model id |
| `OLLAMA_BASE_URL` / `OLLAMA_MODEL` | — | `http://localhost:11434` / `llama3.1` | When provider is `ollama` |
| `S3_BUCKET_NAME` | **yes** | — | S3 bucket |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | **yes** | — | S3 credentials |
| `AWS_REGION` | no | `us-east-1` | S3 region |
| `S3_ENDPOINT_URL` | no | — | For non-AWS S3 (Supabase, MinIO) |
| `MAX_UPLOAD_SIZE_MB` | no | `500` | Audio size cap |
| `MAX_VIDEO_UPLOAD_SIZE_MB` | no | `2048` | Video size cap |
| `CORS_ORIGINS` | no | `["http://localhost:3000"]` | Allowed frontend origins |
| `SENTRY_DSN` | no | — | Error tracking |

### Frontend (`frontend/.env.local`)
| Variable | Description |
|---|---|
| `NEXT_PUBLIC_API_URL` | Backend base URL, e.g. `http://localhost:8000` |
| `NEXT_PUBLIC_GOOGLE_CLIENT_ID` | Google OAuth client ID for sign-in |

> ⚠️ `.env` files are git-ignored and must never be committed. Only the
> documented example placeholders should be shared.

---

## Database Migrations

Migrations live in `backend/alembic/versions/` and are applied with Alembic.
Current revisions in order:

1. `b3ad46caea01` — initial schema (users, workspaces, members, meetings, transcript chunks)
2. `7e9f6f8ab7d9` — add `action_items` table
3. `a1b2c3d4e5f6` — add video upload columns
4. `c2d3e4f5a6b7` — add `refresh_token_families` table
5. `e9e4cc5cf7c1` — add `chat_sessions` + `chat_messages`

Useful commands:

```bash
cd backend
alembic upgrade head                            # apply all migrations
alembic downgrade -1                            # roll back one revision
alembic revision --autogenerate -m "describe"   # create a new migration
```

---

## Testing

### Backend (pytest)
The backend has a pytest suite covering auth, auth security, workspace
membership / IDOR, record access control, meetings, and chat/RAG. It runs against
isolated test infrastructure (`docker-compose.test.yml`: pgvector on port
`5433`, Redis on port `6380`) so it never touches real Supabase/Upstash.

```bash
cd backend
docker compose -f docker-compose.test.yml up -d
python -m pytest -q                              # full suite
python -m pytest tests/test_auth.py -q -k "rate_limit"   # targeted
```

A quick sanity compile:

```bash
python -m compileall app
```

### Frontend (TypeScript + ESLint + production build)

```bash
cd frontend
npx tsc --noEmit        # type check
npm run lint            # eslint
npm run build           # production build
```

---

## Comments & Code Style Policy

To keep the codebase clean and docs-in-code minimal, source files generally use
short purpose comments where they improve maintainability. Tooling directives and
Python docstrings are retained when required:

- **Directive comments** required for tooling to work correctly:
  `# noqa: ...` (Python lint suppressions), `eslint-disable` / `eslint-enable`,
  `@ts-ignore` / `@ts-nocheck` / `@ts-expect-error`, `@jsxImportSource`,
  `@vite-ignore`, and `/// <reference>` triple-slash references.
- **Python docstrings** (module/function/class docstrings) — these are kept
  because (a) they are strings, not comments, and (b) FastAPI surfaces endpoint
  docstrings in the OpenAPI `/docs` UI.
- **Generated files** such as `frontend/next-env.d.ts` are left untouched.

Example — backend:

```python
# Authentication routes: signup, login, Google OAuth, refresh-token rotation, logout, and current user.
```

Example — frontend (client component, directive stays first):

```tsx
"use client";
// Dashboard home page.
```

---

## Status & Roadmap

**Current status:** the application is deployed and operational on its main happy
path: authentication, audio/video uploads, asynchronous transcription, embeddings,
AI summaries/action items, multi-meeting RAG chat with sources, and the dashboard UI.
Backend pytest checks and frontend type/lint/build checks are part of CI. Production
deployment is handled by GitHub Actions → EC2, with Vercel serving the frontend.

Ideas for future work (not yet implemented):
- Workspace management UI (create/invite members, role management).
- Streaming chat responses.
- Editing/regenerating meeting summaries.
- Per-meeting chat scoping + persistent conversation threads in the UI.
- More LLM providers and configurable chunking/retrieval tuning.
- Workspace administration and collaboration features.

---

*Documentation generated from the MeetMind codebase. See the file-header comments
in each source file for a one-line description of that file's purpose.*




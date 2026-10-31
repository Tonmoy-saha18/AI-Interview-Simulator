# AI Interview Simulator — Backend Documentation

## Purpose

The **AI Interview Simulator Backend** is an API service that powers an AI-driven interview experience. It:

- Runs an **interview workflow** (generate questions → evaluate answers → optional follow-ups → final feedback) using a LangGraph state machine and OpenAI.
- Supports an **HR workflow**: upload candidate CVs, generate secure one-time interview links, send email invitations, and store results in a database.

Candidates can either start an interview directly via the API or use a link sent by HR; in both cases they answer questions and receive structured feedback. HR can view all created interviews and their results.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **API** | FastAPI |
| **Workflow** | LangGraph (state machine) |
| **LLM** | LangChain + OpenAI (e.g. GPT-4o-mini) |
| **Database** | PostgreSQL (async via SQLAlchemy + asyncpg) |
| **Migrations** | Alembic |
| **Runtime** | Python 3.10+ (Uvicorn) |

---

## Features

### 1. Interview Flow (Candidate-Facing)

- **Start interview** — Provide role, level (junior/mid/senior/…), number of questions, and optional candidate profile. The system returns the first question and a `session_id`.
- **Submit answers** — For each question, the candidate submits an answer (with optional time taken / time expired). The backend evaluates the answer and returns the next question or moves to follow-ups.
- **Follow-up questions** — The model can ask follow-up questions when the score is low or when it suggests a follow-up; these are nested in the Q&A history.
- **Difficulty progression** — Questions progress (e.g. easy → medium → hard) based on role and question count.
- **Time limits** — Per-question time limits by difficulty (e.g. 2 / 5 / 10 minutes for easy / medium / hard).
- **Final feedback** — At the end, the candidate receives an overall summary, multi-dimensional scores (technical depth, communication, problem-solving), strengths, improvements, and question-by-question analysis.

### 2. HR Workflow

- **Create interview from CV** — HR uploads a PDF/DOCX CV and provides candidate email, name, role, level, number of questions, and link expiry. The backend:
  - Parses the CV and extracts structured data (skills, experience, education, etc.) using the LLM.
  - Creates a secure token and stores an interview link in the database.
  - Sends an email to the candidate with a link to the **frontend** (configurable via `FRONTEND_URL`).
  - Returns the interview link and metadata.
- **List interviews** — List all interviews created by an HR user (by `hr_email`).
- **Get interview details** — Fetch a single interview’s details (link, status, expiry, etc.), authorised by `hr_email`.
- **Get interview results** — After the candidate completes the interview, HR can fetch full results (scores, feedback, Q&A history, total time) for that interview, authorised by `hr_email`.

### 3. Token-Based Candidate Access

- **Access by link** — Candidate opens a link like `{FRONTEND_URL}/interview/{token}`. The frontend calls `GET /interview/{token}`. The backend:
  - Validates the token and expiry.
  - Marks the link as “in progress” and creates a new interview session using the CV-derived profile (role, level, question count).
  - Returns the first question so the candidate can continue in the app.

### 4. CV Processing

- **Supported formats** — PDF, DOCX, DOC (up to a configurable size, default 10 MB).
- **Extraction** — Text is extracted (pdfplumber / PyPDF2 for PDF, python-docx for DOCX), then an LLM extracts structured fields: name, email, skills, experience, education, summary, etc.
- **Usage** — The extracted summary is used as candidate context for question generation and evaluation.

### 5. Result Storage

- When an interview started via an HR link is completed, the backend stores:
  - Final feedback, overall score, full Q&A history (including follow-ups), and total time.
- The corresponding interview link is marked **completed** so it cannot be reused.

### 6. Email Notifications

- Optional SMTP integration to send interview invitation emails to candidates (link, role, expiry). Configured via `SMTP_*` environment variables.

---

## API Overview

| Method | Path | Description |
|--------|------|-------------|
| **Interview (candidate / general)** | | |
| POST | `/interviews` | Start a new interview; returns first question and `session_id`. |
| POST | `/interviews/{session_id}/answer` | Submit answer; returns next question or completion. |
| GET | `/interviews/{session_id}` | Get current session state. |
| DELETE | `/interviews/{session_id}` | End and remove session. |
| GET | `/interview/{token}` | Access interview via HR-generated link; validates token and returns first question. |
| **HR** | | |
| POST | `/hr/interviews/create` | Upload CV (multipart), create link, send email; returns link details. |
| GET | `/hr/interviews?hr_email=...` | List interviews for an HR email. |
| GET | `/hr/interviews/{id}?hr_email=...` | Get interview details. |
| GET | `/hr/interviews/{id}/results?hr_email=...` | Get interview results. |

- **OpenAPI docs**: `GET /docs` (Swagger UI), `GET /openapi.json`.

---

## Project Structure

```
AI-Interview-Simulator-Backend/
├── src/ai_interview_bot/
│   ├── api.py           # FastAPI app, all HTTP endpoints, session manager
│   ├── graph.py         # LangGraph workflow (nodes, edges, interrupts)
│   ├── nodes.py         # Question generation, evaluation, follow-up, feedback
│   ├── state.py         # Interview state schema
│   ├── stream_utils.py  # Helpers for LangGraph stream handling
│   ├── config.py        # Prompts and LLM config
│   ├── database.py      # Async SQLAlchemy engine and session
│   ├── models.py        # SQLAlchemy models (InterviewLink, InterviewResult)
│   ├── link_service.py  # Create/validate interview links, mark completed
│   ├── cv_parser.py     # CV file parsing and LLM extraction
│   ├── email_service.py # SMTP invitation emails
│   └── cli.py           # Optional CLI for running an interview in the terminal
├── alembic/             # Database migrations
├── docker/              # Docker entrypoint (migrations + uvicorn)
├── pyproject.toml       # Dependencies and package config
├── Dockerfile           # Container image for the API
├── docker-compose.yml   # API + PostgreSQL
├── SETUP_GUIDE.md       # Step-by-step setup (Docker and local)
└── PROJECT_DOCUMENTATION.md  # This file
```

---

## Configuration

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | Required for LLM calls. |
| `DATABASE_URL` | PostgreSQL connection (e.g. `postgresql+asyncpg://user:pass@host/db`). Set automatically in Docker Compose. |
| `FRONTEND_URL` | Base URL of the frontend app; used for interview links so candidates open the app, not the API (e.g. `http://localhost:8080`). |
| `BASE_URL` | Fallback for link generation if `FRONTEND_URL` is not set. |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL` | Optional; for sending invitation emails. |
| `AI_INTERVIEW_ALLOW_ORIGINS` | CORS origins (default `*`). |
| `MAX_CV_FILE_SIZE_MB` | Max CV upload size in MB (default 10). |
| `DEFAULT_LINK_EXPIRY_DAYS` | Default link validity in days (e.g. 7). |

See `.env.example` and `SETUP_GUIDE.md` for full examples.

---

## Running the Backend

- **Docker (recommended):** `docker compose up --build` — starts PostgreSQL and the API; migrations run on startup. API at `http://localhost:8000`.
- **Local:** Install deps (`uv pip install -e .[dev]`), set `DATABASE_URL` and `OPENAI_API_KEY`, run `alembic upgrade head`, then `uvicorn ai_interview_bot.api:app --reload`.

For detailed steps, see **SETUP_GUIDE.md**.

---

## Summary

The backend provides a full **AI interview pipeline** (questions, evaluation, follow-ups, feedback) and an **HR pipeline** (CV upload, secure links, email invites, result storage). It is designed to be used with a frontend that calls these APIs and optionally with the CLI for quick testing.

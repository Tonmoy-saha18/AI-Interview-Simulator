# AI Interview Bot

An interactive interview simulator powered by [LangGraph](https://github.com/langchain-ai/langgraph). The workflow generates interview questions, evaluates the candidate's answers, and provides summarised feedback when the session ends.

## Features

- Question generation node adapts upcoming questions based on role, seniority, and prior answers.
- Answer evaluation node scores each response and highlights strengths, weaknesses, and follow-up recommendations.
- Feedback node produces a closing report with actionable advice for the candidate.
- FastAPI HTTP service exposes the workflow for frontend or third-party integrations.
- Command-line interface for quick local runs and experimentation.
- **HR Workflow**: Upload candidate CVs, generate secure interview links with expiry, and send email invitations.
- **CV Processing**: AI-powered extraction of structured data from PDF and DOCX resumes.
- **Link Management**: Secure token-based interview links with configurable expiry times.
- **Result Storage**: Automatic storage of interview results in PostgreSQL database.

## Project Structure

```
ai-interview-bot/
  pyproject.toml                # Project metadata and dependencies
  alembic/                      # Database migrations
    versions/                   # Migration files
  uploads/                      # Uploaded CV files
    cvs/
  src/
    ai_interview_bot/
      __init__.py
      api.py                    # FastAPI application (includes HR and candidate endpoints)
      cli.py                    # Command-line driver
      config.py                 # Prompt templates and settings
      graph.py                  # LangGraph workflow definition
      nodes.py                  # Node implementations
      state.py                  # Typed state helpers
      stream_utils.py           # LangGraph stream helpers
      database.py               # Database connection and session management
      models.py                 # SQLAlchemy database models
      cv_parser.py              # CV parsing and AI extraction service
      link_service.py           # Interview link generation and validation
      email_service.py          # Email sending service
  tests/
    test_routing.py             # Example unit test
```

## Getting Started

### Quick start with Docker (no Python/PostgreSQL install needed)

1. Create a `.env` file in the project root with at least:
   ```env
   OPENAI_API_KEY=your_openai_api_key_here
   ```
2. From the project root run:
   ```bash
   docker compose up --build
   ```
3. Open **http://localhost:8000**. The API and PostgreSQL run in containers; migrations run on startup. See [SETUP_GUIDE.md](SETUP_GUIDE.md) for more options (e.g. SMTP).

### Local development (Python + PostgreSQL)

1. **Install dependencies**

   ```bash
   uv pip install -e .[dev]
   ```

2. **Set up PostgreSQL database**

   Create a PostgreSQL database for storing interview links and results:

   ```bash
   createdb ai_interview_db
   ```

   Or using psql:
   ```sql
   CREATE DATABASE ai_interview_db;
   ```

3. **Run database migrations**

   ```bash
   alembic upgrade head
   ```

   This will create the necessary tables (`interview_links` and `interview_results`).

4. **Configure environment variables**

   Copy `.env.example` to `.env` and configure the following:

   ```bash
   cp .env.example .env
   ```

   Required variables:
   - `OPENAI_API_KEY` - Your OpenAI API key
   - `DATABASE_URL` - PostgreSQL connection string (e.g., `postgresql+asyncpg://user:password@localhost/ai_interview_db`)
   - `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL` - For sending interview invitation emails
   - `BASE_URL` - Base URL for generating interview links (e.g., `http://localhost:8000`)

   Optional variables:
   - `DEFAULT_LINK_EXPIRY_DAYS` - Default expiry for interview links (default: 7)
   - `MAX_CV_FILE_SIZE_MB` - Maximum CV file size in MB (default: 10)

5. **Run the CLI interview**

   ```bash
   python -m ai_interview_bot.cli --role "Machine Learning Engineer" --level "Senior" --questions 3
   ```

   The bot asks questions one at a time, evaluates each answer, and prints a feedback summary when finished.

## Run the HTTP API

The FastAPI app wraps the same LangGraph workflow with session management that is easier to consume from a frontend.

```bash
uvicorn ai_interview_bot.api:app --reload
```

### Interview Endpoints (Candidate/General)

- `POST /interviews` – start a session. Returns the first question alongside a `session_id`.
- `POST /interviews/{session_id}/answer` – submit the candidate's answer for evaluation. Returns the updated state, including the next question (or final feedback).
- `GET /interviews/{session_id}` – fetch the latest state (useful for polling dashboards).
- `DELETE /interviews/{session_id}` – dispose of cached session state once you've stored the results elsewhere.
- `GET /interview/{token}` – access interview via secure token link (for candidates).

### HR Endpoints

- `POST /hr/interviews/create` – upload CV, create interview link, and send email invitation to candidate.
- `GET /hr/interviews?hr_email={email}` – list all interviews created by an HR user.
- `GET /hr/interviews/{interview_id}?hr_email={email}` – get interview details.
- `GET /hr/interviews/{interview_id}/results?hr_email={email}` – get interview results.

### Example: Create Interview from CV (HR)

```bash
curl -X POST http://localhost:8000/hr/interviews/create \
  -F "hr_email=hr@example.com" \
  -F "candidate_email=candidate@example.com" \
  -F "candidate_name=John Doe" \
  -F "role=Machine Learning Engineer" \
  -F "level=Senior" \
  -F "questions=5" \
  -F "expires_in_days=7" \
  -F "cv_file=@/path/to/resume.pdf"
```

This will:
1. Parse the CV and extract structured information
2. Generate a secure interview link
3. Send an email invitation to the candidate
4. Return the interview link details

### Example: Start Interview (Candidate/General)

```bash
curl -X POST http://localhost:8000/interviews \
  -H "Content-Type: application/json" \
  -d '{
    "role": "Machine Learning Engineer",
    "level": "Senior",
    "questions": 3,
    "candidate_profile": "10 years of production ML experience."
  }'
```

### Example: Access Interview via Link

```bash
curl http://localhost:8000/interview/{token}
```

### Example: Get Interview Results (HR)

```bash
curl "http://localhost:8000/hr/interviews/{interview_id}/results?hr_email=hr@example.com"
```

To restrict CORS when deploying alongside a frontend, set `AI_INTERVIEW_ALLOW_ORIGINS` (defaults to `*`).

## Customisation

- Adjust prompt templates in `src/ai_interview_bot/config.py` to tweak tone, scoring, or feedback structure.
- Swap the default `ChatOpenAI` model for any LangChain-compatible chat model in `src/ai_interview_bot/graph.py`.
- Extend the FastAPI behaviour (serialisation, session lifetime, routing) in `src/ai_interview_bot/api.py`.
- Add new nodes or edges in `src/ai_interview_bot/graph.py` to experiment with richer interview flows.

## Testing

Run the sample test suite:

```bash
pytest
```

## License

MIT License. See `LICENSE` for details.

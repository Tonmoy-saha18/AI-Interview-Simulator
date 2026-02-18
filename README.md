# AI Interview Bot

An interactive interview simulator powered by [LangGraph](https://github.com/langchain-ai/langgraph). The workflow generates interview questions, evaluates the candidate's answers, and provides summarised feedback when the session ends.

## Features

- Question generation node adapts upcoming questions based on role, seniority, and prior answers.
- Answer evaluation node scores each response and highlights strengths, weaknesses, and follow-up recommendations.
- Feedback node produces a closing report with actionable advice for the candidate.
- FastAPI HTTP service exposes the workflow for frontend or third-party integrations.
- Command-line interface for quick local runs and experimentation.

## Project Structure

```
ai-interview-bot/
  pyproject.toml                # Project metadata and dependencies
  src/
    ai_interview_bot/
      __init__.py
      api.py                    # FastAPI application
      cli.py                    # Command-line driver
      config.py                 # Prompt templates and settings
      graph.py                  # LangGraph workflow definition
      nodes.py                  # Node implementations
      state.py                  # Typed state helpers
      stream_utils.py           # LangGraph stream helpers
  tests/
    test_routing.py             # Example unit test
```

## Getting Started

1. **Install dependencies**

   ```bash
   uv pip install -e .[dev]
   ```

2. **Configure environment variables**

   Copy `.env.example` to `.env` and set an OpenAI-compatible API key.

   ```bash
   cp .env.example .env
   ```

   The workflow expects `OPENAI_API_KEY` (or another key supported by your chosen LangChain-compatible provider).

3. **Run the CLI interview**

   ```bash
   python -m ai_interview_bot.cli --role "Machine Learning Engineer" --level "Senior" --questions 3
   ```

   The bot asks questions one at a time, evaluates each answer, and prints a feedback summary when finished.

## Run the HTTP API

The FastAPI app wraps the same LangGraph workflow with session management that is easier to consume from a frontend.

```bash
uvicorn ai_interview_bot.api:app --reload
```

Key endpoints:

- `POST /interviews` – start a session. Returns the first question alongside a `session_id`.
- `POST /interviews/{session_id}/answer` – submit the candidate's answer for evaluation. Returns the updated state, including the next question (or final feedback).
- `GET /interviews/{session_id}` – fetch the latest state (useful for polling dashboards).
- `DELETE /interviews/{session_id}` – dispose of cached session state once you've stored the results elsewhere.

Example start request:

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

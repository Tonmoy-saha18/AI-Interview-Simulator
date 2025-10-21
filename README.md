# AI Interview Bot

An interactive interview simulator that uses [LangGraph](https://github.com/langchain-ai/langgraph) nodes to conduct a structured technical interview. The bot generates questions, evaluates the candidate's answers, and provides summarised feedback upon completion.

## Features

- **Question generation node** – adapts upcoming questions based on role, seniority, and prior answers.
- **Answer evaluation node** – scores each response and highlights strengths, weaknesses, and follow-up recommendations.
- **Feedback node** – creates a closing report with actionable advice for the candidate.
- Reusable LangGraph workflow that can be embedded in other applications or run as a CLI session.

## Project Structure

```
ai-interview-bot
├── pyproject.toml         # Project metadata and dependencies
├── src/
│   └── ai_interview_bot/
│       ├── __init__.py
│       ├── cli.py         # Command-line interface driver
│       ├── config.py      # Settings and prompt templates
│       ├── graph.py       # LangGraph workflow definition
│       ├── nodes.py       # Node implementations
│       └── state.py       # Shared state typing helpers
└── tests/
    └── test_routing.py    # Example unit test demonstrating routing logic
```

## Getting Started

1. **Install dependencies**

   ```bash
   pip install -e .[dev]
   ```

2. **Configure environment variables**

   Copy `.env.example` to `.env` and set an OpenAI-compatible API key:

   ```bash
   cp .env.example .env
   ```

   The CLI expects `OPENAI_API_KEY` (or another key supported by your chosen LangChain-compatible provider).

3. **Run the interactive interview**

   ```bash
   python -m ai_interview_bot.cli --role "Machine Learning Engineer" --level "Senior" --questions 3
   ```

   The workflow will start, ask you questions one at a time, evaluate your answers, and end with a detailed feedback summary.

## Customisation

- Edit prompt templates in `src/ai_interview_bot/config.py` to adjust tone, scoring rubric, or feedback style.
- Swap the default `ChatOpenAI` model for any LangChain-compatible chat model (e.g., Azure OpenAI, Anthropic) by modifying `src/ai_interview_bot/graph.py`.
- Extend the workflow by adding additional nodes (e.g., follow-up probing questions) and wiring them into the graph's routing logic.

## Testing

Run the sample test suite:

```bash
pytest
```

This project includes a lightweight routing test; you can add behavioural tests around your chosen LLM provider and prompts.

## License

MIT License. See `LICENSE` for details.

# AI Interview Simulator - Project Analysis & LangGraph Structure

## Project Overview

This is an **AI Interview Simulator** built with **LangGraph** that conducts interactive interviews by:
1. Generating adaptive interview questions
2. Evaluating candidate answers
3. Providing comprehensive feedback

## LangGraph Architecture

### Graph Structure

```
┌─────────────────────┐
│   START (Entry)     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ generate_question   │ ◄───┐
│  (QuestionNode)     │     │
└──────────┬──────────┘     │
           │                │
           │ (always)       │
           ▼                │
┌─────────────────────┐     │
│ evaluate_answer     │     │
│ (EvaluationNode)    │     │
└──────────┬──────────┘     │
           │                │
           │ (conditional)  │
           ├────────────────┤
           │                │
           │ route_after_   │
           │ evaluation     │
           │                │
     ┌─────┴─────┐          │
     │           │          │
     ▼           ▼          │
"ask_next"   "finish"      │
     │           │          │
     │           ▼          │
     │   ┌───────────────┐  │
     │   │generate_      │  │
     │   │feedback       │  │
     │   │(FeedbackNode) │  │
     │   └───────┬───────┘  │
     │           │          │
     └───────────┴──────────┘
                 │
                 ▼
           ┌─────────┐
           │   END   │
           └─────────┘
```

### Nodes

1. **generate_question** (QuestionNode)
   - **Purpose**: Generates the next interview question
   - **Input**: InterviewState (role, level, candidate_profile, qa_history)
   - **Output**: Updates `current_question` and `question_index`
   - **Adaptive**: Questions adapt based on previous Q&A history

2. **evaluate_answer** (EvaluationNode)
   - **Purpose**: Evaluates the candidate's answer
   - **Input**: InterviewState (current_question, answer, role, candidate_profile)
   - **Output**: Updates `evaluation`, `qa_history`, clears `answer`
   - **Returns**: Structured evaluation with score (1-5), reasoning, strengths, improvements

3. **generate_feedback** (FeedbackNode)
   - **Purpose**: Generates final feedback summary
   - **Input**: InterviewState (qa_history, role, level)
   - **Output**: Updates `feedback` field
   - **Runs**: Only after all questions are answered

### Edges

- **Entry Point**: `generate_question`
- **Direct Edge**: `generate_question` → `evaluate_answer` (always)
- **Conditional Edge**: `evaluate_answer` → `route_after_evaluation()`
  - If `asked < question_limit`: route to `"ask_next"` → `generate_question`
  - If `asked >= question_limit`: route to `"finish"` → `generate_feedback`
- **Final Edge**: `generate_feedback` → `END`

### State Management

**InterviewState** (TypedDict) contains:
- `candidate_profile`: str - Candidate background info
- `role`: str - Job role being interviewed for
- `level`: str - Seniority level (junior/mid/senior)
- `current_question`: str - Current question text
- `question_index`: int - Current question number
- `question_limit`: int - Maximum questions (default: 3)
- `answer`: str - Candidate's current answer
- `evaluation`: EvaluationBreakdown - Latest evaluation
- `qa_history`: List[QARecord] - All Q&A pairs with evaluations
- `feedback`: str - Final feedback summary

### Routing Logic

The `route_after_evaluation()` function determines the next step:
- Counts questions in `qa_history`
- Compares against `question_limit`
- Returns `"ask_next"` or `"finish"` accordingly

### Interrupts

When `interrupt_after_question=True`:
- Graph pauses after `generate_question` node
- Allows external systems (CLI/API) to:
  1. Display the question to the candidate
  2. Collect the answer
  3. Resume execution with the answer in state

## File Structure

```
src/ai_interview_bot/
├── __init__.py          # Package entry point
├── graph.py             # LangGraph workflow definition
├── nodes.py             # Node implementations (Question, Evaluation, Feedback)
├── routing.py           # Conditional routing logic
├── state.py             # State definitions and config
├── config.py            # Prompt templates
├── api.py               # FastAPI HTTP service
├── cli.py               # Command-line interface
└── stream_utils.py      # Streaming utilities
```

## Key Features

1. **Adaptive Question Generation**: Questions adapt based on:
   - Candidate profile
   - Previous answers
   - Role and seniority level

2. **Structured Evaluation**: Each answer gets:
   - Score (1-5)
   - Reasoning
   - Strengths list
   - Improvements list
   - Optional follow-up

3. **Session Management**: Uses LangGraph checkpoints for:
   - State persistence
   - Interrupt/resume capability
   - Multi-session support (via API)

4. **Flexible Deployment**:
   - CLI for local testing
   - FastAPI for web integration
   - Configurable LLM and prompts

## Workflow Flow

1. **Initialize**: Create graph with LLM, prompts, and checkpointer
2. **Start Interview**: Invoke with initial state (role, level, profile)
3. **Generate Question**: LLM creates question based on context
4. **[Interrupt]**: External system displays question, collects answer
5. **Evaluate Answer**: LLM evaluates answer, stores in history
6. **Route**: Check if more questions needed
7. **Loop**: Return to step 3 if more questions, else continue
8. **Generate Feedback**: LLM creates final summary
9. **End**: Return final state with feedback

## Technologies Used

- **LangGraph**: Graph-based workflow orchestration
- **LangChain**: LLM integration and prompt management
- **FastAPI**: HTTP API layer
- **Python 3.10+**: Core language






# Example Implementations - Getting Started

This document shows concrete code examples for implementing key improvements. Use these as starting points.

---

## Example 1: Question Categories

### Step 1: Update State Definition

```python
# src/ai_interview_bot/state.py

class InterviewState(TypedDict, total=False):
    """State passed between LangGraph nodes."""
    
    # ... existing fields ...
    question_category: str  # "technical", "behavioral", "system_design", "coding"
    question_type: str      # "conceptual", "practical", "scenario"
    current_topic: str      # e.g., "machine_learning", "algorithms", "leadership"
```

### Step 2: Update QuestionNode

```python
# src/ai_interview_bot/nodes.py

class QuestionNode:
    """Generates the next interview question."""
    
    def __call__(self, state: InterviewState) -> InterviewState:
        qa_history = state.get("qa_history", [])
        question_index = state.get("question_index", 0) + 1
        question_limit = state.get("question_limit", 3)
        
        if question_index > question_limit:
            return state
        
        # Determine question category based on interview phase
        question_category = self._determine_category(state, qa_history)
        question_type = self._determine_type(state, question_category)
        current_topic = self._determine_topic(state, qa_history)
        
        formatted_history = format_history(qa_history)
        prompt_inputs = {
            "level": state.get("level", "mid"),
            "role": state.get("role", "Engineer"),
            "candidate_profile": state.get("candidate_profile", ""),
            "formatted_history": formatted_history,
            "next_index": question_index,
            "question_category": question_category,
            "question_type": question_type,
            "current_topic": current_topic,
        }
        
        question_text = self._runnable.invoke(prompt_inputs)
        
        state.update({
            "current_question": question_text.strip(),
            "question_index": question_index,
            "question_category": question_category,
            "question_type": question_type,
            "current_topic": current_topic,
        })
        return state
    
    def _determine_category(self, state: InterviewState, history: List[QARecord]) -> str:
        """Determine the category for the next question."""
        # Simple strategy: alternate between technical and behavioral
        # Or use weak area analysis, interview phase, etc.
        asked = len(history)
        if asked == 0:
            return "technical"  # Start with technical
        elif asked % 2 == 0:
            return "behavioral"
        else:
            return "technical"
    
    def _determine_type(self, state: InterviewState, category: str) -> str:
        """Determine question type based on category."""
        if category == "behavioral":
            return "scenario"  # STAR method scenarios
        elif category == "technical":
            return "conceptual"  # Technical concepts
        elif category == "system_design":
            return "practical"  # Practical design problems
        return "conceptual"
    
    def _determine_topic(self, state: InterviewState, history: List[QARecord]) -> str:
        """Determine specific topic for the question."""
        role = state.get("role", "").lower()
        if "machine learning" in role or "ml" in role:
            return "machine_learning"
        elif "backend" in role:
            return "backend_systems"
        elif "frontend" in role:
            return "frontend_development"
        return "general"
```

### Step 3: Update Prompt Template

```python
# src/ai_interview_bot/config.py

question_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        (
            "You are an interviewer creating {question_category} questions for a {level} level {role} position.\n"
            "Question type: {question_type}\n"
            "Topic focus: {current_topic}\n"
            "Adapt each question using the candidate's profile and previous QA pairs.\n"
            "Ask one question at a time, ensuring variety across topics.\n"
            "Respond with the question only."
        ),
    ),
    (
        "human",
        (
            "Candidate profile:\n{candidate_profile}\n\n"
            "Previous discussion:\n{formatted_history}\n\n"
            "Next question number: {next_index}\n"
            "Generate a {question_category} {question_type} question about {current_topic}."
        ),
    ),
])
```

---

## Example 2: Multi-Dimensional Evaluation

### Step 1: Extend EvaluationBreakdown

```python
# src/ai_interview_bot/state.py

class EvaluationBreakdown(TypedDict, total=False):
    """Structured evaluation returned by the evaluation node."""
    
    # Overall score
    overall_score: int  # 1-5 (weighted average)
    
    # Dimension scores
    technical_depth: int  # 1-5
    communication: int    # 1-5
    problem_solving: int  # 1-5
    code_quality: Optional[int] = None  # 1-5 (if coding question)
    
    # Detailed feedback
    reasoning: str
    strengths: List[str]
    improvements: List[str]
    follow_up: Optional[str]
    
    # Legacy support (for backward compatibility)
    score: int  # Deprecated, use overall_score
```

### Step 2: Update Evaluation Prompt

```python
# src/ai_interview_bot/config.py

evaluation_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        (
            "You are an expert interviewer assessing responses for {role} candidates.\n"
            "Evaluate the answer across multiple dimensions:\n"
            "1. Technical Depth (1-5): Understanding of concepts, technical accuracy\n"
            "2. Communication (1-5): Clarity, structure, articulation\n"
            "3. Problem Solving (1-5): Approach, reasoning, solution quality\n"
            "4. Code Quality (1-5, if applicable): Code correctness, efficiency, best practices\n\n"
            "Return valid JSON with keys:\n"
            "- overall_score (int 1-5): Weighted average\n"
            "- technical_depth (int 1-5)\n"
            "- communication (int 1-5)\n"
            "- problem_solving (int 1-5)\n"
            "- code_quality (int 1-5, optional)\n"
            "- reasoning (str): Overall assessment\n"
            "- strengths (list[str]): What they did well\n"
            "- improvements (list[str]): Areas to improve\n"
            "- follow_up (str, optional): Suggested follow-up question"
        ),
    ),
    (
        "human",
        (
            "Question:\n{question}\n\n"
            "Answer:\n{answer}\n"
            "Candidate profile:\n{candidate_profile}"
        ),
    ),
])
```

### Step 3: Update Evaluation Parsing

```python
# src/ai_interview_bot/nodes.py

def _parse_evaluation(raw_response: Any) -> EvaluationBreakdown:
    """Parse evaluation with multi-dimensional scores."""
    if isinstance(raw_response, dict):
        data = raw_response
    else:
        text = str(raw_response).strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = {
                "overall_score": 3,
                "technical_depth": 3,
                "communication": 3,
                "problem_solving": 3,
                "reasoning": text,
                "strengths": [],
                "improvements": []
            }
    
    # Extract dimension scores
    technical_depth = _clamp_score(data.get("technical_depth", 3))
    communication = _clamp_score(data.get("communication", 3))
    problem_solving = _clamp_score(data.get("problem_solving", 3))
    code_quality = data.get("code_quality")
    if code_quality is not None:
        code_quality = _clamp_score(code_quality)
    
    # Calculate overall score (weighted average)
    weights = {"technical_depth": 0.4, "communication": 0.2, "problem_solving": 0.4}
    if code_quality is not None:
        weights = {"technical_depth": 0.3, "communication": 0.15, 
                   "problem_solving": 0.3, "code_quality": 0.25}
        overall = int(round(
            technical_depth * weights["technical_depth"] +
            communication * weights["communication"] +
            problem_solving * weights["problem_solving"] +
            code_quality * weights["code_quality"]
        ))
    else:
        overall = int(round(
            technical_depth * weights["technical_depth"] +
            communication * weights["communication"] +
            problem_solving * weights["problem_solving"]
        ))
    
    evaluation: EvaluationBreakdown = {
        "overall_score": overall,
        "technical_depth": technical_depth,
        "communication": communication,
        "problem_solving": problem_solving,
        "reasoning": data.get("reasoning", ""),
        "strengths": data.get("strengths", []),
        "improvements": data.get("improvements", []),
    }
    
    if code_quality is not None:
        evaluation["code_quality"] = code_quality
    
    # Legacy support
    evaluation["score"] = overall
    
    follow_up = data.get("follow_up")
    if follow_up:
        evaluation["follow_up"] = str(follow_up)
    
    return evaluation

def _clamp_score(score: Any) -> int:
    """Clamp score to 1-5 range."""
    try:
        score = int(score)
        return max(1, min(score, 5))
    except (ValueError, TypeError):
        return 3
```

### Step 4: Update CLI Display

```python
# src/ai_interview_bot/cli.py

if "evaluation" in payload:
    evaluation = payload["evaluation"]
    print("-" * 60)
    print(f"Overall Score: {evaluation.get('overall_score', 'N/A')}/5")
    print("\nDimension Scores:")
    print(f"  Technical Depth: {evaluation.get('technical_depth', 'N/A')}/5")
    print(f"  Communication: {evaluation.get('communication', 'N/A')}/5")
    print(f"  Problem Solving: {evaluation.get('problem_solving', 'N/A')}/5")
    if evaluation.get('code_quality'):
        print(f"  Code Quality: {evaluation.get('code_quality', 'N/A')}/5")
    # ... rest of display
```

---

## Example 3: Time Tracking

### Step 1: Add Time Fields to State

```python
# src/ai_interview_bot/state.py

class InterviewState(TypedDict, total=False):
    # ... existing fields ...
    question_time_limit: int  # seconds
    answer_start_time: Optional[str]  # ISO timestamp
    answer_time_taken: Optional[int]  # seconds
    total_time_elapsed: int  # cumulative seconds
```

### Step 2: Update QuestionNode to Set Timer

```python
# src/ai_interview_bot/nodes.py

from datetime import datetime

class QuestionNode:
    def __call__(self, state: InterviewState) -> InterviewState:
        # ... existing question generation ...
        
        # Set time limit based on question category
        category = state.get("question_category", "technical")
        time_limits = {
            "technical": 300,  # 5 minutes
            "behavioral": 180,  # 3 minutes
            "system_design": 600,  # 10 minutes
            "coding": 900,  # 15 minutes
        }
        time_limit = time_limits.get(category, 300)
        
        state.update({
            "current_question": question_text.strip(),
            "question_index": question_index,
            "question_category": question_category,
            "question_time_limit": time_limit,
            "answer_start_time": datetime.now().isoformat(),
        })
        return state
```

### Step 3: Calculate Time in EvaluationNode

```python
# src/ai_interview_bot/nodes.py

class EvaluationNode:
    def __call__(self, state: InterviewState) -> InterviewState:
        # ... existing evaluation ...
        
        # Calculate time taken
        start_time_str = state.get("answer_start_time")
        if start_time_str:
            start_time = datetime.fromisoformat(start_time_str)
            time_taken = int((datetime.now() - start_time).total_seconds())
            total_time = state.get("total_time_elapsed", 0) + time_taken
            
            state.update({
                "answer_time_taken": time_taken,
                "total_time_elapsed": total_time,
            })
        
        # ... rest of evaluation ...
```

### Step 4: Display Time in CLI

```python
# src/ai_interview_bot/cli.py

import time
from datetime import datetime

# When question is shown
if "current_question" in payload:
    question = payload["current_question"]
    time_limit = payload.get("question_time_limit", 300)
    print(f"\nQuestion {question_number}: {question}")
    print(f"Time limit: {time_limit // 60} minutes\n")
    
    # Start timer
    start_time = time.time()
    answer = input("Your answer: ").strip()
    elapsed = int(time.time() - start_time)
    
    # Warn if approaching limit
    if elapsed > time_limit * 0.8:
        print("⚠️  Warning: Approaching time limit!")
```

---

## Example 4: Follow-up Questions

### Step 1: Add Follow-up Node

```python
# src/ai_interview_bot/nodes.py

class FollowUpQuestionNode:
    """Generates follow-up questions when answer needs clarification."""
    
    def __init__(self, runnable: Runnable, prompts: PromptBundle) -> None:
        self._runnable = runnable
        self._prompts = prompts
    
    def __call__(self, state: InterviewState) -> InterviewState:
        evaluation = state.get("evaluation", {})
        follow_up_hint = evaluation.get("follow_up")
        current_question = state.get("current_question", "")
        last_answer = state.get("answer", "")
        
        if not follow_up_hint:
            return state  # No follow-up needed
        
        prompt_inputs = {
            "original_question": current_question,
            "original_answer": last_answer,
            "evaluation": evaluation.get("reasoning", ""),
            "follow_up_hint": follow_up_hint,
            "role": state.get("role", "Engineer"),
        }
        
        follow_up_question = self._runnable.invoke(prompt_inputs)
        
        state.update({
            "current_question": follow_up_question.strip(),
            "is_follow_up": True,
        })
        return state
```

### Step 2: Update Graph with Follow-up Routing

```python
# src/ai_interview_bot/graph.py

def build_interview_app(...):
    # ... existing setup ...
    
    follow_up_node = FollowUpQuestionNode(_build_question_chain(llm, prompts), prompts)
    
    graph = StateGraph(InterviewState)
    graph.add_node("generate_question", question_node)
    graph.add_node("evaluate_answer", evaluation_node)
    graph.add_node("ask_follow_up", follow_up_node)
    graph.add_node("generate_feedback", feedback_node)
    
    graph.set_entry_point("generate_question")
    graph.add_edge("generate_question", "evaluate_answer")
    
    # Route after evaluation
    graph.add_conditional_edges(
        "evaluate_answer",
        route_after_evaluation_with_followup,  # New routing function
        {
            "ask_next": "generate_question",
            "ask_follow_up": "ask_follow_up",
            "finish": "generate_feedback",
        },
    )
    
    graph.add_edge("ask_follow_up", "evaluate_answer")  # Re-evaluate after follow-up
    graph.add_edge("generate_feedback", END)
    
    # ... rest of compilation ...
```

### Step 3: Update Routing Logic

```python
# src/ai_interview_bot/routing.py

def route_after_evaluation_with_followup(state: InterviewState) -> str:
    """Route after evaluation, considering follow-ups."""
    asked = len(state.get("qa_history", []))
    limit = state.get("question_limit", 3)
    evaluation = state.get("evaluation", {})
    
    # Check if follow-up is needed (low score or incomplete answer)
    score = evaluation.get("overall_score") or evaluation.get("score", 0)
    needs_followup = score < 3 and not state.get("is_follow_up", False)
    
    if asked >= limit:
        return "finish"
    elif needs_followup:
        return "ask_follow_up"
    else:
        return "ask_next"
```

---

## Next Steps

1. **Choose one feature** from the examples above
2. **Test incrementally** - implement, test, refine
3. **Update tests** - add unit tests for new functionality
4. **Document** - update README with new features
5. **Iterate** - build on what works, refactor what doesn't

These examples provide a solid foundation. Adapt them to your specific needs and coding style!



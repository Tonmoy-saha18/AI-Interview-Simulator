# API Enhancements for Your Frontend

Based on your current FastAPI implementation, here are specific improvements you can make to better support your frontend.

---

## 🎯 Quick Wins (Easy to Add)

### 1. **Add Progress Calculation**
Enhance `InterviewStepResponse` to include progress percentage:

```python
# In api.py - Update InterviewStepResponse
class InterviewStepResponse(BaseModel):
    # ... existing fields ...
    progress: float = Field(0.0, ge=0.0, le=1.0)  # 0.0 to 1.0
    questions_answered: int = 0
    questions_remaining: int = 0
```

Update `_prepare_response`:
```python
def _prepare_response(...):
    # ... existing code ...
    questions_answered = len(qa_history)
    questions_remaining = max(0, question_limit - questions_answered)
    progress = questions_answered / question_limit if question_limit > 0 else 0.0
    
    return InterviewStepResponse(
        # ... existing fields ...
        progress=progress,
        questions_answered=questions_answered,
        questions_remaining=questions_remaining,
    )
```

**Frontend Benefit**: Progress bars, "Question X of Y" display

---

### 2. **Add Question Metadata**
Include question category and type in responses:

```python
# Update InterviewStepResponse
class InterviewStepResponse(BaseModel):
    # ... existing fields ...
    question_category: Optional[str] = None  # "technical", "behavioral", etc.
    question_type: Optional[str] = None      # "conceptual", "scenario", etc.
    difficulty: Optional[str] = None         # "easy", "medium", "hard"
```

**Frontend Benefit**: Category badges, difficulty indicators

---

### 3. **Add Time Tracking**
Include timing information:

```python
# Update InterviewStepResponse
class InterviewStepResponse(BaseModel):
    # ... existing fields ...
    time_limit: Optional[int] = None      # seconds per question
    time_elapsed: Optional[int] = None    # seconds spent on current question
    total_time_elapsed: Optional[int] = None  # total interview time
```

**Frontend Benefit**: Timer widgets, time tracking UI

---

### 4. **Enhanced Evaluation Model**
Add multi-dimensional scores:

```python
# Update EvaluationModel
class EvaluationModel(BaseModel):
    score: int  # Keep for backward compatibility
    overall_score: Optional[int] = None  # New primary score
    
    # Dimension scores
    technical_depth: Optional[int] = None
    communication: Optional[int] = None
    problem_solving: Optional[int] = None
    
    reasoning: str = ""
    strengths: List[str] = Field(default_factory=list)
    improvements: List[str] = Field(default_factory=list)
    follow_up: Optional[str] = None
```

**Frontend Benefit**: Radar charts, detailed score breakdowns

---

### 5. **Add Session Metadata Endpoint**
Create a lightweight metadata endpoint:

```python
class SessionMetadata(BaseModel):
    session_id: str
    role: str
    level: str
    status: str  # "in_progress", "completed", "paused"
    progress: float
    questions_answered: int
    questions_total: int
    average_score: Optional[float] = None
    started_at: Optional[str] = None  # ISO timestamp

@app.get("/interviews/{session_id}/metadata", response_model=SessionMetadata)
async def get_session_metadata(session_id: str):
    """Get lightweight session metadata for dashboards."""
    session = await manager.get_session(session_id)
    state = get_state_values(session.app, session.graph_config)
    
    qa_history = state.get("qa_history", [])
    scores = [q.get("evaluation", {}).get("score", 0) for q in qa_history if q.get("evaluation")]
    avg_score = sum(scores) / len(scores) if scores else None
    
    return SessionMetadata(
        session_id=session_id,
        role=state.get("role", ""),
        level=state.get("level", ""),
        status="completed" if session.finished else "in_progress",
        progress=len(qa_history) / state.get("question_limit", 1),
        questions_answered=len(qa_history),
        questions_total=state.get("question_limit", 0),
        average_score=avg_score,
    )
```

**Frontend Benefit**: Dashboard widgets, session lists

---

## 🚀 Medium Priority Enhancements

### 6. **Streaming Support (SSE)**
Add Server-Sent Events for real-time updates:

```python
from fastapi.responses import StreamingResponse
import json

@app.get("/interviews/{session_id}/stream")
async def stream_interview_updates(session_id: str):
    """Stream interview updates in real-time using SSE."""
    async def event_generator():
        session = await manager.get_session(session_id)
        
        async for event in session.app.astream(None, config=session.graph_config):
            for payload in iter_event_values(event):
                yield f"data: {json.dumps(payload)}\n\n"
            
            if "__interrupt__" in event:
                yield f"data: {json.dumps({'type': 'interrupt'})}\n\n"
        
        yield f"data: {json.dumps({'type': 'complete'})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )
```

**Frontend Usage**:
```javascript
const eventSource = new EventSource(`/interviews/${sessionId}/stream`);
eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    updateUI(data);
};
```

**Frontend Benefit**: Real-time question appearance, live updates

---

### 7. **Enhanced Answer Request**
Support richer answer submissions:

```python
# Update AnswerRequest
class AnswerRequest(BaseModel):
    answer: str = Field(..., min_length=1)
    time_taken: Optional[int] = Field(None, ge=0)  # seconds
    is_revision: bool = False
    request_hint: bool = False
```

Update `submit_answer`:
```python
@app.post("/interviews/{session_id}/answer")
async def submit_answer(session_id: str, payload: AnswerRequest):
    session = await manager.get_session(session_id)
    async with session.lock:
        if session.finished:
            raise HTTPException(...)
        
        update_data = {"answer": payload.answer.strip()}
        if payload.time_taken is not None:
            update_data["time_taken"] = payload.time_taken
        
        session.app.update_state(session.graph_config, update_data)
    
    response = await _drive_session(session_id, session)
    return response
```

**Frontend Benefit**: Time tracking, answer revision support

---

### 8. **Pagination for History**
Add pagination support:

```python
class PaginatedQARecords(BaseModel):
    items: List[QARecordModel]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_prev: bool

@app.get("/interviews/{session_id}/history")
async def get_interview_history(
    session_id: str,
    page: int = 1,
    page_size: int = 10
):
    """Get paginated interview history."""
    session = await manager.get_session(session_id)
    state = get_state_values(session.app, session.graph_config)
    qa_history = state.get("qa_history", [])
    
    total = len(qa_history)
    start = (page - 1) * page_size
    end = start + page_size
    paginated_items = qa_history[start:end]
    
    return PaginatedQARecords(
        items=_serialise_history(paginated_items),
        total=total,
        page=page,
        page_size=page_size,
        has_next=end < total,
        has_prev=page > 1,
    )
```

**Frontend Benefit**: Better handling of long interview histories

---

## 📊 Advanced Features

### 9. **WebSocket Support**
For bidirectional real-time communication:

```python
from fastapi import WebSocket, WebSocketDisconnect

@app.websocket("/interviews/{session_id}/ws")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    session = await manager.get_session(session_id)
    
    try:
        # Send updates
        async def send_updates():
            async for event in session.app.astream(None, config=session.graph_config):
                await websocket.send_json(event)
        
        # Receive answers
        async def receive_answers():
            while True:
                data = await websocket.receive_json()
                if data.get("type") == "answer":
                    session.app.update_state(
                        session.graph_config,
                        {"answer": data["answer"]}
                    )
        
        await asyncio.gather(send_updates(), receive_answers())
    except WebSocketDisconnect:
        pass
```

**Frontend Benefit**: Lower latency, bidirectional communication

---

### 10. **Interview List Endpoint**
List all user interviews:

```python
@app.get("/interviews", response_model=List[SessionMetadata])
async def list_interviews(limit: int = 10, offset: int = 0):
    """List all interview sessions."""
    # Note: Currently in-memory, you'd need persistence for this
    sessions = list(manager._sessions.values())
    total = len(sessions)
    
    paginated = sessions[offset:offset + limit]
    return [
        SessionMetadata(
            session_id=s.config.thread_id or "",
            role=s.config.role,
            level=s.config.level,
            status="completed" if s.finished else "in_progress",
            progress=len(get_state_values(s.app, s.graph_config).get("qa_history", [])) / s.config.question_limit,
            questions_answered=len(get_state_values(s.app, s.graph_config).get("qa_history", [])),
            questions_total=s.config.question_limit,
        )
        for s in paginated
    ]
```

**Frontend Benefit**: Interview history dashboard

---

## 🔧 Implementation Order

### Phase 1 (Do First - 30 minutes):
1. Add `progress`, `questions_answered`, `questions_remaining` to responses
2. Add `question_category` and `question_type` fields
3. Add session metadata endpoint

### Phase 2 (Next - 1-2 hours):
4. Add time tracking fields
5. Enhance evaluation model with dimensions
6. Add enhanced answer request with time tracking

### Phase 3 (Later - 3-4 hours):
7. Add streaming support (SSE)
8. Add pagination for history
9. Add interview list endpoint

### Phase 4 (Advanced - 1 day+):
10. WebSocket support
11. Interview analytics endpoints
12. Export functionality

---

## 📝 Quick Implementation Example

Here's a minimal enhancement you can add right now:

```python
# Add to InterviewStepResponse
class InterviewStepResponse(BaseModel):
    # ... existing fields ...
    
    # Quick additions
    progress: float = 0.0
    questions_answered: int = 0
    questions_remaining: int = 0
    question_category: Optional[str] = None

# Update _prepare_response
def _prepare_response(...):
    # ... existing code ...
    
    questions_answered = len(qa_history)
    questions_remaining = max(0, question_limit - questions_answered)
    progress = questions_answered / question_limit if question_limit > 0 else 0.0
    
    # Get category from state if available
    question_category = state_values.get("question_category")
    
    return InterviewStepResponse(
        # ... existing fields ...
        progress=progress,
        questions_answered=questions_answered,
        questions_remaining=questions_remaining,
        question_category=question_category,
    )
```

**That's it!** Your frontend can now display progress bars and category badges.

---

## 🤔 Questions for You

To provide more targeted suggestions:

1. **What frontend framework are you using?** (React, Vue, Angular, etc.)
2. **What features does your frontend currently have?** (timer, progress bar, etc.)
3. **What's missing?** What data do you need that the API doesn't provide?
4. **Are you using TypeScript?** (I can generate type definitions)
5. **Do you need real-time updates?** (streaming, WebSocket)

Let me know and I can create more specific implementations!



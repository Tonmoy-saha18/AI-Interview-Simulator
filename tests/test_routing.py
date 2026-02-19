from ai_interview_bot.graph.routing import route_after_evaluation


def test_route_after_evaluation_continues_when_below_limit():
    state = {
        "question_limit": 3,
        "qa_history": [{"question": "Q1", "answer": "A1", "evaluation": {"score": 4}}],
    }
    assert route_after_evaluation(state) == "ask_next"


def test_route_after_evaluation_finishes_when_limit_reached():
    state = {
        "question_limit": 2,
        "qa_history": [
            {"question": "Q1", "answer": "A1", "evaluation": {"score": 4}},
            {"question": "Q2", "answer": "A2", "evaluation": {"score": 3}},
        ],
    }
    assert route_after_evaluation(state) == "finish"

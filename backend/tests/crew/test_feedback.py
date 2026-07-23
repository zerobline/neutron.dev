import threading
import time

from app.crew.feedback import FeedbackRequest, WebSocketFeedbackProvider


def test_feedback_request_defaults():
    req = FeedbackRequest(phase="leading", agent="team_leader", output="text")
    assert req.phase == "leading"
    assert req.agent == "team_leader"
    assert req.output == "text"
    assert isinstance(req.event, threading.Event)
    assert req.response == {}


def test_submit_feedback_returns_true_when_pending():
    provider = WebSocketFeedbackProvider()

    result_holder = {}

    def request_in_thread():
        result_holder["result"] = provider.request_feedback("leading", "team_leader", "output", timeout=5)

    t = threading.Thread(target=request_in_thread)
    t.start()
    time.sleep(0.05)

    assert provider.has_pending is True
    success = provider.submit_feedback("approve", "looks good")
    assert success is True
    t.join()
    assert result_holder["result"] == {"action": "approve", "feedback": "looks good"}
    assert provider.has_pending is False


def test_submit_feedback_returns_false_when_no_pending():
    provider = WebSocketFeedbackProvider()
    assert provider.has_pending is False
    assert provider.submit_feedback("approve") is False


def test_request_feedback_timeout_returns_default():
    provider = WebSocketFeedbackProvider()
    result = provider.request_feedback("leading", "team_leader", "output", timeout=0.05)
    assert result == {"action": "approve", "feedback": "", "auto": True}


def test_submit_feedback_default_empty_feedback():
    provider = WebSocketFeedbackProvider()

    result_holder = {}

    def request_in_thread():
        result_holder["result"] = provider.request_feedback("leading", "team_leader", "output", timeout=5)

    t = threading.Thread(target=request_in_thread)
    t.start()
    time.sleep(0.05)

    provider.submit_feedback("reject")
    t.join()
    assert result_holder["result"] == {"action": "reject", "feedback": ""}

import asyncio
import threading
from dataclasses import dataclass, field


@dataclass
class FeedbackRequest:
    phase: str
    agent: str
    output: str
    event: threading.Event = field(default_factory=threading.Event)
    response: dict = field(default_factory=dict)


class WebSocketFeedbackProvider:
    """Bridges synchronous CrewAI flow with async WebSocket feedback."""

    def __init__(self):
        self._pending: FeedbackRequest | None = None
        self._lock = threading.Lock()

    def request_feedback(self, phase: str, agent: str, output: str, timeout: float = 600) -> dict:
        req = FeedbackRequest(phase=phase, agent=agent, output=output)
        with self._lock:
            self._pending = req
        req.event.wait(timeout=timeout)
        with self._lock:
            self._pending = None
        if not req.response:
            return {"action": "approve", "feedback": "", "auto": True}
        return req.response

    def submit_feedback(self, action: str, feedback: str = "") -> bool:
        with self._lock:
            req = self._pending
        if not req:
            return False
        req.response = {"action": action, "feedback": feedback}
        req.event.set()
        return True

    @property
    def has_pending(self) -> bool:
        with self._lock:
            return self._pending is not None

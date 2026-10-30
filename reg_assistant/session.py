"""Bounded ephemeral conversation state. User answers are never source evidence."""
from dataclasses import asdict, dataclass
import time
import uuid


@dataclass
class ConversationState:
    topic_question: str = ""
    active_intent: str = ""
    retailer: str = "none"
    pending_clarification: str = ""
    clarification_attempts: int = 0
    turns: int = 0

    def context(self):
        return asdict(self)

    def advance(self, question, decision):
        intent = decision.get("intent", decision.get("action", "clarify"))
        dependent = decision.get("relation") == "followup"
        if decision["action"] in {"clarify", "recovery"}:
            self.clarification_attempts += 1
            self.pending_clarification = "choose_task" if decision["action"] == "recovery" else decision.get("reason", "ambiguous")
            if decision["action"] == "clarify" and decision.get("reason") == "unsupported_retailer":
                self.topic_question = question[:2000] if not dependent or not self.topic_question else self.topic_question
                self.active_intent = "policy"
                self.retailer = "other"
            elif decision["action"] == "recovery" or not dependent:
                self.topic_question = ""
                self.active_intent = ""
                self.retailer = decision.get("retailer", "none") if decision["action"] == "clarify" else "none"
        else:
            if intent != "greeting":
                if not dependent or not self.topic_question:
                    self.topic_question = question[:2000]
                    self.retailer = decision.get("retailer", "none")
                elif decision.get("retailer", "none") != "none":
                    self.retailer = decision["retailer"]
                self.active_intent = intent
            self.clarification_attempts = 0
            self.pending_clarification = ""
        self.turns += 1


class SessionStore:
    """Called under the API's request lock. TTL and count bound retained memory."""
    def __init__(self, limit=128, ttl_seconds=3600, clock=time.monotonic):
        self.limit, self.ttl, self.clock = limit, ttl_seconds, clock
        self._sessions = {}

    def get(self, identifier=None):
        now = self.clock()
        self._sessions = {key: value for key, value in self._sessions.items() if now - value[1] < self.ttl}
        if identifier is not None:
            if identifier not in self._sessions:
                raise KeyError("Conversation expired or server restarted. Start a new research conversation.")
            state = self._sessions[identifier][0]
        else:
            if len(self._sessions) >= self.limit:
                oldest = min(self._sessions, key=lambda key: self._sessions[key][1])
                del self._sessions[oldest]
            identifier, state = str(uuid.uuid4()), ConversationState()
        self._sessions[identifier] = state, now
        return identifier, state

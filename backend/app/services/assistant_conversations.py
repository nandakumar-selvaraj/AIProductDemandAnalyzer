"""Bounded process-local conversations; session token is a bearer ownership capability."""

import time
from dataclasses import dataclass, field
from threading import Lock
from uuid import UUID, uuid4

from app.schemas.assistant import AssistantContext, Intent


class AssistantError(Exception):
    def __init__(self, code: str, message: str, status: int = 422):
        super().__init__(message)
        self.code, self.status = code, status


@dataclass
class Conversation:
    owner: UUID
    context: AssistantContext = field(default_factory=AssistantContext)
    history: list[dict[str, str]] = field(default_factory=list)
    intent: Intent = "general"
    touched: float = field(default_factory=time.monotonic)
    busy: bool = False


class ConversationStore:
    def __init__(self):
        self.lock = Lock()
        self.rows: dict[UUID, Conversation] = {}

    def begin(self, owner: UUID, conversation_id: UUID | None, ttl: int, capacity: int):
        with self.lock:
            now = time.monotonic()
            self.rows = {
                key: row for key, row in self.rows.items() if row.busy or now - row.touched < ttl
            }
            if conversation_id:
                row = self.rows.get(conversation_id)
                if row is None or row.owner != owner:
                    raise AssistantError(
                        "conversation_not_found",
                        "Conversation expired or is unavailable to this session. Start a new chat.",
                        404,
                    )
                if row.busy:
                    raise AssistantError(
                        "conversation_busy", "This conversation already has a pending request.", 409
                    )
            else:
                if len(self.rows) >= capacity:
                    idle = [(key, row) for key, row in self.rows.items() if not row.busy]
                    if not idle:
                        raise AssistantError(
                            "assistant_busy", "The assistant is busy. Try again later.", 429
                        )
                    del self.rows[min(idle, key=lambda pair: pair[1].touched)[0]]
                conversation_id = uuid4()
                row = self.rows[conversation_id] = Conversation(owner=owner)
            row.busy, row.touched = True, now
            return conversation_id, row

    def finish(
        self,
        conversation_id: UUID,
        context: AssistantContext,
        intent: Intent,
        message: str,
        answer: str,
        history_limit: int,
    ):
        with self.lock:
            row = self.rows[conversation_id]
            row.context, row.intent = context, intent
            row.history = (
                row.history
                + [
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": answer[:4000]},
                ]
            )[-history_limit:]
            row.touched, row.busy = time.monotonic(), False

    def abort(self, conversation_id: UUID):
        with self.lock:
            if conversation_id in self.rows:
                self.rows[conversation_id].busy = False


conversations = ConversationStore()

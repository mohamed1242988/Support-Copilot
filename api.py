import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from fastapi.responses import FileResponse

from ai_entry import run_agent
from services.sync import incremental_sync

app = FastAPI(title="Support Copilot API")

FEEDBACK_PATH = Path(__file__).resolve().parent / "storage" / "feedback.json"
FEEDBACK_LOCK = threading.Lock()


@app.get("/stats")
def stats():
    conn = sqlite3.connect("storage/support_copilot.db")

    tickets = conn.execute(
        "SELECT COUNT(*) FROM Freshdesk_tickets"
    ).fetchone()[0]

    customers = conn.execute(
        "SELECT COUNT(*) FROM customers"
    ).fetchone()[0]

    last_sync = conn.execute(
        "SELECT value FROM sync_state WHERE key = 'last_sync'"
    ).fetchone()

    conn.close()

    return {
        "tickets": tickets,
        "customers": customers,
        "last_sync": last_sync[0] if last_sync else None
    }

@app.get("/")
def home():
    return FileResponse("static/index.html")


class ChatRequest(BaseModel):
    message: str
    history: list = []


class FeedbackRequest(BaseModel):
    rating: str
    comment: str = ""
    conversation_id: str
    conversation_title: str = "New conversation"
    user_message: str = ""
    assistant_response: str
    conversation_history: list = Field(default_factory=list)


@app.post("/feedback")
def submit_feedback(request: FeedbackRequest):
    """Append response feedback to a server-side JSON collection."""
    if request.rating not in {"helpful", "needs_improvement", "not_helpful"}:
        raise HTTPException(status_code=400, detail="Invalid feedback rating.")

    conversation_history = [
        {
            "role": message.get("role", ""),
            "content": str(message.get("content", "")).splitlines() or [""]
        }
        for message in request.conversation_history
    ]

    record = {
        "feedback_id": str(uuid.uuid4()),
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "rating": request.rating,
        "feedback_comment": request.comment,
        "conversation_id": request.conversation_id,
        "conversation_title": request.conversation_title,
        "related_user_message": request.user_message,
        "feedback_on_response": request.assistant_response.splitlines() or [""],
        "conversation_history": conversation_history,
    }

    FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)

    with FEEDBACK_LOCK:
        try:
            if FEEDBACK_PATH.exists():
                with FEEDBACK_PATH.open("r", encoding="utf-8") as file:
                    feedback = json.load(file)
                if not isinstance(feedback, list):
                    feedback = []
            else:
                feedback = []
        except (json.JSONDecodeError, OSError):
            feedback = []

        feedback.append(record)
        temporary_path = FEEDBACK_PATH.with_suffix(".tmp")
        with temporary_path.open("w", encoding="utf-8") as file:
            json.dump(feedback, file, ensure_ascii=False, indent=2)
        temporary_path.replace(FEEDBACK_PATH)

    return {"status": "success", "feedback_id": record["feedback_id"]}


@app.post("/chat")
def chat(request: ChatRequest):
    answer, history = run_agent(request.message, request.history)

    return {
        "answer": answer,
        "history": history,
    }


@app.post("/sync")
def sync():
    incremental_sync()

    return {
        "status": "success",
        "message": "Freshdesk sync completed."
    }


@app.get("/health")
def health():
    return {"status": "ok"}

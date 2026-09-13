import sqlite3

from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.responses import FileResponse

from ai_entry import run_agent
from services.sync import incremental_sync

app = FastAPI(title="Support Copilot API")


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
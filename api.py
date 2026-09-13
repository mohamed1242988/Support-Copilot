from fastapi import FastAPI
from pydantic import BaseModel

from ai_entry import run_agent
from fastapi.responses import FileResponse

app = FastAPI(title="Support Copilot API")

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


@app.get("/health")
def health():
    return {"status": "ok"}
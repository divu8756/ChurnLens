"""Ask the Data: POST /chat/{id} (rate limited per IP) and GET /chat/{id} (history)."""

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app import sessions
from app.api.contract import HTTPErrorOut
from app.chat import history
from app.chat.agent import ask
from app.ratelimit import enforce

router = APIRouter(prefix="/chat", tags=["chat"])
ERRORS: dict[int | str, dict[str, Any]] = {
    code: {"model": HTTPErrorOut} for code in (409, 410, 429)}
class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


class ToolUse(BaseModel):
    tool: str | None
    args: dict[str, Any] | None = None
    error: str | None = None


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    text: str
    status: str | None = None
    tools_used: list[ToolUse] = Field(default_factory=list)


class ChatResponse(BaseModel):
    answer: ChatMessage
    history: list[ChatMessage]


def _values(session_id: str, request: Request) -> dict[str, Any]:
    try:
        sessions.read_meta(session_id)
    except sessions.SessionNotFound:
        raise HTTPException(410, "Session expired, please re-upload.") from None
    graph = request.app.state.runs.graph
    values = graph.get_state({"configurable": {"thread_id": session_id}}).values or {}
    if not values.get("clean_path"):
        raise HTTPException(409, "Run the analysis before asking questions about the data.")
    return values


@router.get("/{session_id}", response_model=list[ChatMessage], responses=ERRORS)
def chat_history(session_id: str) -> list[ChatMessage]:
    try:
        folder = sessions.require_session(session_id)
    except sessions.SessionNotFound:
        raise HTTPException(410, "Session expired, please re-upload.") from None
    return [ChatMessage(**m) for m in history.load(folder)]


@router.post("/{session_id}", response_model=ChatResponse, responses=ERRORS)
def chat(session_id: str, body: ChatRequest, request: Request) -> ChatResponse:
    enforce(request.app.state.chat_limiter, request, "chat")
    values = _values(session_id, request)
    folder = sessions.session_dir(session_id)
    past = [{"role": m["role"], "text": m["text"]} for m in history.load(folder)]
    result = ask(values, body.message.strip(), past)
    answer = {"role": "assistant", "text": result["answer"], "status": result["status"],
              "tools_used": result["tools_used"]}
    saved = history.append(folder, {"role": "user", "text": body.message.strip()}, answer)
    return ChatResponse(answer=ChatMessage(**answer), history=[ChatMessage(**m) for m in saved])

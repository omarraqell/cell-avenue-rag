"""
FastAPI application for the Cell Avenue RAG chatbot.

Endpoints:
  POST /chat        — ask a question, get an answer with citations (with memory)
  POST /chat/stream — stream the answer token-by-token via SSE
  POST /session     — create a new conversation session
  GET  /health      — health check
  GET  /index-info  — current FAISS index metadata
"""

import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

# Will be initialized on startup
rag = None


# ── request / response models ───────────────────────────────
class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000, description="The user's question")
    session_id: str | None = Field(
        default=None,
        description="Session ID for conversation memory. Omit to start a new session automatically.",
    )


class ChatResponse(BaseModel):
    answer: str
    citations: list[str]
    language: str
    as_of: str
    chunks_used: int
    session_id: str = Field(description="Use this session_id in subsequent requests to maintain conversation context")


class SessionResponse(BaseModel):
    session_id: str


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    index_loaded: bool


# ── app lifecycle ────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load the RAG chain once at startup."""
    global rag
    from app.rag.retriever import CellAvenueRAG

    print("Loading FAISS index and RAG chain …")
    rag = CellAvenueRAG()
    print(f"  ✓ Index loaded: {rag.vectorstore.index.ntotal} vectors")
    yield
    print("Shutting down.")


app = FastAPI(
    title="Cell Avenue RAG API",
    description="AI-powered product & policy assistant for Cell Avenue Store — with conversation memory",
    version="1.1.0",
    lifespan=lifespan,
)

# Allow CORS for local frontend dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── endpoints ────────────────────────────────────────────────
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Ask a question about Cell Avenue products, shipping, returns, etc.

    **Memory**: Pass `session_id` from a previous response to continue a conversation.
    The bot will remember what you talked about and understand follow-up questions like
    "what are they?" or "tell me more".

    If you don't pass a `session_id`, a new session is created automatically.
    """
    if rag is None:
        raise HTTPException(status_code=503, detail="RAG chain not initialized")

    try:
        result = rag.query(
            question=request.question,
            session_id=request.session_id,
        )
        return ChatResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Stream the AI response token-by-token via Server-Sent Events (SSE).

    Compatible with Vercel AI SDK `useChat` hook.
    Text tokens are sent as `0:"token"` events.
    Final metadata (citations, session_id) is sent as `d:{json}` event.
    """
    if rag is None:
        raise HTTPException(status_code=503, detail="RAG chain not initialized")

    def event_generator():
        try:
            for item in rag.query_stream(
                question=request.question,
                session_id=request.session_id,
            ):
                if isinstance(item, dict) and item.get("__metadata__"):
                    # Final metadata event — Vercel AI SDK data format
                    meta = {k: v for k, v in item.items() if k != "__metadata__"}
                    yield f"d:{json.dumps(meta, ensure_ascii=False)}\n"
                else:
                    # Text token — Vercel AI SDK text format
                    yield f"0:{json.dumps(item, ensure_ascii=False)}\n"
        except Exception as e:
            yield f"e:{json.dumps({'error': str(e)})}\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/plain; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/session", response_model=SessionResponse)
async def create_session():
    """Create a new conversation session. Returns a session_id to use with /chat."""
    if rag is None:
        raise HTTPException(status_code=503, detail="RAG chain not initialized")
    session_id = rag.create_session()
    return SessionResponse(session_id=session_id)


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc).isoformat(),
        index_loaded=rag is not None,
    )


@app.get("/index-info")
async def index_info():
    """Return metadata about the current FAISS index."""
    if rag is None:
        raise HTTPException(status_code=503, detail="RAG chain not initialized")
    return rag.get_index_info()

"""
RAG retriever for Cell Avenue e-commerce chatbot.

Loads the FAISS vector store, builds a retrieval-augmented generation chain
using GPT-4o-mini that answers ONLY from the retrieved context and returns
structured JSON with citations.

Supports server-side conversation memory via session-based chat history.
"""

import json
import os
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

# ── paths ────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]
INDEX_DIR = ROOT / "app" / "vectorstore" / "faiss_index"
MANIFEST_DIR = ROOT / "app" / "data" / "manifests"

# ── load env once at import time ─────────────────────────────
load_dotenv(ROOT / ".env")

# ── system prompt ────────────────────────────────────────────
SYSTEM_PROMPT = """\
You are the Cell Avenue Store AI assistant.
You help customers with questions about products, pricing, shipping, returns, and store policies.

RULES — follow these strictly:
1. Answer ONLY from the provided context below. Never invent information.
2. If the answer is not in the context, say: "I'm sorry, I don't have that information. Please contact Cell Avenue support for help."
3. Include the source URL(s) for every claim you make. Place them naturally in your answer or list them at the end as "Sources:".
4. Match the language of the user's question. If they ask in Arabic, reply in Arabic. If in English, reply in English.
5. Be concise, friendly, and professional.
6. When listing products or prices, use bullet points for clarity.
7. Always mention the currency (KWD/دينار كويتي) when discussing prices.

CONTEXT:
{context}
"""

USER_PROMPT = "{question}"

# ── query rewriter prompt for follow-up questions ────────────
REWRITE_PROMPT = """\
Given the following conversation history and a follow-up question, rewrite the follow-up question as a standalone question that captures the full intent. Keep it concise.

Conversation history:
{chat_history}

Follow-up question: {question}

Standalone question:"""

MAX_HISTORY_TURNS = 10  # max messages per session to keep


def _format_docs(docs: list[Document]) -> str:
    """Format retrieved documents into a context string for the LLM."""
    parts = []
    for i, doc in enumerate(docs, 1):
        meta = doc.metadata
        title = meta.get("source_title", "Untitled")
        url = meta.get("url", "")
        lang = meta.get("language", "")
        page_type = meta.get("page_type", "")
        parts.append(
            f"--- Document {i} ---\n"
            f"Title: {title}\n"
            f"URL: {url}\n"
            f"Type: {page_type} | Language: {lang}\n\n"
            f"{doc.page_content}\n"
        )
    return "\n".join(parts)


def _extract_citations(docs: list[Document]) -> list[str]:
    """Extract unique URLs from retrieved documents."""
    seen = set()
    urls = []
    for doc in docs:
        url = doc.metadata.get("url", "")
        if url and url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def _format_history_for_rewrite(history: list[dict]) -> str:
    """Format chat history as a readable string for the rewrite prompt."""
    lines = []
    for msg in history:
        role = "User" if msg["role"] == "user" else "Assistant"
        lines.append(f"{role}: {msg['content']}")
    return "\n".join(lines)


class CellAvenueRAG:
    """Main RAG class — holds the vector store, LLM chain, and session memory."""

    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        embed_model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
        chat_model = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")

        # Embeddings
        self.embeddings = OpenAIEmbeddings(
            model=embed_model, openai_api_key=api_key
        )

        # Vector store
        self.vectorstore = FAISS.load_local(
            str(INDEX_DIR),
            self.embeddings,
            allow_dangerous_deserialization=True,
        )

        # Retriever — MMR for diversity
        self.retriever = self.vectorstore.as_retriever(
            search_type="mmr",
            search_kwargs={"k": 8, "fetch_k": 40},
        )

        # LLM
        self.llm = ChatOpenAI(
            model=chat_model,
            temperature=0.1,
            openai_api_key=api_key,
        )

        # Prompt
        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", SYSTEM_PROMPT),
                ("human", USER_PROMPT),
            ]
        )

        # Load embed manifest for metadata
        embed_manifest_path = MANIFEST_DIR / "embed_manifest.json"
        if embed_manifest_path.exists():
            self.embed_manifest = json.loads(
                embed_manifest_path.read_text(encoding="utf-8")
            )
        else:
            self.embed_manifest = {}

        # ── session memory ───────────────────────────────────
        self._sessions: dict[str, list[dict]] = defaultdict(list)
        self._lock = Lock()

    # ── session management ───────────────────────────────────
    def create_session(self) -> str:
        """Create a new conversation session and return its ID."""
        session_id = uuid.uuid4().hex[:12]
        with self._lock:
            self._sessions[session_id] = []
        return session_id

    def get_session_history(self, session_id: str) -> list[dict]:
        """Get the chat history for a session."""
        with self._lock:
            return list(self._sessions.get(session_id, []))

    def _append_to_session(self, session_id: str, role: str, content: str):
        """Append a message to a session's history."""
        with self._lock:
            history = self._sessions[session_id]
            history.append({"role": role, "content": content})
            # Trim to max history
            if len(history) > MAX_HISTORY_TURNS * 2:
                self._sessions[session_id] = history[-(MAX_HISTORY_TURNS * 2):]

    def _rewrite_with_context(self, question: str, history: list[dict]) -> str:
        """Use the LLM to rewrite a follow-up question as a standalone question."""
        if not history:
            return question

        history_text = _format_history_for_rewrite(history[-6:])  # last 3 turns
        rewrite_resp = self.llm.invoke(
            REWRITE_PROMPT.format(chat_history=history_text, question=question)
        )
        rewritten = rewrite_resp.content.strip()
        return rewritten if rewritten else question

    # ── main query ───────────────────────────────────────────
    def query(self, question: str, session_id: str | None = None) -> dict:
        """
        Run a RAG query with automatic session memory.

        Args:
            question:   The user's question
            session_id: Session ID for conversation continuity.
                        If None, treated as a one-off query (no memory).

        Returns:
            {
                "answer": str,
                "citations": [str],
                "language": str,
                "as_of": str,
                "chunks_used": int,
                "session_id": str,
            }
        """
        # If no session, create one
        if not session_id:
            session_id = self.create_session()

        # Get existing history for this session
        history = self.get_session_history(session_id)

        # Rewrite the question using conversation context for better retrieval
        search_query = self._rewrite_with_context(question, history)

        # Retrieve relevant documents using the rewritten query
        docs = self.retriever.invoke(search_query)

        # Build context
        context = _format_docs(docs)
        citations = _extract_citations(docs)

        # Detect likely language from the question
        language = "ar" if any("\u0600" <= c <= "\u06FF" for c in question) else "en"

        # Build messages: system + history + current question
        system_msg = self.prompt.format_messages(
            context=context,
            question=question,
        )[0]  # just the system message

        # Convert history to LangChain messages
        history_msgs = []
        for msg in history[-6:]:  # last 3 turns (6 messages)
            if msg["role"] == "user":
                history_msgs.append(HumanMessage(content=msg["content"]))
            else:
                history_msgs.append(AIMessage(content=msg["content"]))

        # Final message list: system → history → current question
        messages = [system_msg] + history_msgs + [HumanMessage(content=question)]

        # Invoke LLM
        response = self.llm.invoke(messages)

        # Save to session memory
        self._append_to_session(session_id, "user", question)
        self._append_to_session(session_id, "assistant", response.content)

        return {
            "answer": response.content,
            "citations": citations,
            "language": language,
            "as_of": datetime.now(timezone.utc).isoformat(),
            "chunks_used": len(docs),
            "session_id": session_id,
        }

    def query_stream(self, question: str, session_id: str | None = None):
        """
        Stream a RAG query token-by-token.

        Yields:
            str tokens as they arrive from the LLM.
            After all tokens, yields a dict with metadata (citations, session_id, etc.)
        """
        # If no session, create one
        if not session_id:
            session_id = self.create_session()

        # Get existing history for this session
        history = self.get_session_history(session_id)

        # Rewrite the question using conversation context for better retrieval
        search_query = self._rewrite_with_context(question, history)

        # Retrieve relevant documents using the rewritten query
        docs = self.retriever.invoke(search_query)

        # Build context
        context = _format_docs(docs)
        citations = _extract_citations(docs)

        # Detect likely language from the question
        language = "ar" if any("\u0600" <= c <= "\u06FF" for c in question) else "en"

        # Build messages: system + history + current question
        system_msg = self.prompt.format_messages(
            context=context,
            question=question,
        )[0]

        # Convert history to LangChain messages
        history_msgs = []
        for msg in history[-6:]:
            if msg["role"] == "user":
                history_msgs.append(HumanMessage(content=msg["content"]))
            else:
                history_msgs.append(AIMessage(content=msg["content"]))

        messages = [system_msg] + history_msgs + [HumanMessage(content=question)]

        # Stream LLM response
        full_response = ""
        for chunk in self.llm.stream(messages):
            token = chunk.content
            if token:
                full_response += token
                yield token

        # Save to session memory
        self._append_to_session(session_id, "user", question)
        self._append_to_session(session_id, "assistant", full_response)

        # Yield final metadata
        yield {
            "__metadata__": True,
            "citations": citations,
            "language": language,
            "as_of": datetime.now(timezone.utc).isoformat(),
            "chunks_used": len(docs),
            "session_id": session_id,
        }

    def get_index_info(self) -> dict:
        """Return info about the current FAISS index."""
        return {
            "index_path": str(INDEX_DIR),
            "total_vectors": self.vectorstore.index.ntotal,
            "embedding_model": self.embed_manifest.get("embedding_model", "unknown"),
            "indexed_at": self.embed_manifest.get("generated_at", "unknown"),
            "languages": self.embed_manifest.get("languages", {}),
            "page_types": self.embed_manifest.get("page_types", {}),
            "active_sessions": len(self._sessions),
        }

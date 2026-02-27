"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import MessageBubble from "@/components/chat/MessageBubble";
import ChatInput from "@/components/chat/ChatInput";
import LoadingIndicator from "@/components/chat/LoadingIndicator";
import Sidebar from "@/components/sidebar/Sidebar";
import { Sparkles } from "lucide-react";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: string[];
}

interface SessionInfo {
  id: string;
  title: string;
  backendSessionId: string | null;
  messages: Message[];
}

// Calls go through Next.js API route proxy (/api/chat)
// which forwards to the FastAPI backend server-side

const WELCOME_SUGGESTIONS = [
  "What phones do you have?",
  "What is your shipping policy?",
  "ما هي سياسة الإرجاع؟",
  "Show me the latest Honor phones",
];

function generateId(): string {
  return Math.random().toString(36).substring(2, 15);
}

export default function ChatPage() {
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const [streamingCitations, setStreamingCitations] = useState<string[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const abortControllerRef = useRef<AbortController | null>(null);

  const activeSession = sessions.find((s) => s.id === activeSessionId);
  const messages = activeSession?.messages || [];

  // Auto-scroll to bottom
  const scrollToBottom = useCallback(() => {
    if (autoScroll) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [autoScroll]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingContent, isLoading, scrollToBottom]);

  // Detect manual scroll
  const handleScroll = () => {
    const container = chatContainerRef.current;
    if (container) {
      const { scrollTop, scrollHeight, clientHeight } = container;
      const isNearBottom = scrollHeight - scrollTop - clientHeight < 100;
      setAutoScroll(isNearBottom);
    }
  };

  // Update session in state
  const updateSession = (id: string, updater: (s: SessionInfo) => SessionInfo) => {
    setSessions((prev) => prev.map((s) => (s.id === id ? updater(s) : s)));
  };

  // Send message with streaming
  const sendMessage = async (text: string, sessionId: string) => {
    const session = sessions.find((s) => s.id === sessionId);
    if (!session) return;

    // Add user message
    const userMsg: Message = { id: generateId(), role: "user", content: text };
    updateSession(sessionId, (s) => ({
      ...s,
      messages: [...s.messages, userMsg],
      title: s.title === "New Chat" ? text.slice(0, 40) + (text.length > 40 ? "…" : "") : s.title,
    }));

    setIsLoading(true);
    setStreamingContent("");
    setStreamingCitations([]);
    setAutoScroll(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const response = await fetch(`/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: text,
          session_id: session.backendSessionId,
        }),
        signal: controller.signal,
      });

      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const reader = response.body?.getReader();
      if (!reader) throw new Error("No reader");

      const decoder = new TextDecoder();
      let fullContent = "";
      let citations: string[] = [];
      let backendSessionId = session.backendSessionId;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split("\n").filter(Boolean);

        for (const line of lines) {
          if (line.startsWith("0:")) {
            // Text token
            const token = JSON.parse(line.slice(2));
            fullContent += token;
            setStreamingContent(fullContent);
          } else if (line.startsWith("d:")) {
            // Metadata
            const meta = JSON.parse(line.slice(2));
            citations = meta.citations || [];
            backendSessionId = meta.session_id || backendSessionId;
            setStreamingCitations(citations);
          }
        }
      }

      // Add assistant message to session
      const assistantMsg: Message = {
        id: generateId(),
        role: "assistant",
        content: fullContent,
        citations,
      };

      updateSession(sessionId, (s) => ({
        ...s,
        messages: [...s.messages, assistantMsg],
        backendSessionId,
      }));
    } catch (err) {
      if ((err as Error).name === "AbortError") {
        // User cancelled — save what we have
        if (streamingContent) {
          const partialMsg: Message = {
            id: generateId(),
            role: "assistant",
            content: streamingContent,
            citations: streamingCitations,
          };
          updateSession(sessionId, (s) => ({
            ...s,
            messages: [...s.messages, partialMsg],
          }));
        }
      } else {
        const errorMsg: Message = {
          id: generateId(),
          role: "assistant",
          content: "Sorry, something went wrong. Please try again.",
        };
        updateSession(sessionId, (s) => ({
          ...s,
          messages: [...s.messages, errorMsg],
        }));
      }
    } finally {
      setIsLoading(false);
      setStreamingContent("");
      setStreamingCitations([]);
      abortControllerRef.current = null;
    }
  };

  // Handle submit
  const handleSend = () => {
    const text = input.trim();
    if (!text || isLoading) return;

    let sessionId = activeSessionId;

    // Create session if none
    if (!sessionId) {
      const newSession: SessionInfo = {
        id: generateId(),
        title: text.slice(0, 40) + (text.length > 40 ? "…" : ""),
        backendSessionId: null,
        messages: [],
      };
      setSessions((prev) => [newSession, ...prev]);
      setActiveSessionId(newSession.id);
      sessionId = newSession.id;

      // Need to use the new session directly since state hasn't updated yet
      setInput("");
      setTimeout(() => sendMessage(text, sessionId!), 50);
      return;
    }

    setInput("");
    sendMessage(text, sessionId);
  };

  // Stop generation
  const handleStop = () => {
    abortControllerRef.current?.abort();
  };

  // New chat
  const handleNewChat = () => {
    const newSession: SessionInfo = {
      id: generateId(),
      title: "New Chat",
      backendSessionId: null,
      messages: [],
    };
    setSessions((prev) => [newSession, ...prev]);
    setActiveSessionId(newSession.id);
    setStreamingContent("");
    setSidebarOpen(false);
  };

  // Select session
  const handleSelectSession = (id: string) => {
    setActiveSessionId(id);
    setStreamingContent("");
    setSidebarOpen(false);
  };

  // Delete session
  const handleDeleteSession = (id: string) => {
    setSessions((prev) => prev.filter((s) => s.id !== id));
    if (activeSessionId === id) {
      setActiveSessionId(null);
      setStreamingContent("");
    }
  };

  // Handle suggestion click
  const handleSuggestion = (text: string) => {
    const newSession: SessionInfo = {
      id: generateId(),
      title: text.slice(0, 40) + (text.length > 40 ? "…" : ""),
      backendSessionId: null,
      messages: [],
    };
    setSessions((prev) => [newSession, ...prev]);
    setActiveSessionId(newSession.id);

    setTimeout(() => sendMessage(text, newSession.id), 50);
  };

  const showWelcome = messages.length === 0 && !isLoading && !streamingContent;

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <Sidebar
        sessions={sessions.map((s) => ({ id: s.id, title: s.title }))}
        activeSessionId={activeSessionId}
        onNewChat={handleNewChat}
        onSelectSession={handleSelectSession}
        onDeleteSession={handleDeleteSession}
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
      />

      {/* Main chat area */}
      <main className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <header
          className="glass border-b flex items-center justify-center px-4 py-3"
          style={{ borderColor: "var(--border)" }}
        >
          <div className="flex items-center gap-2">
            <div
              className="w-7 h-7 rounded-lg flex items-center justify-center"
              style={{ background: "var(--accent-glow)" }}
            >
              <Sparkles size={14} style={{ color: "var(--accent)" }} />
            </div>
            <h1 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
              Cell Avenue AI
            </h1>
          </div>
        </header>

        {/* Messages area */}
        <div
          ref={chatContainerRef}
          className="flex-1 overflow-y-auto"
          onScroll={handleScroll}
        >
          <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
            {showWelcome && (
              <div className="flex flex-col items-center justify-center min-h-[60vh]">
                <div
                  className="w-16 h-16 rounded-2xl flex items-center justify-center mb-6 pulse-glow"
                  style={{ background: "var(--accent-glow)" }}
                >
                  <Sparkles size={28} style={{ color: "var(--accent)" }} />
                </div>
                <h2
                  className="text-xl font-semibold mb-2"
                  style={{ color: "var(--text-primary)" }}
                >
                  Cell Avenue AI Assistant
                </h2>
                <p
                  className="text-sm mb-8 text-center max-w-md"
                  style={{ color: "var(--text-secondary)" }}
                >
                  Ask me about products, prices, shipping, returns, and store
                  policies. I support both English and Arabic.
                </p>

                {/* Suggestion cards */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-lg">
                  {WELCOME_SUGGESTIONS.map((suggestion) => (
                    <button
                      key={suggestion}
                      onClick={() => handleSuggestion(suggestion)}
                      className="text-left px-4 py-3 rounded-xl text-sm transition-all"
                      style={{
                        background: "var(--bg-secondary)",
                        border: "1px solid var(--border)",
                        color: "var(--text-secondary)",
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.borderColor = "var(--accent)";
                        e.currentTarget.style.color = "var(--text-primary)";
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.borderColor = "var(--border)";
                        e.currentTarget.style.color = "var(--text-secondary)";
                      }}
                      dir="auto"
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Chat messages */}
            {messages.map((message) => (
              <MessageBubble
                key={message.id}
                role={message.role}
                content={message.content}
                citations={message.citations}
              />
            ))}

            {/* Streaming message */}
            {streamingContent && (
              <MessageBubble
                role="assistant"
                content={streamingContent}
                citations={streamingCitations.length > 0 ? streamingCitations : undefined}
              />
            )}

            {/* Loading indicator (before streaming starts) */}
            {isLoading && !streamingContent && (
              <LoadingIndicator />
            )}

            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Input area */}
        <ChatInput
          value={input}
          onChange={setInput}
          onSubmit={handleSend}
          onStop={handleStop}
          isLoading={isLoading}
        />
      </main>
    </div>
  );
}

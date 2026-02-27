"use client";

import { Plus, MessageSquare, Trash2, Menu, X } from "lucide-react";

interface Session {
    id: string;
    title: string;
}

interface SidebarProps {
    sessions: Session[];
    activeSessionId: string | null;
    onNewChat: () => void;
    onSelectSession: (id: string) => void;
    onDeleteSession: (id: string) => void;
    isOpen: boolean;
    onToggle: () => void;
}

export default function Sidebar({
    sessions,
    activeSessionId,
    onNewChat,
    onSelectSession,
    onDeleteSession,
    isOpen,
    onToggle,
}: SidebarProps) {
    return (
        <>
            {/* Mobile toggle button */}
            <button
                onClick={onToggle}
                className="md:hidden fixed top-3 left-3 z-50 w-10 h-10 rounded-lg flex items-center justify-center"
                style={{ background: "var(--bg-secondary)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
            >
                {isOpen ? <X size={18} /> : <Menu size={18} />}
            </button>

            {/* Overlay for mobile */}
            {isOpen && (
                <div
                    className="md:hidden fixed inset-0 bg-black/50 z-30"
                    onClick={onToggle}
                />
            )}

            {/* Sidebar */}
            <aside
                className={`fixed md:relative z-40 h-full flex flex-col transition-transform duration-300 ease-in-out ${isOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
                    }`}
                style={{
                    width: "var(--sidebar-width)",
                    minWidth: "var(--sidebar-width)",
                    background: "var(--bg-secondary)",
                    borderRight: "1px solid var(--border)",
                }}
            >
                {/* Header */}
                <div className="p-3">
                    <button
                        onClick={onNewChat}
                        className="w-full flex items-center gap-2 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors"
                        style={{
                            border: "1px solid var(--border)",
                            color: "var(--text-primary)",
                            background: "transparent",
                        }}
                        onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-hover)")}
                        onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                    >
                        <Plus size={16} />
                        New Chat
                    </button>
                </div>

                {/* Chat list */}
                <div className="flex-1 overflow-y-auto px-2 space-y-0.5">
                    {sessions.length === 0 && (
                        <p
                            className="text-xs text-center py-8"
                            style={{ color: "var(--text-muted)" }}
                        >
                            No conversations yet
                        </p>
                    )}
                    {sessions.map((session) => (
                        <div
                            key={session.id}
                            className={`group flex items-center gap-2 px-3 py-2.5 rounded-lg cursor-pointer transition-colors text-sm`}
                            style={{
                                background:
                                    session.id === activeSessionId
                                        ? "var(--bg-hover)"
                                        : "transparent",
                                color:
                                    session.id === activeSessionId
                                        ? "var(--text-primary)"
                                        : "var(--text-secondary)",
                            }}
                            onClick={() => onSelectSession(session.id)}
                            onMouseEnter={(e) => {
                                if (session.id !== activeSessionId)
                                    e.currentTarget.style.background = "var(--bg-tertiary)";
                            }}
                            onMouseLeave={(e) => {
                                if (session.id !== activeSessionId)
                                    e.currentTarget.style.background = "transparent";
                            }}
                        >
                            <MessageSquare size={14} className="shrink-0" />
                            <span className="truncate flex-1">{session.title}</span>
                            <button
                                onClick={(e) => {
                                    e.stopPropagation();
                                    onDeleteSession(session.id);
                                }}
                                className="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:bg-[var(--bg-hover)]"
                                style={{ color: "var(--text-muted)" }}
                            >
                                <Trash2 size={12} />
                            </button>
                        </div>
                    ))}
                </div>

                {/* Footer */}
                <div
                    className="p-3 text-xs text-center"
                    style={{ color: "var(--text-muted)", borderTop: "1px solid var(--border)" }}
                >
                    Cell Avenue AI v1.0
                </div>
            </aside>
        </>
    );
}

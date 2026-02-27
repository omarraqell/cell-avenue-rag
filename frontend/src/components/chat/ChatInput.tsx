"use client";

import { useRef, useEffect, KeyboardEvent } from "react";
import { Send, Square } from "lucide-react";

interface ChatInputProps {
    value: string;
    onChange: (value: string) => void;
    onSubmit: () => void;
    onStop?: () => void;
    isLoading: boolean;
    disabled?: boolean;
}

export default function ChatInput({
    value,
    onChange,
    onSubmit,
    onStop,
    isLoading,
    disabled,
}: ChatInputProps) {
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    // Auto-resize textarea
    useEffect(() => {
        const textarea = textareaRef.current;
        if (textarea) {
            textarea.style.height = "auto";
            textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
        }
    }, [value]);

    // Focus on mount
    useEffect(() => {
        textareaRef.current?.focus();
    }, []);

    const safeValue = value || "";

    const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            if (!isLoading && safeValue.trim()) {
                onSubmit();
            }
        }
    };

    const handleButtonClick = () => {
        if (isLoading && onStop) {
            onStop();
        } else if (safeValue.trim()) {
            onSubmit();
        }
    };

    return (
        <div className="glass border-t" style={{ borderColor: "var(--border)" }}>
            <div className="max-w-3xl mx-auto px-4 py-3">
                <div
                    className="flex items-end gap-2 rounded-xl px-4 py-2 transition-all focus-within:ring-1"
                    style={{
                        background: "var(--bg-input)",
                        border: "1px solid var(--border)",
                        "--tw-ring-color": "var(--accent)",
                    } as React.CSSProperties}
                >
                    <textarea
                        ref={textareaRef}
                        value={value}
                        onChange={(e) => onChange(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="Message Cell Avenue AI…"
                        disabled={disabled}
                        rows={1}
                        className="flex-1 bg-transparent resize-none outline-none text-sm py-2 placeholder:text-[var(--text-muted)]"
                        style={{
                            color: "var(--text-primary)",
                            maxHeight: "var(--input-max-height)",
                        }}
                        dir="auto"
                    />
                    <button
                        onClick={handleButtonClick}
                        disabled={disabled || (!isLoading && !safeValue.trim())}
                        className="shrink-0 w-8 h-8 rounded-lg flex items-center justify-center transition-all disabled:opacity-30"
                        style={{
                            background: isLoading ? "var(--bg-hover)" : safeValue.trim() ? "var(--accent)" : "var(--bg-hover)",
                            color: isLoading || !safeValue.trim() ? "var(--text-muted)" : "#fff",
                        }}
                    >
                        {isLoading ? <Square size={14} /> : <Send size={16} />}
                    </button>
                </div>
                <p
                    className="text-center text-[11px] mt-2"
                    style={{ color: "var(--text-muted)" }}
                >
                    Cell Avenue AI can make mistakes. Verify important product info.
                </p>
            </div>
        </div>
    );
}

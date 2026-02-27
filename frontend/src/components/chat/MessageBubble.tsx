"use client";

import { User, Bot } from "lucide-react";
import MarkdownRenderer from "@/components/markdown/MarkdownRenderer";
import Citations from "./Citations";

interface MessageBubbleProps {
    role: "user" | "assistant";
    content: string;
    citations?: string[];
}

export default function MessageBubble({
    role,
    content,
    citations,
}: MessageBubbleProps) {
    const isUser = role === "user";

    return (
        <div
            className={`flex items-start gap-3 message-enter ${isUser ? "flex-row-reverse" : ""
                }`}
        >
            {/* Avatar */}
            <div
                className="w-8 h-8 rounded-full flex items-center justify-center shrink-0"
                style={{
                    background: isUser ? "var(--user-bubble)" : "var(--accent-glow)",
                    color: isUser ? "#fff" : "var(--accent)",
                }}
            >
                {isUser ? <User size={16} /> : (
                    <span className="text-sm font-bold">CA</span>
                )}
            </div>

            {/* Message content */}
            <div
                className={`max-w-[75%] rounded-2xl px-4 py-3 ${isUser ? "rounded-tr-md" : "rounded-tl-md"
                    }`}
                style={{
                    background: isUser ? "var(--user-bubble)" : "var(--bg-secondary)",
                    border: isUser ? "none" : "1px solid var(--border)",
                    color: isUser ? "#fff" : "var(--text-primary)",
                }}
                dir="auto"
            >
                {isUser ? (
                    <p className="text-sm leading-relaxed whitespace-pre-wrap">{content}</p>
                ) : (
                    <MarkdownRenderer content={content} />
                )}

                {/* Citations for assistant messages */}
                {!isUser && citations && <Citations citations={citations} />}
            </div>
        </div>
    );
}

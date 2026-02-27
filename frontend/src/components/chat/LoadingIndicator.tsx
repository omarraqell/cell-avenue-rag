"use client";

export default function LoadingIndicator() {
    return (
        <div className="flex items-start gap-3 message-enter">
            {/* Avatar */}
            <div
                className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 text-sm font-bold"
                style={{ background: "var(--accent-glow)", color: "var(--accent)" }}
            >
                CA
            </div>

            {/* Typing dots */}
            <div
                className="rounded-2xl px-5 py-3.5 mt-1"
                style={{ background: "var(--bg-secondary)", border: "1px solid var(--border)" }}
            >
                <div className="flex items-center gap-1.5">
                    <div className="flex gap-1">
                        <span
                            className="typing-dot w-2 h-2 rounded-full"
                            style={{ background: "var(--accent)" }}
                        />
                        <span
                            className="typing-dot w-2 h-2 rounded-full"
                            style={{ background: "var(--accent)" }}
                        />
                        <span
                            className="typing-dot w-2 h-2 rounded-full"
                            style={{ background: "var(--accent)" }}
                        />
                    </div>
                    <span
                        className="text-xs ml-2"
                        style={{ color: "var(--text-muted)" }}
                    >
                        Thinking…
                    </span>
                </div>
            </div>
        </div>
    );
}

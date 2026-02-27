"use client";

import { useState } from "react";
import { ExternalLink, ChevronDown, ChevronUp } from "lucide-react";

interface CitationsProps {
    citations: string[];
}

function extractTitle(url: string): string {
    try {
        const path = new URL(url).pathname;
        const slug = path.split("/").filter(Boolean).pop() || "";
        return slug
            .replace(/[-_]/g, " ")
            .replace(/\b\w/g, (c) => c.toUpperCase());
    } catch {
        return url;
    }
}

export default function Citations({ citations }: CitationsProps) {
    const [expanded, setExpanded] = useState(false);

    if (!citations || citations.length === 0) return null;

    return (
        <div className="mt-2">
            <button
                onClick={() => setExpanded(!expanded)}
                className="flex items-center gap-1.5 text-xs font-medium transition-colors"
                style={{ color: "var(--text-muted)" }}
            >
                <span
                    className="inline-flex items-center justify-center w-5 h-5 rounded-full text-[10px] font-semibold"
                    style={{ background: "var(--accent-glow)", color: "var(--accent)" }}
                >
                    {citations.length}
                </span>
                Sources
                {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            </button>

            {expanded && (
                <div
                    className="mt-2 rounded-lg p-3 space-y-1.5"
                    style={{ background: "var(--bg-tertiary)", border: "1px solid var(--border)" }}
                >
                    {citations.map((url, i) => (
                        <a
                            key={i}
                            href={url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center gap-2 text-xs py-1 px-2 rounded-md transition-colors hover:bg-[var(--bg-hover)]"
                            style={{ color: "var(--accent)" }}
                        >
                            <ExternalLink size={11} className="shrink-0" />
                            <span className="truncate">{extractTitle(url)}</span>
                        </a>
                    ))}
                </div>
            )}
        </div>
    );
}

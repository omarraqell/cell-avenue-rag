"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useState } from "react";
import { Check, Copy } from "lucide-react";

function CodeBlock({
    className,
    children,
}: {
    className?: string;
    children: React.ReactNode;
}) {
    const [copied, setCopied] = useState(false);
    const language = className?.replace("language-", "") || "";
    const code = String(children).replace(/\n$/, "");

    const handleCopy = async () => {
        await navigator.clipboard.writeText(code);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div className="relative group">
            {language && (
                <div
                    className="absolute top-0 left-0 px-3 py-1 text-xs font-medium rounded-br-lg"
                    style={{ color: "var(--text-muted)", background: "var(--bg-hover)" }}
                >
                    {language}
                </div>
            )}
            <button
                onClick={handleCopy}
                className="absolute top-2 right-2 p-1.5 rounded-md opacity-0 group-hover:opacity-100 transition-opacity"
                style={{ background: "var(--bg-hover)", color: "var(--text-secondary)" }}
                title="Copy code"
            >
                {copied ? <Check size={14} /> : <Copy size={14} />}
            </button>
            <pre className={className}>
                <code>{code}</code>
            </pre>
        </div>
    );
}

export default function MarkdownRenderer({ content }: { content: string }) {
    return (
        <div className="markdown-content" dir="auto">
            <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                    code({ className, children, ...props }) {
                        const isInline = !className;
                        if (isInline) {
                            return (
                                <code className={className} {...props}>
                                    {children}
                                </code>
                            );
                        }
                        return <CodeBlock className={className}>{children}</CodeBlock>;
                    },
                    a({ href, children }) {
                        return (
                            <a href={href} target="_blank" rel="noopener noreferrer">
                                {children}
                            </a>
                        );
                    },
                }}
            >
                {content}
            </ReactMarkdown>
        </div>
    );
}

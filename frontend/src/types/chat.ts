export interface ChatMessage {
    id: string;
    role: "user" | "assistant";
    content: string;
    citations?: string[];
    timestamp: Date;
}

export interface ChatSession {
    id: string;
    title: string;
    messages: ChatMessage[];
    createdAt: Date;
    sessionId: string | null; // backend session ID
}

export interface StreamMetadata {
    citations: string[];
    language: string;
    as_of: string;
    chunks_used: number;
    session_id: string;
}

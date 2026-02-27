export async function POST(req: Request) {
    const { messages, data } = await req.json();

    // Get the last user message
    const lastMessage = messages[messages.length - 1];
    const sessionId = data?.sessionId || null;

    // Forward to FastAPI streaming endpoint
    const response = await fetch("http://127.0.0.1:8000/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            question: lastMessage.content,
            session_id: sessionId,
        }),
    });

    if (!response.ok) {
        return new Response("Backend error", { status: response.status });
    }

    // Forward the stream directly to the client
    return new Response(response.body, {
        headers: {
            "Content-Type": "text/plain; charset=utf-8",
            "Cache-Control": "no-cache",
            Connection: "keep-alive",
        },
    });
}

const BACKEND_URL = process.env.API_URL || "http://127.0.0.1:8000";

export async function POST(req: Request) {
    const { question, session_id } = await req.json();

    // Forward to FastAPI streaming endpoint
    const response = await fetch(`${BACKEND_URL}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            question,
            session_id: session_id || null,
        }),
    });

    if (!response.ok) {
        return new Response(
            JSON.stringify({ error: "Backend error" }),
            { status: response.status, headers: { "Content-Type": "application/json" } }
        );
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

"""Quick test: multi-turn conversation memory."""
import json
import urllib.request

BASE = "http://127.0.0.1:8000"


def chat(question: str, session_id: str | None = None) -> dict:
    body = {"question": question}
    if session_id:
        body["session_id"] = session_id
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{BASE}/chat",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    resp = urllib.request.urlopen(req, timeout=120)
    return json.loads(resp.read())


print("=" * 60)
print("TURN 1: Ask about phones")
print("=" * 60)
r1 = chat("What phones do you have?")
print(f"Answer: {r1['answer'][:300]}...")
print(f"Session: {r1['session_id']}")
sid = r1["session_id"]

print()
print("=" * 60)
print("TURN 2: Follow-up — 'tell me more about them'")
print("=" * 60)
r2 = chat("Tell me more about them", session_id=sid)
print(f"Answer: {r2['answer'][:300]}...")
print(f"Session: {r2['session_id']}")

print()
print("=" * 60)
print("TURN 3: Follow-up — 'which one is cheapest?'")
print("=" * 60)
r3 = chat("Which one is the cheapest?", session_id=sid)
print(f"Answer: {r3['answer'][:300]}...")
print(f"Session: {r3['session_id']}")

print()
print("SUCCESS — Memory is working!" if r2["session_id"] == sid else "FAIL — session lost")

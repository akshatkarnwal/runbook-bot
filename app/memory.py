import json
import redis
from app.config import settings

client = redis.Redis(
    host = settings.redis_host,
    port = settings.redis_port,
    decode_responses = True
)

def get_history(session_id: str) -> list[dict]:
    """Get conversation history for a session."""
    raw = client.get(f"chat:{session_id}")
    if not raw:
        return []
    return json.loads(raw)

def add_message(session_id: str,role: str, content: str):
    """Add a message to conversation history."""
    history = get_history(session_id)
    history.append({"role": role,"content": content})

    history = history[-10:]
    client.setex(
        f"chat:{session_id}",
        settings.conversation_ttl,
        json.dumps(history)
    )

def clear_history(session_id:str):
    """clear conversation history for a session."""
    client.delete(f"chat:{session_id}")

def format_history_for_prompt(session_id: str) -> str:
    """Format history as a string for the prompt."""
    history = get_history(session_id)
    if not history:
        return "No previous conversation."
    
    lines = []
    for msg in history:
        role = "User" if msg["role"] == "user" else "Assistant"
        lines.append(f"{role}: {msg['content']}")
    return "\n".join(lines) 
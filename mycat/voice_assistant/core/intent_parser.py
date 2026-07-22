import re


def parse_text_to_intent(text: str) -> dict:
    """Parses transcribed speech text into an abstract intent dictionary."""
    if not text or not text.strip():
        return {"type": "NONE", "data": {}}

    text_clean = text.strip().lower()

    # Rule 1: Reminder Intent
    reminder_match = re.search(r"(?:remind(?:s?|er)?|remember|set(?:s)?\s+(?:a\s+)?(?:reminder|timer))\s+(.+)", text_clean)
    if reminder_match:
        content = reminder_match.group(1).strip()
        return {
            "type": "SET_REMINDER",
            "data": {
                "raw_text": text_clean,
                "message": content,
            },
        }

    # Rule 2: Sleep / Hide Intent
    sleep_keywords = ["sleep", "go to sleep", "hide", "rest", "shut down", "shutdown", "turn off"]
    if any(keyword in text_clean for keyword in sleep_keywords):
        return {
            "type": "SLEEP",
            "data": {"raw_text": text_clean},
        }

    # Default Intent: Chat with Ollama LLM
    return {
        "type": "CHAT",
        "data": {"text": text_clean},
    }

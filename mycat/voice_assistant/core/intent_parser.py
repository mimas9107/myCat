import re


def parse_text_to_intent(text: str) -> dict:
    """Parses transcribed speech text into an abstract intent dictionary."""
    if not text or not text.strip():
        return {"type": "NONE", "data": {}}

    text_clean = text.strip()

    # Rule 1: Reminder Intent
    reminder_match = re.search(r"(?:提醒|記得)(?:我)?\s*(.+)", text_clean)
    if reminder_match:
        content = reminder_match.group(1)
        return {
            "type": "SET_REMINDER",
            "data": {
                "raw_text": text_clean,
                "message": content,
            },
        }

    # Rule 2: Sleep / Hide Intent
    if any(keyword in text_clean for keyword in ["睡覺", "休息", "退下", "隱藏"]):
        return {
            "type": "SLEEP",
            "data": {"raw_text": text_clean},
        }

    # Default Intent: Chat with Ollama LLM
    return {
        "type": "CHAT",
        "data": {"text": text_clean},
    }


TIME_SENSITIVE_KEYWORDS = [
    "current", "now", "today",
    "president", "prime minister", "ceo",
    "latest", "recent", "election",
    "news", "weather", "price", "stock",
    "who is", "what is the" # Broaden to catch "Who is the president"
]

def is_time_sensitive(query: str) -> bool:
    """
    Detect if a query requires up-to-date information.
    """
    q = query.lower()
    return any(k in q for k in TIME_SENSITIVE_KEYWORDS)

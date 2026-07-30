
# AgentCore/knowledge/config.py

import os

SERP_ENGINES = ["duckduckgo", "bing"]

# Knowledge-discovery provider chain, tried in this order (S0-E3).
# Config-driven: override with the KNOWLEDGE_PROVIDER_ORDER env var as a
# comma-separated list, e.g. "serper,browser" to skip SerpApi entirely.
# Providers whose API key isn't configured are skipped, not treated as
# failures -- see provider_chain.py.
KNOWLEDGE_PROVIDER_ORDER = [
    p.strip()
    for p in os.environ.get("KNOWLEDGE_PROVIDER_ORDER", "serpapi,serper,browser").split(",")
    if p.strip()
]

MAX_CANDIDATES = 20
MAX_TOP_SOURCES = 5
CONCURRENCY = 5
TRUST_THRESHOLD = 0.6

# Cache and Freshness Settings (seconds)
REFRESH_POLICY = {
    "news": 24 * 3600,        # 1 day
    "time_sensitive": 6 * 3600, # 6 hours
    "stable": 30 * 24 * 3600    # 30 days
}

# User Agent for crawling
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

# Timeout settings
REQUEST_TIMEOUT = 10.0

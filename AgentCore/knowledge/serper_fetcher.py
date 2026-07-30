
# AgentCore/knowledge/serper_fetcher.py
"""
Serper.dev client -- secondary tier of the knowledge-retrieval provider chain.

Config-driven: reads SERPER_KEY from the environment, same pattern as
serpapi_fetcher.py's SERPAPI_KEY.

**Not live-verified.** No SERPER_KEY was available to build against
during this phase (2026-07-30) -- built from Serper.dev's published API
contract (POST https://google.serper.dev/search, header X-API-KEY,
JSON body {"q": query}, response has an "organic" array with
"title"/"link"/"snippet"), the normal way to write a client before a
key exists to test against. This is different from inferring an
*internal* contract from identifier names (the GeneratorHelper/
LLMAdapter failure this session already hit) -- it's using a published
external API spec, which is the only option with no key. Flagged
explicitly rather than claimed as verified: whoever supplies a real
SERPER_KEY should re-run this phase's live-call test before trusting
this tier in production.
"""
import os
from typing import Dict, List

import requests

SERPER_SEARCH_URL = "https://google.serper.dev/search"
REQUEST_TIMEOUT = 15.0


class SerperConfigError(Exception):
    """Raised when SERPER_KEY is not configured."""


class SerperCallError(Exception):
    """Raised when a configured Serper call fails (network, non-200, malformed body)."""


def _get_api_key() -> str:
    key = os.environ.get("SERPER_KEY")
    if not key:
        raise SerperConfigError("SERPER_KEY is not set in the environment")
    return key


def fetch_serper(query: str, max_results: int = 10) -> List[Dict]:
    """
    Fetch search results from Serper.dev.

    Returns the same shape as serp_fetcher.fetch_serp() and
    serpapi_fetcher.fetch_serpapi() for drop-in compatibility:
    [{"title", "url", "snippet", "source"}, ...].

    Raises SerperConfigError if no key is configured, SerperCallError
    on any other failure -- same fall-through contract as the SerpApi
    tier.
    """
    api_key = _get_api_key()

    try:
        resp = requests.post(
            SERPER_SEARCH_URL,
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": query},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as e:
        raise SerperCallError(f"Serper request failed: {e}") from e

    if resp.status_code != 200:
        raise SerperCallError(f"Serper returned HTTP {resp.status_code}: {resp.text[:200]}")

    try:
        data = resp.json()
    except ValueError as e:
        raise SerperCallError(f"Serper returned non-JSON body: {e}") from e

    results = []
    for item in data.get("organic", [])[:max_results]:
        link = item.get("link")
        title = item.get("title")
        if link and title:
            results.append({
                "title": title,
                "url": link,
                "snippet": item.get("snippet", ""),
                "source": "serper",
            })
    return results

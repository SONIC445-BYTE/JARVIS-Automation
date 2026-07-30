
# AgentCore/knowledge/serpapi_fetcher.py
"""
SerpApi client -- primary tier of the knowledge-retrieval provider chain.

Config-driven: reads SERPAPI_KEY from the environment (same pattern as
RHINAL_API_KEY in rhinal_mcp_client.py), never hardcoded. If the key
isn't set, fetch_serpapi() raises SerpApiConfigError so the provider
chain can fall through to the next tier honestly, rather than this
module silently returning an empty list that looks identical to "no
results found".

Quota: verified live against the real endpoint (2026-07-30) that
SerpApi does NOT expose quota in response headers -- the search
endpoint's headers carry no rate-limit/quota fields at all. Real quota
lives at a separate account endpoint (https://serpapi.com/account.json),
returning plan_searches_left/total_searches_left/this_month_usage. This
corrects the blueprint's original "quota tracking from response
headers" assumption -- recorded in the execution log, not silently
reworded here.
"""
import os
from typing import Dict, List, Optional

import requests

SERPAPI_SEARCH_URL = "https://serpapi.com/search"
SERPAPI_ACCOUNT_URL = "https://serpapi.com/account.json"
REQUEST_TIMEOUT = 15.0


class SerpApiConfigError(Exception):
    """Raised when SERPAPI_KEY is not configured."""


class SerpApiCallError(Exception):
    """Raised when a configured SerpApi call fails (network, non-200, malformed body)."""


def _get_api_key() -> str:
    key = os.environ.get("SERPAPI_KEY")
    if not key:
        raise SerpApiConfigError("SERPAPI_KEY is not set in the environment")
    return key


def fetch_serpapi(query: str, max_results: int = 10) -> List[Dict]:
    """
    Fetch search results from SerpApi (Google engine).

    Returns the same shape as serp_fetcher.fetch_serp() for drop-in
    compatibility with discovery_manager: [{"title", "url", "snippet",
    "source"}, ...].

    Raises SerpApiConfigError if no key is configured, SerpApiCallError
    on any other failure -- callers use these to decide whether to fall
    through to the next provider tier, rather than getting an
    indistinguishable empty list.
    """
    api_key = _get_api_key()

    try:
        resp = requests.get(
            SERPAPI_SEARCH_URL,
            params={"q": query, "api_key": api_key, "engine": "google"},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as e:
        raise SerpApiCallError(f"SerpApi request failed: {e}") from e

    if resp.status_code != 200:
        raise SerpApiCallError(f"SerpApi returned HTTP {resp.status_code}: {resp.text[:200]}")

    try:
        data = resp.json()
    except ValueError as e:
        raise SerpApiCallError(f"SerpApi returned non-JSON body: {e}") from e

    if data.get("search_metadata", {}).get("status") != "Success":
        raise SerpApiCallError(f"SerpApi search did not succeed: {data.get('search_metadata')}")

    results = []
    for item in data.get("organic_results", [])[:max_results]:
        link = item.get("link")
        title = item.get("title")
        if link and title:
            results.append({
                "title": title,
                "url": link,
                "snippet": item.get("snippet", ""),
                "source": "serpapi",
            })
    return results


def get_quota() -> Optional[Dict]:
    """
    Real, on-demand quota check against SerpApi's actual account
    endpoint -- not parsed from search-response headers (see module
    docstring). Deliberately not called on every search: this hits a
    separate endpoint and would double API traffic for no benefit in
    the hot path. Callers (status box, ops tooling) call this
    explicitly when they want a fresh number.

    Returns None if SERPAPI_KEY isn't configured or the call fails --
    quota visibility degrading gracefully, not crashing the caller.
    """
    try:
        api_key = _get_api_key()
    except SerpApiConfigError:
        return None

    try:
        resp = requests.get(SERPAPI_ACCOUNT_URL, params={"api_key": api_key}, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return None
        data = resp.json()
    except (requests.RequestException, ValueError):
        return None

    return {
        "plan_searches_left": data.get("plan_searches_left"),
        "total_searches_left": data.get("total_searches_left"),
        "searches_per_month": data.get("searches_per_month"),
        "this_month_usage": data.get("this_month_usage"),
        "account_rate_limit_per_hour": data.get("account_rate_limit_per_hour"),
        "this_hour_searches": data.get("this_hour_searches"),
    }


# AgentCore/knowledge/provider_chain.py
"""
Tiered knowledge-discovery provider chain (S0-E3): SerpApi -> Serper ->
browser automation (Selenium DuckDuckGo scrape), in that order by
default, config-driven via KNOWLEDGE_PROVIDER_ORDER (config.py / env
var).

Before this, the only discovery path was the Selenium scraper directly
-- no API tier, no failover, no user-visible narration of which
provider actually answered. This tries each configured tier in order,
skips tiers whose key isn't configured (not a failure, just
unavailable), and falls through to the next tier on a real call
failure. Honest failure if every tier is exhausted: returns an empty
list, the same "no sources found" contract discover_sources() already
had -- resolve_knowledge() turns that into an honest UNKNOWN verdict,
not a fabricated answer.
"""
from typing import Callable, Dict, List, Optional, Tuple

from .config import KNOWLEDGE_PROVIDER_ORDER
from .serpapi_fetcher import SerpApiCallError, SerpApiConfigError, fetch_serpapi
from .serper_fetcher import SerperCallError, SerperConfigError, fetch_serper

NarrationFn = Callable[[str], None]

_PROVIDER_LABELS = {
    "serpapi": "SerpApi",
    "serper": "Serper",
    "browser": "a direct browser search",
}


def _fetch_browser(query: str, max_results: int) -> List[Dict]:
    # Imported lazily -- this is the only tier that pulls in selenium/
    # webdriver_manager, and those imports must not fire just because
    # this module (or discovery_manager) was imported. Same lazy-import
    # discipline already applied to NetHyTechSTT and browser_automation.py.
    from .serp_fetcher import fetch_serp
    return fetch_serp(query, max_results=max_results)


def fetch_with_fallback(
    query: str,
    max_results: int = 10,
    notify: Optional[NarrationFn] = None,
    provider_order: Optional[List[str]] = None,
) -> Tuple[List[Dict], Optional[str]]:
    """
    Try each configured provider tier in order until one returns real
    results. Returns (results, provider_name_that_answered) --
    provider_name is None only when every tier was exhausted without
    results (honest failure, not a crash, not a silent empty success).

    notify(message), if given, is called once before the first attempt
    and again on each fallback, so a caller can narrate "let me check
    that" / provider switches to the user instead of this happening
    silently.
    """
    order = provider_order if provider_order is not None else KNOWLEDGE_PROVIDER_ORDER

    if notify and order:
        notify("Let me check that...")

    for i, provider in enumerate(order):
        if i > 0 and notify:
            notify(f"That didn't come through -- trying {_PROVIDER_LABELS.get(provider, provider)}...")

        try:
            if provider == "serpapi":
                results = fetch_serpapi(query, max_results=max_results)
            elif provider == "serper":
                results = fetch_serper(query, max_results=max_results)
            elif provider == "browser":
                results = _fetch_browser(query, max_results)
            else:
                print(f"[ProviderChain] Unknown provider '{provider}' in KNOWLEDGE_PROVIDER_ORDER, skipping")
                continue
        except (SerpApiConfigError, SerperConfigError) as e:
            print(f"[ProviderChain] {provider} not configured ({e}), trying next tier")
            continue
        except (SerpApiCallError, SerperCallError) as e:
            print(f"[ProviderChain] {provider} call failed ({e}), trying next tier")
            continue
        except Exception as e:
            # fetch_serp() already catches its own Selenium exceptions
            # internally and returns [], but guard here too so one
            # tier's unexpected error can't silently kill the whole
            # chain before later tiers get a chance.
            print(f"[ProviderChain] {provider} raised unexpectedly ({e}), trying next tier")
            continue

        if results:
            return results, provider

    if notify:
        notify("I couldn't find anything on that.")
    return [], None

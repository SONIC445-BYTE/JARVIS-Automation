"""
RHINAL MCP integration -- client wrapper.

RHINAL (github.com/SONIC445-BYTE/RHINAL) is a separate project with its
own MCP server (RHINAL/mcp-server), stdio transport only -- no HTTP
endpoint, no hosted deployment of the MCP server itself (only RHINAL's
own web app is deployed, to Vercel; the MCP server is a local
build-from-source subprocess that talks to that deployed web app's API
with a scoped rhk_ bearer key).

Verified live before writing this file, per instruction: cloned RHINAL,
read mcp-server/src/{index,tools,config}.ts, built it (npm install &&
npm run build), then spawned the real built server and called the real
MCP tools/list over stdio using the official MCP Python SDK -- not a
description, the actual protocol response. 14 tools came back, exactly
matching what's registered in index.ts (rhinal_capture, rhinal_recall,
rhinal_ask_vault, rhinal_classify_worthiness, rhinal_decision_log,
rhinal_idea_to_spec, rhinal_confront, rhinal_tag_prediction,
rhinal_resolve_prediction, rhinal_get_calibration_score,
rhinal_start_case, rhinal_get_case_graph, rhinal_check_contradiction,
rhinal_attach_file). The only drift found was between RHINAL's own
README ("Tools (Phase 1)", documenting 4) and its actual source/live
behavior (14) -- not between source and live protocol, which agreed
exactly.

Scope of THIS file, deliberately incremental (matching Phase 2g's
"start with 1-2 real adapters, expand later" precedent): wires
rhinal_capture only. The other 13 verified-live tools are not wired
here -- a real, working client for one tool, not a partial client for
fourteen.

Configuration is entirely environment-driven, matching RHINAL's own
mcp-server/src/config.ts convention (RHINAL_BASE_URL, RHINAL_API_KEY,
optional RHINAL_MODEL_ID/RHINAL_PROVIDER) plus one JARVIS-side addition:
RHINAL_MCP_SERVER_PATH, the absolute path to RHINAL's built
mcp-server/dist/index.js (RHINAL lives in a separate repo/checkout;
there is no reliable relative path to guess, so this is required, not
inferred).

Each call spawns the Node subprocess, does the MCP initialize handshake,
calls the one tool, and closes -- no persistent connection kept between
calls. Simpler and safer than a persistent-connection-plus-background-
event-loop for what's expected to be an occasional voice command, not a
hot loop; revisit if call frequency ever makes the per-call spawn cost
(a few hundred ms) actually matter.
"""
from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional


class RhinalConfigError(Exception):
    """Raised when required RHINAL_* environment variables are missing.
    Distinct from RhinalCallError (a reachable server that failed) --
    callers should give a different, more specific honest message for
    "not configured" vs. "configured but unreachable/failed"."""


class RhinalCallError(Exception):
    """Raised when the MCP server process, the handshake, or the tool
    call itself fails -- covers "Node/RHINAL not built", "server process
    wouldn't start", "RHINAL backend unreachable", and "tool call
    returned isError=True" (e.g. RHINAL's own classifier/distill/Notion
    write failed) uniformly. Never silently swallowed -- every caller
    must surface .args[0] to the physician, not report success."""


@dataclass
class RhinalConfig:
    server_path: str
    base_url: str
    api_key: str
    model_id: Optional[str] = None
    provider: Optional[str] = None


def load_rhinal_config() -> RhinalConfig:
    server_path = os.environ.get("RHINAL_MCP_SERVER_PATH")
    base_url = os.environ.get("RHINAL_BASE_URL")
    api_key = os.environ.get("RHINAL_API_KEY")

    missing = [
        name
        for name, value in (
            ("RHINAL_MCP_SERVER_PATH", server_path),
            ("RHINAL_BASE_URL", base_url),
            ("RHINAL_API_KEY", api_key),
        )
        if not value
    ]
    if missing:
        raise RhinalConfigError(
            "Rhinal isn't configured -- missing environment variable(s): "
            + ", ".join(missing)
            + ". RHINAL_MCP_SERVER_PATH must point at RHINAL's built "
            "mcp-server/dist/index.js (npm install && npm run build in "
            "that checkout first); RHINAL_BASE_URL/RHINAL_API_KEY are the "
            "same values RHINAL's own mcp-server/README.md documents."
        )

    return RhinalConfig(
        server_path=server_path,
        base_url=base_url.rstrip("/"),
        api_key=api_key,
        model_id=os.environ.get("RHINAL_MODEL_ID") or None,
        provider=os.environ.get("RHINAL_PROVIDER") or None,
    )


async def _call_tool_async(config: RhinalConfig, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    if not os.path.exists(config.server_path):
        raise RhinalCallError(
            f"Rhinal's MCP server isn't built at {config.server_path!r} -- "
            f"run `npm install && npm run build` in RHINAL's mcp-server directory first."
        )

    env = dict(os.environ)
    env["RHINAL_BASE_URL"] = config.base_url
    env["RHINAL_API_KEY"] = config.api_key
    if config.model_id:
        env["RHINAL_MODEL_ID"] = config.model_id
    if config.provider:
        env["RHINAL_PROVIDER"] = config.provider

    server_params = StdioServerParameters(command="node", args=[config.server_path], env=env)

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
    except RhinalCallError:
        raise
    except Exception as e:
        raise RhinalCallError(f"Could not reach Rhinal ({tool_name}): {e}") from e

    if result.isError:
        error_text = "".join(getattr(block, "text", "") for block in result.content)
        raise RhinalCallError(f"Rhinal reported an error for {tool_name}: {error_text or 'unknown error'}")

    text = "".join(getattr(block, "text", "") for block in result.content)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw_text": text}


def _run_async(coro):
    """asyncio.run() from a plain sync call site -- jarvis.py's
    conversation loop is entirely synchronous (see Phase 3b's design doc
    for why threading, not asyncio, is this codebase's concurrency
    idiom); this is the boundary where the MCP SDK's async-only client
    gets bridged into that synchronous world, once per call."""
    return asyncio.run(coro)


class RhinalMCPClient:
    """Thin sync wrapper. config=None loads from environment (the normal
    path); pass a RhinalConfig directly for tests."""

    def __init__(self, config: Optional[RhinalConfig] = None):
        self._config = config

    def _get_config(self) -> RhinalConfig:
        if self._config is None:
            self._config = load_rhinal_config()
        return self._config

    def capture(self, text: str, mode: Optional[str] = None) -> Dict[str, Any]:
        """Calls the real rhinal_capture tool -- classify -> distill ->
        save, exactly as RHINAL's web app does. Returns the structured
        record and whether it was flagged vault-worthy. Raises
        RhinalConfigError/RhinalCallError on any failure -- never
        returns a fabricated success."""
        config = self._get_config()
        arguments: Dict[str, Any] = {"text": text}
        if mode:
            arguments["mode"] = mode
        return _run_async(_call_tool_async(config, "rhinal_capture", arguments))

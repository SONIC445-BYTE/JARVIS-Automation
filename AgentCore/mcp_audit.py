"""
DEC-002 audit coverage for non-GUI MCP writes (D15, rhinal_capture half).

WHY THIS MODULE EXISTS AT ALL
-----------------------------
UIExecutor.execute_intent() is the single pre-adapter audit chokepoint
for everything that travels the Intent -> CommandRouter -> ResolutionGate
-> AdapterBase path. jarvis.py's conversation loop, however, dispatches
some handlers directly out of its elif chain, never touching that path.
D15 flagged two of them; the owner has since confirmed `code_engine` is
NOT a gap (build/development infrastructure, same category as Level6,
deliberately outside the clinical action path), leaving exactly one real
hole: `rhinal_capture`, which performs a network write into the
physician's external RHINAL vault with no who/what/when/why/source/
consent record.

The obvious-looking fix -- force rhinal_capture through Intent/
AdapterBase/ResolutionGate so it inherits UIExecutor's chokepoint -- is
wrong, and the existing comment in jarvis.py already says why: that
machinery models a *GUI platform with an install-detection question*
("is WhatsApp Desktop installed? should I offer to install it?"). RHINAL
is a stdio MCP subprocess talking to a hosted API; it is either
configured or it isn't, and "install it for you" is not a coherent
offer. Dressing an MCP call up as a GUI intent to reach the audit code
would make the routing layer lie about what kind of thing it is.

So this module reuses the *audit mechanism* (AgentCore.audit_trail:
get_clinical_audit_log / emit_clinical_action, and its DEC-002 two-tier
failure model) without reusing the *routing machinery*. It is the
reusable pattern for any future non-GUI MCP write -- rhinal_decision_log,
rhinal_attach_file, and the eleven other verified-live RHINAL tools, or
any other MCP server wired later. A new write tool adopts it by wrapping
its client call in audited_mcp_write(); it does not have to re-derive
any of the reasoning below.

PLACEMENT
---------
A new module rather than a function inside audit_trail.py. audit_trail.py
is immutable for structural changes, and this genuinely is a different
layer anyway: audit_trail.py is the storage engine plus the record shape,
this is a *call-site policy* (what to emit, in what order, and what to do
when emission fails) for one class of caller. Keeping policy out of the
storage module is also what let UIExecutor's version live in
ui_executor.py rather than in audit_trail.py. audit_trail.py is imported
and called here, never modified.

TWO-TIER FAILURE MODEL -- preserved exactly, not reinterpreted
--------------------------------------------------------------
1. Configuration-class (the audit trail's key cannot be resolved at all
   -> KeyConfigurationError): a hard stop, checked BEFORE anything is
   sent. An external, network-crossing, clinical-adjacent write that
   cannot be audited must not happen. This is the one case where the
   audit system blocks the underlying action, and it blocks it *before*
   the action, not after -- the same sequencing bug UIExecutor's
   docstring records catching in an earlier draft (checking after the
   fact is not a hard stop, it is an exception thrown over an action
   that already happened).
2. Transient (the log resolves fine, but this particular write fails --
   disk full, permission blip): never blocks the vault write. It comes
   back as a warning string on the result, which the caller is expected
   to append to the physician-facing response. It must be spoken, not
   buried in a log file nobody reads.

Any *other* exception while checking the audit log (not
KeyConfigurationError) is treated like the transient case: printed
loudly, action proceeds. Same discipline as UIExecutor.execute_intent()
-- "we know this is a config failure" is a narrower claim than "something
went wrong", and only the former earns a hard stop.

ORDERING: TWO RECORDS PER WRITE, AND WHY
----------------------------------------
Every audited MCP write emits *two* records: an "attempted" record
before the call, and an outcome record ("success"/"failed") after it.
UIExecutor emits only one, after the fact. This deliberately diverges,
and the divergence is driven by a property GUI actions do not have:

- A UIExecutor action is local and synchronous. If the process dies
  mid-action, the effect is on the physician's own machine and is
  directly observable there. Post-hoc auditing loses little.
- rhinal_capture puts the content on the wire to a third-party hosted
  vault. Once the request is sent, the remote effect can persist even if
  this process is killed, the machine loses power, or the network drops
  before the response. A post-only record means the realistic failure
  mode "content reached the external vault, JARVIS died before writing
  the audit line" produces an external clinical-adjacent write with zero
  trail. That is precisely the compliance hole D15 is about, reintroduced
  in miniature.
- Worse, RhinalCallError deliberately covers "unreachable" and "server
  reported an error" uniformly (see rhinal_mcp_client.py), so a failure
  return does NOT prove nothing was written remotely. A timeout after the
  server accepted the write is indistinguishable from a rejected write.
  The only thing this process can ever honestly assert is "at time T we
  attempted to send this content to the external vault"; the outcome
  record is JARVIS's *view* of what happened, which can be wrong.

Pre-only was rejected too: a compliance reader could not then tell an
attempt that succeeded from one that was refused, and a failed external
write is itself a real event worth reading.

So: the pre-record is the durable fact, the post-record is the observed
resolution. A compliance reader gets "we tried to send this" and, when
the process survived long enough to know, "here is what came back". An
"attempted" record with no following outcome record is meaningful on its
own -- it means the process did not survive the call, which is exactly
the situation the reader most needs flagged.

Cost accepted: two lines per write instead of one. At voice-command
frequency this is nothing.

PAIRING THE TWO RECORDS -- a real limitation, stated rather than hidden
-----------------------------------------------------------------------
The pair is identified by adjacency plus identical who/what/why/source,
not by an explicit correlation id. There is no correlation id because
emit_clinical_action()'s field set is fixed and audit_trail.py is
immutable for structural changes here; hand-rolling a dict through
AppendOnlyAuditLog.append() instead would duplicate the DEC-002 record
shape in a second place, which is worse than this limitation.

Adjacency is sound *today* for a specific, checked reason: this call
site is only ever reached from jarvis.py's _conversation_loop, which is
strictly one-command-at-a-time and synchronous (RhinalMCPClient.capture()
bridges the MCP SDK's async client through a single asyncio.run() per
call), so no other clinical action can interleave between the two
records. If a concurrent or queued dispatch path is ever added, this
stops being true and an explicit correlation id becomes necessary --
which will require an additive field on emit_clinical_action(). Flagged
here so that change is a decision someone makes, not an assumption that
quietly rots.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, List, Optional


@dataclass
class AuditedMCPWriteResult:
    """
    What the caller needs to build its physician-facing response.

    - blocked_reason: non-empty means the write never happened, because
      the audit trail is unconfigured (tier-1 failure). `call` was not
      invoked. Speak this.
    - ok/value/error: the real outcome of `call`, untouched. `error` is
      the original exception object, not a string, so callers keep the
      ability to branch on its type -- jarvis.py gives a different,
      more specific message for RhinalConfigError ("not configured")
      than for RhinalCallError ("configured but unreachable/failed"),
      and this wrapper must not flatten that distinction away.
    - audit_warning: non-empty means a transient audit write failed.
      The vault write is unaffected; append this to the spoken response.
    """
    ok: bool = False
    value: Any = None
    error: Optional[BaseException] = None
    blocked_reason: str = ""
    audit_warning: str = ""

    @property
    def blocked(self) -> bool:
        return bool(self.blocked_reason)


def _audit_trail_is_configured() -> Optional[str]:
    """
    Tier-1 check. Returns a physician-facing reason string if the audit
    trail is unconfigured (caller must block), or None to proceed.

    Imported inside the function, matching ui_executor.py: keeps import
    time free of key resolution, and keeps the module attribute
    patchable by tests the same way the existing audit-wiring tests do
    it.
    """
    from AgentCore.audit_trail import get_clinical_audit_log

    try:
        get_clinical_audit_log()
    except Exception as e:
        from AgentCore.secure_key import KeyConfigurationError

        if isinstance(e, KeyConfigurationError):
            return (
                f"I can't do that -- the audit trail isn't configured ({e}), and I'm not "
                f"writing to your vault without a record of it. This needs fixing first."
            )
        # Not the known configuration failure: loud, but not a hard stop.
        print(f"*** [MCPAudit] Unexpected error checking the audit log before an external write: {e} ***")
    return None


def _emit(
    *,
    what_adapter: str,
    what_action: str,
    what_target: str,
    why: str,
    source: str,
    outcome_status: str,
    outcome_ok: Optional[bool],
    outcome_error: Optional[str],
) -> str:
    """
    One DEC-002 record. Returns a warning string if the write failed
    transiently (empty string on success) -- never raises, so an audit
    problem can never become the reason an already-completed external
    write looks like a crash.
    """
    from AgentCore.audit_trail import emit_clinical_action

    try:
        audit_result = emit_clinical_action(
            what_adapter=what_adapter,
            what_action=what_action,
            what_target=what_target,
            why=why,
            source=source,
            outcome_status=outcome_status,
            outcome_ok=outcome_ok,
            outcome_error=outcome_error,
        )
    except Exception as e:
        print(f"*** [MCPAudit] Audit emission raised unexpectedly: {e} -- the external write is unaffected. ***")
        return (
            f"Heads up: the audit record for that ({outcome_status}) could not be written ({e}). "
            f"This needs attention."
        )

    if audit_result.ok:
        return ""

    if getattr(audit_result, "queued_to_fallback", False):
        return (
            f"Heads up: the audit record for that ({outcome_status}) could not be written "
            f"({audit_result.error}) -- it's queued for retry, not lost. This needs attention."
        )
    return (
        f"Heads up: the audit record for that ({outcome_status}) could not be written or queued "
        f"({audit_result.error}). This needs urgent attention."
    )


def audited_mcp_write(
    *,
    what_adapter: str,
    what_action: str,
    what_target: str,
    why: str,
    source: str,
    call: Callable[[], Any],
) -> AuditedMCPWriteResult:
    """
    Run `call` (an external MCP write) inside DEC-002 audit coverage.

    `call` is a zero-argument callable so this wrapper stays agnostic
    about the client's signature -- it never inspects or transforms the
    payload, which also means the captured content is not copied into
    this module or into any extra field of the record.

    Field values are the caller's responsibility precisely because they
    are not mechanical; see jarvis.py's rhinal_capture branch for a
    worked example with each choice justified.
    """
    blocked_reason = _audit_trail_is_configured()
    if blocked_reason:
        # Tier 1: the write does not happen. `call` is never invoked.
        return AuditedMCPWriteResult(ok=False, blocked_reason=blocked_reason)

    warnings: List[str] = []

    # Record 1: "attempted". Written before anything goes on the wire.
    warnings.append(
        _emit(
            what_adapter=what_adapter,
            what_action=what_action,
            what_target=what_target,
            why=why,
            source=source,
            outcome_status="attempted",
            # ok=None, not False: at this point the outcome is genuinely
            # unknown, and False would read as "it failed" to anyone
            # querying the log.
            outcome_ok=None,
            outcome_error=None,
        )
    )

    try:
        value = call()
    except Exception as e:
        # A failed external write is a real event a compliance reader
        # needs -- audited with the failure outcome, not skipped because
        # "nothing happened". (And per this module's header, a failure
        # return does not actually prove nothing happened remotely.)
        warnings.append(
            _emit(
                what_adapter=what_adapter,
                what_action=what_action,
                what_target=what_target,
                why=why,
                source=source,
                outcome_status="failed",
                outcome_ok=False,
                outcome_error=str(e),
            )
        )
        return AuditedMCPWriteResult(
            ok=False,
            error=e,
            audit_warning=" ".join(w for w in warnings if w),
        )

    warnings.append(
        _emit(
            what_adapter=what_adapter,
            what_action=what_action,
            what_target=what_target,
            why=why,
            source=source,
            outcome_status="success",
            outcome_ok=True,
            outcome_error=None,
        )
    )
    return AuditedMCPWriteResult(
        ok=True,
        value=value,
        audit_warning=" ".join(w for w in warnings if w),
    )

# Companion app — Phase 1 scaffolding

**Status:** built. `AgentCore/comm_gateway/`.
**Scope:** project structure, the auth handshake, and the Session-creation flow. Not feature-complete — no real remote channel, no real Mobile Trust Companion, no T3 write execution.
**Track A only.** Nothing here reaches a real hospital system, real patient data, or a live financial/record-modification action. Stage 0.5 remains independently blocked and this track does not move its gate.

---

## 1. What this builds against

Started from §4.4c as written, with Phase 0's resolutions folded in rather than the original text:

- **Communication Gateway** — the channel-agnostic session boundary. "Session Manager must never know which channel a session originated from."
- **PG-001's mode selection and Capability Negotiation** — Modes A/B/C declared at connect (never inferred, same principle as the Mode C drift-catch gate), producing `(capability set, max tier, confirmation modalities)` fixed for session lifetime.
- **Security Broker's approval-request pattern** — "phone approves, desktop acts" — scaffolded as an interface only.
- **The v3.9 trust-tier resolution** (`docs/trust_tier_clinical_writes.md`) — T0–T3, and specifically that no tier decision may be made silently.

## 2. Package layout

```
AgentCore/comm_gateway/
    audit.py              # reuses AppendOnlyAuditLog, own record shape, own key purpose
    channel.py             # Channel ABC, ChannelIdentity, DesktopChannel, SyntheticRemoteChannel
    deployment_policy.py  # PG-001 "policy is configuration"; STRICT_LOCAL enforced default
    auth.py                # second-factor handshake, fail-closed
    capability.py           # Capability Negotiation: (mode, channel, policy) -> CapabilitySet
    session.py              # Session (channel-opaque), SessionManager (register refuses re-registration)
    gateway.py              # CommunicationGateway.connect(): the one orchestration point
    approval.py             # Security Broker checkpoint table, interface only
AgentCore/policy/comm_gateway_deployment.yaml   # example/default policy file
```

## 3. Channel opacity — enforced structurally, not by convention

`Session` has no `channel` field. Not private, not renamed — absent. Verified by a test that inspects `dataclasses.fields(Session)` directly rather than trusting that no code path happens to read one. `CapabilitySet`, which `Session` embeds, is checked the same way — the opacity guarantee would be trivially defeated one level down otherwise.

The Gateway is the only place channel identity and session identity meet. Its audit log is allowed to know the channel (a compliance record legitimately needs provenance); `SessionManager` and everything downstream of `connect()`'s return value never can.

## 4. Auth handshake

Per §Stage 1c: *"second factor (PIN/pairing), session-based trust with timeout... phone-number identity alone is insufficient."*

- `DesktopChannel.requires_second_factor()` is `False`, stated as a method each channel overrides — not inferred from a `ChannelKind` value at the call site, which is exactly the "don't infer a contract from a name" mistake this project has already been burned by twice (`GeneratorHelper`/`LLMAdapter`, `vaultWorthy`). The reason desktop is exempt is documented in code: there is no remote party to authenticate, and the OS session boundary is the auth boundary, the same honest limit DEC-002's `who` field already states.
- Every other channel requires a second factor verified against `PairingStore`, constant-time compared. No factor, or a wrong one, or a correct factor for a *different* principal, all raise `AuthenticationError` — tested as three distinct adversarial cases, not folded into one.
- `PairingStore` is in-memory and Track-A only. A real pairing mechanism (QR + device-bound token, most likely) replaces it without changing `AuthHandshake`'s contract — that class is the intended seam.
- Session-trust records carry a real expiry (`SessionTrustRecord.is_expired()`), and every authentication failure is audited.

## 5. Capability Negotiation

One entry point, `CapabilityNegotiator.negotiate(channel, declared_mode, policy)`. No incremental "add a capability" method exists anywhere — that absence is deliberate, since a mutation path is exactly what "never renegotiated upward" would need to forbid one at a time instead of by construction.

**STRICT_LOCAL is the enforced default**, both in `deployment_policy.load_deployment_policy()` (a missing policy file defaults to it) and in `DeploymentPolicy`'s own dataclass default (so code that forgets to load a policy still gets the safe value, not an accidentally-permissive one). A remote channel under STRICT_LOCAL still gets a `CapabilitySet` — an empty one, T0 only — rather than a distinguishable refusal, so "a remote channel tried to connect" and "a remote channel connected and got nothing" look identical from outside.

**No channel reaches T3 in this phase**, for all deployment modes, tested exhaustively rather than spot-checked. Not because desktop voice is architecturally excluded from T3 — `docs/trust_tier_clinical_writes.md` names it as one of the two intended confirmation channels — but because the four-invariant-property confirmation mechanism itself (payload-rendered presentation, distinguishing-token consent, bounded validity, silence-is-refusal) isn't built for any channel yet. A channel cannot honestly be marked T3-capable before the thing that would make it honest exists.

**Remote channels cap at T1** (disclosing read), not T2, even under SECURE_REMOTE/HYBRID with remote voice enabled — because nothing built in this phase provides an honest Security-Broker-style approval flow over a remote transport. This is more conservative than the blueprint strictly requires; stated as a phase-scoping choice, not a permanent architectural ceiling.

**"Never renegotiated upward mid-session" is enforced by `SessionManager.register()`**, not only by `CapabilitySet` being a frozen dataclass. A frozen dataclass only stops one instance being mutated; it says nothing about whether a *new*, more permissive `CapabilitySet` could be attached to an *existing* `session_id`. `register()` refuses any re-registration of a session_id that already exists, and the refusal is itself an audited `renegotiation_refused` event — tested by constructing a genuinely stronger `CapabilitySet` and confirming the attempt to attach it to an already-registered session_id fails and the original, weaker session is what remains on file.

## 6. Security Broker — interface only

`ApprovalGate` reproduces §4.4c's checkpoint table verbatim (seven gates). `ApprovalRequest.rendered_description` is required to describe the actual action about to happen, matching the payload-rendering discipline `docs/trust_tier_clinical_writes.md` states for T3, applied here at T2 even though not strictly required at that tier — consistency between the two mechanisms seemed more valuable than the narrower requirement.

`SynchronousTestApprover` is the only implementation. It exists so the approval-request *shape* is exercisable now, and records every request it decided so a test can check what was actually rendered, not only the final boolean. It must never be reachable from any code path outside tests — there is no real Mobile Trust Companion, and building one needs an actual paired device to integrate against.

## 7. What is deliberately not here

- No real remote channel (phone, WhatsApp, Telegram, WebRTC). Stage 1c work, needs real transport integration.
- No T3 confirmation execution, and therefore no extension of `AgentCore/mcp_audit.py`'s three-record pattern to a `t3_confirmation_requested` event — `docs/trust_tier_clinical_writes.md` §6 specifies this but nothing in this phase triggers a real T3 action to confirm.
- No real Mobile Trust Companion / paired device.
- No integration into `jarvis.py`'s live conversation loop. This package is standalone and independently tested; wiring an existing single-channel (desktop voice) loop to be fed by Gateway-issued Sessions is a real architectural decision about the live path, not a scaffolding task, and is left for its own phase.
- No use of `AgentCore.rhinal_mcp_client` or any other real external write. `rhinal_writes` in `CapabilitySet` is a capability *flag* only — nothing in this package calls RHINAL.

## 8. Test isolation, built correctly the first time

`AgentCore/comm_gateway/tests/conftest.py` redirects the audit log directory and pins an explicit key **before** any `AppendOnlyAuditLog` is constructed, via env vars set before the first import that could trigger construction. This session already found the same category of mistake twice — DEC-002's fixture initially used `JARVIS_INSECURE_DEV_KEY`, which writes a real key file into the real repo with no `tmp_path` awareness; D14's own first test draft redirected `log_dir` *after* construction, too late, since `__init__` had already created the real directory. Both are recorded in `JARVIS_EXECUTION_LOG.md`. This fixture is written against that history rather than re-deriving it — verified by confirming `data/comm_gateway/` does not exist in the real repo after a full test run.

## 9. Where a future phase picks this up

- **Real remote channel(s)** — Stage 1c. Each new channel implements `Channel`; nothing else in this package should need to change.
- **Real pairing** — replace `PairingStore` behind `AuthHandshake`'s existing contract.
- **T3 confirmation execution** — a `ConfirmationFlow` module extending `mcp_audit.py`'s pattern to three records (`t3_confirmation_requested` / `attempted` / outcome), gated behind `CapabilitySet.permits(TrustTier.T3_CLINICAL_WRITE)`, which is `False` everywhere today and becomes the thing that flips once a channel genuinely satisfies all four invariant properties.
- **Real Mobile Trust Companion** — a second `ApprovalResponder` implementation talking to a real paired device.
- **Live-loop integration** — its own explicit decision, not implied by this scaffold existing.

"""
PG-001 "policy is configuration, loaded per deployment, not hardcoded
branches" -- applied to the Communication Gateway's deployment mode.

YAML, matching the existing declarative-policy idiom
(AgentCore/policy/ownership_registry.yaml, AgentCore/policy/
adapter_sandbox_dependencies.yaml, feature_flags/*.yaml) rather than a
new format.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

import yaml

POLICY_PATH_ENV_VAR = "JARVIS_COMM_GATEWAY_POLICY_PATH"
DEFAULT_POLICY_PATH = "AgentCore/policy/comm_gateway_deployment.yaml"


class DeploymentMode(Enum):
    STRICT_LOCAL = "strict_local"      # no remote access at all
    SECURE_REMOTE = "secure_remote"    # encrypted remote; compute/storage stay on org infra
    HYBRID = "hybrid"                  # selected cloud services, explicit admin approval


@dataclass(frozen=True)
class DeploymentPolicy:
    """
    `mode` governs whether remote channels may connect at all.
    `remote_voice_enabled` / `patient_identifiers_tokenize` /
    `clinical_notes_allow_remote` are PG-001's own named example fields
    (§4.4c) -- kept as the literal names the blueprint gives them, not
    renamed for this module's convenience, so a deployment YAML written
    against the blueprint's own prose still means the same thing here.
    """
    mode: DeploymentMode = DeploymentMode.STRICT_LOCAL
    remote_voice_enabled: bool = False
    patient_identifiers_tokenize: bool = True
    clinical_notes_allow_remote: bool = False

    def allows_remote_channels(self) -> bool:
        """
        STRICT_LOCAL refuses every remote channel, full stop -- this is
        the enforcement point for "Strict Local Mode should be the
        enforced default until an organization's actual policy authority
        says otherwise, not a config value sitting equal beside the
        others by default" (§4.4c). SECURE_REMOTE/HYBRID both permit
        remote connection attempts; whether a given channel actually gets
        capabilities is still Capability Negotiation's job, not this
        method's.
        """
        return self.mode is not DeploymentMode.STRICT_LOCAL


def load_deployment_policy(path: Optional[os.PathLike] = None) -> DeploymentPolicy:
    """
    Missing file -> STRICT_LOCAL default, not an error. The absence of a
    deployment policy must be the SAFEST state, not a startup failure
    that someone works around by writing a permissive file just to get
    the service running. A present-but-malformed file still fails loudly
    (surfaces the real YAML error) rather than silently falling back --
    the difference is "no policy was ever configured" versus "someone
    configured one and it's broken."
    """
    resolved = Path(path or os.environ.get(POLICY_PATH_ENV_VAR, DEFAULT_POLICY_PATH))
    if not resolved.exists():
        return DeploymentPolicy()

    raw = yaml.safe_load(resolved.read_text(encoding="utf-8")) or {}
    mode_value = raw.get("mode", DeploymentMode.STRICT_LOCAL.value)
    try:
        mode = DeploymentMode(mode_value)
    except ValueError as e:
        raise ValueError(
            f"{resolved}: unknown deployment mode {mode_value!r}, "
            f"expected one of {[m.value for m in DeploymentMode]}"
        ) from e

    return DeploymentPolicy(
        mode=mode,
        remote_voice_enabled=bool(raw.get("remote_voice", {}).get("enabled", False)),
        patient_identifiers_tokenize=bool(
            raw.get("patient_identifiers", {}).get("tokenize", True)
        ),
        clinical_notes_allow_remote=bool(
            raw.get("clinical_notes", {}).get("allow_remote", False)
        ),
    )

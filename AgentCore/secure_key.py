"""
Shared key resolution for at-rest protection (D2).

memory_store.py's XOR "encryption" and mode_manager/audit.py's HMAC
signing key shared the identical weakness: a hardcoded/env-fallback
insecure default key (`"jarvis_default_key"`, `b"dev_insecure_key_default"`)
that every real caller silently used, because no real caller ever
passed a key of its own. Fixed together, sharing this one
implementation, so the two call sites can't drift out of sync on
security-critical logic.

Three explicit, non-fallback-chained sources. Exactly one is chosen
per process; failure in the chosen source is a hard error, never a
silent slide into a weaker one -- that silent-degrade shape is
precisely what D2 already was.

1. JARVIS_INSECURE_DEV_KEY=1 -- explicit dev opt-in. Reads/creates a
   local key file, logs a loud warning at every startup while active.
   Never the default; must be deliberately set.
2. A purpose-specific env var (e.g. JARVIS_MEMORY_KEY, JARVIS_HMAC_KEY),
   explicitly set -- honored, logs loudly that a non-keyring source is
   active. For CI/containers/machines where the OS keyring genuinely
   isn't usable -- a deliberate choice by whoever set it.
3. Default, zero configuration: the OS keyring (Windows Credential
   Manager via the `keyring` package), generated once on first run if
   no key exists yet. If keyring access itself fails for any reason,
   that is a startup error -- refuses to start, explains why, and does
   NOT fall through to the env var or file path automatically.

If more than one source is configured at once, that's treated as
ambiguous configuration and refused outright -- never silently
resolved by picking one.
"""
import base64
import os
import secrets
import sys
from pathlib import Path
from typing import Optional


class KeyConfigurationError(Exception):
    """
    Raised whenever a real key cannot be resolved, or the configuration
    is ambiguous. Callers must let this propagate -- fail closed. Never
    catch this and substitute an insecure default; that reintroduces
    exactly the weakness this module exists to close.
    """


def resolve_key(
    purpose: str,
    env_var_name: str,
    key_bytes: int = 32,
    dev_key_env_var: str = "JARVIS_INSECURE_DEV_KEY",
    dev_key_dir: Optional[Path] = None,
) -> bytes:
    """
    Resolve a real key for `purpose` (used in log/error messages and as
    the OS keyring account name) from exactly one of the three sources
    above. Raises KeyConfigurationError on any failure -- there is no
    return value that means "insecure default, proceed anyway."
    """
    dev_opt_in = os.environ.get(dev_key_env_var) == "1"
    env_key = os.environ.get(env_var_name)

    if dev_opt_in and env_key:
        raise KeyConfigurationError(
            f"[{purpose}] Ambiguous key configuration: both {dev_key_env_var}=1 and "
            f"{env_var_name} are set. Choose exactly one key source -- refusing to "
            f"silently pick one over the other."
        )

    if dev_opt_in:
        print(
            f"*** [{purpose}] INSECURE DEV KEY IN USE ({dev_key_env_var}=1) -- this is "
            f"not a real key. Never set this outside local development. ***",
            file=sys.stderr,
        )
        return _dev_file_key(purpose, dev_key_dir, key_bytes)

    if env_key:
        print(
            f"[{purpose}] Using the key from environment variable {env_var_name}, not "
            f"the OS keyring. Confirm this is intentional for this deployment.",
            file=sys.stderr,
        )
        return _decode_env_key(purpose, env_var_name, env_key, key_bytes)

    return _keyring_key(purpose, env_var_name, key_bytes)


def _dev_file_key(purpose: str, dev_key_dir: Optional[Path], key_bytes: int) -> bytes:
    directory = dev_key_dir or (Path(__file__).resolve().parent.parent / "data" / "dev_keys")
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{purpose}.key"
    if path.exists():
        key = path.read_bytes()
        if len(key) != key_bytes:
            raise KeyConfigurationError(
                f"[{purpose}] Dev key file {path} is {len(key)} bytes, expected {key_bytes} "
                f"-- delete it to regenerate, or it was written by an incompatible version."
            )
        return key
    key = secrets.token_bytes(key_bytes)
    path.write_bytes(key)
    return key


def _decode_env_key(purpose: str, env_var_name: str, env_key: str, key_bytes: int) -> bytes:
    try:
        key = base64.b64decode(env_key, validate=True)
    except Exception as e:
        raise KeyConfigurationError(
            f"[{purpose}] {env_var_name} is not valid base64: {e}"
        ) from e
    if len(key) != key_bytes:
        raise KeyConfigurationError(
            f"[{purpose}] {env_var_name} decodes to {len(key)} bytes, expected {key_bytes} "
            f"-- generate a key with secrets.token_bytes({key_bytes}) and base64-encode it."
        )
    return key


def _keyring_key(purpose: str, env_var_name: str, key_bytes: int) -> bytes:
    try:
        import keyring
    except ImportError as e:
        raise KeyConfigurationError(
            f"[{purpose}] No key source configured, and the 'keyring' package is not "
            f"installed -- cannot use the OS keyring default. Install 'keyring', set "
            f"{env_var_name} explicitly, or set JARVIS_INSECURE_DEV_KEY=1 for local dev "
            f"only."
        ) from e

    service = "jarvis"
    account = f"{purpose}_key"

    try:
        existing = keyring.get_password(service, account)
    except Exception as e:
        raise KeyConfigurationError(
            f"[{purpose}] OS keyring access failed ({e}) -- refusing to fall back to an "
            f"env var or file automatically. Fix keyring access, or explicitly set "
            f"{env_var_name} / JARVIS_INSECURE_DEV_KEY=1 to choose a different source."
        ) from e

    if existing:
        try:
            key = base64.b64decode(existing, validate=True)
        except Exception as e:
            raise KeyConfigurationError(
                f"[{purpose}] The value stored in the OS keyring is corrupt: {e}"
            ) from e
        if len(key) != key_bytes:
            raise KeyConfigurationError(
                f"[{purpose}] The key stored in the OS keyring is {len(key)} bytes, "
                f"expected {key_bytes}."
            )
        return key

    key = secrets.token_bytes(key_bytes)
    try:
        keyring.set_password(service, account, base64.b64encode(key).decode())
    except Exception as e:
        raise KeyConfigurationError(
            f"[{purpose}] Generated a new key but failed to store it in the OS keyring "
            f"({e}) -- refusing to proceed with a key that would be lost on restart."
        ) from e

    print(f"[{purpose}] Generated and stored a new key in the OS keyring.", file=sys.stderr)
    return key

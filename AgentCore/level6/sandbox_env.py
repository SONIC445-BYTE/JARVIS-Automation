"""
Provisioning of the adapter-generation sandbox's Python environment, and
enforcement of the vetted dependency set (D18, and the Phase 0 decision
recorded in AgentCore/policy/adapter_sandbox_dependencies.yaml).

WHAT IS GENUINELY ENFORCED HERE
-------------------------------
1. A SEPARATE INTERPRETER. The sandbox does not run the host interpreter.
   `provision()` builds a standalone Python tree -- python.exe, the runtime
   DLLs, DLLs/, and the standard library -- with an EMPTY site-packages. The
   child's `sys.prefix` genuinely differs from the host's, and every host
   third-party package is genuinely not importable. That is checkable, and
   `test_sandbox_isolation.py` checks it against a package that really is
   installed on the host.

2. THE VETTED SET, BY CONSTRUCTION. site-packages is then populated ONLY from
   the manifest's `layer: image` entries plus their resolved runtime
   dependency closure, copied from the host's own installation. There is no
   index, no pip, and no network in the provisioning path -- which is the
   manifest's "pre-staged, not proxied" decision implemented rather than
   described. A package outside the set is absent because it was never copied,
   not because something refused to import it.

3. FAIL CLOSED BEFORE EXECUTION. `check_imports()` AST-scans the generated
   files and refuses the run, with the diagnostic from the design note, if any
   import resolves outside the vetted set. Nothing executes first.

WHAT IS NOT ENFORCED HERE, STATED PLAINLY
-----------------------------------------
* NO HASH PINNING, NO PROVENANCE. The manifest specifies a digest-pinned base
  image and a `pip install --require-hashes` lockfile. Neither exists, because
  neither is possible without a container runtime. Packages are copied from
  whatever the host has installed. The sandbox therefore inherits the host's
  supply chain exactly as-is; this reduces what is REACHABLE from generated
  code, and does nothing whatsoever for supply-chain integrity. The manifest's
  residual-risk section 8.2 is unchanged and unaddressed.
* VERSION DRIFT IS REAL AND RECORDED, NOT PREVENTED. The manifest's `version`
  fields are a starting point resolved on 2026-08-12. `provision()` records
  what it ACTUALLY copied in `_provisioned.json` and flags any mismatch. It
  does not fail on a mismatch, because the host is the only available source.
* DEPENDENCY CURATION IS NOT CAPABILITY RESTRICTION. `socket`, `subprocess`
  and `urllib.request` are standard library and are present. Curating
  third-party packages removes the fetch path and the supply-chain surface. It
  does not reduce what generated code can attempt. Egress is denied by the
  AppContainer in sandbox_isolation.py or it is not denied at all.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.metadata as md
import json
import os
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = REPO_ROOT / "AgentCore" / "policy" / "adapter_sandbox_dependencies.yaml"

# Directories under the host stdlib that the sandbox has no use for. `test` is
# the CPython test suite (~30MB and full of network/subprocess exercisers),
# tkinter/idlelib need a display the sandbox does not have, and ensurepip would
# put a package installer inside a sandbox whose entire dependency policy is
# "no installer at runtime".
_STDLIB_SKIP = {
    "site-packages", "__pycache__", "test", "idlelib", "tkinter",
    "turtledemo", "lib2to3", "ensurepip", "venv",
}

# Import names that differ from the distribution name and are not reliably
# discoverable from metadata. Anything resolvable from `top_level.txt` is
# resolved from there instead; this map is the fallback for the rest.
_FALLBACK_IMPORT_NAMES = {
    "pillow": ["PIL"],
    "beautifulsoup4": ["bs4"],
    "opencv-python-headless": ["cv2"],
    "opencv-python": ["cv2"],
    "pyyaml": ["yaml"],
    "pywin32": ["win32api", "win32con", "win32gui", "win32process", "win32security",
                "win32job", "win32file", "win32event", "pywintypes", "win32com",
                "win32clipboard"],
    "pytest": ["pytest", "_pytest", "py"],
}


def _norm(name: str) -> str:
    return name.lower().replace("_", "-").replace(".", "-")


# --------------------------------------------------------------------------
# Manifest
# --------------------------------------------------------------------------

@dataclass
class Manifest:
    path: Path
    raw: Dict[str, Any]

    @property
    def image_packages(self) -> List[Dict[str, Any]]:
        return [p for p in self.raw.get("packages") or []
                if p.get("layer") == "image"]

    @property
    def host_mocked_packages(self) -> List[Dict[str, Any]]:
        return [p for p in self.raw.get("packages") or []
                if p.get("layer") == "host_mocked"]

    @property
    def refused(self) -> Dict[str, str]:
        return {_norm(r["name"]): (r.get("reason") or "").strip()
                for r in self.raw.get("refused") or []}

    def digest(self) -> str:
        return hashlib.sha256(self.path.read_bytes()).hexdigest()[:12]


def load_manifest(path: Optional[os.PathLike] = None) -> Manifest:
    p = Path(path or DEFAULT_MANIFEST)
    if yaml is None:
        raise RuntimeError("PyYAML unavailable on the host; cannot read the "
                           "sandbox dependency manifest")
    with open(p, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    return Manifest(path=p, raw=raw)


def declared_import_names(entry: Dict[str, Any]) -> List[str]:
    """Import names for a manifest entry.

    Preference order: an explicit `import_names:` in the manifest, then the
    installed distribution's own top_level.txt, then the fallback map, then the
    distribution name itself. Explicit-first matters because the manifest is
    the reviewed artifact -- the thing a human signed off on -- and a name
    inferred from host metadata is not.
    """
    if entry.get("import_names"):
        return list(entry["import_names"])
    name = entry["name"]
    tl = _top_level_from_host(name)
    if tl:
        return tl
    return _FALLBACK_IMPORT_NAMES.get(_norm(name), [name.replace("-", "_")])


def _top_level_from_host(dist_name: str) -> List[str]:
    try:
        dist = md.distribution(dist_name)
    except Exception:
        return []
    try:
        txt = dist.read_text("top_level.txt")
        if txt:
            return [l.strip() for l in txt.splitlines() if l.strip()]
    except Exception:
        pass
    names: Set[str] = set()
    for f in dist.files or []:
        parts = Path(str(f)).parts
        if not parts or parts[0].startswith(".."):
            continue
        head = parts[0]
        if head.endswith((".dist-info", ".egg-info", ".pth")):
            continue
        names.add(head[:-3] if head.endswith(".py") else head)
    return sorted(names)


# --------------------------------------------------------------------------
# Dependency closure, resolved from host metadata
# --------------------------------------------------------------------------

def _requirements(dist_name: str) -> List[str]:
    """Runtime requirements of an installed distribution, markers evaluated.

    Requirements guarded by an `extra == ...` marker are excluded: those are
    optional extras, and the sandbox installs no extras. Markers are evaluated
    against the *host* environment, which is legitimate here only because the
    sandbox runs on the same OS and Python version as the host -- unlike the
    manifest's linux/amd64 image, where they would need re-evaluating.
    """
    try:
        dist = md.distribution(dist_name)
    except Exception:
        return []
    out: List[str] = []
    for req in dist.requires or []:
        try:
            from packaging.requirements import Requirement
            r = Requirement(req)
            if r.marker is not None:
                if "extra" in str(r.marker):
                    continue
                if not r.marker.evaluate():
                    continue
            out.append(r.name)
        except Exception:
            base = req.split(";")[0].strip()
            for sep in ("==", ">=", "<=", "~=", "!=", ">", "<", "[", "("):
                base = base.split(sep)[0]
            base = base.strip()
            if base:
                out.append(base)
    return out


def resolve_closure(roots: Sequence[str]) -> Tuple[List[str], List[str]]:
    """Transitive runtime closure of `roots` over installed host metadata.

    Returns (resolved, missing). `missing` is the honest half: a manifest entry
    the host does not have cannot be provisioned, and the caller must not
    substitute something similar. `opencv-python-headless` is the live example
    -- the manifest names the headless build deliberately, the host has the GUI
    build, and these are different distributions.
    """
    seen: Dict[str, None] = {}
    missing: List[str] = []
    stack = list(roots)
    while stack:
        name = stack.pop()
        key = _norm(name)
        if key in seen:
            continue
        try:
            md.distribution(name)
        except Exception:
            if key not in [_norm(m) for m in missing]:
                missing.append(name)
            continue
        seen[key] = None
        for dep in _requirements(name):
            if _norm(dep) not in seen:
                stack.append(dep)
    return list(seen.keys()), missing


def _canonical_dist(name: str):
    return md.distribution(name)


def _copy_distribution(name: str, site_packages: Path) -> Dict[str, Any]:
    """Copy one installed distribution's files into the sandbox site-packages."""
    dist = _canonical_dist(name)
    base = Path(dist.locate_file(""))
    copied = 0
    skipped_outside = 0
    files = dist.files or []
    for rel in files:
        rel_s = str(rel)
        if rel_s.startswith("..") or Path(rel_s).is_absolute():
            # Entry-point scripts and data files live outside site-packages
            # (../../Scripts/pytest.exe). The sandbox invokes modules with
            # `-m`, never console scripts, so these are deliberately not
            # copied -- and a console script is an executable the sandbox
            # would otherwise gain for free.
            skipped_outside += 1
            continue
        src = base / rel_s
        if not src.exists():
            continue
        if "__pycache__" in Path(rel_s).parts:
            continue
        dst = site_packages / rel_s
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(src, dst)
            copied += 1
        except OSError:
            pass
    return {
        "name": dist.metadata["Name"] or name,
        "version": dist.version,
        "files_copied": copied,
        "files_skipped_outside_site_packages": skipped_outside,
    }


# --------------------------------------------------------------------------
# Provisioning
# --------------------------------------------------------------------------

@dataclass
class SandboxEnv:
    root: Path
    python_exe: Path
    site_packages: Path
    allowed_imports: Set[str]
    refused: Dict[str, str]
    provisioned: Dict[str, Any]
    unavailable: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.python_exe.exists()


def _build_interpreter(dest: Path) -> None:
    base = Path(sys.prefix)
    dest.mkdir(parents=True, exist_ok=True)
    for fname in ("python.exe", "pythonw.exe", "python3.dll",
                  f"python{sys.version_info.major}{sys.version_info.minor}.dll",
                  "vcruntime140.dll", "vcruntime140_1.dll"):
        src = base / fname
        if src.exists():
            shutil.copy2(src, dest / fname)
    if (base / "DLLs").exists():
        shutil.copytree(base / "DLLs", dest / "DLLs",
                        ignore=shutil.ignore_patterns("__pycache__"),
                        dirs_exist_ok=True)
    shutil.copytree(
        base / "Lib", dest / "Lib",
        ignore=lambda d, names: [n for n in names if n in _STDLIB_SKIP],
        dirs_exist_ok=True)
    (dest / "Lib" / "site-packages").mkdir(parents=True, exist_ok=True)


_MOCK_STUB = '''"""Auto-generated sandbox stub for `{mod}` (manifest layer: host_mocked).

NOT the real module. `{dist}` is Windows-only or display-only; the manifest
records that the sandbox satisfies it with a double and that real behaviour is
verified on the host, outside the sandbox, by the developer.

A test that passes against this stub has exercised the generated adapter's
control flow and contract conformance. It has NOT verified that the adapter
does anything correct on a real screen. Do not read a green sandbox run as
"tested on Windows".
"""
import sys as _sys
from unittest.mock import MagicMock as _MagicMock


class _SandboxStub(_MagicMock):
    __sandbox_stub__ = True
    __module_name__ = {mod!r}


_sys.modules[__name__] = _SandboxStub(name={mod!r})
'''


def provision(manifest: Optional[Manifest] = None,
              cache_root: Optional[os.PathLike] = None,
              force: bool = False) -> SandboxEnv:
    """Build (or reuse) the sandbox interpreter + vetted site-packages.

    Cached by a digest over the manifest, the host Python version, and the
    resolved versions of the vetted packages -- so editing the manifest or
    upgrading a host package reprovisions rather than silently reusing an
    environment that no longer matches what the manifest says.
    """
    man = manifest or load_manifest()
    roots = [p["name"] for p in man.image_packages]
    resolved, missing = resolve_closure(roots)

    versions = {}
    for n in resolved:
        try:
            versions[n] = md.version(n)
        except Exception:
            versions[n] = "?"

    key = hashlib.sha256(json.dumps({
        "manifest": man.digest(),
        "python": sys.version,
        "prefix": sys.prefix,
        "versions": versions,
        "schema": 3,
    }, sort_keys=True).encode()).hexdigest()[:16]

    cache_root = Path(cache_root or (REPO_ROOT / "projects" / ".sandbox_env"))
    root = cache_root / key
    stamp = root / "_provisioned.json"

    if stamp.exists() and not force:
        try:
            with open(stamp, "r", encoding="utf-8") as fh:
                rec = json.load(fh)
            env = _env_from_record(root, man, rec)
            if env.ok:
                return env
        except Exception:
            shutil.rmtree(root, ignore_errors=True)

    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    _build_interpreter(root)
    site_packages = root / "Lib" / "site-packages"

    copied: List[Dict[str, Any]] = []
    failed: List[Dict[str, str]] = []
    for name in resolved:
        try:
            copied.append(_copy_distribution(name, site_packages))
        except Exception as exc:
            failed.append({"name": name, "error": f"{type(exc).__name__}: {exc}"})

    # host_mocked layer -> generated stubs, never the real module.
    mocks: List[str] = []
    for entry in man.host_mocked_packages:
        for mod in declared_import_names(entry):
            target = site_packages / f"{mod}.py"
            if target.exists():
                continue
            target.write_text(_MOCK_STUB.format(mod=mod, dist=entry["name"]),
                              encoding="utf-8")
            mocks.append(mod)

    # Version drift against the manifest's recorded expectations.
    drift = []
    by_norm = {_norm(c["name"]): c for c in copied}
    for entry in man.image_packages:
        want = entry.get("version")
        got = by_norm.get(_norm(entry["name"]), {}).get("version")
        if want and got and str(want) != str(got):
            drift.append({"package": entry["name"], "manifest": want, "provisioned": got})

    record = {
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "elapsed_sec": round(time.time() - t0, 2),
        "manifest_path": str(man.path),
        "manifest_digest": man.digest(),
        "host_python": sys.version,
        "host_prefix": sys.prefix,
        "roots": roots,
        "closure": copied,
        "closure_failed": failed,
        "unavailable_on_host": missing,
        "host_mocked_stubs": sorted(mocks),
        "version_drift_vs_manifest": drift,
        "not_claimed": [
            "No hash pinning: packages are copied from the host installation, "
            "not fetched with --require-hashes from an index. Supply-chain "
            "integrity is exactly the host's.",
            "No digest-pinned base image: there is no image and no container "
            "runtime on this machine.",
        ],
    }
    with open(stamp, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2)

    _prune_stale(cache_root, keep=key)
    return _env_from_record(root, man, record)


def _prune_stale(cache_root: Path, keep: str) -> None:
    """Delete previously-provisioned environments other than the current one.

    Each environment is ~200MB (playwright and numpy dominate), and the cache
    key includes the manifest digest and every resolved package version -- so
    editing the manifest or upgrading any host package strands the previous
    tree. Without pruning, routine dependency work silently accumulates
    hundreds of megabytes per change under projects/.
    """
    try:
        for child in cache_root.iterdir():
            if child.name == keep or not child.is_dir():
                continue
            # Only ever delete directories this module created.
            if (child / "_provisioned.json").exists():
                shutil.rmtree(child, ignore_errors=True)
    except OSError:
        pass


def _env_from_record(root: Path, man: Manifest, rec: Dict[str, Any]) -> SandboxEnv:
    site_packages = root / "Lib" / "site-packages"
    allowed: Set[str] = set(sys.stdlib_module_names)
    allowed.discard("this")
    allowed.discard("antigravity")

    for entry in man.image_packages:
        if _norm(entry["name"]) in {_norm(m) for m in rec.get("unavailable_on_host", [])}:
            continue
        allowed.update(declared_import_names(entry))
    for entry in man.host_mocked_packages:
        allowed.update(declared_import_names(entry))
    # Transitive dependencies were genuinely copied in, so they are genuinely
    # importable; the allow-list must say so or the static check would block an
    # import that would in fact succeed -- a false diagnostic is its own defect.
    for item in rec.get("closure", []):
        for n in _top_level_from_host(item["name"]) or [item["name"]]:
            allowed.add(n)
    for mod in rec.get("host_mocked_stubs", []):
        allowed.add(mod)

    return SandboxEnv(
        root=root,
        python_exe=root / "python.exe",
        site_packages=site_packages,
        allowed_imports=allowed,
        refused=man.refused,
        provisioned=rec,
        unavailable=list(rec.get("unavailable_on_host", [])),
    )


# --------------------------------------------------------------------------
# Static import check -- fail closed, before anything executes
# --------------------------------------------------------------------------

@dataclass
class ImportViolation:
    module: str
    file: str
    line: int
    reason: str


def _iter_imports(source: str) -> Iterable[Tuple[str, int]]:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name.split(".")[0], node.lineno
        elif isinstance(node, ast.ImportFrom):
            if node.level:      # relative import -- resolves inside the sandbox
                continue
            if node.module:
                yield node.module.split(".")[0], node.lineno


def check_imports(files: Dict[str, str],
                  env: SandboxEnv,
                  local_modules: Optional[Set[str]] = None
                  ) -> List[ImportViolation]:
    """AST-scan generated sources for imports outside the vetted set.

    Runs BEFORE execution, which is the point: the developer gets a precise
    diagnostic naming the package and the import site rather than an
    ImportError buried in pytest output, and nothing has run by the time the
    block is recorded.

    HONEST LIMITATION, because this is exactly the kind of thing D18 punishes:
    this is a STATIC check and it is trivially evadable by design --
    `__import__(base64.b64decode(...))` or `importlib.import_module(name)` are
    not detected. It is a developer-facing diagnostic and a policy tripwire. It
    is NOT the boundary, and it must never be described as one. The boundary is
    that the package is genuinely absent from the sandbox's site-packages, so
    an evasive import fails at runtime anyway.
    """
    local = set(local_modules or ())
    violations: List[ImportViolation] = []
    for path, source in files.items():
        try:
            imports = list(_iter_imports(source))
        except SyntaxError as exc:
            violations.append(ImportViolation(
                module="<syntax>", file=path, line=exc.lineno or 0,
                reason=f"could not parse to check imports: {exc}"))
            continue
        for mod, lineno in imports:
            if mod in local or mod in env.allowed_imports:
                continue
            key = _norm(mod)
            reason = None
            for refused_name, why in env.refused.items():
                if key == refused_name or mod in _FALLBACK_IMPORT_NAMES.get(refused_name, []):
                    reason = (f"on the manifest's refused list -- "
                              f"{' '.join(why.split())[:200]}")
                    break
            if reason is None:
                if any(_norm(u) == key or mod in _FALLBACK_IMPORT_NAMES.get(_norm(u), [])
                       for u in env.unavailable):
                    reason = ("vetted in the manifest but NOT installed on this "
                              "host, so it could not be provisioned; the sandbox "
                              "does not substitute a similar package")
                else:
                    reason = "not in the vetted set; not on the refused list"
            violations.append(ImportViolation(mod, path, lineno, reason))
    return violations


def format_block(violations: Sequence[ImportViolation],
                 env: SandboxEnv,
                 ledger_entries: Sequence[str] = (),
                 tried: str = "(not reported by the generator)") -> str:
    """The one-block diagnostic from docs/adapter_sandbox_dependencies.md section 6."""
    lines = ["BLOCKED: adapter generation halted on an unvetted import.", ""]
    for v in violations:
        lines.append(f"  file:      {v.file}")
        lines.append(f"  import:    line {v.line}  ->  {v.module}")
        lines.append(f"  resolves:  {v.module} ({v.reason})")
    lines.append(f"  triggered: {', '.join(ledger_entries) if ledger_entries else '(no ledger provenance supplied)'}")
    lines.append(f"  tried:     {tried}")
    lines += [
        "",
        "  The sandbox did not install anything, did not retry, and did not",
        "  reach the network. Nothing was executed.",
        "",
        f"  Vetted set: {env.provisioned.get('manifest_path')}",
        "  To escalate: add a reviewed entry with `review_by` and `justified_by`.",
    ]
    return "\n".join(lines)

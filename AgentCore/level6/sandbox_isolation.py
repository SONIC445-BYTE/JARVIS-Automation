"""
OS-enforced containment for the Level6 adapter-generation sandbox (D18).

WHAT THIS IS, PRECISELY
-----------------------
This module launches a child process on Windows inside three stacked,
*OS-enforced* boundaries, and measures that they hold rather than asserting it:

  1. AppContainer  -- a LowBox token with NO capabilities. Windows denies the
     process every filesystem object that does not carry an explicit ACE for
     the AppContainer's own SID (or for ALL APPLICATION PACKAGES), and the
     Windows Filtering Platform denies it all network sockets because it holds
     neither `internetClient` nor `privateNetworkClientServer`.
  2. Restricted token -- the caller's own primary token with the caller's user
     SID marked SE_GROUP_USE_FOR_DENY_ONLY and all privileges except
     SeChangeNotifyPrivilege deleted. The user's profile ACLs grant the user
     SID; deny-only means those grants no longer apply to the child.
  3. Job object -- kill-on-job-close, an active-process cap, a per-process
     memory cap, a per-process CPU-time cap, and UI restrictions.

WHAT THIS IS NOT
----------------
This is NOT a container and NOT a VM. There is no separate kernel, no separate
filesystem namespace, and no separate network stack. A kernel-level or
WFP-level vulnerability defeats all three layers at once. Per JARVIS_BLUEPRINT
4.4b the ResolutionGate remains the primary control; this is defence-in-depth.

Everything above is verifiable and is verified -- see `verify_containment()`,
which runs a real child that actively attempts each escape and reports what
actually happened. Nothing in this module reports a boundary it has not
measured. That property is the entire point of D18: the defect being fixed was
an environment variable shaped like a network control that nothing read.

NON-ADMIN. Every mechanism here works as a standard user. None of it requires
Administrator, a container runtime, WSL, or Windows Sandbox -- none of which
exist on the target machine.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

# --------------------------------------------------------------------------
# Availability. Import failures are recorded, never swallowed -- a missing
# dependency must surface as "this boundary is absent", not as a silent pass.
# --------------------------------------------------------------------------

_IMPORT_ERRORS: Dict[str, str] = {}

try:
    import win32api
    import win32con
    import win32job
    import win32security
    _HAVE_PYWIN32 = True
except Exception as exc:  # pragma: no cover - environment dependent
    _HAVE_PYWIN32 = False
    _IMPORT_ERRORS["pywin32"] = f"{type(exc).__name__}: {exc}"

_IS_WINDOWS = os.name == "nt"

if _IS_WINDOWS:
    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    try:
        _userenv = ctypes.WinDLL("userenv", use_last_error=True)
    except Exception as exc:  # pragma: no cover
        _userenv = None
        _IMPORT_ERRORS["userenv"] = f"{type(exc).__name__}: {exc}"
else:  # pragma: no cover - the project targets Windows
    _k32 = _advapi = _userenv = None


# --------------------------------------------------------------------------
# Win32 declarations.
#
# argtypes/restype are declared for EVERY function used. ctypes defaults a
# return value to C `int`, which truncates a 64-bit HANDLE or PSID to 32 bits
# and produces a corrupt pointer that "works" until it doesn't. On a security
# boundary a silently truncated SID would mean launching with the wrong token.
# --------------------------------------------------------------------------

PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES = 0x00020009
PROC_THREAD_ATTRIBUTE_HANDLE_LIST = 0x00020002
EXTENDED_STARTUPINFO_PRESENT = 0x00080000
CREATE_NO_WINDOW = 0x08000000
CREATE_SUSPENDED = 0x00000004
CREATE_UNICODE_ENVIRONMENT = 0x00000400
CREATE_BREAKAWAY_FROM_JOB = 0x01000000
STARTF_USESTDHANDLES = 0x00000100
WAIT_TIMEOUT = 0x00000102
STILL_ACTIVE = 259
HANDLE_FLAG_INHERIT = 0x00000001
GENERIC_ALL = 0x10000000
GENERIC_READ = 0x80000000
FILE_SHARE_READ = 0x1
FILE_SHARE_WRITE = 0x2
OPEN_EXISTING = 3
CREATE_ALWAYS = 2
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

OBJECT_INHERIT_ACE = 0x1
CONTAINER_INHERIT_ACE = 0x2

# S-1-5-32-545 BUILTIN\Users -- the group the restricted token retains once the
# user's own SID is deny-only. Sandbox directories are ACL'd for it so the
# restricted child can reach its own workspace and nothing else in the profile.
SID_BUILTIN_USERS = "S-1-5-32-545"
SID_LOCAL_SYSTEM = "S-1-5-18"


class _SID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Sid", ctypes.c_void_p), ("Attributes", wt.DWORD)]


class SECURITY_CAPABILITIES(ctypes.Structure):
    _fields_ = [
        ("AppContainerSid", ctypes.c_void_p),
        ("Capabilities", ctypes.POINTER(_SID_AND_ATTRIBUTES)),
        ("CapabilityCount", wt.DWORD),
        ("Reserved", wt.DWORD),
    ]


class STARTUPINFOW(ctypes.Structure):
    _fields_ = [
        ("cb", wt.DWORD), ("lpReserved", wt.LPWSTR), ("lpDesktop", wt.LPWSTR),
        ("lpTitle", wt.LPWSTR), ("dwX", wt.DWORD), ("dwY", wt.DWORD),
        ("dwXSize", wt.DWORD), ("dwYSize", wt.DWORD), ("dwXCountChars", wt.DWORD),
        ("dwYCountChars", wt.DWORD), ("dwFillAttribute", wt.DWORD),
        ("dwFlags", wt.DWORD), ("wShowWindow", wt.WORD), ("cbReserved2", wt.WORD),
        ("lpReserved2", ctypes.c_void_p), ("hStdInput", wt.HANDLE),
        ("hStdOutput", wt.HANDLE), ("hStdError", wt.HANDLE),
    ]


class STARTUPINFOEXW(ctypes.Structure):
    _fields_ = [("StartupInfo", STARTUPINFOW), ("lpAttributeList", ctypes.c_void_p)]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [("hProcess", wt.HANDLE), ("hThread", wt.HANDLE),
                ("dwProcessId", wt.DWORD), ("dwThreadId", wt.DWORD)]


def _declare() -> None:
    if not _IS_WINDOWS:  # pragma: no cover
        return
    _k32.CreateProcessW.restype = wt.BOOL
    _k32.CreateProcessW.argtypes = [
        wt.LPCWSTR, wt.LPWSTR, ctypes.c_void_p, ctypes.c_void_p, wt.BOOL,
        wt.DWORD, ctypes.c_void_p, wt.LPCWSTR,
        ctypes.POINTER(STARTUPINFOEXW), ctypes.POINTER(PROCESS_INFORMATION)]
    _advapi.CreateProcessAsUserW.restype = wt.BOOL
    _advapi.CreateProcessAsUserW.argtypes = [
        wt.HANDLE, wt.LPCWSTR, wt.LPWSTR, ctypes.c_void_p, ctypes.c_void_p,
        wt.BOOL, wt.DWORD, ctypes.c_void_p, wt.LPCWSTR,
        ctypes.POINTER(STARTUPINFOEXW), ctypes.POINTER(PROCESS_INFORMATION)]
    _k32.InitializeProcThreadAttributeList.restype = wt.BOOL
    _k32.InitializeProcThreadAttributeList.argtypes = [
        ctypes.c_void_p, wt.DWORD, wt.DWORD, ctypes.POINTER(ctypes.c_size_t)]
    _k32.UpdateProcThreadAttribute.restype = wt.BOOL
    _k32.UpdateProcThreadAttribute.argtypes = [
        ctypes.c_void_p, wt.DWORD, ctypes.c_size_t, ctypes.c_void_p,
        ctypes.c_size_t, ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t)]
    _k32.DeleteProcThreadAttributeList.restype = None
    _k32.DeleteProcThreadAttributeList.argtypes = [ctypes.c_void_p]
    _k32.WaitForSingleObject.restype = wt.DWORD
    _k32.WaitForSingleObject.argtypes = [wt.HANDLE, wt.DWORD]
    _k32.GetExitCodeProcess.restype = wt.BOOL
    _k32.GetExitCodeProcess.argtypes = [wt.HANDLE, ctypes.POINTER(wt.DWORD)]
    _k32.CloseHandle.restype = wt.BOOL
    _k32.CloseHandle.argtypes = [wt.HANDLE]
    _k32.ResumeThread.restype = wt.DWORD
    _k32.ResumeThread.argtypes = [wt.HANDLE]
    _k32.TerminateProcess.restype = wt.BOOL
    _k32.TerminateProcess.argtypes = [wt.HANDLE, wt.UINT]
    _k32.CreateFileW.restype = wt.HANDLE
    _k32.CreateFileW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD, ctypes.c_void_p,
                                 wt.DWORD, wt.DWORD, wt.HANDLE]
    _k32.SetHandleInformation.restype = wt.BOOL
    _k32.SetHandleInformation.argtypes = [wt.HANDLE, wt.DWORD, wt.DWORD]
    _advapi.ConvertSidToStringSidW.restype = wt.BOOL
    _advapi.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p,
                                               ctypes.POINTER(wt.LPWSTR)]
    _advapi.ConvertStringSidToSidW.restype = wt.BOOL
    _advapi.ConvertStringSidToSidW.argtypes = [wt.LPCWSTR,
                                               ctypes.POINTER(ctypes.c_void_p)]
    if _userenv is not None:
        _userenv.CreateAppContainerProfile.restype = ctypes.c_long
        _userenv.CreateAppContainerProfile.argtypes = [
            wt.LPCWSTR, wt.LPCWSTR, wt.LPCWSTR,
            ctypes.POINTER(_SID_AND_ATTRIBUTES), wt.DWORD,
            ctypes.POINTER(ctypes.c_void_p)]
        _userenv.DeriveAppContainerSidFromAppContainerName.restype = ctypes.c_long
        _userenv.DeriveAppContainerSidFromAppContainerName.argtypes = [
            wt.LPCWSTR, ctypes.POINTER(ctypes.c_void_p)]
        _userenv.DeleteAppContainerProfile.restype = ctypes.c_long
        _userenv.DeleteAppContainerProfile.argtypes = [wt.LPCWSTR]


_declare()

E_ALREADY_EXISTS = 0x800700B7


# --------------------------------------------------------------------------
# Results
# --------------------------------------------------------------------------

@dataclass
class ContainmentPlan:
    """Which layers this launch will actually apply, and why any are missing.

    `reasons` carries a human-readable explanation for every layer that is
    False. A layer is never reported as present unless it was constructed
    successfully.
    """
    appcontainer: bool = False
    restricted_token: bool = False
    job_object: bool = False
    separate_interpreter: bool = False
    reasons: Dict[str, str] = field(default_factory=dict)

    @property
    def filesystem_isolated(self) -> bool:
        return self.appcontainer or self.restricted_token

    @property
    def network_denied(self) -> bool:
        """Network denial comes from AppContainer only.

        The restricted token does NOT restrict sockets, and the job object does
        not either. If AppContainer is absent, the child has the host's network.
        """
        return self.appcontainer

    def as_dict(self) -> Dict[str, Any]:
        return {
            "appcontainer": self.appcontainer,
            "restricted_token": self.restricted_token,
            "job_object": self.job_object,
            "separate_interpreter": self.separate_interpreter,
            "filesystem_isolated": self.filesystem_isolated,
            "network_denied": self.network_denied,
            "reasons": dict(self.reasons),
        }


@dataclass
class ContainedResult:
    returncode: Optional[int]
    stdout: str
    stderr: str
    timed_out: bool
    containment: ContainmentPlan
    launch_error: Optional[str] = None


# --------------------------------------------------------------------------
# ACL helpers
# --------------------------------------------------------------------------

def _sid_from_string(s: str):
    p = ctypes.c_void_p()
    if not _advapi.ConvertStringSidToSidW(s, ctypes.byref(p)):
        raise ctypes.WinError(ctypes.get_last_error())
    return p


def sid_to_string(psid) -> str:
    out = wt.LPWSTR()
    if not _advapi.ConvertSidToStringSidW(psid, ctypes.byref(out)):
        raise ctypes.WinError(ctypes.get_last_error())
    return out.value


FILE_READ_ATTRIBUTES = 0x80
FILE_TRAVERSE = 0x20
SYNCHRONIZE = 0x100000
# Enough for os.stat() on a directory and nothing else. Notably WITHOUT
# FILE_LIST_DIRECTORY, so a holder can confirm the directory exists and read
# its timestamps but cannot enumerate what is inside it.
STAT_ONLY = FILE_READ_ATTRIBUTES | FILE_TRAVERSE | SYNCHRONIZE


def grant_dir(path: str, sid_string: str, mask: int = GENERIC_ALL,
              inheritable: bool = True) -> None:
    """Add an inheritable allow-ACE for `sid_string` to a directory.

    Used to hand the contained child exactly the directories it needs -- its
    workspace (read/write) and the provisioned interpreter (read/execute) --
    and nothing else. This is the positive half of the boundary: AppContainer
    and the deny-only user SID remove everything, and these ACEs add back only
    the sandbox's own tree.
    """
    if not _HAVE_PYWIN32:
        raise RuntimeError("pywin32 unavailable; cannot set ACLs")
    sd = win32security.GetNamedSecurityInfo(
        path, win32security.SE_FILE_OBJECT, win32security.DACL_SECURITY_INFORMATION)
    dacl = sd.GetSecurityDescriptorDacl()
    if dacl is None:
        dacl = win32security.ACL()
    sid = win32security.ConvertStringSidToSid(sid_string)

    # Idempotent. The provisioned interpreter directory is shared across every
    # sandbox run, so a blind AddAccessAllowedAceEx would append a duplicate
    # ACE per run and grow the DACL without bound until the ACL hits its size
    # limit and ACL writes start failing -- i.e. the boundary would degrade
    # with use. Skip if an equivalent ACE is already present.
    inherit = (OBJECT_INHERIT_ACE | CONTAINER_INHERIT_ACE) if inheritable else 0
    for i in range(dacl.GetAceCount()):
        ace = dacl.GetAce(i)
        (ace_type, ace_flags), ace_mask, ace_sid = ace[0], ace[1], ace[2]
        if (ace_type == 0  # ACCESS_ALLOWED_ACE_TYPE
                and ace_sid == sid
                and (ace_flags & inherit) == inherit
                and (ace_mask & mask) == mask):
            return

    dacl.AddAccessAllowedAceEx(win32security.ACL_REVISION, inherit, mask, sid)
    win32security.SetNamedSecurityInfo(
        path, win32security.SE_FILE_OBJECT,
        win32security.DACL_SECURITY_INFORMATION, None, None, dacl, None)


# --------------------------------------------------------------------------
# AppContainer
# --------------------------------------------------------------------------

class AppContainerProfile:
    """A capability-less AppContainer profile.

    No capabilities are requested. In particular NOT `internetClient` and NOT
    `privateNetworkClientServer`, which is what makes the Windows Filtering
    Platform deny the process every outbound socket.

    THE ONE DEPENDENCY WORTH NAMING: that denial is enforced by the Windows
    Filtering Platform, which is driven by the Base Filtering Engine (BFE) and
    the Windows Defender Firewall service (mpssvc). If those services are
    stopped, AppContainer network isolation is not applied. `firewall_state()`
    reports them, and `verify_containment()` proves the denial empirically
    rather than inferring it from service state.
    """

    def __init__(self, name: str = "JarvisAdapterSandbox"):
        self.name = name
        self.sid_ptr: Optional[ctypes.c_void_p] = None
        self.sid_string: Optional[str] = None
        self.error: Optional[str] = None
        self._create()

    def _create(self) -> None:
        if not _IS_WINDOWS or _userenv is None:
            self.error = "userenv.dll unavailable (not Windows?)"
            return
        sid = ctypes.c_void_p()
        hr = _userenv.CreateAppContainerProfile(
            self.name, self.name,
            "JARVIS Level6 adapter-generation sandbox (no capabilities)",
            None, 0, ctypes.byref(sid))
        hr &= 0xFFFFFFFF
        if hr == E_ALREADY_EXISTS:
            hr2 = _userenv.DeriveAppContainerSidFromAppContainerName(
                self.name, ctypes.byref(sid)) & 0xFFFFFFFF
            if hr2 != 0:
                self.error = f"DeriveAppContainerSidFromAppContainerName hr=0x{hr2:08X}"
                return
        elif hr != 0:
            self.error = f"CreateAppContainerProfile hr=0x{hr:08X}"
            return
        self.sid_ptr = sid
        try:
            self.sid_string = sid_to_string(sid)
        except OSError as exc:
            self.error = f"ConvertSidToStringSid: {exc}"
            self.sid_ptr = None

    @property
    def ok(self) -> bool:
        return self.sid_ptr is not None and self.sid_string is not None

    def security_capabilities(self) -> SECURITY_CAPABILITIES:
        caps = SECURITY_CAPABILITIES()
        caps.AppContainerSid = self.sid_ptr
        caps.Capabilities = None
        caps.CapabilityCount = 0
        caps.Reserved = 0
        return caps


def firewall_state() -> Dict[str, str]:
    """Report BFE and mpssvc state -- the services AppContainer egress denial rides on.

    Advisory only. It is reported so that a stopped firewall shows up as a
    named condition instead of a silently missing boundary; the authoritative
    check is the live egress probe in `verify_containment()`.
    """
    out: Dict[str, str] = {}
    for svc in ("BFE", "mpssvc"):
        try:
            r = subprocess.run(["sc", "query", svc], capture_output=True,
                               text=True, timeout=10)
            txt = r.stdout or ""
            out[svc] = "RUNNING" if "RUNNING" in txt else (
                "STOPPED" if "STOPPED" in txt else "UNKNOWN")
        except Exception as exc:
            out[svc] = f"query failed: {type(exc).__name__}"
    return out


# --------------------------------------------------------------------------
# Restricted token
# --------------------------------------------------------------------------

def make_restricted_token(extra_default_dacl_sids: Sequence[str] = ()):
    """The caller's primary token with its user SID deny-only and privileges stripped.

    Two details found live while building this, both of which produce a child
    that dies before running a single instruction if you get them wrong:

    1. THE DEFAULT DACL. A token carries a default DACL applied to objects the
       process creates for itself. On this machine it grants exactly
       {user SID, BUILTIN\\Administrators, SYSTEM} -- and the first is now
       deny-only while the second is already deny-only under UAC. The child
       therefore could not access its own process heap/objects and died at
       0xC0000142 (STATUS_DLL_INIT_FAILED) before `main`. Measured, not
       guessed: cmd.exe failed identically, which ruled out anything
       Python-specific. Fix: replace the default DACL with one granting SYSTEM
       and BUILTIN\\Users (plus the AppContainer SID when stacking).

    2. SeChangeNotifyPrivilege IS DELIBERATELY KEPT. It is "bypass traverse
       checking". Deleting it forces a traverse ACL check on every intermediate
       directory, and the sandbox workspace lives under a user profile whose
       intermediate directories grant only the (now deny-only) user SID. Strip
       it and the child cannot reach its own workspace. It confers no ability
       to read a file whose own ACL denies it, so keeping it costs nothing.

    Returns a primary token handle, or raises.
    """
    if not _HAVE_PYWIN32:
        raise RuntimeError("pywin32 unavailable; cannot build a restricted token")

    src = win32security.OpenProcessToken(
        win32api.GetCurrentProcess(),
        win32con.TOKEN_DUPLICATE | win32con.TOKEN_QUERY | win32con.TOKEN_ASSIGN_PRIMARY)
    user_sid, _ = win32security.GetTokenInformation(src, win32security.TokenUser)
    privs = win32security.GetTokenInformation(src, win32security.TokenPrivileges)
    to_delete = [
        (luid, 0) for luid, _attr in privs
        if win32security.LookupPrivilegeName(None, luid) != "SeChangeNotifyPrivilege"
    ]

    restricted = win32security.CreateRestrictedToken(
        src,
        0,
        [(user_sid, 0)],   # SidsToDisable -> SE_GROUP_USE_FOR_DENY_ONLY
        to_delete,         # PrivilegesToDelete
        [],                # SidsToRestrict
    )
    # CreateRestrictedToken's handle does not carry TOKEN_ADJUST_DEFAULT, so the
    # default DACL cannot be replaced through it. Re-duplicate for full access.
    token = win32security.DuplicateTokenEx(
        restricted, win32security.SecurityImpersonation,
        win32con.TOKEN_ALL_ACCESS, win32security.TokenPrimary)

    dacl = win32security.ACL()
    for s in (SID_LOCAL_SYSTEM, SID_BUILTIN_USERS, *extra_default_dacl_sids):
        dacl.AddAccessAllowedAce(
            win32security.ACL_REVISION, GENERIC_ALL,
            win32security.ConvertStringSidToSid(s))
    win32security.SetTokenInformation(token, win32security.TokenDefaultDacl, dacl)
    return token


# --------------------------------------------------------------------------
# Job object
# --------------------------------------------------------------------------

@dataclass
class JobLimits:
    active_process_limit: int = 12
    process_memory_bytes: int = 1024 * 1024 * 1024
    per_process_user_time_sec: int = 120
    job_user_time_sec: int = 300


def make_job_object(limits: JobLimits):
    """A job object that bounds process count, memory, CPU time and lifetime.

    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE is the important one: when the last
    handle to the job closes -- including because the parent crashed -- Windows
    terminates every process in it. Nothing the sandbox started can outlive the
    run, which is a property the previous `subprocess.run(timeout=...)` did not
    have (its timeout kills the direct child only, orphaning grandchildren).
    """
    if not _HAVE_PYWIN32:
        raise RuntimeError("pywin32 unavailable; cannot create a job object")
    job = win32job.CreateJobObject(None, "")
    info = win32job.QueryInformationJobObject(
        job, win32job.JobObjectExtendedLimitInformation)
    basic = info["BasicLimitInformation"]
    basic["LimitFlags"] = (
        win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        | win32job.JOB_OBJECT_LIMIT_ACTIVE_PROCESS
        | win32job.JOB_OBJECT_LIMIT_PROCESS_MEMORY
        | win32job.JOB_OBJECT_LIMIT_PROCESS_TIME
        | win32job.JOB_OBJECT_LIMIT_JOB_TIME
        | win32job.JOB_OBJECT_LIMIT_DIE_ON_UNHANDLED_EXCEPTION
    )
    basic["ActiveProcessLimit"] = limits.active_process_limit
    basic["PerProcessUserTimeLimit"] = limits.per_process_user_time_sec * 10_000_000
    basic["PerJobUserTimeLimit"] = limits.job_user_time_sec * 10_000_000
    info["ProcessMemoryLimit"] = limits.process_memory_bytes
    win32job.SetInformationJobObject(
        job, win32job.JobObjectExtendedLimitInformation, info)

    # UI restrictions: no reading the host clipboard, no reaching windows or
    # desktops outside the job, no changing display/system parameters.
    try:
        ui = (win32job.JOB_OBJECT_UILIMIT_DESKTOP
              | win32job.JOB_OBJECT_UILIMIT_DISPLAYSETTINGS
              | win32job.JOB_OBJECT_UILIMIT_EXITWINDOWS
              | win32job.JOB_OBJECT_UILIMIT_GLOBALATOMS
              | win32job.JOB_OBJECT_UILIMIT_HANDLES
              | win32job.JOB_OBJECT_UILIMIT_READCLIPBOARD
              | win32job.JOB_OBJECT_UILIMIT_WRITECLIPBOARD
              | win32job.JOB_OBJECT_UILIMIT_SYSTEMPARAMETERS)
        win32job.SetInformationJobObject(
            job, win32job.JobObjectBasicUIRestrictions, {"UIRestrictionsClass": ui})
    except Exception:
        # UI restrictions are a bonus, not the boundary. If this specific call
        # is unavailable the process/memory/lifetime limits above still apply,
        # and the caller is not told UI restrictions were applied.
        pass
    return job


# --------------------------------------------------------------------------
# Launch
# --------------------------------------------------------------------------

def _env_block(env: Dict[str, str]) -> ctypes.Array:
    parts = [f"{k}={v}" for k, v in env.items()]
    return ctypes.create_unicode_buffer("\0".join(parts) + "\0\0")


def _inheritable_file(path: str, write: bool) -> int:
    if write:
        h = _k32.CreateFileW(path, 0x40000000, FILE_SHARE_READ | FILE_SHARE_WRITE,
                             None, CREATE_ALWAYS, 0x80, None)
    else:
        h = _k32.CreateFileW(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE,
                             None, OPEN_EXISTING, 0x80, None)
    if h == INVALID_HANDLE_VALUE or h is None:
        raise ctypes.WinError(ctypes.get_last_error())
    _k32.SetHandleInformation(h, HANDLE_FLAG_INHERIT, HANDLE_FLAG_INHERIT)
    return h


class ContainedLauncher:
    """Launches one command inside as many of the three boundaries as are available.

    `require` names the layers the caller insists on. If any is unavailable the
    launcher REFUSES rather than quietly running with less. That default is
    deliberate: D18 exists because a control that was not enforced still looked
    like one, and a sandbox that silently degrades to "no sandbox" is the same
    defect with more code.
    """

    def __init__(self,
                 workspace: str,
                 readonly_paths: Sequence[str] = (),
                 stat_only_paths: Sequence[str] = (),
                 appcontainer_name: str = "JarvisAdapterSandbox",
                 limits: Optional[JobLimits] = None,
                 use_appcontainer: bool = True,
                 use_restricted_token: bool = True,
                 use_job_object: bool = True):
        self.workspace = os.path.abspath(workspace)
        self.readonly_paths = [os.path.abspath(p) for p in readonly_paths]
        self.stat_only_paths = [os.path.abspath(p) for p in stat_only_paths]
        self.limits = limits or JobLimits()
        self._want = {
            "appcontainer": use_appcontainer,
            "restricted_token": use_restricted_token,
            "job_object": use_job_object,
        }
        self.plan = ContainmentPlan()
        self.profile: Optional[AppContainerProfile] = None
        self._token = None

        if not _IS_WINDOWS:
            for k in self._want:
                self.plan.reasons[k] = "not running on Windows"
            return
        if not _HAVE_PYWIN32:
            for k in ("restricted_token", "job_object"):
                self.plan.reasons[k] = _IMPORT_ERRORS.get("pywin32", "pywin32 missing")

        if self._want["appcontainer"]:
            self.profile = AppContainerProfile(appcontainer_name)
            if self.profile.ok:
                self.plan.appcontainer = True
            else:
                self.plan.reasons["appcontainer"] = self.profile.error or "unknown"
        else:
            self.plan.reasons["appcontainer"] = "disabled by caller"

        if self._want["restricted_token"] and _HAVE_PYWIN32:
            extra = [self.profile.sid_string] if (self.profile and self.profile.ok) else []
            try:
                self._token = make_restricted_token(extra)
                self.plan.restricted_token = True
            except Exception as exc:
                self.plan.reasons["restricted_token"] = f"{type(exc).__name__}: {exc}"
        elif not self._want["restricted_token"]:
            self.plan.reasons["restricted_token"] = "disabled by caller"

        # Probe job-object availability NOW rather than at launch. The caller
        # decides whether to run at all based on which layers exist, and that
        # decision has to be made before a process is created -- discovering
        # at assign time that jobs are unavailable would mean the generated
        # code is already running.
        if self._want["job_object"] and _HAVE_PYWIN32:
            try:
                probe = make_job_object(self.limits)
                probe.Close()
                self.plan.job_object = True
            except Exception as exc:
                self.plan.reasons["job_object"] = f"{type(exc).__name__}: {exc}"
        elif not self._want["job_object"]:
            self.plan.reasons["job_object"] = "disabled by caller"

        self._apply_acls()

    def _apply_acls(self) -> None:
        """Grant the contained identities access to exactly the sandbox's own tree."""
        if not _HAVE_PYWIN32:
            return
        sids_rw: List[str] = []
        if self.plan.appcontainer and self.profile and self.profile.sid_string:
            sids_rw.append(self.profile.sid_string)
        if self.plan.restricted_token:
            sids_rw.append(SID_BUILTIN_USERS)
        for sid in sids_rw:
            try:
                grant_dir(self.workspace, sid, GENERIC_ALL)
            except Exception as exc:
                self.plan.reasons.setdefault(
                    "acl", f"workspace grant {sid}: {type(exc).__name__}: {exc}")
            for ro in self.readonly_paths:
                try:
                    # 0x1200A9 = GENERIC_READ|GENERIC_EXECUTE expanded for files
                    grant_dir(ro, sid, 0x1200A9)
                except Exception as exc:
                    self.plan.reasons.setdefault(
                        "acl_ro", f"ro grant {sid} on {ro}: {type(exc).__name__}: {exc}")
            for so in self.stat_only_paths:
                # NON-inheritable, and stat-only. pytest unconditionally stats
                # the parent of the directory it collects from (measured: no
                # combination of --rootdir/--confcutdir/--noconftest avoids
                # it), so the parent must be stat-able or collection dies with
                # a PermissionError instead of a test result. Granting it
                # non-inheritably and without FILE_LIST_DIRECTORY means the
                # child can stat that one directory but cannot enumerate it,
                # and sibling sandbox directories from other runs do not
                # inherit the grant. Verified: with this ACE in place,
                # `os.listdir(parent)` and reading a sibling's file both still
                # fail with WinError 5 / Errno 13.
                try:
                    grant_dir(so, sid, STAT_ONLY, inheritable=False)
                except Exception as exc:
                    self.plan.reasons.setdefault(
                        "acl_stat", f"stat grant {sid} on {so}: {type(exc).__name__}: {exc}")

    def missing(self, require: Sequence[str]) -> List[str]:
        got = self.plan.as_dict()
        return [r for r in require if not got.get(r)]

    def run(self,
            argv: Sequence[str],
            cwd: Optional[str] = None,
            env: Optional[Dict[str, str]] = None,
            timeout: float = 120.0) -> ContainedResult:
        cwd = os.path.abspath(cwd or self.workspace)
        env = dict(env or {})
        cmdline = subprocess.list2cmdline(list(argv))

        out_path = os.path.join(self.workspace, f"_contained_stdout_{os.getpid()}.log")
        err_path = os.path.join(self.workspace, f"_contained_stderr_{os.getpid()}.log")
        h_out = h_err = h_in = None
        attr_buf = None
        job = None
        pi = PROCESS_INFORMATION()
        launched = False
        try:
            h_out = _inheritable_file(out_path, True)
            h_err = _inheritable_file(err_path, True)
            h_in = _inheritable_file("NUL", False)

            si = STARTUPINFOEXW()
            si.StartupInfo.cb = ctypes.sizeof(STARTUPINFOEXW)
            si.StartupInfo.dwFlags = STARTF_USESTDHANDLES
            si.StartupInfo.hStdInput = h_in
            si.StartupInfo.hStdOutput = h_out
            si.StartupInfo.hStdError = h_err

            flags = (CREATE_NO_WINDOW | CREATE_SUSPENDED
                     | CREATE_UNICODE_ENVIRONMENT)

            # Two proc-thread attributes: the AppContainer security
            # capabilities, and an explicit handle list.
            #
            # The handle list matters more than it looks. bInheritHandles=TRUE
            # hands the child EVERY inheritable handle this process happens to
            # hold -- which, in a long-running assistant, can include open
            # files well outside the sandbox. An inherited handle bypasses ACL
            # checks entirely because the access check already happened when
            # the parent opened it, so it is a straight path through the
            # boundary. PROC_THREAD_ATTRIBUTE_HANDLE_LIST pins inheritance to
            # exactly the three stdio handles below.
            n_attrs = 1 + (1 if self.plan.appcontainer else 0)
            size = ctypes.c_size_t(0)
            _k32.InitializeProcThreadAttributeList(None, n_attrs, 0, ctypes.byref(size))
            attr_buf = ctypes.create_string_buffer(size.value)
            if not _k32.InitializeProcThreadAttributeList(
                    attr_buf, n_attrs, 0, ctypes.byref(size)):
                raise ctypes.WinError(ctypes.get_last_error())

            handle_arr = (wt.HANDLE * 3)(h_in, h_out, h_err)
            if not _k32.UpdateProcThreadAttribute(
                    attr_buf, 0, ctypes.c_size_t(PROC_THREAD_ATTRIBUTE_HANDLE_LIST),
                    ctypes.byref(handle_arr), ctypes.sizeof(handle_arr), None, None):
                raise ctypes.WinError(ctypes.get_last_error())

            caps = None
            if self.plan.appcontainer and self.profile is not None:
                caps = self.profile.security_capabilities()
                if not _k32.UpdateProcThreadAttribute(
                        attr_buf, 0,
                        ctypes.c_size_t(PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES),
                        ctypes.byref(caps), ctypes.sizeof(caps), None, None):
                    raise ctypes.WinError(ctypes.get_last_error())

            si.lpAttributeList = ctypes.cast(attr_buf, ctypes.c_void_p)
            flags |= EXTENDED_STARTUPINFO_PRESENT

            block = _env_block(env)
            cmd_buf = ctypes.create_unicode_buffer(cmdline)

            if self.plan.restricted_token and self._token is not None:
                ok = _advapi.CreateProcessAsUserW(
                    int(self._token), None, cmd_buf, None, None, True, flags,
                    ctypes.cast(block, ctypes.c_void_p), cwd,
                    ctypes.byref(si), ctypes.byref(pi))
            else:
                ok = _k32.CreateProcessW(
                    None, cmd_buf, None, None, True, flags,
                    ctypes.cast(block, ctypes.c_void_p), cwd,
                    ctypes.byref(si), ctypes.byref(pi))
            if not ok:
                raise ctypes.WinError(ctypes.get_last_error())
            launched = True

            if self.plan.job_object:
                try:
                    job = make_job_object(self.limits)
                    win32job.AssignProcessToJobObject(job, int(pi.hProcess))
                except Exception as exc:
                    # The process exists but is suspended and unconstrained by
                    # a job. Kill it rather than resuming outside the boundary
                    # the caller was told it would have.
                    self.plan.job_object = False
                    self.plan.reasons["job_object"] = (
                        f"assign failed: {type(exc).__name__}: {exc}")
                    _k32.TerminateProcess(pi.hProcess, 1)
                    return ContainedResult(
                        returncode=None, stdout="", stderr="", timed_out=False,
                        containment=self.plan,
                        launch_error=("job object assignment failed after launch; "
                                      "suspended child was terminated rather than "
                                      "resumed uncontained"))

            _k32.ResumeThread(pi.hThread)

            waited = _k32.WaitForSingleObject(pi.hProcess, int(timeout * 1000))
            timed_out = waited == WAIT_TIMEOUT
            if timed_out:
                if job is not None:
                    try:
                        win32job.TerminateJobObject(job, 1)
                    except Exception:
                        _k32.TerminateProcess(pi.hProcess, 1)
                else:
                    _k32.TerminateProcess(pi.hProcess, 1)
                _k32.WaitForSingleObject(pi.hProcess, 5000)

            code = wt.DWORD()
            _k32.GetExitCodeProcess(pi.hProcess, ctypes.byref(code))
            rc = code.value
            if rc >= 0x80000000:
                rc -= 0x100000000

            return ContainedResult(
                returncode=rc, timed_out=timed_out,
                stdout=_read(out_path), stderr=_read(err_path),
                containment=self.plan)

        except Exception as exc:
            return ContainedResult(
                returncode=None, stdout=_read(out_path), stderr=_read(err_path),
                timed_out=False, containment=self.plan,
                launch_error=f"{type(exc).__name__}: {exc}")
        finally:
            for h in (h_out, h_err, h_in):
                if h:
                    _k32.CloseHandle(h)
            if attr_buf is not None:
                _k32.DeleteProcThreadAttributeList(
                    ctypes.cast(attr_buf, ctypes.c_void_p))
            if launched:
                _k32.CloseHandle(pi.hThread)
                _k32.CloseHandle(pi.hProcess)
            # Closing the job handle last kills anything still alive in it.
            if job is not None:
                try:
                    job.Close()
                except Exception:
                    pass
            for p in (out_path, err_path):
                try:
                    os.remove(p)
                except OSError:
                    pass


def _read(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


# --------------------------------------------------------------------------
# Empirical verification
# --------------------------------------------------------------------------

_PROBE = r'''
import json, os, socket, sys
r = {"prefix": sys.prefix, "executable": sys.executable}

target = sys.argv[2]
try:
    with open(target, "r", encoding="utf-8") as fh:
        r["host_file_read"] = "ALLOWED: " + fh.read()[:64]
except Exception as e:
    r["host_file_read"] = "blocked: %s: %s" % (type(e).__name__, e)

try:
    r["home_listing"] = "ALLOWED: %d entries" % len(os.listdir(sys.argv[3]))
except Exception as e:
    r["home_listing"] = "blocked: %s: %s" % (type(e).__name__, e)

socket.setdefaulttimeout(5)
try:
    socket.create_connection(("1.1.1.1", 443), timeout=5).close()
    r["tcp_egress"] = "ALLOWED"
except Exception as e:
    r["tcp_egress"] = "blocked: %s: %s" % (type(e).__name__, e)

try:
    r["dns"] = "ALLOWED: " + socket.gethostbyname("example.com")
except Exception as e:
    r["dns"] = "blocked: %s: %s" % (type(e).__name__, e)

try:
    import importlib.util as u
    r["host_only_package_importable"] = u.find_spec(sys.argv[4]) is not None
except Exception as e:
    r["host_only_package_importable"] = "error: %s" % e

with open(sys.argv[1], "w", encoding="utf-8") as fh:
    json.dump(r, fh)
'''


def verify_containment(python_exe: str,
                       workspace: str,
                       readonly_paths: Sequence[str] = (),
                       host_only_package: str = "yaml",
                       **launcher_kwargs) -> Dict[str, Any]:
    """Run a real child that actively attempts each escape; report what happened.

    This is the mechanical check that makes the rest of this module's claims
    checkable. It does not read configuration and conclude a boundary exists.
    It creates a genuine file outside the sandbox, has a genuine child process
    genuinely try to open it, and reports the genuine result.
    """
    ws = os.path.abspath(workspace)
    os.makedirs(ws, exist_ok=True)
    canary_dir = os.path.expanduser("~")
    canary = os.path.join(canary_dir, ".jarvis_sandbox_canary.txt")
    created = False
    try:
        if not os.path.exists(canary):
            with open(canary, "w", encoding="utf-8") as fh:
                fh.write("JARVIS-SANDBOX-CANARY-DO-NOT-SHIP")
            created = True

        script = os.path.join(ws, "_containment_probe.py")
        with open(script, "w", encoding="utf-8") as fh:
            fh.write(_PROBE)
        out = os.path.join(ws, "_containment_probe.json")

        launcher = ContainedLauncher(ws, readonly_paths=readonly_paths,
                                     **launcher_kwargs)
        res = launcher.run(
            [python_exe, script, out, canary, canary_dir, host_only_package],
            cwd=ws, env=minimal_env(ws), timeout=90)

        # The launcher is handed an argv and cannot know whether that
        # interpreter is a provisioned one; the probe measures it directly, so
        # backfill from the measurement rather than reporting a stale False.
        if os.path.exists(out):
            try:
                with open(out, "r", encoding="utf-8") as fh:
                    launcher.plan.separate_interpreter = (
                        json.load(fh).get("prefix") != sys.prefix)
            except Exception:
                pass

        report: Dict[str, Any] = {
            "containment": launcher.plan.as_dict(),
            "firewall": firewall_state(),
            "returncode": res.returncode,
            "timed_out": res.timed_out,
            "launch_error": res.launch_error,
            "stderr": res.stderr[-1500:],
        }
        if os.path.exists(out):
            with open(out, "r", encoding="utf-8") as fh:
                report["probe"] = json.load(fh)
        else:
            report["probe"] = None
        report["verdict"] = _verdict(report)
        return report
    finally:
        if created:
            try:
                os.remove(canary)
            except OSError:
                pass


def _verdict(report: Dict[str, Any]) -> Dict[str, Any]:
    probe = report.get("probe")
    if not probe:
        return {"measured": False,
                "note": "probe produced no output; nothing is claimed"}
    def blocked(key: str) -> bool:
        v = probe.get(key, "")
        return isinstance(v, str) and v.startswith("blocked:")
    return {
        "measured": True,
        "host_file_read_blocked": blocked("host_file_read"),
        "home_listing_blocked": blocked("home_listing"),
        "tcp_egress_blocked": blocked("tcp_egress"),
        "dns_blocked": blocked("dns"),
        "host_only_package_absent": probe.get("host_only_package_importable") is False,
        "separate_prefix": probe.get("prefix") != sys.prefix,
    }


def minimal_env(workspace: str) -> Dict[str, str]:
    """A deliberately small environment for the contained child.

    The host environment is not inherited. It carries API keys, proxy settings,
    and paths into the developer's profile -- none of which the sandbox has any
    business seeing, and several of which are exactly what an escape would want.
    HOME/USERPROFILE/TEMP are redirected into the workspace so that anything
    resolving `~` lands inside the boundary rather than being denied at it.
    """
    winroot = os.environ.get("SystemRoot", r"C:\Windows")
    home = os.path.join(workspace, "_home")
    tmp = os.path.join(workspace, "_tmp")
    for d in (home, tmp):
        os.makedirs(d, exist_ok=True)
    return {
        "SystemRoot": winroot,
        "windir": winroot,
        "PATH": os.pathsep.join([os.path.join(winroot, "System32"), winroot]),
        "TEMP": tmp,
        "TMP": tmp,
        "HOME": home,
        "USERPROFILE": home,
        "APPDATA": os.path.join(home, "AppData", "Roaming"),
        "LOCALAPPDATA": os.path.join(home, "AppData", "Local"),
        "NUMBER_OF_PROCESSORS": os.environ.get("NUMBER_OF_PROCESSORS", "2"),
        "PROCESSOR_ARCHITECTURE": os.environ.get("PROCESSOR_ARCHITECTURE", "AMD64"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "PYTHONUNBUFFERED": "1",
        "PYTHONIOENCODING": "utf-8",
    }

"""Graph API transport: pinned version, forced proxy, rate-limit backoff, typed errors.

Every other script in this directory calls Graph through this module. Nothing here
knows about campaigns — it only makes requests survivable and errors legible.

Credentials come from the environment, never from argv (argv lands in shell history
and process lists):

    META_TOKEN        System User or long-lived user token. Required.
    META_PROXY        socks5h://user:pass@host:port  (see 01 — socks5:// breaks TLS)
    META_COOKIES      Optional. Session cookies ("c_user=...; xs=...") required for scraped EAAB tokens.
    META_USER_AGENT   Optional. Browser User-Agent override. Not required for an EAAB on the same IP
                      (default and another browser's UA both passed 2026-09-29); the cookies are.
    META_TOKEN_BUSINESS / _CATALOG / _EVENTS / _RULES
                      Optional per-capability tokens (business reads, catalog, CAPI events, rules).
                      A capability without its own variable falls back to META_TOKEN only when that
                      token's class carries it (tokens.py); otherwise the call exits naming the
                      missing variable. META_COOKIES_<BUSINESS|CATALOG|EVENTS|RULES> override
                      META_COOKIES for that token (same login = same cookies, so usually unset).
    <VAR>_APP_ID      Optional. The app id `metaops token import` confirmed for <VAR>; overrides the
                      prefix guess of the token class.
    METAOPS_ALLOW_TOKEN_CLASS  Comma list (EAAd,...) or `all`: lets that class act as an ads writer
                      despite the refusal / warning (a System User token can share a prefix).
    META_API_VERSION  Override the pinned version below. Must look like vNN.N (validated at
                      import; outside the supported window it warns on stderr).
    META_ALLOW_NO_PROXY=1  Deliberate confirmation that direct egress is expected for this BM.
                      Honoured by direct script use only: under metaops with a workspace the
                      export is dropped and only workspace.json defaults.allow_no_proxy=true
                      lifts the proxy requirement.
    META_APP_SECRET   Optional. When set, every call carries `appsecret_proof`
                      (HMAC-SHA256 of the token) — required once the app enforces
                      "Require App Secret", and cheap insurance against a leaked token
                      being replayed from elsewhere.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import hmac
import json
import os
import random
import re
import sys
import tempfile
import threading
import time
from collections.abc import Callable, Iterator
from typing import Any, NamedTuple
from urllib.parse import quote, urlsplit

import tokens

try:  # POSIX only; without it the pacing file falls back to atomic-replace without a lock
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]


def _requests():
    """Imported lazily so --help works on a box that has not installed it yet."""
    try:
        import requests
    except ImportError:  # pragma: no cover
        sys.exit("Missing dependency. Run:  pip install 'requests[socks]'")
    return requests


# Pinned deliberately. An unpinned call silently changes behavior when Meta ships a
# version; re-pin only after re-validating this transport and its SDK/API references.
DEFAULT_API_VERSION = "v26.0"
_API_VERSION_RE = re.compile(r"^v[0-9]{1,3}\.[0-9]{1,2}$")


def resolve_api_version(raw: str | None) -> str:
    """META_API_VERSION → the version string used in BASE.

    The value is pasted into every request URL, so its shape is checked (vNN.N, e.g. v26.0):
    a typo or a value like "v26.0/../x" must not silently re-route or re-version calls.
    Unset or blank → the pinned default. Raises ValueError on a malformed value."""
    value = (raw or "").strip()
    if not value:
        return DEFAULT_API_VERSION
    if not _API_VERSION_RE.fullmatch(value):
        raise ValueError(
            f"META_API_VERSION={raw!r} is not a Graph API version (expected vNN.N, e.g. "
            f"{DEFAULT_API_VERSION}); unset it to use the pinned default"
        )
    return value


try:
    API_VERSION = resolve_api_version(os.environ.get("META_API_VERSION"))
except ValueError as _version_error:
    sys.exit(str(_version_error))
BASE = f"https://graph.facebook.com/{API_VERSION}"

# Accepted API window: current major (N) + previous stable (N-1). Marketing API
# versions live ~12 months TOTAL (meta-ads/00 §4.1: v24.0 2025-10-08 → 2026-10-06,
# v25.0 2026-02-18 supported/TBD, v26.0 2026-07-29 current). A workspace/receipt/plan
# on N-1 is accepted with an explicit sunset warning, never a silent pass. Anything
# outside the window hard-fails; money stays fail-closed where the payload shape is
# genuinely incompatible (field mismatches still refuse even inside the window).
SUPPORTED_VERSIONS = ("v26.0", "v25.0")
# Minimum duplicated sunset table (canonical lives in meta-ads/00 §4.1):
# v24 death 2026-10-06. v25 expiry TBD. v26 current, no expiry announced.
VERSION_SUNSET = {
    "v24.0": "2026-10-06",
    "v25.0": "TBD (still supported 2026-08-31)",
    "v26.0": "current",
}


def api_version_window_warning(value: str) -> str | None:
    """Warning text when `value` (the effective API version) is outside SUPPORTED_VERSIONS."""
    if value in SUPPORTED_VERSIONS:
        return None
    return (
        f"META_API_VERSION resolves to {value}, outside the supported window "
        f"({', '.join(SUPPORTED_VERSIONS)}); payload shapes and receipts were validated only "
        "on the supported versions — expect field rejections or a sunset error"
    )


_window_warning = api_version_window_warning(API_VERSION)
if _window_warning:
    print(f"  ! {_window_warning}", file=sys.stderr)


def version_status(value: str | None) -> str:
    """Classify an api_version string: 'current', 'previous', or 'unsupported'."""
    if value == API_VERSION:
        return "current"
    if value in SUPPORTED_VERSIONS:
        return "previous"
    return "unsupported"


def version_warning(value: str | None) -> str | None:
    """Human-readable N-1 warning, or None when already current / unsupported."""
    if version_status(value) != "previous":
        return None
    return (
        f"uses {value}, launcher uses {API_VERSION} — N-1 accepted with warning; "
        f"v24 died {VERSION_SUNSET['v24.0']} (meta-ads/00 §4.1), "
        f"migrate to {API_VERSION} before the v25 sunset"
    )

# Header budget at which we stop and wait rather than earn a block.
USAGE_PAUSE_PCT = 85.0

# Pacing (FIELD 2026-09-27): the account with the heaviest API day + a code-17 retry storm
# (60→300 s sleeps for ~12 min) was disabled for Account Integrity "automation" hours later;
# siblings on the same token lived. Graph docs: after a rate limit STOP calling — every retry
# extends the block. So a throttle is never retried: the account goes on a cooldown that every
# later metaops process honours (state is global, not per workspace), and campaign creates are
# spaced per account. METAOPS_PACE_OVERRIDE=1 bypasses both — only to stop spend (pause).
THROTTLE_COOLDOWN_MIN = float(os.environ.get("METAOPS_THROTTLE_COOLDOWN_MIN", "30"))
CAMPAIGN_CREATE_GAP_H = float(os.environ.get("METAOPS_CREATE_GAP_HOURS", "3"))
ACCOUNT_THROTTLE_CODES = {17, 613}          # + 80000-80999 (BUC); per ad account
GLOBAL_THROTTLE_CODES = {4, 32}             # app / user level — every account waits
_LAST_ACCOUNT: str | None = os.environ.get("METAOPS_ACCOUNT_CONTEXT") or None


def _pace_file() -> str:
    base = os.path.expanduser(os.environ.get("METAOPS_PACE_DIR", "~/.metaops"))
    return os.path.join(base, "pacing.json")


def _pace_load() -> dict[str, Any]:
    try:
        with open(_pace_file(), encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


# The pacing file is shared by EVERY metaops process on the box (state is global, not per
# workspace). Two processes doing load → modify → save on it can drop each other's cooldown
# or campaign-create record, so the whole read-modify-write runs under an exclusive flock on
# a sidecar lock file, and each write goes through its own tmp file (a shared "<file>.tmp"
# lets one process replace or truncate the other's half-written copy).
_PACE_THREAD_LOCK = threading.RLock()
_PACE_LOCK_STATE: dict[str, Any] = {"fd": None, "depth": 0}


@contextlib.contextmanager
def _pace_lock() -> Iterator[None]:
    """Exclusive, re-entrant lock over the pacing file (thread lock + flock across processes)."""
    with _PACE_THREAD_LOCK:
        if _PACE_LOCK_STATE["depth"] == 0:
            path = _pace_file()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            fd = os.open(path + ".lock", os.O_CREAT | os.O_RDWR, 0o600)
            if fcntl is not None:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX)
                except BaseException:
                    os.close(fd)
                    raise
            _PACE_LOCK_STATE["fd"] = fd
        _PACE_LOCK_STATE["depth"] += 1
        try:
            yield
        finally:
            _PACE_LOCK_STATE["depth"] -= 1
            if _PACE_LOCK_STATE["depth"] == 0:
                fd = _PACE_LOCK_STATE["fd"]
                _PACE_LOCK_STATE["fd"] = None
                try:
                    if fcntl is not None:
                        fcntl.flock(fd, fcntl.LOCK_UN)
                finally:
                    os.close(fd)


def _pace_write(data: dict[str, Any]) -> None:
    """Atomic write through a tmp file unique to this process and call. Caller holds the lock."""
    path = _pace_file()
    parent = os.path.dirname(path)
    os.makedirs(parent, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".pacing.{os.getpid()}.", suffix=".tmp", dir=parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=1, sort_keys=True)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _pace_save(data: dict[str, Any]) -> None:
    """Replace the pacing file with `data` under the lock. A caller that also READ the file
    first is still racy between its load and this save: use _pace_update() for that."""
    with _pace_lock():
        _pace_write(data)


def _pace_update(mutate: Callable[[dict[str, Any]], Any]) -> dict[str, Any]:
    """Load, `mutate(data)` in place, save: one critical section across processes."""
    with _pace_lock():
        data = _pace_load()
        mutate(data)
        _pace_write(data)
        return data


def _pace_override() -> bool:
    return os.environ.get("METAOPS_PACE_OVERRIDE", "").strip() == "1"


def _account_of(path: str) -> str | None:
    m = re.search(r"\b(act_\d+)", path or "")
    return m.group(1) if m else None


def cooldown_remaining(account: str | None) -> float:
    """Seconds left on the cooldown covering this account (its own or the global one)."""
    until = (_pace_load().get("cooldown") or {})
    now = time.time()
    left = [float(until.get("*", 0)) - now]
    if account:
        left.append(float(until.get(account, 0)) - now)
    return max(0.0, *left)


def _key_remaining(key: str) -> float:
    return max(0.0, float((_pace_load().get("cooldown") or {}).get(key, 0)) - time.time())


def _set_cooldown(key: str, seconds: float, reason: str) -> None:
    def apply(data: dict[str, Any]) -> None:
        cd = data.setdefault("cooldown", {})
        cd[key] = max(float(cd.get(key, 0)), time.time() + seconds)
        data.setdefault("cooldown_reason", {})[key] = reason

    _pace_update(apply)


def clear_cooldown(key: str) -> bool:
    """Drop one cooldown key (an account id, `*` or `obj:<id>`) and its reason. True when it
    existed. Locked read-modify-write like every other pacing change."""
    existed = {"value": False}

    def apply(data: dict[str, Any]) -> None:
        cd = data.get("cooldown")
        if isinstance(cd, dict) and key in cd:
            existed["value"] = True
            del cd[key]
        reasons = data.get("cooldown_reason")
        if isinstance(reasons, dict):
            reasons.pop(key, None)

    _pace_update(apply)
    return existed["value"]


def check_campaign_create_pace(account: str) -> None:
    """Refuse a new campaign on an account that got one less than CAMPAIGN_CREATE_GAP_H ago."""
    account = normalize_account(account)
    last = float((_pace_load().get("last_campaign_create") or {}).get(account, 0))
    gap_h = float(os.environ.get("METAOPS_CREATE_GAP_HOURS", CAMPAIGN_CREATE_GAP_H))
    gap = gap_h * 3600
    if last and time.time() - last < gap and not _pace_override():
        wait_min = (gap - (time.time() - last)) / 60
        raise PacingError(
            f"{account}: a campaign was created {(time.time() - last) / 60:.0f} min ago; pacing allows one "
            f"per {gap_h:g} h per account (FIELD 2026-09-27 automation ban). Wait "
            f"{wait_min:.0f} min, or METAOPS_PACE_OVERRIDE=1 only if the operator explicitly asks.")


def record_campaign_create(account: str) -> None:
    account = normalize_account(account)

    def apply(data: dict[str, Any]) -> None:
        data.setdefault("last_campaign_create", {})[account] = time.time()

    _pace_update(apply)


OUTCOME_UNKNOWN_MARKER = "[outcome unknown]"


class GraphError(Exception):
    """A Graph API error, parsed into the fields worth branching on.

    Branch on (code, subcode) — the stable machine key. `user_msg` is for humans and
    logs only: Meta rewrites and localizes those strings. See meta-ads/14.
    """

    def __init__(self, status: int, payload: dict[str, Any], context: str = ""):
        err = (payload or {}).get("error", {}) or {}
        self.status = status
        self.code = err.get("code")
        self.subcode = err.get("error_subcode")
        self.type = err.get("type")
        self.message = err.get("message", "")
        self.user_title = err.get("error_user_title", "")
        self.user_msg = err.get("error_user_msg", "")
        self.is_transient = bool(err.get("is_transient", False))
        self.trace = err.get("fbtrace_id", "")
        # Meta sometimes returns error_data as a JSON *string* rather than an object
        # (field-observed 2026-09-22 on a campaign budget rejection). Reading it as a dict
        # raised AttributeError and masked the real error, so parse it defensively.
        error_data = err.get("error_data") or {}
        if isinstance(error_data, str):
            try:
                error_data = json.loads(error_data)
            except Exception:
                error_data = {}
        if not isinstance(error_data, dict):
            error_data = {}
        self.blame_field = error_data.get("blame_field_specs")
        self.context = context
        # True when we cannot know whether the server actually applied the request:
        # the transport failed (status 0), or the server answered without a Graph error
        # envelope (an HTML 5xx from a proxy or edge). Graph answering with a real error
        # code IS knowledge — it means the call was rejected and nothing was created.
        self.outcome_unknown = self.status == 0 or (
            self.status >= 500 and self.type is None and self.code in (None, -1)
        )
        super().__init__(str(self))

    def __str__(self) -> str:
        head = f"[{self.context}] " if self.context else ""
        key = f"code={self.code} subcode={self.subcode}"
        detail = self.user_msg or self.message
        blame = f" blame={self.blame_field}" if self.blame_field else ""
        # The marker rides the text so a parent process that only sees a child's stderr
        # (metaops.graph_error) can still tell "rejected" from "may have been applied".
        unknown = f" {OUTCOME_UNKNOWN_MARKER}" if self.outcome_unknown else ""
        return f"{head}{key}: {detail}{blame} (trace {self.trace}){unknown}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "context": self.context,
            "status": self.status,
            "code": self.code,
            "subcode": self.subcode,
            "type": self.type,
            "message": self.message,
            "user_title": self.user_title,
            "user_msg": self.user_msg,
            "is_transient": self.is_transient,
            "blame_field_specs": self.blame_field,
            "fbtrace_id": self.trace,
            "outcome_unknown": self.outcome_unknown,
        }


class CooldownError(GraphError):
    """Refused locally: the account is on a throttle cooldown. No request was sent, so
    nothing was created (outcome is known). Carries code 17 so callers that already branch
    on throttles (e.g. `assets swap --watch`) treat it as one."""

    def __init__(self, account: str, seconds_left: float, context: str = ""):
        self.account = account
        self.seconds_left = seconds_left
        super().__init__(0, {"error": {
            "code": 17, "error_subcode": "local_cooldown", "type": "MetaOpsCooldown",
            "message": (f"{account} is on throttle cooldown for {seconds_left / 60:.0f} more min — "
                        "no call sent. Do not retry; come back later (METAOPS_PACE_OVERRIDE=1 only "
                        "to stop spend)."),
        }}, context)
        self.outcome_unknown = False


class PacingError(SystemExit):
    """Refused locally: campaign creates on this account are too close together. A SystemExit
    so launch.py prints the reason and exits 1 before anything is created, and bulk.py fails
    only this account."""


def token() -> str:
    t = os.environ.get("META_TOKEN", "").strip()
    if not t:
        sys.exit("META_TOKEN is not set. Export it; never pass a token on the command line.")
    return t


# ---- capability routing (tokens.py is the table) ----------------------------------------------------
# One token slot per capability. Ads reads/writes use META_TOKEN exactly as before; business reads,
# catalog, CAPI events and rules may have a variable of their own so a scraped EAAG / EAAH / EAAd /
# EAAI can serve them while an EAAB launches. Without its own variable a capability falls back to
# META_TOKEN only if META_TOKEN's class carries it, so a single-token setup behaves as it always did.
_DEFAULT_CAPABILITY: list[str | None] = [None]
_WORKSPACE_ENVS_CACHE: dict[str, Any] = {}
_WARNED_WRITE_CLASSES: set[str] = set()


class TokenChoice(NamedTuple):
    token: str
    var: str                    # the env var it came from
    capability: str | None
    cookies: str | None         # per-token cookie header when it differs from META_COOKIES


def set_default_capability(capability: str | None) -> None:
    """Scripts run as children (rules.py, mutate_set.py) name their capability once; every call
    without an explicit `capability=` then routes to that token."""
    if capability is not None and capability not in tokens.CAPABILITIES:
        raise ValueError(f"unknown token capability {capability!r}; known: {tokens.CAPABILITIES}")
    _DEFAULT_CAPABILITY[0] = capability


@contextlib.contextmanager
def using_capability(capability: str | None) -> Iterator[None]:
    previous = _DEFAULT_CAPABILITY[0]
    set_default_capability(capability)
    try:
        yield
    finally:
        _DEFAULT_CAPABILITY[0] = previous


def workspace_token_envs() -> dict[str, str]:
    """`defaults.token_envs` ({capability: ENV_NAME}) of the workspace in METAOPS_WORKSPACE, which
    metaops sets and children inherit. Missing file, bad JSON or a bad entry -> ignored."""
    path = os.environ.get("METAOPS_WORKSPACE", "")
    if not path:
        return {}
    try:
        stamp = os.stat(path).st_mtime_ns
    except OSError:
        return {}
    cached = _WORKSPACE_ENVS_CACHE.get(path)
    if cached and cached[0] == stamp:
        return cached[1]
    try:
        with open(path, encoding="utf-8") as fh:
            raw = (json.load(fh).get("defaults") or {}).get("token_envs") or {}
    except (OSError, ValueError, AttributeError):
        raw = {}
    envs = {}
    if isinstance(raw, dict):
        envs = {cap: name for cap, name in raw.items()
                if cap in tokens.ROUTED_CAPABILITIES and isinstance(name, str)
                and tokens.ENV_NAME.fullmatch(name)}
    _WORKSPACE_ENVS_CACHE[path] = (stamp, envs)
    return envs


def token_var_for(capability: str) -> str:
    if capability in tokens.ROUTED_CAPABILITIES:
        return workspace_token_envs().get(capability) or tokens.CAPABILITY_VARS[capability]
    return "META_TOKEN"


def _cookie_override(var: str, capability: str) -> str | None:
    own = os.environ.get(tokens.cookie_var(var, capability), "").strip()
    return own if own and own != os.environ.get("META_COOKIES", "").strip() else None


def cookies_for(var: str, capability: str | None = None) -> str | None:
    """The cookie header that goes with a token variable (its META_COOKIES_<X>, else META_COOKIES)."""
    return _cookie_override(var, capability or "") or os.environ.get("META_COOKIES", "").strip() or None


def resolve_token(capability: str | None = None) -> TokenChoice:
    """The token for a capability. None / ads_read / ads_write = META_TOKEN (unchanged behaviour).
    Exits with a message naming the missing variable and the fitting class, never a bare KeyError."""
    cap = capability or _DEFAULT_CAPABILITY[0]
    if cap is None or cap in ("ads_read", "ads_write"):
        return TokenChoice(token(), "META_TOKEN", cap, None)
    if cap not in tokens.CAPABILITIES:
        raise ValueError(f"unknown token capability {cap!r}; known: {tokens.CAPABILITIES}")
    var = token_var_for(cap)
    own = os.environ.get(var, "").strip()
    if own:
        return TokenChoice(own, var, cap, _cookie_override(var, cap))
    fit = tokens.TOKEN_CLASSES[tokens.FIT_CLASS[cap]]
    how = ("`pbpaste | metaops token import --env-file <file>` writes it to "
           f"{var} by class")
    base = os.environ.get("META_TOKEN", "").strip()
    if not base:
        sys.exit(f"{var} is not set (and META_TOKEN is empty). The {cap} capability needs a "
                 f"{fit.key} ({fit.name}) token; {how}.")
    cls = tokens.classify(base, os.environ.get(tokens.app_id_var("META_TOKEN"))).cls
    if tokens.carries(cls, cap):
        return TokenChoice(base, "META_TOKEN", cap, None)
    sys.exit(f"{var} is not set and META_TOKEN is a {cls.key} ({cls.name}) token, which does not "
             f"carry {cap}. Set {var} to a {fit.key} ({fit.name}) token; {how}.")


def token_for(capability: str | None = None) -> str:
    """Just the token string of `resolve_token`. Never print it."""
    return resolve_token(capability).token


def _guard_ads_write(choice: TokenChoice) -> None:
    """The acting token of an ads write must be able to write ads. Policy per class (tokens.py):
    refuse (EAAd: cannot even read the ad set, code 10, live 2026-09-29), allow (EAAB, EAAI, EAAG,
    EAAH: a real ad-set rename + restore worked with each on the own BM 2026-09-29), warn (the
    policy exists for a class whose writes are only partly proven; none uses it today). A prefix
    is only a guess (an own-app System User token can start with EAAd), so the message says how to
    clear a false positive."""
    if choice.capability not in (None, "ads_read", "ads_write"):
        return
    hit = tokens.classify(choice.token, os.environ.get(tokens.app_id_var(choice.var), ""))
    cls = hit.cls
    if cls.ads_write_policy == "allow":
        return
    allowed = {x.strip() for x in os.environ.get("METAOPS_ALLOW_TOKEN_CLASS", "").split(",") if x.strip()}
    if cls.key in allowed or "all" in allowed:
        return
    guess = "" if hit.confirmed else " (class from the 4-char prefix only, GET /app has not confirmed it)"
    if cls.ads_write_policy == "refuse":
        sys.exit(
            f"ads write refused: {choice.var} is a {cls.key} ({cls.name}) token{guess}: "
            f"{cls.known_failures.get('ads_objects', 'no ad-object access')}. Put an EAAB in "
            f"META_TOKEN and this one in {cls.default_var}. A System User or own-app token that "
            f"only starts with {cls.key}: re-import it with `metaops token import --allow-unknown` "
            f"(records {tokens.app_id_var(choice.var)}) or set METAOPS_ALLOW_TOKEN_CLASS={cls.key}."
        )
    if cls.key not in _WARNED_WRITE_CLASSES:
        _WARNED_WRITE_CLASSES.add(cls.key)
        note = cls.capabilities.get("ads_write", ("", ""))[1]
        print(f"  ! ads write with a {cls.key} ({cls.name}) token{guess}: {note}. "
              "Set METAOPS_ALLOW_TOKEN_CLASS to silence this.",
              file=sys.stderr)


# Central secret registry: META_TOKEN alone does not cover Page tokens minted via
# page_token() and passed as token_override, nor META_APP_SECRET / TG_BOT_TOKEN.
# Every token that crosses this transport registers here so redact() masks the whole
# known set — not just the process env token. Page-token leak into a log is a real
# hole (Page token = write access to the Page); it is covered by unit tests.
_KNOWN_SECRETS: set[str] = set()


def register_secret(value: str | None) -> None:
    """Remember one more credential for redact(). Short fragments are skipped so a
    1-3 char page id can never blank a whole log."""
    if not value or not isinstance(value, str):
        return
    text = value.strip()
    if len(text) >= 4:
        _KNOWN_SECRETS.add(text)


def _mask(text: str, secret: str, placeholder: str) -> str:
    if not secret:
        return text
    if secret in text:
        text = text.replace(secret, placeholder)
    encoded = quote(secret, safe="")
    if encoded != secret and encoded in text:
        text = text.replace(encoded, placeholder)
    return text


def _secret_env_names(prefix: str) -> list[str]:
    """META_TOKEN_* / META_COOKIES_* variables, plus the workspace's token_envs names for tokens."""
    names = {k for k in os.environ if k.startswith(prefix + "_") and not k.endswith("_APP_ID")}
    if prefix == "META_TOKEN":
        names |= set(workspace_token_envs().values())
    return sorted(names)


# The c_user cookie is the Facebook user id of the session: an account identifier, not a secret.
# It is also the id `GET /me` answers with, so masking it hides "who is this token" in doctor and
# makes the c_user == /me.id check unreadable. Every other cookie (xs, datr, sb, fr, ...) is masked.
OPEN_COOKIES = {"c_user"}


def _cookie_secret_values(cookies: str) -> list[str]:
    """The values of a cookie header that must never be printed: all but the OPEN_COOKIES."""
    values = []
    for part in (cookies or "").split(";"):
        name, sep, value = part.strip().partition("=")
        if sep and name.strip() not in OPEN_COOKIES and value.strip():
            values.append(value.strip())
    return values


def _mask_cookies(text: str, cookies: str) -> str:
    if not cookies:
        return text
    text = text.replace(cookies, "<COOKIES>")
    for part in cookies.split(";"):
        part = part.strip()
        if not part or part.partition("=")[0].strip() in OPEN_COOKIES:
            continue
        text = text.replace(part, "<COOKIE>")
        if "=" in part:
            _, val = part.split("=", 1)
            val = val.strip()
            if len(val) > 3:
                text = text.replace(val, "<COOKIE_VAL>")
    return text


def redact(text: str) -> str:
    """Strip every credential from anything about to be printed or written to disk.

    Covers the raw token, its URL-encoded form (requests percent-encodes it into the
    exception's request.url), every registered Page/override token (not only
    META_TOKEN), META_APP_SECRET, TG_BOT_TOKEN, cookies, and the proxy's user:pass —
    which rides in META_PROXY and lands in connection-error text."""
    t = os.environ.get("META_TOKEN", "")
    if t:
        text = _mask(text, t, "<TOKEN>")
        register_secret(t)
    for name in _secret_env_names("META_TOKEN"):
        other = os.environ.get(name, "").strip()
        if other and other != t:
            text = _mask(text, other, "<TOKEN>")
            register_secret(other)
    for extra in sorted(_KNOWN_SECRETS):
        # META_TOKEN itself is already masked above; extras are Page/override tokens.
        if extra != t:
            text = _mask(text, extra, "<TOKEN>")
    secret = os.environ.get("META_APP_SECRET", "").strip()
    if secret:
        text = _mask(text, secret, "<APP_SECRET>")
    tg = os.environ.get("TG_BOT_TOKEN", "").strip()
    if tg:
        text = _mask(text, tg, "<TG_TOKEN>")
    for name in ("META_COOKIES", *_secret_env_names("META_COOKIES")):
        text = _mask_cookies(text, os.environ.get(name, ""))
    proxy = os.environ.get("META_PROXY", "")
    m = re.search(r"://([^/@]+)@", proxy)
    if m:
        creds = m.group(1)
        text = text.replace(creds, "<PROXY_CREDS>")
        user = creds.split(":")[0]
        if len(user) > 2:
            text = text.replace(user, "<PROXY_USER>")
    return text


def _session(cookies: bool = True):
    s = _requests().Session()
    # Ignore HTTPS_PROXY / ALL_PROXY / NO_PROXY from the shell: the exit IP is decided by
    # META_PROXY alone, and an ambient proxy variable must not silently override it.
    s.trust_env = False
    proxy = os.environ.get("META_PROXY", "").strip()
    if proxy:
        if proxy.startswith("socks5://"):
            sys.exit(
                "META_PROXY uses socks5:// — DNS then resolves locally and TLS to "
                "graph.facebook.com dies with UNEXPECTED_EOF_WHILE_READING. Use socks5h://."
            )
        s.proxies = {"http": proxy, "https": proxy}
    elif os.environ.get("META_ALLOW_NO_PROXY") != "1":
        sys.exit(
            "META_PROXY is not set. A user-token persona must exit the same IP as its "
            "antidetect profile (01). For a server-side System User token, direct egress must "
            "be confirmed deliberately: under metaops with a workspace ONLY workspace.json "
            "defaults.allow_no_proxy=true does that (an exported META_ALLOW_NO_PROXY=1 is dropped "
            "by metaops on purpose); direct script use / workspace-free commands honour "
            "META_ALLOW_NO_PROXY=1."
        )
    cookie_header = os.environ.get("META_COOKIES", "").strip() if cookies else ""
    if cookie_header:
        s.headers["Cookie"] = cookie_header
    user_agent = os.environ.get("META_USER_AGENT", "").strip()
    s.headers["User-Agent"] = user_agent if user_agent else "meta-grey-ops/graph.py"
    return s


_SESSION = None
_SESSION_CONFIG = None
_WRITE_ACCOUNTS: set[str] | None = None
_WRITE_CAPABILITY_LOADED = False


def _session_config() -> tuple[str, str, str, str]:
    return (
        os.environ.get("META_PROXY", "").strip(),
        os.environ.get("META_ALLOW_NO_PROXY", ""),
        os.environ.get("META_COOKIES", "").strip(),
        os.environ.get("META_USER_AGENT", "").strip(),
    )


def session():
    global _SESSION, _SESSION_CONFIG
    current = _session_config()
    # A non-None config marks a real cached requests.Session. Tests and embedded callers
    # may inject a session directly; leave that object alone when no config was recorded.
    if _SESSION is None or (_SESSION_CONFIG is not None and _SESSION_CONFIG != current):
        _SESSION = _session()
        _SESSION_CONFIG = current
    return _SESSION


def plain_session():
    """Same proxy gate as session(), but no META_COOKIES header — for non-Graph hosts
    (Telegram, fbcdn). The Facebook session cookies must never leave for another host."""
    return _session(cookies=False)


def authorize_writes(accounts: list[str] | set[str]) -> None:
    """Authorize this metaops process after it has validated a workspace."""
    global _WRITE_ACCOUNTS, _WRITE_CAPABILITY_LOADED
    _WRITE_ACCOUNTS = {normalize_account(value) for value in accounts}
    _WRITE_CAPABILITY_LOADED = True


def _load_write_capability() -> None:
    """Load a one-shot capability inherited from the parent metaops process."""
    global _WRITE_ACCOUNTS, _WRITE_CAPABILITY_LOADED
    if _WRITE_CAPABILITY_LOADED:
        return
    _WRITE_CAPABILITY_LOADED = True
    fd_text = os.environ.pop("METAOPS_AUTH_FD", "")
    if not fd_text.isdigit():
        return
    try:
        raw = os.read(int(fd_text), 65536)
        os.close(int(fd_text))
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError, TypeError):
        return
    if payload.get("parent_pid") != os.getppid():
        return
    accounts = payload.get("allowed_accounts")
    if isinstance(accounts, list) and all(isinstance(value, str) for value in accounts):
        _WRITE_ACCOUNTS = {normalize_account(value) for value in accounts}


# A path segment that HTTP clients rewrite or decode before sending. `requests` collapses
# `act_1/../act_99/campaigns` to `/act_99/campaigns` AFTER the allow-list below matched the
# first segment, so the account gate must never see such a segment in the first place.
_SEGMENT_FORBIDDEN = re.compile(r"[%?#\\\s\x00-\x1f\x7f]")
_RAW_URL_FORBIDDEN = re.compile(r"[\\\s\x00-\x1f\x7f]")


def validate_graph_path(path: str) -> str:
    """Return `path` without leading slashes, or exit if any segment could be rewritten.

    Refused: `.` / `..` / empty segments (dot-segment traversal, `//`, a trailing `/`) and any
    segment carrying `%` (percent-encoded `..`), `?`, `#`, a backslash, whitespace or a
    control character. Runs for every method, before the account allow-list matches."""
    if not isinstance(path, str):
        sys.exit(f"refusing Graph path {path!r}: not a string")
    clean = path.lstrip("/")
    for segment in clean.split("/"):
        if segment in ("", ".", "..") or _SEGMENT_FORBIDDEN.search(segment):
            sys.exit(
                f"refusing Graph path {path!r}: segment {segment!r} is empty, a dot segment or "
                "holds a %, ?, #, backslash, whitespace or control character"
            )
    return clean


def require_write_authority(method: str, path: str) -> None:
    """Block accidental use of low-level mutators outside a validated metaops workspace."""
    path = validate_graph_path(path)
    if method.upper() == "GET":
        return
    _load_write_capability()
    if not _WRITE_ACCOUNTS:
        sys.exit(
            f"direct Graph {method.upper()} is disabled for {path}; use metaops from a "
            "validated workspace (low-level write scripts are internal implementations)"
        )
    match = re.match(r"^/?(act_[0-9]+)(?:/|$)", path)
    if match and match.group(1) not in _WRITE_ACCOUNTS:
        sys.exit(
            f"workspace does not authorize Graph write target {match.group(1)}"
        )


def next_page_params(response: dict[str, Any], params: dict[str, Any]) -> dict[str, Any] | None:
    """Return the next cursor request without following Graph's opaque ``paging.next`` URL.

    Graph has historically embedded access tokens in that URL. Requests here authenticate with
    a Bearer header, so preserve the original edge and query while advancing only with its
    cursor. Returning ``None`` also covers a malformed/terminal paging envelope.
    """
    paging = response.get("paging") or {}
    after = (paging.get("cursors") or {}).get("after")
    if not after or not paging.get("next"):
        return None
    return {**params, "after": str(after)}


def normalize_graph_path(path: str) -> str:
    """Validate an absolute Graph URL and return its version-free path for authorization.

    Every path segment is checked with validate_graph_path() first, so a dot segment or an
    encoded/oddly-delimited segment cannot reach the account allow-list (or the wire)."""
    if path.startswith(("http://", "https://")):
        if _RAW_URL_FORBIDDEN.search(path):
            sys.exit(f"refusing absolute Graph URL with whitespace, control chars or a backslash: {path!r}")
        parsed = urlsplit(path)
        if parsed.scheme != "https" or parsed.netloc.lower() != "graph.facebook.com":
            sys.exit(
                f"refusing absolute Graph URL outside https://graph.facebook.com: {path}"
            )
        path = parsed.path
    clean = validate_graph_path(path)
    return re.sub(r"^v[0-9]+\.[0-9]+/", "", clean)


def normalize_account(x) -> str:
    """`123` / `act_123` → `act_123`. One helper so every CLI accepts both forms."""
    x = str(x).strip()
    return x if x.startswith("act_") else f"act_{x}"


# `x-fb-ads-insights-throttle` is flat JSON on Insights calls:
# {"app_id_util_pct": 25.5, "acc_id_util_pct": 10.0, "ads_api_access_tier": "standard_access"}.
# Its *_util_pct keys are matched by _worst_usage's `_pct` rule; the tier string is skipped.
USAGE_HEADERS = (
    "x-app-usage",
    "x-ad-account-usage",
    "x-business-use-case-usage",
    "x-fb-ads-insights-throttle",
)


def _worst_usage(headers) -> float:
    """Highest utilisation percentage across every usage header Meta returned.

    In `x-business-use-case-usage` the per-bucket `call_count`, `total_cputime`, `total_time`
    ARE percentages of the hourly quota (0-100), not counts — doc-confirmed, meta-ads/14
    "Rate limits". Values are clamped to 0-100 so a future absolute counter under the same
    name cannot trip the pause threshold on its own."""
    worst = 0.0
    for name in USAGE_HEADERS:
        raw = headers.get(name)
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            continue
        buckets = []
        if isinstance(data, dict):
            # x-app-usage is flat; x-business-use-case-usage is keyed by business id.
            for v in data.values():
                if isinstance(v, list):
                    buckets.extend(v)
            if not buckets:
                buckets = [data]
        for b in buckets:
            if not isinstance(b, dict):
                continue
            for k, v in b.items():
                if k.endswith(("_pct", "_util_pct")) or k in (
                    "call_count",
                    "total_cputime",
                    "total_time",
                ):
                    try:
                        worst = max(worst, min(float(v), 100.0))
                    except (TypeError, ValueError):
                        pass
    return worst


def _regain_seconds(headers) -> int:
    raw = headers.get("x-business-use-case-usage")
    if not raw:
        return 0
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return 0
    worst = 0
    for buckets in data.values():
        if not isinstance(buckets, list):
            continue
        for b in buckets:
            try:
                worst = max(worst, int(b.get("estimated_time_to_regain_access", 0)))
            except (TypeError, ValueError, AttributeError):
                pass
    return worst * 60


def _encode(v: Any) -> Any:
    """Graph takes complex values as JSON strings — in the QUERY STRING as well as the
    body. `time_range` and `action_attribution_windows` on the Insights edge are query
    params: left as Python objects they arrive as `{'since': ...}` with single quotes and
    are ignored or rejected, so the call silently reports the wrong window.

    Booleans need it too: requests renders a bare Python bool as "True"/"False", which
    Graph does not accept as a boolean. json.dumps gives true/false.
    """
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (dict, list)):
        return json.dumps(v, separators=(",", ":"))
    return v


def _file_bytes(value: Any) -> Any:
    """(name, handle[, ...]) or a bare handle → the same shape with bytes in place."""
    if isinstance(value, tuple) and len(value) >= 2 and hasattr(value[1], "read"):
        return (value[0], value[1].read(), *value[2:])
    if hasattr(value, "read"):
        return value.read()
    return value


def call(
    method: str,
    path: str,
    params: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    files: dict[str, Any] | None = None,
    token_override: str | None = None,
    context: str = "",
    retries: int = 4,
    idempotent: bool | None = None,
    capability: str | None = None,
    cookies: str | None = None,
) -> Any:
    """One Graph call with rate-limit backoff. Raises GraphError on a hard failure.

    Nested values in `data` are JSON-encoded, because Graph takes complex fields as
    JSON strings in a form body. The rule is ENCODE EXACTLY ONCE. This encoder already
    satisfies it either way — dicts and lists are stringified once, strings pass through
    untouched — so pass whichever you have. The trap lives one layer up: stringify a
    value yourself and then hand it to something that stringifies everything (the
    business SDK does), and it arrives double-encoded. A double-encoded product-set
    `filter` silently no-ops: HTTP 200, set id returned, filter unchanged (04).
    """
    authorization_path = normalize_graph_path(path)
    require_write_authority(method, authorization_path)

    global _LAST_ACCOUNT
    account = _account_of(path)
    if account:
        _LAST_ACCOUNT = account
    left = max(cooldown_remaining(account or _LAST_ACCOUNT),
               _key_remaining("obj:" + authorization_path.split("/")[0]))
    if left > 0 and not _pace_override():
        raise CooldownError(account or _LAST_ACCOUNT or "*", left, context or path)

    # A transport failure, a bodyless 5xx or an `is_transient` Graph error on a CREATE is not
    # safe to retry: the request may have been applied before the reply was lost or the error
    # raised, so a retry duplicates the object. Only GETs and calls marked idempotent=True
    # are re-sent; a non-idempotent call surfaces the error once, with outcome_unknown set.
    if idempotent is None:
        idempotent = method.upper() == "GET"

    url = path if path.startswith(("http://", "https://")) else f"{BASE}/{path.lstrip('/')}"
    params = {k: _encode(v) for k, v in (params or {}).items() if v is not None}
    # `capability` picks the token slot (tokens.py); `cookies` forces a per-request cookie header
    # (a token_override call otherwise rides the session-level META_COOKIES, as it always did).
    choice = None if token_override else resolve_token(capability)
    tok = token_override or choice.token
    if choice is not None and method.upper() != "GET":
        _guard_ads_write(choice)
    # Register every effective token (including Page-token overrides) so a later
    # redact() masks it even though it never lived in META_TOKEN.
    register_secret(tok)
    if token_override:
        register_secret(token_override)
    # The token travels in the Authorization header, never in the query string: a URL
    # lands in proxy/access logs and exception strings, a header does not.
    headers = {"Authorization": f"Bearer {tok}"}
    cookie_header = cookies if cookies is not None else (choice.cookies if choice else None)
    if cookie_header:
        headers["Cookie"] = cookie_header
        for value in _cookie_secret_values(cookie_header):
            register_secret(value)
    secret = os.environ.get("META_APP_SECRET", "").strip()
    if secret:
        params["appsecret_proof"] = hmac.new(secret.encode(), tok.encode(), hashlib.sha256).hexdigest()

    body = None
    if data is not None:
        body = {k: _encode(v) for k, v in data.items() if v is not None}
    # Materialize file handles once. A retry re-sends `files`; a handle the first attempt
    # already read to EOF would upload an empty body the second time.
    if files:
        files = {k: _file_bytes(v) for k, v in files.items()}

    delay = 2.0
    for attempt in range(retries + 1):
        try:
            resp = session().request(
                method.upper(), url, params=params, data=body, files=files, headers=headers,
                timeout=180,
            )
        except Exception as exc:  # noqa: BLE001 - transport errors embed the tokenised URL
            # The token is a header now, but redact anyway: an overridden Page token or a
            # caller-built URL could still carry one into the exception string.
            # A dropped proxy connection or a read timeout is exactly what retries exist
            # for: back off and try again, and only surface it once they are exhausted.
            err = GraphError(
                0, {"error": {"message": redact(str(exc)), "code": -1, "is_transient": True}},
                context,
            )
            if not idempotent:
                # Do not retry. The caller records this as an unknown outcome and stops.
                raise err from None
            if attempt < retries:
                wait = delay + random.uniform(0, 1)
                print(f"  ! transport error — retrying in {wait:.1f}s ({err.message[:120]})",
                      file=sys.stderr)
                time.sleep(wait)
                delay = min(delay * 2, 60)
                continue
            raise err from None

        usage = _worst_usage(resp.headers)
        if usage >= USAGE_PAUSE_PCT:
            wait = 60 * (usage / 100.0)
            print(f"  ! usage at {usage:.0f}% — sleeping {wait:.0f}s", file=sys.stderr)
            time.sleep(wait)

        try:
            payload = resp.json()
        except ValueError:
            payload = {"error": {"message": redact(resp.text[:500]), "code": -1}}

        if resp.ok and "error" not in payload:
            return payload

        err = GraphError(resp.status_code, payload, context)

        account_level = err.code in ACCOUNT_THROTTLE_CODES or (
            isinstance(err.code, int) and 80000 <= err.code <= 80999
        )
        if err.code == 613 and err.subcode == 4841018 and attempt < retries:
            # "concurrent request rate limit of 1 calls per 30 seconds" on ONE object (live
            # 2026-09-27: status edit right after create). Meta states the wait; one spaced retry
            # is compliant, not a storm, and no cooldown is set for the account.
            print("  ! 613/4841018 per-object 1 call/30 s — waiting 35 s, one retry", file=sys.stderr)
            time.sleep(35)
            retries = attempt + 1
            continue
        if account_level or err.code in GLOBAL_THROTTLE_CODES:
            # Never retry a throttle (see THROTTLE_COOLDOWN_MIN). Code 17 / 80004 is the
            # ad-account score cap; on the Limited tier the block is ~300 s and retries extend
            # it. Put the account (or everything, for app/user-level codes) on cooldown and stop.
            # Unknown account on an object path: charge the object, never every account.
            obj = "obj:" + normalize_graph_path(path).split("/")[0]
            key = (account or _LAST_ACCOUNT or obj) if account_level else "*"
            minutes = float(os.environ.get("METAOPS_THROTTLE_COOLDOWN_MIN", THROTTLE_COOLDOWN_MIN))
            seconds = max(minutes * 60, float(_regain_seconds(resp.headers)))
            _set_cooldown(key, seconds, f"code {err.code}/{err.subcode} at {context or path}")
            print(f"  ! throttled ({err.code}/{err.subcode}) — {key} on cooldown {seconds / 60:.0f} min, "
                  "not retrying", file=sys.stderr)
            raise err

        # A 5xx with no Graph error envelope (an HTML page from the proxy or Meta's edge)
        # is the same class of event as a dropped connection: the request may or may not
        # have been applied, and `is_transient` is absent because Meta never answered.
        # Retry it on the same terms as a transport error — idempotent callers only.
        if err.outcome_unknown and idempotent and attempt < retries:
            wait = delay + random.uniform(0, 1)
            print(f"  ! {resp.status_code} with no Graph error body — retrying in {wait:.1f}s",
                  file=sys.stderr)
            time.sleep(wait)
            delay = min(delay * 2, 60)
            continue

        if err.is_transient:
            if not idempotent:
                # Graph flagged the failure as temporary, but it did not promise the request
                # was not applied — a re-sent create can become a duplicate object. Surface
                # it without re-sending; the caller records an unknown outcome and reconciles.
                err.outcome_unknown = True
                print(f"  ! transient ({err.code}) on a non-idempotent {method.upper()} — not retried, "
                      "outcome unknown", file=sys.stderr)
                raise err
            if attempt < retries:
                wait = delay + random.uniform(0, 1)
                print(f"  ! transient ({err.code}) — retrying in {wait:.1f}s", file=sys.stderr)
                time.sleep(wait)
                delay = min(delay * 2, 60)
                continue

        raise err

    raise GraphError(0, {"error": {"message": "retries exhausted", "code": -1}}, context)


def get(path: str, **kw) -> Any:
    return call("GET", path, params=kw.pop("params", None), context=kw.pop("context", path), **kw)


def post(path: str, data: dict[str, Any], **kw) -> Any:
    """Defaults to NOT retrying on a transport error — a create may already have been
    applied. Pass idempotent=True for writes that are safe to repeat (status flips,
    budget updates, filter swaps)."""
    return call("POST", path, data=data, context=kw.pop("context", path), **kw)


def page_token(page_id: str) -> str:
    """A Page access token. Required for the PBIA edge — a user/SU token returns 190
    'must be called with a Page Access Token', which means wrong token type, not a
    missing PBIA (meta-ads/13 §5).

    Graph does not error when the caller lacks Page admin rights: it returns the node
    WITHOUT the access_token field. Left unhandled that surfaces as a KeyError traceback
    instead of a diagnosable gate failure, so it is converted here."""
    node = get(f"{page_id}", params={"fields": "access_token"}, context="page_token")
    if "access_token" not in node:
        # status 403 deliberately: status 0 is this module's "outcome unknown" sentinel,
        # and a permissions gap is a definite, knowable answer.
        raise GraphError(
            403,
            {"error": {"message": (
                f"Page {page_id} returned no access_token. The token lacks a Page role "
                f"(need >=ADVERTISER, and pages_manage_ads / pages_read_engagement). "
                f"This is a permissions gap, not a missing PBIA."),
                "code": -1, "type": "OAuthException"}},
            "page_token",
        )
    register_secret(str(node["access_token"]))
    return node["access_token"]


def main() -> int:
    argparse.ArgumentParser(
        description="Internal Meta Graph transport used by workspace-bound metaops commands."
    ).parse_args()
    return 0


if __name__ == "__main__":
    sys.exit(main())

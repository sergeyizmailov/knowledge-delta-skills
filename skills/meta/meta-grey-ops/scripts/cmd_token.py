#!/usr/bin/env python3
"""`metaops token import`: turn a pasted FB Helper block into a verified, correctly routed env file.

    pbpaste | metaops token import --env-file .notes/meta.env             # verify, then write
    pbpaste | metaops token import                                        # verify only (dry run)
    pbpaste | metaops token import --env-file F --name META_TOKEN_CATALOG   # explicit variable

Reads stdin: a token (`EAA...`), optionally the cookie header (`c_user=...; xs=...`, or the JSON
array of the extension's cookie button) and a User-Agent line, bare or as `META_TOKEN=...
META_COOKIES=... META_USER_AGENT=...`. The FB Helper "token + cookies" block is `token`, a blank
line, `cookie header`. The extension gives one such block per class: a paste may hold several,
provided every token is of a DIFFERENT class (EAAB, EAAI, EAAG, EAAH, EAAd, at most one unknown
with --allow-unknown); they share one login's cookies and User-Agent. Two tokens of the same class,
cookie blocks of different logins (c_user differs) or different User-Agents are refused as
ambiguous; cookie sets that differ but share the c_user keep the last complete one and warn.

The class of the token is decided by prefix AND app id (tokens.py): EAAB Ads Manager, EAAI
Automated Rules, EAAG Business Manager, EAAH Commerce Manager, EAAd Events Manager. Anything else
is unknown and needs --allow-unknown. Each class is written to its own variable (EAAB META_TOKEN,
EAAG META_TOKEN_BUSINESS, EAAH META_TOKEN_CATALOG, EAAd META_TOKEN_EVENTS, EAAI META_TOKEN_RULES;
or the workspace `defaults.token_envs` name); --name overrides. Cookies and the User-Agent go to
the shared META_COOKIES / META_USER_AGENT (same login = same session) unless --cookies-suffix.

With several tokens each is verified in paste order and the first failure stops everything
(nothing is written); the env file is then written once, atomically. Per-token flags (--name,
--cookies-suffix) are refused, every class goes to its own variable.

Session facts (live 2026-09-29): EAAB, EAAI, EAAG and EAAH answer code 1 without the cookies, an
EAAd reads without them (so an EAAd-only paste never warns about cookies, and a paste of EAAd plus
others still shares the cookies); the User-Agent is optional (the extension exports none).

Verification (skipped by --no-verify) is two GETs at most per token: /me?fields=id,name and /app?fields=id,name,
through the proxy in META_PROXY with the pasted cookies and User-Agent. It refuses, writing nothing,
on 190 / 102 / 459 / 460 / 463 / 467 and code 1, and when the c_user cookie is not the /me id.

Writing is atomic (temp file in the same directory, mode 0600, os.replace), keeps every unrelated
line, replaces only the keys it manages, leaves a 0600 `.bak` of the previous file, and never
prints the token or the cookies: only class, app, user, the token's first and last 4 characters,
the cookie NAMES and the path.
"""

from __future__ import annotations

import argparse
import contextlib
import functools
import json
import os
import pathlib
import re
import secrets
import sys
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import tokens

MAX_INPUT_BYTES = 1_000_000
TOKEN_RE = re.compile(r"(?<![A-Za-z0-9])EAA[A-Za-z0-9]{20,}(?![A-Za-z0-9])")
KEYED_RE = re.compile(r"(?:^|(?<=\s))(?:export\s+)?(?P<key>[A-Za-z_][A-Za-z0-9_]*)=")
COOKIE_NAME_RE = re.compile(r"^[A-Za-z0-9_.\-]+$")
SESSION_COOKIES = {"c_user", "xs"}
COOKIE_SUFFIXES = ("BUSINESS", "CATALOG", "EVENTS", "RULES")
COOKIES_VAR, UA_VAR = "META_COOKIES", "META_USER_AGENT"
DEATH_CODES = {190, 102}
DEATH_SUBCODES = {459, 460, 463, 467}
# The class -> capability whose workspace `defaults.token_envs` name it may take.
CLASS_CAPABILITY = {"EAAG": "business_read", "EAAH": "catalog", "EAAd": "events_write",
                    "EAAI": "rules"}


class ImportRefused(Exception):
    """The paste or the token is not acceptable; nothing is written. `calls` = Graph calls spent."""

    def __init__(self, message: str, calls: int | None = None):
        super().__init__(message)
        self.calls = calls


@dataclass
class Paste:
    token: str
    cookies: str | None = None
    user_agent: str | None = None


@dataclass
class Batch:
    """Everything one paste holds: one token per class, one shared cookie set / User-Agent."""
    tokens: list[str]
    cookies: str | None = None
    user_agent: str | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass
class Verification:
    ran: bool = False
    calls: int = 0
    me: dict[str, Any] | None = None
    app: dict[str, Any] | None = None
    app_error: str | None = None


# --------------------------------------------------------------------------- parsing

def _unquote(raw: str) -> str:
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] in "'\"":
        end = raw.find(raw[0], 1)
        return raw[1:end] if end != -1 else raw[1:]
    return raw


def _cookie_header(line: str) -> str | None:
    """`Cookie: c_user=1; xs=2` or `c_user=1; xs=2` -> "c_user=1; xs=2", else None."""
    body = re.sub(r"^\s*cookie:\s*", "", line, flags=re.IGNORECASE)
    pairs: list[str] = []
    names: set[str] = set()
    for part in (p.strip() for p in body.split(";")):
        if not part:
            continue
        name, sep, value = part.partition("=")
        if not sep or not COOKIE_NAME_RE.fullmatch(name.strip()):
            return None
        names.add(name.strip())
        pairs.append(f"{name.strip()}={value.strip()}")
    return "; ".join(pairs) if names & SESSION_COOKIES else None


def _json_cookies(text: str) -> tuple[str | None, str]:
    """The extension's cookie JSON (`[{"name":..,"value":..}, ...]`) -> header; text without it."""
    match = re.search(r"\[\s*\{.*?\}\s*\]", text, re.DOTALL)
    if not match:
        return None, text
    try:
        rows = json.loads(match.group(0))
    except ValueError:
        return None, text
    if not (isinstance(rows, list) and rows and all(isinstance(r, dict) for r in rows)):
        return None, text
    by_name: dict[str, str] = {}
    for row in rows:
        if isinstance(row.get("name"), str) and isinstance(row.get("value"), str):
            by_name[row["name"]] = row["value"]
    if not by_name:
        return None, text
    return "; ".join(f"{k}={v}" for k, v in by_name.items()), text.replace(match.group(0), "\n")


def cookie_pairs(header: str | None) -> dict[str, str]:
    pairs: dict[str, str] = {}
    for part in (header or "").split(";"):
        name, sep, value = part.strip().partition("=")
        if sep and name.strip():
            pairs[name.strip()] = value.strip()
    return pairs


def _one(values: list[str], what: str) -> str | None:
    distinct = list(dict.fromkeys(values))
    if len(distinct) > 1:
        raise ImportRefused(f"ambiguous input: {len(distinct)} different {what} in the paste; "
                            "paste one login's block at a time")
    return distinct[0] if distinct else None


@dataclass
class _Scan:
    found: list[str]
    cookies: list[str]
    agents: list[str]


def _scan(text: str, extra_keys: tuple[str, ...]) -> _Scan:
    if len(text.encode("utf-8", "replace")) > MAX_INPUT_BYTES:
        raise ImportRefused("input is larger than 1 MB; paste only the token block")
    text = text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    json_cookies, text = _json_cookies(text)
    managed = set(extra_keys)

    def is_managed(key: str) -> bool:
        return (key in managed or key.startswith(("META_TOKEN", "META_COOKIES", "META_USER_AGENT"))
                ) and not key.endswith("_APP_ID")

    keyed_tokens: list[str] = []
    cookies: list[str] = [json_cookies] if json_cookies else []
    agents: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        marks = [m for m in KEYED_RE.finditer(stripped) if is_managed(m.group("key"))]
        if marks:
            for index, mark in enumerate(marks):
                end = marks[index + 1].start() if index + 1 < len(marks) else len(stripped)
                key, value = mark.group("key"), _unquote(stripped[mark.end():end])
                if key.startswith("META_COOKIES"):
                    header = _cookie_header(value)
                    if header is None and value:
                        raise ImportRefused(f"{key} does not look like a cookie header (name=value; ...)")
                    if header:
                        cookies.append(header)
                elif key.startswith("META_USER_AGENT"):
                    if value:
                        agents.append(value)
                elif value:
                    keyed_tokens.append(value)
            continue
        agent = re.sub(r"^\s*user-agent:\s*", "", stripped, flags=re.IGNORECASE)
        if re.match(r"^Mozilla/\d", agent):
            agents.append(agent)
            continue
        header = _cookie_header(stripped)
        if header:
            cookies.append(header)
    found = list(TOKEN_RE.findall(text))
    for value in keyed_tokens:
        if not TOKEN_RE.fullmatch(value):
            raise ImportRefused("a META_TOKEN value is present but is not a Graph token (EAA...)")
    if not found:
        raise ImportRefused("no token found: expected a Graph token starting with EAA (paste the "
                            "FB Helper block or a META_TOKEN=... line)")
    return _Scan(found, cookies, agents)


def _check_storable(cookies: str | None, agent: str | None) -> None:
    for label, value in (("cookies", cookies), ("User-Agent", agent)):
        if value and (re.search(r"[\x00-\x1f\x7f']", value) or len(value) > 8000):
            raise ImportRefused(f"the {label} value has a control character, a single quote or is "
                                "over 8000 characters; it cannot be stored in an env file safely")


def parse_paste(text: str, extra_keys: tuple[str, ...] = ()) -> Paste:
    """Extract token, cookies and User-Agent from any of the shapes above. Raises ImportRefused
    on no token, a value that is not a Graph token, or more than one distinct token / cookie
    header / User-Agent."""
    scan = _scan(text, extra_keys)
    token = _one(scan.found, "tokens")
    header = _one(scan.cookies, "cookie sets")
    agent = _one(scan.agents, "User-Agent lines")
    _check_storable(header, agent)
    assert token is not None
    return Paste(token=token, cookies=header, user_agent=agent)


def _class_of_prefix(token: str) -> str:
    return token[:4] if token[:4] in tokens.FIRST_PARTY else "unknown"


def _shared_cookies(headers: list[str]) -> tuple[str | None, list[str]]:
    """Several tokens share one login, so their cookie blocks should be the same. Different
    c_user = different logins: refuse. Same c_user but different sets (an older or partial copy):
    keep the LAST complete one (c_user and xs), else the last, and say so."""
    distinct = list(dict.fromkeys(headers))
    if len(distinct) <= 1:
        return (distinct[0] if distinct else None), []
    users = {cookie_pairs(h).get("c_user") for h in distinct} - {None}
    if len(users) > 1:
        raise ImportRefused("ambiguous input: the cookie blocks belong to different logins (their c_user "
                            "differs); paste the blocks of one login at a time")
    chosen = next((h for h in reversed(headers) if SESSION_COOKIES <= set(cookie_pairs(h))),
                  headers[-1])
    return chosen, [f"{len(distinct)} different cookie sets in the paste (same c_user): kept the last "
                    "complete one for all tokens"]


def parse_batch(text: str, extra_keys: tuple[str, ...] = ()) -> Batch:
    """The FB Helper gives one block per class (token, blank line, cookie header). One paste may
    hold several, provided every token is of a DIFFERENT class; two of one class stay ambiguous.
    A single-token paste is parsed exactly as parse_paste does."""
    scan = _scan(text, extra_keys)
    found = list(dict.fromkeys(scan.found))
    if len(found) == 1:
        header = _one(scan.cookies, "cookie sets")
        agent = _one(scan.agents, "User-Agent lines")
        _check_storable(header, agent)
        return Batch(found, header, agent)
    by_class: dict[str, str] = {}
    for token in found:
        key = _class_of_prefix(token)
        if key in by_class:
            what = "of unknown class" if key == "unknown" else f"of the same class ({key})"
            raise ImportRefused(
                f"ambiguous input: two tokens {what} in the paste ({tokens.mask(by_class[key])} and "
                f"{tokens.mask(token)}); paste one token per class")
        by_class[key] = token
    header, warnings = _shared_cookies(scan.cookies)
    agent = _one(scan.agents, "User-Agent lines")
    _check_storable(header, agent)
    return Batch(found, header, agent, warnings)


# --------------------------------------------------------------------------- verification

@contextlib.contextmanager
def _scoped_env(overrides: dict[str, str | None]) -> Iterator[None]:
    saved = {name: os.environ.get(name) for name in overrides}
    try:
        for name, value in overrides.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        yield
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def _scrub(ctx: Any, paste: Paste, text: str) -> str:
    """Nothing pasted may reach output, whatever an error message carries."""
    for secret in [paste.token, paste.cookies or "", *ctx.graph._cookie_secret_values(paste.cookies or "")]:
        if len(secret) >= 4:
            text = text.replace(secret, "<SECRET>")
    return ctx.graph.redact(text)


def _graph_reason(exc: Any) -> tuple[str, str]:
    """(kind, one line) for a GraphError. kinds: dead, session, transport, graph."""
    code, sub = exc.code, exc.subcode
    if code in DEATH_CODES or code in DEATH_SUBCODES or sub in DEATH_SUBCODES:
        return "dead", (f"code {code}/{sub}: the token is dead or invalid (logout, password change, "
                        "checkpoint or a bad copy); take a fresh one from a live session")
    if code == 1:
        return "session", ("code 1: Meta rejects the token outside its session. Paste the token "
                           "together with the cookies of the SAME browser profile (EAAB, EAAI, EAAG "
                           "and EAAH answer code 1 without them) and use that profile's proxy "
                           "(META_PROXY)")
    if getattr(exc, "status", None) == 0 or code == -1:
        return "transport", (f"could not reach Graph ({exc.message[:160]}). Check META_PROXY; "
                             "--no-verify writes without checking")
    return "graph", f"code {code}/{sub}: {(exc.user_msg or exc.message)[:200]}"


def verify(ctx: Any, paste: Paste) -> Verification:
    """/me then /app: two GETs, no retries, no debug_token (first-party tokens answer #100).
    Cookies come from the paste only (an older session's ambient cookies must not vouch for a new
    token); the User-Agent falls back to the ambient one; the app-secret proof is dropped (it is
    an HMAC of a different app's secret and would turn a good token into a 190)."""
    graph = ctx.graph
    graph.register_secret(paste.token)
    for value in [paste.cookies or "", *graph._cookie_secret_values(paste.cookies or "")]:
        graph.register_secret(value)  # not c_user: the user id is an identifier, printed on purpose
    result = Verification(ran=True)
    overrides = {COOKIES_VAR: paste.cookies, "META_APP_SECRET": None}
    if paste.user_agent:
        overrides[UA_VAR] = paste.user_agent
    saved_account = graph._LAST_ACCOUNT
    graph._LAST_ACCOUNT = None  # /me belongs to no ad account: an account cooldown is not its business
    try:
        with _scoped_env(overrides):
            try:
                me = graph.get("me", params={"fields": "id,name"}, token_override=paste.token,
                               retries=0, context="token import identity")
                result.calls = 1
            except graph.GraphError as exc:
                result.calls = 1
                kind, line = _graph_reason(exc)
                raise ImportRefused(f"/me refused: {_scrub(ctx, paste, line)}", calls=1) from None
            result.me = {"id": str(me.get("id") or ""), "name": me.get("name")}
            try:
                app = graph.get("app", params={"fields": "id,name"}, token_override=paste.token,
                                retries=0, context="token import app")
                result.calls = 2
                result.app = {"id": str(app.get("id") or ""), "name": app.get("name")}
            except graph.GraphError as exc:
                result.calls = 2
                kind, line = _graph_reason(exc)
                if kind in ("dead", "session"):
                    raise ImportRefused(f"/app refused: {_scrub(ctx, paste, line)}", calls=2) from None
                result.app_error = _scrub(ctx, paste, line)
    except SystemExit as exc:  # graph._session: META_PROXY missing or socks5:// instead of socks5h://
        raise ImportRefused(_scrub(ctx, paste, str(exc.code))) from None
    finally:
        graph._LAST_ACCOUNT = saved_account
    return result


# --------------------------------------------------------------------------- the gate

@dataclass
class Decision:
    cls: tokens.TokenClass
    confirmed: bool
    var: str
    cookies_var: str
    refusals: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _workspace_token_envs(workspace: Any) -> dict[str, str]:
    defaults = (workspace.data.get("defaults") or {}) if workspace else {}
    return dict(defaults.get("token_envs") or {})


def _ads_variables(workspace: Any) -> set[str]:
    names = {"META_TOKEN"}
    if workspace:
        names.add(str((workspace.data.get("defaults") or {}).get("token_env") or "META_TOKEN"))
    return names


def decide(args: argparse.Namespace, paste: Paste, seen: Verification, workspace: Any,
           existing: dict[str, str]) -> Decision:
    """Class, target variable, and every reason to refuse or warn. Pure: no I/O."""
    prefix_cls = tokens.by_prefix(paste.token)
    app_id = (seen.app or {}).get("id") or ""
    app_cls = tokens.by_app_id(app_id) if app_id else None
    unknown = tokens.TOKEN_CLASSES["unknown"]
    refusals: list[str] = []
    warnings: list[str] = []
    if app_id and app_cls is not None:
        cls, confirmed = app_cls, True
        if prefix_cls is not app_cls:
            msg = (f"the prefix {paste.token[:4]} says "
                   f"{prefix_cls.key if prefix_cls else 'not a first-party class'} but GET /app "
                   f"returned app {app_id}, which is {app_cls.key} {app_cls.name}")
            if not args.force:
                refusals.append(f"{msg}. Refused; --force takes the app id as authoritative.")
            else:
                warnings.append(f"{msg}; --force: class set from the app id.")
    elif app_id:
        cls, confirmed = unknown, True
        why = (f"prefix {paste.token[:4]} names {prefix_cls.key}, but " if prefix_cls else "")
        if not args.allow_unknown:
            refusals.append(
                f"unknown token class: {why}GET /app returned app {app_id} "
                f"({(seen.app or {}).get('name')}), which is none of the five first-party apps "
                "(a System User or own-app token can share a prefix). Refused without "
                "--allow-unknown; it is then written to META_TOKEN with its app id recorded.")
    else:
        cls, confirmed = (prefix_cls or unknown), False
        if not seen.ran:
            warnings.append("--no-verify: the class comes from the prefix only and is not confirmed")
        elif seen.app_error:
            warnings.append(f"GET /app failed ({seen.app_error}): class from the prefix, not confirmed")
        if prefix_cls is None and not args.allow_unknown:
            refusals.append(f"unknown token class: prefix {paste.token[:4]} is none of EAAB, EAAI, "
                            "EAAG, EAAH, EAAd. Refused without --allow-unknown.")
    ws_envs = _workspace_token_envs(workspace)
    default_var = ws_envs.get(CLASS_CAPABILITY.get(cls.key, ""), cls.default_var)
    ads_vars = _ads_variables(workspace)
    var = args.name or ("META_TOKEN" if (args.as_ads and cls.key == "EAAG") else default_var)
    if var in ads_vars and cls.first_party and cls.key != "EAAB":
        if cls.key == "EAAG":
            current = existing.get(var, "")
            if not args.as_ads:
                refusals.append(f"{var} is the ads token; an EAAG belongs in "
                                f"{ws_envs.get('business_read', 'META_TOKEN_BUSINESS')}. --as-ads writes it "
                                f"to {var} (only when the file holds no EAAB there).")
            elif current[:4] == "EAAB" and not args.force:
                refusals.append(f"{var} in the env file already holds an EAAB; --as-ads is only for "
                                "a file without one (--force overrides)")
        elif not args.force:
            why = ("it cannot write ads (no ad-object access)" if cls.ads_write_policy == "refuse"
                   else "it is not the launch token, META_TOKEN is the EAAB slot (its ad-set writes "
                        "work on the own BM, 2026-09-29)")
            refusals.append(
                f"{cls.key} ({cls.name}) does not belong in {var}: {why}. It goes in "
                f"{cls.default_var}; --force writes it to {var} anyway.")
    if args.as_ads and cls.key != "EAAG":
        warnings.append("--as-ads only applies to an EAAG; ignored")
    cookies_var = COOKIES_VAR
    if args.cookies_suffix:
        suffix = args.cookies_suffix
        if suffix == "auto":
            suffix = var[len("META_TOKEN_"):] if var.startswith("META_TOKEN_") else ""
        if suffix not in COOKIE_SUFFIXES:
            refusals.append(f"--cookies-suffix must be one of {list(COOKIE_SUFFIXES)} (graph.py reads "
                            "only those); with --name pick one explicitly")
        else:
            cookies_var = f"{COOKIES_VAR}_{suffix}"
    if paste.cookies and cookies_var == COOKIES_VAR:
        old = cookie_pairs(existing.get(COOKIES_VAR, "")).get("c_user")
        new = cookie_pairs(paste.cookies).get("c_user")
        if old and new and old != new and not args.force:
            refusals.append(
                "the env file's shared META_COOKIES belong to another login (its c_user differs from "
                "this paste); replacing them would break the tokens already in the file. Use "
                "--cookies-suffix for this token's own cookies, or --force.")
    pairs = cookie_pairs(paste.cookies)
    if paste.cookies:
        if "c_user" not in pairs:
            warnings.append("no c_user cookie in the paste: the session binding cannot be checked")
        if "xs" not in pairs:
            warnings.append("no xs cookie in the paste: the session is incomplete")
    if cls.first_party and cls.needs_cookies and not paste.cookies:
        # Verified 2026-09-29: EAAB, EAAI, EAAG and EAAH answer code 1 without the cookies. An EAAd
        # needs none, and no class needs the User-Agent (the extension exports none).
        warnings.append(f"{cls.key} without cookies: Meta answers code 1 outside its session. "
                        "Paste the token with the cookies of the same login.")
    if seen.ran and paste.cookies and "c_user" in pairs and seen.me:
        if pairs["c_user"] != seen.me["id"]:
            refusals.append(f"the c_user cookie is not the /me id ({seen.me['id']}): the cookies "
                            "belong to another login. Copy token and cookies from the same profile.")
    elif paste.cookies and "c_user" in pairs and not seen.ran:
        warnings.append("--no-verify: the c_user cookie was not compared with the /me id")
    if var != "META_TOKEN" and paste.cookies and cookies_var == COOKIES_VAR:
        warnings.append("META_COOKIES / META_USER_AGENT are shared by every token in the file; this "
                        "paste replaces them (same login assumed)")
    profile = getattr(args, "profile_data", None)
    if profile is not None:
        name, row = profile
        me_id = (seen.me or {}).get("id")
        if cls.first_party and row.get("token_kind") == "system_user":
            warnings.append(f"profile {name} declares token_kind system_user; a scraped {cls.key} is "
                            "a user session (set token_kind: user or auto)")
        if row.get("system_user_id") and me_id and row["system_user_id"] != me_id:
            warnings.append(f"profile {name} declares system_user_id {row['system_user_id']}; this "
                            f"token is user {me_id}")
        if row.get("app_id") and app_id and row["app_id"] != app_id:
            warnings.append(f"profile {name} declares app_id {row['app_id']}; this token's app is {app_id}")
    return Decision(cls, confirmed, var, cookies_var, refusals, warnings)


# --------------------------------------------------------------------------- env file

_KEY_LINE = re.compile(r"^\s*(?:export\s+)?(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*=(?P<value>.*)$")
_SAFE_VALUE = re.compile(r"^[A-Za-z0-9_@%+=:,./-]*$")


def format_value(value: str) -> str:
    """Unquoted when plain, single-quoted otherwise (shell `source` and dotenv both read it). The
    parser refused any value containing a single quote or a control character."""
    return value if _SAFE_VALUE.fullmatch(value) else f"'{value}'"


def read_env_values(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.split("\n"):
        match = _KEY_LINE.match(line)
        if match and not line.lstrip().startswith("#"):
            values[match.group("key")] = _unquote(match.group("value"))
    return values


def apply_updates(text: str, updates: dict[str, str | None]) -> str:
    """Replace the managed keys, keep every other line byte for byte. A key that appears twice
    keeps its first position and loses the later copies (the later one used to win in a shell).
    `None` removes the key. New keys are appended."""
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    placed: set[str] = set()
    out: list[str] = []
    for line in lines:
        match = _KEY_LINE.match(line) if not line.lstrip().startswith("#") else None
        key = match.group("key") if match else None
        if key in updates:
            value = match.group("value").strip()
            if value[:1] in "'\"" and (len(value) < 2 or value[-1] != value[0]):
                raise ImportRefused(f"{key} in the env file spans several lines; edit it by hand")
            if key in placed or updates[key] is None:
                continue
            placed.add(key)
            export = "export " if re.match(r"^\s*export\s", line) else ""
            out.append(f"{export}{key}={format_value(str(updates[key]))}")
            continue
        out.append(line)
    for key, value in updates.items():
        if key not in placed and value is not None:
            out.append(f"{key}={format_value(value)}")
    return "\n".join(out) + "\n"


def _write_private(path: pathlib.Path, data: bytes, exclusive: bool) -> None:
    flags = os.O_WRONLY | os.O_CREAT | (os.O_EXCL if exclusive else os.O_TRUNC)
    fd = os.open(path, flags, 0o600)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fd = -1
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
    finally:
        if fd != -1:
            os.close(fd)


def write_env(path: pathlib.Path, new_text: str, old_bytes: bytes | None) -> dict[str, Any]:
    """Temp file in the same directory (0600) + os.replace; the previous file is copied to `.bak`
    (0600) first. A symlinked env file is written through to its target."""
    target = path.resolve()
    backup = None
    if old_bytes is not None:
        backup = target.with_name(target.name + ".bak")
        _write_private(backup, old_bytes, exclusive=False)
    tmp = target.with_name(f".{target.name}.{os.getpid()}.{secrets.token_hex(4)}.tmp")
    try:
        _write_private(tmp, new_text.encode("utf-8"), exclusive=True)
        os.replace(tmp, target)
    finally:
        if tmp.exists():
            tmp.unlink()
    try:
        dir_fd = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError:
        pass
    return {"path": str(target), "backup": str(backup) if backup else None,
            "mode": oct(os.stat(target).st_mode & 0o777)}


# --------------------------------------------------------------------------- command

def _summary(paste: Paste, seen: Verification, decision: Decision) -> dict[str, Any]:
    cls = decision.cls
    return {
        "type": cls.key,
        "type_name": cls.name,
        "confirmed": decision.confirmed,
        "token": {"prefix": paste.token[:4], "last4": paste.token[-4:], "masked": tokens.mask(paste.token),
                  "length": len(paste.token)},
        "app": seen.app,
        "user": seen.me,
        "cookie_names": sorted(cookie_pairs(paste.cookies)),
        "user_agent_present": bool(paste.user_agent),
        "variable": decision.var,
        "cookies_variable": decision.cookies_var if paste.cookies else None,
        "provides": {cap: {"evidence": ev, "note": note}
                     for cap, (ev, note) in cls.capabilities.items()},
        "session": {"need": cls.session[0], "evidence": cls.session[1]},
        "role": cls.hint,
        "graph_calls": seen.calls,
    }


def _print(data: dict[str, Any], out: Any) -> None:
    user = data["user"]
    app = data["app"]
    lines = [
        f"  type       {data['type']} {data['type_name']}"
        + ("" if data["confirmed"] else "  (from the prefix, not confirmed)"),
        f"  token      {data['token']['masked']} ({data['token']['length']} chars)",
        f"  app        {app['id']} {app['name']}" if app else "  app        not read",
        f"  user       {user['id']} {user['name']}" if user else "  user       not read",
        f"  cookies    {', '.join(data['cookie_names']) or 'none'}"
        + ("" if not data["user_agent_present"] else "  + User-Agent"),
        f"  variable   {data['variable']}"
        + (f"  (cookies -> {data['cookies_variable']})" if data["cookies_variable"] else ""),
        f"  role       {data['role']}",
        "  provides   " + ", ".join(
            f"{cap}{'' if row['evidence'] == tokens.VERIFIED else '?'}" for cap, row in data["provides"].items())
        + "   (? = evidence not verified live, tokens.py)",
    ]
    for warning in data.get("warnings", []):
        lines.append(f"  ! {warning}")
    print("\n".join(lines), file=out)


@dataclass
class EnvTarget:
    """The env file being updated: where, what it holds now (text, bytes, parsed values)."""
    path: pathlib.Path | None
    text: str = ""
    raw: bytes | None = None
    values: dict[str, str] = field(default_factory=dict)


def _load_target(ctx: Any, args: argparse.Namespace) -> EnvTarget:
    if not args.env_file:
        return EnvTarget(None)
    path = pathlib.Path(args.env_file).expanduser()
    real = path.resolve()
    if real.is_dir():
        raise ctx.MetaOpsError(f"--env-file is a directory: {path}")
    if not real.parent.is_dir():
        raise ctx.MetaOpsError(f"the directory of --env-file does not exist: {real.parent}")
    if not real.exists():
        return EnvTarget(path)
    raw = real.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise ctx.MetaOpsError(f"{path} is not UTF-8 text; not touching it") from None
    return EnvTarget(path, text, raw, read_env_values(text))


def _write(target: EnvTarget, updates: dict[str, str | None]) -> dict[str, Any]:
    """One atomic write of every update; a byte-identical result touches nothing."""
    assert target.path is not None
    new_text = apply_updates(target.text, updates)
    if target.raw is not None and new_text.encode("utf-8") == target.raw:
        written: dict[str, Any] = {"path": str(target.path.resolve()), "backup": None, "unchanged": True}
    else:
        written = write_env(target.path, new_text, target.raw)
    return {**written, "keys": [k for k, v in updates.items() if v is not None],
            "removed": [k for k, v in updates.items() if v is None and k in target.values]}


def _token_import(ctx: Any, args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    command = "token import"
    if args.name is not None and not tokens.ENV_NAME.fullmatch(args.name):
        raise ctx.MetaOpsError("--name must be an uppercase environment variable name")
    profile_data = None
    workspace = getattr(args, "workspace_obj", None)
    requested = getattr(args, "profile", None)
    if requested is not None:
        if not workspace:
            raise ctx.MetaOpsError("--profile needs a workspace (run inside one or pass --workspace)")
        try:
            profile_data = workspace.profile(requested)
        except Exception as exc:  # noqa: BLE001 - WorkspaceError text is the message
            raise ctx.MetaOpsError(str(exc)) from exc
    args.profile_data = profile_data
    dry_run = bool(args.dry_run or not args.env_file)
    if sys.stdin is None or sys.stdin.isatty():
        raise ctx.MetaOpsError("nothing on stdin: pipe the block, e.g. `pbpaste | metaops token import`")
    try:
        batch = parse_batch(sys.stdin.read(), (args.name,) if args.name else ())
    except ImportRefused as exc:
        raise ctx.MetaOpsError(str(exc)) from None
    target = _load_target(ctx, args)
    existing = target.values
    out = sys.stderr if getattr(args, "json", False) else sys.stdout

    def refuse(reason: str, data: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
        return 1, ctx.result_envelope(
            command, False, "refused", data=data,
            error={"kind": "token_gate", "message": reason}, next_action="Nothing was written.")

    if len(batch.tokens) > 1:
        return _import_many(ctx, args, batch, workspace, profile_data, target, dry_run, out, refuse)
    paste = Paste(batch.tokens[0], batch.cookies, batch.user_agent)
    if args.no_verify:
        seen = Verification()
    else:
        try:
            seen = verify(ctx, paste)
        except ImportRefused as exc:
            return refuse(str(exc), {"token": {"masked": tokens.mask(paste.token)},
                                     "graph_calls": exc.calls})
    decision = decide(args, paste, seen, workspace, existing)
    data = _summary(paste, seen, decision)
    data["warnings"] = decision.warnings
    if decision.refusals:
        data["refusals"] = decision.refusals
        _print(data, out)
        for reason in decision.refusals:
            print(f"  REFUSED  {reason}", file=out)
        return refuse("; ".join(decision.refusals), data)

    updates: dict[str, str | None] = {decision.var: paste.token}
    app_var = tokens.app_id_var(decision.var)
    updates[app_var] = (seen.app or {}).get("id") or None  # None: drop a stale confirmation
    if paste.cookies:
        updates[decision.cookies_var] = paste.cookies
    if paste.user_agent:
        updates[UA_VAR] = paste.user_agent
    if seen.ran and not paste.cookies and existing.get(COOKIES_VAR) and decision.cls.needs_cookies:
        decision.warnings.append("META_COOKIES already in the file was kept; it belongs to the "
                                 "previous session, not to this token")
    data["warnings"] = decision.warnings
    _print(data, out)
    profile_flag = f" --profile {profile_data[0]}" if profile_data else ""
    if dry_run:
        print("  dry run: nothing written" + ("" if args.env_file else " (no --env-file)"), file=out)
        return 0, ctx.result_envelope(
            command, True, "dry_run", data=data,
            next_action="Re-run with --env-file PATH to write "
                        f"{', '.join(k for k, v in updates.items() if v is not None)}.")
    data["written"] = _write(target, updates)
    written = data["written"]
    print(f"  wrote      {written['path']}  keys {', '.join(written['keys'])}"
          + (f"  (backup {written['backup']})" if written.get("backup") else ""), file=out)
    return 0, ctx.result_envelope(
        command, True, "written", artifacts={"env_file": written["path"]}, data=data,
        next_action=f"set -a; . {written['path']}; set +a; then: metaops{profile_flag} doctor"
                    + ("" if profile_data else " --whoami"))


def _merge_notes(items: list[tuple[str, str]]) -> list[str]:
    """(class, text) pairs -> texts; one that every token raised is shown once, the rest keep
    their class in front."""
    counts: dict[str, int] = {}
    for _cls, text in items:
        counts[text] = counts.get(text, 0) + 1
    merged: list[str] = []
    for cls_key, text in items:
        line = text if counts[text] > 1 else f"[{cls_key}] {text}"
        if line not in merged:
            merged.append(line)
    return merged


def _print_rows(rows: list[dict[str, Any]], shared: dict[str, Any], out: Any) -> None:
    lines = []
    for index, row in enumerate(rows, 1):
        app = row["app"]
        user = row["user"]
        lines.append(
            f"  [{index}/{len(rows)}] {row['type']:<11} {row['token']['masked']}  -> {row['variable']:<20} "
            f"app {app['id'] + ' ' + str(app['name']) if app else 'not read'} | "
            f"user {user['id'] + ' ' + str(user['name']) if user else 'not read'}"
            + ("" if row["confirmed"] else "  (prefix only)"))
    lines.append(f"  cookies    {', '.join(shared['cookie_names']) or 'none'}"
                 + ("  + User-Agent" if shared["user_agent_present"] else "")
                 + (f"  (shared, -> {shared['cookies_variable']})" if shared["cookies_variable"] else ""))
    for warning in shared["warnings"]:
        lines.append(f"  ! {warning}")
    print("\n".join(lines), file=out)


def _import_many(ctx: Any, args: argparse.Namespace, batch: Batch, workspace: Any,
                 profile_data: Any, target: EnvTarget, dry_run: bool, out: Any,
                 refuse: Any) -> tuple[int, dict[str, Any]]:
    """Several tokens of different classes in one paste (the FB Helper block, once per class).
    Each is verified (max 2 Graph calls); the first failure stops the import, and one atomic
    write happens only when every token passed."""
    command = "token import"
    count = len(batch.tokens)
    if args.name:
        raise ctx.MetaOpsError("--name names one variable; with several tokens every class goes to "
                               "its own (drop --name, or import them one at a time)")
    if args.cookies_suffix:
        raise ctx.MetaOpsError("--cookies-suffix is for one token; several tokens share META_COOKIES")
    pastes = [Paste(token, batch.cookies, batch.user_agent) for token in batch.tokens]
    seens: list[Verification] = []
    spent = 0
    if args.no_verify:
        seens = [Verification() for _ in pastes]
    else:
        for index, paste in enumerate(pastes, 1):
            try:
                seens.append(verify(ctx, paste))
            except ImportRefused as exc:
                calls = spent + (exc.calls or 0)
                return refuse(
                    f"token {index} of {count} ({tokens.mask(paste.token)}): {exc}. Stopped there, "
                    f"{index - 1} verified before it; nothing was written.",
                    {"failed": {"index": index, "token": tokens.mask(paste.token)}, "graph_calls": calls})
            spent += seens[-1].calls
    existing = target.values
    decisions = [decide(args, paste, seen, workspace, existing) for paste, seen in zip(pastes, seens)]
    rows = [_summary(paste, seen, decision) for paste, seen, decision in zip(pastes, seens, decisions)]
    refusals = [(d.cls.key, reason) for d in decisions for reason in d.refusals]
    # "the shared cookies get replaced" is the point of a multi-token paste, not news; the per-class
    # "without cookies" warning becomes one line naming the classes that need them
    warnings = [(d.cls.key, text) for d in decisions for text in d.warnings
                if not text.startswith("META_COOKIES / META_USER_AGENT are shared")
                and " without cookies:" not in text]
    cookieless = [d.cls.key for d in decisions if d.cls.first_party and d.cls.needs_cookies] \
        if not batch.cookies else []
    if cookieless:
        warnings.append(("all", f"no cookies in the paste: {', '.join(cookieless)} answer code 1 without "
                                "them (an EAAd would not care). Paste the token blocks with their cookies."))
    classes: dict[str, int] = {}
    variables: dict[str, int] = {}
    for index, decision in enumerate(decisions):
        for registry, key, what in ((classes, decision.cls.key, "class"), (variables, decision.var, "variable")):
            if key in registry:
                refusals.append((decision.cls.key, f"tokens {registry[key] + 1} and {index + 1} resolve to "
                                 f"the same {what} ({key}); one token per {what}"))
            registry.setdefault(key, index)
    user_ids = {seen.me["id"] for seen in seens if seen.me}
    if len(user_ids) > 1:
        refusals.append(("all", f"the tokens belong to {len(user_ids)} different users ({', '.join(sorted(user_ids))}); "
                                "paste one login's tokens"))
    if seens and seens[0].ran and not batch.cookies and existing.get(COOKIES_VAR) and any(
            d.cls.needs_cookies for d in decisions):
        warnings.append(("all", "META_COOKIES already in the file was kept; it belongs to the previous "
                                "session, not to these tokens"))
    shared = {
        "cookie_names": sorted(cookie_pairs(batch.cookies)),
        "user_agent_present": bool(batch.user_agent),
        "cookies_variable": COOKIES_VAR if batch.cookies else None,
        "warnings": batch.warnings + _merge_notes(warnings),
    }
    data: dict[str, Any] = {
        "tokens": rows, "types": [d.cls.key for d in decisions], "graph_calls": spent if seens[0].ran else 0,
        **{k: v for k, v in shared.items() if k != "cookies_variable"}, "cookies_variable": shared["cookies_variable"],
    }
    _print_rows(rows, shared, out)
    if refusals:
        data["refusals"] = _merge_notes(refusals)
        for reason in data["refusals"]:
            print(f"  REFUSED  {reason}", file=out)
        return refuse("; ".join(data["refusals"]) + ". Nothing was written.", data)

    updates: dict[str, str | None] = {}
    for paste, seen, decision in zip(pastes, seens, decisions):
        updates[decision.var] = paste.token
        updates[tokens.app_id_var(decision.var)] = (seen.app or {}).get("id") or None
    if batch.cookies:
        updates[COOKIES_VAR] = batch.cookies
    if batch.user_agent:
        updates[UA_VAR] = batch.user_agent
    profile_flag = f" --profile {profile_data[0]}" if profile_data else ""
    if dry_run:
        print("  dry run: nothing written" + ("" if args.env_file else " (no --env-file)"), file=out)
        return 0, ctx.result_envelope(
            command, True, "dry_run", data=data,
            next_action="Re-run with --env-file PATH to write "
                        f"{', '.join(k for k, v in updates.items() if v is not None)}.")
    data["written"] = _write(target, updates)
    written = data["written"]
    print(f"  wrote      {written['path']}  {len(written['keys'])} keys"
          + (f"  (backup {written['backup']})" if written.get("backup") else ""), file=out)
    return 0, ctx.result_envelope(
        command, True, "written", artifacts={"env_file": written["path"]}, data=data,
        next_action=f"set -a; . {written['path']}; set +a; then: metaops{profile_flag} doctor"
                    + ("" if profile_data else " --whoami"))


def register(sub: Any, ctx: Any) -> None:
    p = sub.add_parser("token", help="import scraped first-party tokens (FB Helper block) with a "
                                     "type gate")
    token_sub = p.add_subparsers(dest="token_action", required=True)
    a = token_sub.add_parser(
        "import", help="stdin block -> verified, class-routed env file (never prints the token)",
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("--env-file", help="env file to update; without it the run is a dry run")
    a.add_argument("--name", help="variable for the token (default by class: EAAB META_TOKEN, "
                                  "EAAG META_TOKEN_BUSINESS, EAAH META_TOKEN_CATALOG, "
                                  "EAAd META_TOKEN_EVENTS, EAAI META_TOKEN_RULES)")
    a.add_argument("--profile", default=argparse.SUPPRESS,
                   help="workspace profile: cross-check the token against its declared token_kind, "
                        "system_user_id and app_id (warnings only, no extra Graph call)")
    a.add_argument("--dry-run", action="store_true", help="verify and print, write nothing")
    a.add_argument("--no-verify", action="store_true",
                   help="skip /me and /app (class from the prefix only, c_user not compared)")
    a.add_argument("--allow-unknown", action="store_true",
                   help="accept a token whose prefix or app id is none of the five first-party "
                        "classes (System User / own-app); records <VAR>_APP_ID")
    a.add_argument("--as-ads", action="store_true",
                   help="write an EAAG to META_TOKEN (only when the file holds no EAAB there)")
    a.add_argument("--cookies-suffix", nargs="?", const="auto", metavar="SUFFIX",
                   help="store the cookies as META_COOKIES_<SUFFIX> (BUSINESS, CATALOG, EVENTS, "
                        "RULES) instead of the shared META_COOKIES; bare = the token variable's own")
    a.add_argument("--force", action="store_true",
                   help="write a non-ads class to an ads variable, accept a prefix/app-id "
                        "disagreement, or replace another login's shared cookies")
    a.set_defaults(handler=functools.partial(_token_import, ctx), offline_ok=True)

#!/usr/bin/env python3
"""Pre-flight gate. Proves the token can actually WRITE before anything is built.

    export META_TOKEN=...  META_PROXY=socks5h://user:pass@host:port
    python3 probe.py --account act_123 --page 456 [--dataset 789 [--attach-pixel --business 111]] [--json report.json]

Every check is a separate gate (meta-ads/13 §4): a successful GET proves nothing about
write access, and an asset visible to a human is not an asset assigned to the token.

Every call here retries on a dropped connection, reads and writes alike. This script is
diagnostic: its writes create nothing that a repeat could duplicate (validate_only
mutates nothing, the CAPI probe posts an empty batch, and the PBIA edge is
get-or-create), so a one-shot POST would only let a proxy blip report "no write access"
on an account that has it.
Exit code 1 if any REQUIRED gate fails. Run this before launch.py, every new account.

--risk appends a read-only account / pixel / Page / ads snapshot with `risk_findings`. It never
changes the exit code: its rows are ok/warn only. The thresholds are the operator's own priors.
"""

from __future__ import annotations

import argparse
import datetime as dt
import decimal
import json
import os
import re
import sys

import graph
import meta_workspace
import tokens

PASS, FAIL, WARN = "PASS", "FAIL", "WARN"

# account_status is undocumented as an enum; these are the widely-observed values.
# Never diagnose from this number alone — confirm in Account Quality (meta-ads/13 §4).
ACCOUNT_STATUS = {
    1: "ACTIVE",
    2: "DISABLED",
    3: "UNSETTLED",
    7: "PENDING_RISK_REVIEW",
    8: "PENDING_SETTLEMENT",
    9: "IN_GRACE_PERIOD",
    100: "PENDING_CLOSURE",
    101: "CLOSED",
    201: "ANY_ACTIVE",
    202: "ANY_CLOSED",
}

REQUIRED_SCOPES = ["ads_management", "ads_read"]
# The full-access set a launch persona should hold (meta-grey-ops/02). Missing ones are a
# WARN, not a FAIL: catalog work fails later without catalog_management, Page-avatar edits
# fail #283 without pages_manage_metadata, IG identity reads need instagram_basic.
RECOMMENDED_SCOPES = [
    "business_management", "read_insights", "pages_manage_ads", "pages_read_engagement",
    "pages_show_list", "pages_manage_metadata", "pages_manage_posts", "instagram_basic",
    "catalog_management",
]


class Report:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def add(self, gate: str, state: str, detail: str, data=None) -> None:
        self.rows.append({"gate": gate, "state": state, "detail": detail, "data": data})
        mark = {PASS: "ok  ", FAIL: "FAIL", WARN: "warn"}[state]
        print(f"  {mark}  {gate}: {graph.redact(detail)}")

    @property
    def failed(self) -> bool:
        return any(r["state"] == FAIL for r in self.rows)


def cookie_pairs(header: str) -> dict[str, str]:
    """`c_user=1; xs=2` -> {"c_user": "1", "xs": "2"}. Values are never printed by callers."""
    pairs: dict[str, str] = {}
    for part in (header or "").split(";"):
        name, sep, value = part.strip().partition("=")
        if sep and name.strip():
            pairs[name.strip()] = value.strip()
    return pairs


def acting_class() -> tokens.Classification | None:
    """Class of META_TOKEN from its prefix, or from the app id a `token import` recorded. No network."""
    token = os.environ.get("META_TOKEN", "").strip()
    if not token:
        return None
    return tokens.classify(token, os.environ.get("META_TOKEN_APP_ID", ""))


def gate_token_class(r: Report) -> None:
    """Name the token's class (no network, nothing secret printed) and warn when a first-party
    session token runs without the session it belongs to (02 §5)."""
    hit = acting_class()
    if hit is None:
        return
    cls = hit.cls
    if not cls.first_party:
        r.add("token class", PASS,
              f"prefix {os.environ['META_TOKEN'].strip()[:4]}: {cls.name}; its type comes from "
              "debug_token below")
        return
    how = "confirmed by the recorded app id" if hit.confirmed else "from the prefix, confirmed by GET /app below"
    head = f"{cls.key} {cls.name} (app {cls.app_id}, {how}): {cls.hint}"
    # Cookies are what matters (verified 2026-09-29: no cookies -> code 1 for EAAB / EAAI / EAAG / EAAH,
    # EAAd reads without them). A missing User-Agent is not a finding: EAAB passed with the default
    # UA and with another browser's (same IP); the extension exports none.
    if cls.needs_cookies and not os.environ.get("META_COOKIES", "").strip():
        r.add("token class", WARN,
              f"{cls.key} {cls.name} (app {cls.app_id}, {how}). META_COOKIES is not set: this class "
              "answers code 1 without the browser session's cookies. Re-import it with them "
              "(`pbpaste | metaops token import --env-file <file>`); keep the proxy IP of the profile.")
    elif cls.ads_write_policy == "refuse":
        r.add("token class", WARN,
              f"{head} Not the launch token: it cannot write ads; META_TOKEN should be an EAAB, this "
              f"class belongs in {cls.default_var}.")
    else:
        r.add("token class", PASS, head)


def check_session_binding(r: Report, me_id: str) -> None:
    """The c_user cookie is the Facebook user id of the session the cookies belong to. It must be
    the id `/me` answers with; otherwise the cookies are from another persona's session."""
    c_user = cookie_pairs(os.environ.get("META_COOKIES", "")).get("c_user")
    if c_user and str(me_id) and c_user != str(me_id):
        r.add("cookie / token binding", WARN,
              f"META_COOKIES c_user does not match /me id {me_id}: the cookies belong to another "
              "session. Re-import token and cookies from the same browser profile.")


def gate_identity(r: Report) -> None:
    try:
        me = graph.get("me", params={"fields": "id,name"}, context="identity")
        r.add("token identity", PASS, f"{me.get('name', '?')} ({me['id']})", me)
        check_session_binding(r, str(me["id"]))
    except graph.GraphError as e:
        r.add("token identity", FAIL, str(e), e.as_dict())


def gate_token_debug(r: Report) -> None:
    """/debug_token accepts the System User token as its own app token (live 2026-09-02):
    returns type, app, expires_at (0 = never), data_access_expires_at, scopes.

    A first-party token (EAAB / EAAI / EAAG / EAAH / EAAd) cannot self-debug (#100), so when the
    prefix names one this asks GET /app instead: one call, and it confirms the class. If the app id
    is NOT the guessed first-party app (an own-app token sharing a prefix), debug_token runs."""
    hit = acting_class()
    if hit is not None and hit.cls.first_party:
        cls = hit.cls
        try:
            app = graph.get("app", params={"fields": "id,name"}, context="token app")
        except graph.GraphError as e:
            r.add("token app", WARN, f"GET /app failed: {e}")
            return
        same = str(app.get("id")) == cls.app_id
        r.add("token app", PASS if same else WARN,
              f"{app.get('name')} ({app.get('id')}): "
              + (f"class {cls.key} confirmed; debug_token skipped (first-party tokens answer #100)"
                 if same else f"NOT the {cls.key} app {cls.app_id}: an own-app token that shares the "
                              "prefix; reading debug_token"),
              {"app": app, "class": cls.key, "confirmed": same})
        if same:
            return
    try:
        d = graph.get("debug_token", params={"input_token": graph.token()}, context="debug_token")["data"]
    except graph.GraphError as e:
        r.add("token debug", WARN, f"debug_token unavailable for this token: {e}")
        if hit is not None and hit.cls.first_party:
            return
        # Not a known first-party prefix and no self-debug: GET /app still names the minting app.
        try:
            app = graph.get("app", params={"fields": "id,name"}, context="token app")
            r.add("token app", PASS, f"{app.get('name')} ({app.get('id')})", {"app": app})
        except graph.GraphError as e2:
            r.add("token app", WARN, str(e2))
        return
    exp = d.get("expires_at")
    life = "never" if exp == 0 else str(exp)
    r.add("token debug", PASS if d.get("is_valid") else FAIL,
          f"type={d.get('type')} app={d.get('app_id')} ({d.get('application')}) expires={life} "
          f"data_access_expires={d.get('data_access_expires_at')}", d)


def gate_scopes(r: Report) -> None:
    hit = acting_class()
    if hit is not None and hit.cls.first_party and "permissions" in hit.cls.known_failures:
        r.add("granted scopes", WARN,
              f"skipped for {hit.cls.key}: {hit.cls.known_failures['permissions']}. Scopes are not "
              "readable for this class; the write gate below is the proof.")
        return
    try:
        perms = graph.get("me/permissions", context="scopes")["data"]
    except graph.GraphError as e:
        r.add("granted scopes", FAIL, str(e), e.as_dict())
        return
    granted = {p["permission"] for p in perms if p.get("status") == "granted"}
    missing = [s for s in REQUIRED_SCOPES if s not in granted]
    if missing:
        r.add("granted scopes", FAIL, f"missing {missing}; granted={sorted(granted)}", sorted(granted))
    else:
        r.add("granted scopes", PASS, ", ".join(sorted(granted)), sorted(granted))
    soft = [s for s in RECOMMENDED_SCOPES if s not in granted]
    if soft:
        r.add("recommended scopes", WARN, f"not granted: {soft} — catalog/page/IG steps will fail "
              "later if the job needs them (02)")


def gate_visible_accounts(r: Report, account: str | None) -> None:
    """The token must SEE the account through its own assignment, not just read it by id.
    An account absent from /me/adaccounts is one the System User was not assigned to —
    reads may still work through a Page role while every write fails."""
    try:
        rows: list[dict] = []
        params: dict = {"fields": "id,name", "limit": 500}
        while True:
            page = graph.get("me/adaccounts", params=params, context="visible ad accounts")
            rows.extend(page.get("data", []))
            params = graph.next_page_params(page, params)
            if params is None:
                break
    except graph.GraphError as e:
        r.add("visible ad accounts", WARN, f"could not list: {e}")
        return
    ids = {x["id"] for x in rows}
    if account is None:
        names = ", ".join(f"{x['id']} {x.get('name', '')[:20]}" for x in rows[:12])
        r.add("visible ad accounts", PASS if rows else WARN,
              f"{len(ids)} visible: {names}{' …' if len(rows) > 12 else ''}" if rows else
              "none — this token is assigned to no ad account", rows)
        return
    if account in ids:
        r.add("visible ad accounts", PASS, f"{account} is assigned to this token ({len(ids)} visible)")
    else:
        r.add("visible ad accounts", FAIL,
              f"{account} is NOT in /me/adaccounts ({len(ids)} visible). Assign the ad account "
              "to the System User (Business Settings → System users → Assign assets).")


def whoami_verdict(r: Report) -> None:
    """Turn the intake gates into the decision a fresh agent needs: which pipe, proxy or not,
    how long the token lives, what it cannot do (02 §1, §4)."""
    dbg = next((x["data"] for x in r.rows if x["gate"] == "token debug" and x["data"]), {}) or {}
    ttype, exp = dbg.get("type"), dbg.get("expires_at")
    scopes = set(dbg.get("scopes") or [])
    lines = []
    if ttype == "SYSTEM_USER":
        lines.append("SYSTEM_USER token: session-independent, but token type does not waive the "
                     "Business Portfolio's assigned egress. Use META_PROXY unless the operator has "
                     "explicitly confirmed direct egress for this BM (then set defaults.allow_no_proxy=true in workspace.json; an exported META_ALLOW_NO_PROXY=1 is dropped under metaops).")
    elif ttype == "USER":
        lines.append("USER token: it IS a persona session. Route every call through that persona's proxy "
                     "(META_PROXY=socks5h://…); it dies on logout/password change/checkpoint (190/460-467) "
                     "and cannot be revived — re-mint. No appsecret_proof for EAAB tokens from Ads Manager.")
        if exp:
            lines.append(f"expires_at={exp} — plan the re-mint; exchange to long-lived only if it came from "
                         "your own app (02 §4).")
    elif ttype == "PAGE":
        lines.append("PAGE token: comments/page edits only — no ad account writes.")
    elif ttype is None and (acting_class() is not None) and acting_class().cls.first_party:
        cls = acting_class().cls
        lines.append(f"{cls.key} first-party {cls.name} token: a user session that cannot "
                     "self-debug. "
                     + ("It needs the session's cookies (no cookies -> code 1) and the proxy IP of the "
                        "browser profile; " if cls.needs_cookies else "Its reads need no cookies; ")
                     + "it dies on logout, password change or checkpoint (190/459-467). " + cls.hint)
    else:
        lines.append(f"token type {ttype!r}: unknown to this probe; read 02 §4 before writing.")
    missing = {"ads_management", "business_management", "pages_read_engagement"} - scopes
    if missing and dbg:  # first-party tokens cannot self-debug: their scopes are not known here
        lines.append(f"missing for launches: {sorted(missing)}")
    if "ads_mcp_management" not in scopes:
        lines.append("no ads_mcp_management → the official Meta Ads MCP will answer 401; API-only.")
    if "catalog_management" not in scopes:
        lines.append("no catalog_management → no DLO/catalog creatives or product-set edits.")
    for ln in lines:
        r.add("verdict", WARN if ("missing" in ln or "unknown" in ln) else PASS, ln)


def gate_pixel_attached(r: Report, account: str, dataset_id: str, business: str | None,
                        attach: bool) -> None:
    """A pixel shared to the BM is NOT on the ad account. Ad set create fails 1815045 until
    it is attached (Data sources → Connected assets, or POST /{pixel}/shared_accounts).
    Field-hit 2026-09-01. --attach-pixel does the POST; it needs the owning business id and
    is idempotent (re-sharing an already-shared account is a no-op)."""
    def listed() -> list[str]:
        rows: list[dict] = []
        params: dict = {"fields": "id,name", "limit": 200}
        while params is not None:
            page = graph.get(f"{account}/adspixels", params=params, context="account pixels")
            rows.extend(row for row in page.get("data", []) if isinstance(row, dict))
            params = graph.next_page_params(page, params)
        return [str(row["id"]) for row in rows if row.get("id")]

    try:
        ids = listed()
    except graph.GraphError as e:
        r.add("pixel attached to account", FAIL, str(e), e.as_dict())
        return
    if str(dataset_id) in ids:
        r.add("pixel attached to account", PASS, f"{dataset_id} listed on {account}")
        return
    if attach:
        if not business:
            r.add("pixel attached to account", FAIL,
                  "--attach-pixel needs --business <BM id that owns the pixel>")
            return
        try:
            graph.post(f"{dataset_id}/shared_accounts",
                       {"account_id": account.replace("act_", ""), "business": business},
                       context="attach pixel", idempotent=True)
            ids = listed()
        except graph.GraphError as e:
            r.add("pixel attached to account", FAIL, f"attach failed: {e}", e.as_dict())
            return
        if str(dataset_id) in ids:
            r.add("pixel attached to account", PASS, f"{dataset_id} attached to {account} just now")
            return
        r.add("pixel attached to account", FAIL,
              f"POST /shared_accounts succeeded but {dataset_id} still not listed — propagation "
              "lag or wrong business id; re-run in a minute")
        return
    r.add("pixel attached to account", FAIL,
          f"{dataset_id} is not on {account} (has {ids}). Re-run with --attach-pixel --business "
          "<BM id>, or Business Settings → Data sources → Datasets → Add assets → this ad "
          "account. Ad set create will fail 1815045 until then.")


def gate_account(r: Report, account: str) -> dict | None:
    fields = (
        "id,name,account_status,disable_reason,currency,timezone_name,"
        "timezone_offset_hours_utc,spend_cap,amount_spent,balance,"
        "funding_source_details,business,is_prepay_account,capabilities"
    )
    try:
        acct = graph.get(account, params={"fields": fields}, context="ad account")
    except graph.GraphError as e:
        r.add("ad account read", FAIL, str(e), e.as_dict())
        return None

    status = acct.get("account_status")
    label = ACCOUNT_STATUS.get(status, f"UNKNOWN({status})")
    state = PASS if status == 1 else FAIL
    r.add("ad account status", state, f"{label} disable_reason={acct.get('disable_reason')}", acct)

    r.add(
        "currency / timezone",
        WARN,
        f"{acct.get('currency')} / {acct.get('timezone_name')} — "
        "changing either CLOSES the account and opens a new act id (08). Confirm with the TL.",
    )
    if not acct.get("funding_source_details"):
        r.add("funding source", FAIL, "no payment method on the ad account", None)
    else:
        r.add("funding source", PASS, str(acct["funding_source_details"].get("type_name", "set")))
    return acct


def gate_page_and_pbia(r: Report, page_id: str, create: bool) -> str | None:
    try:
        ptoken = graph.page_token(page_id)
        r.add("page access token", PASS, f"page {page_id}")
    except graph.GraphError as e:
        r.add("page access token", FAIL, f"{e} — needs >=ADVERTISER role on the Page", e.as_dict())
        return None

    # The `page_backed_instagram_accounts` EDGE was removed from the Page schema after
    # 2025-04 with no changelog entry (its reference page is a 404; the edge is absent from
    # the live Page node schema, while the older prose guide still tells you to call it).
    # Reading it now returns (#100) "Tried accessing nonexisting field" on every version,
    # even on Pages that DO have a PBIA. The schema replacement is the to-one field
    # `connected_page_backed_instagram_account`; `instagram_business_account` and
    # `connected_instagram_account` are the two other ways a Page can be Instagram-ready.
    # Verified live 2026-09-22 (`18`).
    try:
        node = graph.call(
            "GET",
            page_id,
            params={"fields": "instagram_business_account,connected_instagram_account,"
                              "connected_page_backed_instagram_account"},
            token_override=ptoken,
            context="pbia read",
        )
    except graph.GraphError as e:
        r.add("PBIA", FAIL, str(e), e.as_dict())
        return None

    for key in ("connected_page_backed_instagram_account", "instagram_business_account",
                "connected_instagram_account"):
        node_value = node.get(key) or {}
        if node_value.get("id"):
            pbia = node_value["id"]
            r.add("PBIA", PASS, f"{key} instagram_user_id={pbia}", pbia)
            return pbia

    if not create:
        # Instagram placements are mandatory (operator rule 2026-09-26), so no PBIA blocks.
        r.add(
            "PBIA",
            FAIL,
            "none exists; Instagram placements are mandatory. The API create is deprecated (#10): "
            "create it in the UI (Ads Manager > ad draft > Identity > Instagram account > Use Facebook Page, then discard the draft, 18).",
        )
        return None

    try:
        pbia = graph.call(
            "POST",
            f"{page_id}/page_backed_instagram_accounts",
            token_override=ptoken,
            context="pbia create",
            idempotent=True,
        )["id"]
        r.add("PBIA", PASS, f"created instagram_user_id={pbia}", pbia)
        return pbia
    except graph.GraphError as e:
        r.add("PBIA", FAIL, str(e), e.as_dict())
        return None


def gate_dataset(r: Report, dataset_id: str) -> None:
    """Zero-event CAPI write probe: an empty data array proves auth without writing.

    Meta answers a well-authorised empty POST with 'param data must be non-empty'.
    That error IS the pass condition."""
    try:
        graph.post(dataset_id + "/events", {"data": []}, context="capi probe",
                   idempotent=True, capability="events_write")
        r.add("dataset CAPI write", WARN, "empty POST accepted — unexpected, verify manually")
    except SystemExit as exc:  # no token variable can serve events_write (graph.resolve_token)
        r.add("dataset CAPI write", FAIL, str(exc.code))
    except graph.GraphError as e:
        text = (e.user_msg or e.message).lower()
        if "non-empty" in text or "must be non-empty" in text:
            r.add("dataset CAPI write", PASS, "auth confirmed, no events written")
        else:
            r.add("dataset CAPI write", FAIL, str(e), e.as_dict())


def gate_write(r: Report, account: str) -> None:
    """validate_only campaign create. Runs Meta's own field validation and mutates nothing.

    This is the guardrail that catches a malformed payload without creating an object,
    without spend, and without touching the account's risk surface."""
    hit = acting_class()
    if hit is not None and hit.cls.ads_write_policy == "refuse":
        r.add("write access (validate_only)", FAIL,
              f"{hit.cls.key} {hit.cls.name} token: "
              f"{hit.cls.known_failures.get('ads_objects', 'no ad-object access')}. Put an EAAB in "
              "META_TOKEN; not sent.")
        return
    try:
        graph.post(
            f"{account}/campaigns",
            {
                "name": "probe-validate-only",
                "objective": "OUTCOME_LEADS",
                "status": "PAUSED",
                "special_ad_categories": [],
                # Required from v24 when the campaign carries no budget, which a probe
                # never does. Omitting it fails 4834011 and looks like a permissions
                # problem. It is NOT campaign budget optimization — it is up-to-20%
                # budget sharing between sibling ad sets.
                "is_adset_budget_sharing_enabled": False,
                "execution_options": ["validate_only"],
            },
            context="write probe",
            idempotent=True,
        )
        r.add("write access (validate_only)", PASS, "campaign payload validated, nothing created")
    except graph.GraphError as e:
        r.add(
            "write access (validate_only)",
            FAIL,
            f"{e} — check ads_management granted, System User write task on THIS "
            "account, app-business relationship, and account restriction state (13 §4).",
            e.as_dict(),
        )


# ---- several token variables: one row per token (no debug_token, <= 2 Graph calls each) ---------------

DEATH_CODES = {190, 102}
DEATH_SUBCODES = {459, 460, 463, 467}


def token_variables() -> list[str]:
    """Every token variable that is set: the five standard ones plus the workspace's token_envs."""
    names = list(tokens.TOKEN_VARS) + sorted(set(graph.workspace_token_envs().values()))
    return [name for name in dict.fromkeys(names) if os.environ.get(name, "").strip()]


def _capability_of_var(var: str) -> str | None:
    for cap, name in tokens.CAPABILITY_VARS.items():
        if name == var and cap in tokens.ROUTED_CAPABILITIES:
            return cap
    for cap, name in graph.workspace_token_envs().items():
        if name == var:
            return cap
    return None


def _probe_variable(var: str, cap: str | None, known: dict | None) -> dict:
    """`known` = the /me and /app answers doctor already has for META_TOKEN (no extra calls)."""
    token = os.environ[var].strip()
    cookies = graph.cookies_for(var, cap)
    row: dict = {"variable": var, "valid": None, "user": None, "app": None, "error": None}
    if known is not None:
        row["user"], row["app"] = known.get("user"), known.get("app")
        row["valid"] = known.get("valid")
        row["error"] = known.get("error")
    else:
        try:
            me = graph.call("GET", "me", params={"fields": "id,name"}, token_override=token,
                            cookies=cookies, retries=0, context=f"token table {var}")
            row["user"], row["valid"] = {"id": me.get("id"), "name": me.get("name")}, True
        except graph.GraphError as e:
            row["valid"] = False
            row["error"] = f"code {e.code}/{e.subcode}"
            if not (e.code in DEATH_CODES or e.subcode in DEATH_SUBCODES or e.code == 1):
                row["valid"] = None  # could not tell (throttle, transport): not a dead token
        if row["valid"]:
            try:
                app = graph.call("GET", "app", params={"fields": "id,name"}, token_override=token,
                                 cookies=cookies, retries=0, context=f"token table {var} app")
                row["app"] = {"id": app.get("id"), "name": app.get("name")}
            except graph.GraphError as e:
                row["app_error"] = f"code {e.code}/{e.subcode}"
    hit = tokens.classify(token, (row["app"] or {}).get("id") or os.environ.get(tokens.app_id_var(var), ""))
    row["class"], row["confirmed"] = hit.cls.key, hit.confirmed
    row["needs_cookies"] = hit.cls.needs_cookies
    row["cookies_set"] = bool(cookies)
    row["provides"] = {cap_: hit.cls.capabilities[cap_][0] for cap_ in tokens.provided(hit.cls)}
    c_user = cookie_pairs(cookies or "").get("c_user")
    if c_user and row["user"]:
        row["binding"] = "ok" if c_user == str(row["user"]["id"]) else "MISMATCH"
    return row


def needed_capabilities(business: str | None, dataset: str | None, catalog: str | None) -> list[str]:
    need = ["ads_read", "ads_write"]
    if business:
        need.append("business_read")
    if catalog:
        need.append("catalog")
    if dataset:
        need.append("events_write")
    return need


def gate_token_table(r: Report, need: list[str], out_path: str | None) -> None:
    """Only when several token variables are set. META_TOKEN reuses what the identity and app
    gates already read; every other variable costs /me plus /app (2 calls), never debug_token."""
    variables = token_variables()
    if len(variables) < 2:
        return
    identity = next((x for x in r.rows if x["gate"] == "token identity"), None)
    app_row = next((x for x in r.rows if x["gate"] in ("token app", "token debug")), None)
    known = None
    if "META_TOKEN" in variables and identity is not None:
        app = None
        if app_row and app_row["data"]:
            data = app_row["data"]
            app = data.get("app") if "app" in data else {
                "id": data.get("app_id"), "name": data.get("application")}
        known = {"valid": identity["state"] == PASS,
                 "user": ({"id": identity["data"].get("id"), "name": identity["data"].get("name")}
                          if identity["state"] == PASS and identity["data"] else None),
                 "app": app, "error": None if identity["state"] == PASS else "identity failed"}
    rows: list[dict] = []
    probed: dict[str, dict] = {}   # the same token pasted into two variables costs its calls once
    for var in variables:
        value = os.environ[var].strip()
        prior = probed.get(value)
        answers = known if (var == "META_TOKEN" and known is not None) else (
            {key: prior[key] for key in ("valid", "user", "app", "error")} if prior else None)
        row = _probe_variable(var, _capability_of_var(var), answers)
        probed.setdefault(value, row)
        rows.append(row)
    rank = {tokens.VERIFIED: 2, tokens.CLAIMED: 1, tokens.UNVERIFIED: 0}
    have: dict[str, str] = {}
    for row in rows:
        if row["valid"] is False:
            continue
        for cap, evidence in row["provides"].items():
            if cap not in have or rank[evidence] > rank[have[cap]]:
                have[cap] = evidence
    missing = [cap for cap in need if cap not in have]
    weak = [cap for cap in need if have.get(cap) == tokens.UNVERIFIED]
    lines = []
    for row in rows:
        user = f"{row['user']['name']} ({row['user']['id']})" if row["user"] else "?"
        app = f"{row['app']['id']} {row['app']['name']}" if row["app"] else "?"
        valid = {True: "yes", False: f"NO ({row['error']})", None: f"? ({row['error']})"}[row["valid"]]
        provides = ",".join(f"{cap}{'' if ev == tokens.VERIFIED else '?'}" for cap, ev in row["provides"].items())
        flags = "" if row["confirmed"] else " prefix-only"
        flags += "" if row.get("binding") != "MISMATCH" else " c_user!=/me"
        flags += " NO-COOKIES" if (row["needs_cookies"] and not row["cookies_set"]) else ""
        lines.append(f"    {row['variable']:<22} {row['class']:<11}{flags} app {app} | user {user} | "
                     f"valid {valid} | provides {provides}")
    lines.append(f"    needed for this profile: {','.join(need)}; still missing: "
                 f"{','.join(missing) or 'none'}"
                 + (f"; only unverified: {','.join(weak)}" if weak else "")
                 + "  (? = evidence unverified, tokens.py)")
    bad = any(row["valid"] is False or row.get("binding") == "MISMATCH"
              or (row["needs_cookies"] and not row["cookies_set"]) for row in rows)
    r.add("token table", WARN if (bad or missing) else PASS, "\n" + "\n".join(lines),
          {"tokens": rows, "needed": need, "missing": missing, "unverified_only": weak})
    if out_path:
        payload = graph.redact(json.dumps(
            {"tokens": rows, "needed": need, "missing": missing, "unverified_only": weak},
            indent=2, default=str))
        fd = os.open(out_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)


# ---- doctor --risk: read-only account / asset risk snapshot ---------------------------------------

RISK_SCHEMA = "metaops.risk/v1"
RISK_NOTE = (
    "Thresholds are the operator's own priors (code defaults, overridable in the workspace `risk` "
    "block). No Meta source ties any of them to Spam or Account Integrity disables: a clean "
    "snapshot proves nothing, a flag is a prompt to look, not a diagnosis. The billing threshold "
    "has no API field: read and set it in the UI only (Billing & payments hub); it is not "
    "evaluated here."
)
RISK_UI_ONLY = ["billing threshold (payment threshold that triggers a charge)"]

# Requested together; every name is an AdAccount field declared by facebook_business 26.0.1, and
# the ones probe.gate_account / asset_graph already read are field-proven. `created_time` and the
# `funding_source_details{type,display_string}` sub-selection are SDK-declared only.
RISK_ACCOUNT_FIELDS = (
    "id,created_time,amount_spent,balance,spend_cap,account_status,disable_reason,"
    "funding_source_details{type,display_string},currency,timezone_name,business{id,name},"
    "is_prepay_account"
)
# Requested in a SEPARATE GET that may fail without failing the command.
RISK_ACCOUNT_UNVERIFIED_FIELDS = "age,min_daily_budget"
RISK_PIXEL_FIELDS = "id,name,creation_time,last_fired_time,is_unavailable"
RISK_PAGE_FIELDS = "id,name,fan_count,followers_count,verification_status,is_published"
RISK_PAGE_FIELDS_FALLBACK = "id,name,fan_count,verification_status,is_published"
RISK_ADS_FIELDS = "effective_status,created_time"

# Everything below was never read live by this codebase (declared in the SDK or assumed from
# the Graph reference). Listed in the output so a wrong answer can be traced to its source.
RISK_UNVERIFIED_FIELDS = {
    "AdAccount": {
        "separate_get": ["age", "min_daily_budget"],
        "sdk_declared_not_live": ["created_time", "funding_source_details{type,display_string}"],
    },
    "AdsPixel": {"sdk_declared_not_live": ["creation_time", "last_fired_time", "is_unavailable"]},
    "Page": {"sdk_declared_not_live": ["followers_count"],
             "note": "retried without followers_count when Graph answers code 100"},
    "Ad (edge /act_X/ads)": {
        "sdk_declared_not_live": ["created_time"],
        "note": "window is applied client-side on created_time; which effective_status values the "
                "default read of the edge omits (ARCHIVED / DELETED) is unverified",
    },
    "semantics": [
        "amount_spent / balance / spend_cap are minor units (offset 100; 1 for "
        + "/".join(sorted(["JPY", "KRW", "VND", "CLP", "ISK", "PYG", "TWD"]))
        + "; the offset table is assumed, not read)",
        "spend_cap '0' or absent = no cap",
        "pixel last_fired_time absent = never fired OR not readable with this token",
    ],
}
ZERO_OFFSET_CURRENCIES = {"JPY", "KRW", "VND", "CLP", "ISK", "PYG", "TWD"}

# [first-party, verified 2026-09-24] references/07 disable_reason enum.
DISABLE_REASON = {
    0: "NONE", 1: "ADS_INTEGRITY_POLICY", 2: "ADS_IP_REVIEW", 3: "RISK_PAYMENT",
    4: "GRAY_ACCOUNT_SHUT_DOWN", 5: "ADS_AFC_REVIEW", 6: "BUSINESS_INTEGRITY_RAR",
    7: "PERMANENT_CLOSE", 8: "UNUSED_RESELLER_ACCOUNT", 9: "UNUSED_ACCOUNT",
    10: "UMBRELLA_AD_ACCOUNT", 11: "BUSINESS_MANAGER_INTEGRITY_POLICY",
    12: "MISREPRESENTED_AD_ACCOUNT", 13: "AOAB_DESHARE_LEGAL_ENTITY", 14: "CTX_THREAD_REVIEW",
    15: "COMPROMISED_AD_ACCOUNT",
}


def _parse_time(value) -> dt.datetime | None:
    """Graph datetime (`2026-09-20T10:15:00+0000`, `...Z`, `...+00:00`) or unix seconds -> aware UTC."""
    if value in (None, "", 0):
        return None
    if isinstance(value, (int, float)) or str(value).strip().isdigit():
        try:
            return dt.datetime.fromtimestamp(int(value), dt.timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    text = str(value).strip()
    text = re.sub(r"Z$", "+00:00", text)
    text = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", text)
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)


def _days_since(moment: dt.datetime | None, now: dt.datetime) -> float | None:
    return None if moment is None else round((now - moment).total_seconds() / 86400, 2)


def _money(minor, currency: str | None) -> dict | None:
    """Graph money string (minor units) -> {"minor", "major", "currency"}; None when not a number."""
    if minor in (None, ""):
        return None
    try:
        amount = decimal.Decimal(str(minor))
    except decimal.InvalidOperation:
        return None
    offset = 1 if (currency or "").upper() in ZERO_OFFSET_CURRENCIES else 100
    return {"minor": str(minor), "major": float(amount / offset), "currency": currency}


def _is_throttle(exc: graph.GraphError) -> bool:
    code = exc.code
    return (isinstance(exc, graph.CooldownError) or code in graph.ACCOUNT_THROTTLE_CODES
            or code in graph.GLOBAL_THROTTLE_CODES
            or (isinstance(code, int) and 80000 <= code <= 80999))


def collect_risk(account: str, page_id: str | None, pixel_ids: list[str], cfg: dict,
                 now: dt.datetime) -> dict:
    """Every Graph read of the snapshot. A failed read lands in `errors`, never raises; after a
    throttle the remaining reads are skipped (Graph: stop calling, every retry extends the block)."""
    snap: dict = {"account_raw": None, "account_extra": None, "pixels": [], "page": None,
                  "ads": None, "errors": {}}
    state = {"throttled": False}

    def read(key: str, path: str, params: dict, context: str):
        if state["throttled"]:
            snap["errors"][key] = "skipped: an earlier risk read was throttled"
            return None
        try:
            return graph.get(path, params=params, context=context)
        except graph.GraphError as exc:
            snap["errors"][key] = graph.redact(str(exc))
            state["throttled"] = _is_throttle(exc)
            snap.setdefault("error_codes", {})[key] = exc.code
            return None

    snap["account_raw"] = read("account", account, {"fields": RISK_ACCOUNT_FIELDS}, "risk: ad account")
    snap["account_extra"] = read("account_unverified", account,
                                 {"fields": RISK_ACCOUNT_UNVERIFIED_FIELDS},
                                 "risk: ad account (unverified fields)")
    for pixel_id in pixel_ids:
        key = f"pixel:{pixel_id}"
        node = read(key, pixel_id, {"fields": RISK_PIXEL_FIELDS}, "risk: pixel")
        snap["pixels"].append({"id": pixel_id, "raw": node})
    if page_id:
        node = read("page", page_id, {"fields": RISK_PAGE_FIELDS}, "risk: page")
        if node is None and snap.get("error_codes", {}).get("page") == 100:
            first_error = snap["errors"].pop("page")
            snap["error_codes"].pop("page", None)
            node = read("page", page_id, {"fields": RISK_PAGE_FIELDS_FALLBACK}, "risk: page (fallback)")
            if node is not None:
                snap["errors"]["page_followers_count"] = first_error
        snap["page"] = node
    snap["ads"] = _read_ads(account, cfg, now, read)
    return snap


def _read_ads(account: str, cfg: dict, now: dt.datetime, read) -> dict | None:
    cutoff = now - dt.timedelta(days=float(cfg["ads_window_days"]))
    params: dict | None = {"fields": RISK_ADS_FIELDS, "limit": 200}
    by_status: dict[str, int] = {}
    total = older = pages = 0
    truncated = False
    while params is not None:
        page = read("ads", f"{account}/ads", params, "risk: ads in window")
        if page is None:
            return None if pages == 0 else {
                "window_days": cfg["ads_window_days"], "total": total, "older_than_window": older,
                "by_status": by_status, "pages_read": pages, "truncated": True, "partial": True}
        pages += 1
        for row in page.get("data", []) or []:
            created = _parse_time(row.get("created_time"))
            if created is not None and created < cutoff:
                older += 1
                continue
            total += 1
            status = str(row.get("effective_status") or "UNKNOWN")
            by_status[status] = by_status.get(status, 0) + 1
        params = graph.next_page_params(page, params)
        if params is not None and pages >= int(cfg["ads_max_pages"]):
            truncated = True
            break
    return {"window_days": cfg["ads_window_days"], "total": total, "older_than_window": older,
            "by_status": by_status, "pages_read": pages, "truncated": truncated}


def _level_word(status) -> str:
    return ACCOUNT_STATUS.get(status, f"UNKNOWN({status})")


def summarize_risk(snap: dict, now: dt.datetime) -> dict:
    """Raw Graph answers -> the normalized numbers `evaluate_risk` and the output use."""
    raw = snap.get("account_raw") or {}
    extra = snap.get("account_extra") or {}
    currency = raw.get("currency")
    created = _parse_time(raw.get("created_time"))
    age_days = _days_since(created, now)
    if age_days is None and extra.get("age") not in (None, ""):
        try:
            age_days = round(float(extra["age"]), 2)
        except (TypeError, ValueError):
            age_days = None
    funding = raw.get("funding_source_details") or None
    account = None
    if snap.get("account_raw") is not None:
        status = raw.get("account_status")
        reason = raw.get("disable_reason")
        account = {
            "id": raw.get("id"),
            "created_time": raw.get("created_time"),
            "age_days": age_days,
            "account_status": status,
            "account_status_name": _level_word(status) if status is not None else None,
            "disable_reason": reason,
            "disable_reason_name": DISABLE_REASON.get(reason, f"UNKNOWN({reason})")
            if reason is not None else None,
            "amount_spent": _money(raw.get("amount_spent"), currency),
            "balance": _money(raw.get("balance"), currency),
            "spend_cap": _money(raw.get("spend_cap"), currency),
            "currency": currency,
            "timezone_name": raw.get("timezone_name"),
            "business": raw.get("business"),
            "is_prepay_account": raw.get("is_prepay_account"),
            "funding_source": (
                {"type": funding.get("type"), "display_string": funding.get("display_string")}
                if isinstance(funding, dict) else funding),
            "unverified": {"age": extra.get("age"), "min_daily_budget": extra.get("min_daily_budget")}
            if snap.get("account_extra") is not None else None,
        }
    pixels = []
    for entry in snap.get("pixels", []):
        node = entry.get("raw")
        if node is None:
            pixels.append({"id": entry["id"], "read": False})
            continue
        created_px = _parse_time(node.get("creation_time"))
        pixels.append({
            "id": entry["id"], "read": True, "name": node.get("name"),
            "creation_time": node.get("creation_time"), "age_days": _days_since(created_px, now),
            "last_fired_time": node.get("last_fired_time"),
            "is_unavailable": node.get("is_unavailable"),
        })
    page = snap.get("page")
    page_out = None
    if page is not None:
        page_out = {k: page.get(k) for k in
                    ("id", "name", "fan_count", "followers_count", "verification_status", "is_published")}
    return {"account": account, "pixels": pixels, "page": page_out, "ads": snap.get("ads")}


def evaluate_risk(summary: dict, errors: dict, cfg: dict) -> list[dict]:
    """The findings. Levels: info (context), warn (look at it), high (act before spending).
    Every threshold is a prior from `cfg`; none is a Meta rule."""
    findings: list[dict] = []

    def add(level: str, code: str, message: str) -> None:
        findings.append({"level": level, "code": code, "message": message})

    account = summary.get("account")
    if account is None:
        add("warn", "account_read_failed",
            f"could not read the ad account: {errors.get('account', 'no answer')}")
    else:
        status = account["account_status"]
        reason = account["disable_reason"]
        if status is None:
            add("warn", "account_status_unknown", "account_status was not returned")
        elif status != 1:
            add("high", "account_status_not_active",
                f"account_status {status} {account['account_status_name']}"
                + (f", disable_reason {reason} {account['disable_reason_name']}" if reason else "")
                + ". Do not launch or edit; triage first (23).")
        elif reason:
            add("warn", "disable_reason_set",
                f"account is ACTIVE but disable_reason is {reason} {account['disable_reason_name']}")
        age = account["age_days"]
        if age is None:
            add("info", "account_age_unknown", "created_time (and age) not returned: account age unknown")
        elif age < float(cfg["min_account_age_days"]):
            add("warn", "account_young",
                f"account is {age:g} days old (prior: warn under {cfg['min_account_age_days']:g} days)")
        spent = account["amount_spent"]
        cur = account["currency"] or "?"
        if spent is None:
            add("info", "amount_spent_unknown", "amount_spent not returned")
        elif spent["major"] < float(cfg["min_amount_spent"]):
            add("warn", "spend_low",
                f"lifetime amount_spent {spent['major']:g} {cur} is under {cfg['min_amount_spent']:g} "
                f"(prior; compared in the account currency {cur}, no FX)")
        cap = account["spend_cap"]
        if cap is not None and spent is not None and float(cap["minor"] or 0) > 0:
            used = float(spent["minor"]) / float(cap["minor"])
            if used >= 1:
                add("high", "spend_cap_reached",
                    f"amount_spent {spent['major']:g} has reached spend_cap {cap['major']:g} {cur}: ads pause")
            elif used >= float(cfg["spend_cap_near_ratio"]):
                add("warn", "spend_cap_near",
                    f"amount_spent is {used:.0%} of spend_cap {cap['major']:g} {cur} "
                    f"(prior: warn from {float(cfg['spend_cap_near_ratio']):.0%})")
        if not account["funding_source"]:
            add("high", "no_funding_source", "no funding_source_details on the ad account")
    add("info", "billing_threshold_ui_only",
        "the billing threshold has no API field: check it in the UI (Billing & payments hub)")
    if "account_unverified" in errors:
        add("info", "unverified_fields_unavailable",
            f"AdAccount age / min_daily_budget could not be read: {errors['account_unverified']}")

    pixels = summary.get("pixels") or []
    if not pixels:
        add("info", "pixel_not_configured", "no pixel / dataset id to check")
    for pixel in pixels:
        pid = pixel["id"]
        if not pixel["read"]:
            add("warn", "pixel_read_failed",
                f"could not read pixel {pid}: {errors.get('pixel:' + pid, 'no answer')}")
            continue
        if pixel.get("is_unavailable"):
            add("high", "pixel_unavailable", f"pixel {pid} reports is_unavailable")
        if not pixel.get("last_fired_time"):
            add("warn", "pixel_never_fired",
                f"pixel {pid} has no last_fired_time (never fired, or the field is not readable "
                "with this token)")
        age = pixel.get("age_days")
        if age is not None and age < float(cfg["min_pixel_age_days"]):
            add("warn", "pixel_young",
                f"pixel {pid} was created {age:g} days ago (prior: warn under "
                f"{cfg['min_pixel_age_days']:g} days)")

    page = summary.get("page")
    if page is None:
        if "page" in errors:
            add("warn", "page_read_failed", f"could not read the Page: {errors['page']}")
        else:
            add("info", "page_not_configured", "no Page id to check")
    else:
        if page.get("is_published") is False:
            add("high", "page_unpublished", f"Page {page.get('id')} is not published")
        followers = page.get("followers_count")
        source = "followers_count"
        if followers is None:
            followers, source = page.get("fan_count"), "fan_count"
        if followers is None:
            add("info", "page_followers_unknown", "neither followers_count nor fan_count returned")
        elif followers < float(cfg["min_page_followers"]):
            add("warn", "page_followers_low",
                f"Page has {followers} ({source}), under {cfg['min_page_followers']:g} (prior)")

    ads = summary.get("ads")
    if ads is None:
        add("warn", "ads_read_failed", f"could not read ads: {errors.get('ads', 'no answer')}")
    else:
        total = ads["total"]
        disapproved = ads["by_status"].get("DISAPPROVED", 0)
        issues = ads["by_status"].get("WITH_ISSUES", 0)
        window = ads["window_days"]
        if total == 0:
            add("info", "ads_none_in_window", f"no ads created in the last {window} days")
        else:
            if issues:
                add("info", "ads_with_issues", f"{issues} of {total} ads WITH_ISSUES in the last {window} days")
            ratio = disapproved / total
            if disapproved and total < int(cfg["min_ads_for_ratio"]):
                add("info", "ads_disapproved_small_sample",
                    f"{disapproved} of {total} ads DISAPPROVED in the last {window} days "
                    f"(under {int(cfg['min_ads_for_ratio'])} ads: ratio not judged)")
            elif ratio >= float(cfg["disapproved_high_ratio"]):
                add("high", "ads_disapproved_ratio",
                    f"{disapproved} of {total} ads DISAPPROVED in the last {window} days ({ratio:.0%}; "
                    f"prior: high from {float(cfg['disapproved_high_ratio']):.0%})")
            elif ratio >= float(cfg["max_disapproved_ratio"]):
                add("warn", "ads_disapproved_ratio",
                    f"{disapproved} of {total} ads DISAPPROVED in the last {window} days ({ratio:.0%}; "
                    f"prior: warn from {float(cfg['max_disapproved_ratio']):.0%})")
        if ads.get("truncated"):
            add("info", "ads_sample_truncated",
                f"read {ads['pages_read']} page(s) of ads only; counts are a sample, not the full window")
    return findings


def gate_risk(r: Report, account: str, page_id: str | None, pixel_ids: list[str],
              cfg_override: dict | None = None, out_path: str | None = None,
              now: dt.datetime | None = None) -> dict:
    """Read-only. Never adds a FAIL row, so `--risk` cannot change the doctor verdict."""
    now = now or dt.datetime.now(dt.timezone.utc)
    cfg = meta_workspace.merge_risk(cfg_override)
    snap = collect_risk(account, page_id, pixel_ids, cfg, now)
    summary = summarize_risk(snap, now)
    findings = evaluate_risk(summary, snap["errors"], cfg)
    counts = {level: sum(1 for f in findings if f["level"] == level) for level in ("high", "warn", "info")}
    report = {
        "schema": RISK_SCHEMA,
        "checked_at": now.isoformat(timespec="seconds"),
        "account_id": account,
        "snapshot": summary,
        "risk_findings": findings,
        "counts": counts,
        "errors": snap["errors"],
        "thresholds": cfg,
        "unverified_fields": RISK_UNVERIFIED_FIELDS,
        "ui_only": RISK_UI_ONLY,
        "note": RISK_NOTE,
    }
    acct = summary["account"]
    if acct:
        spent = acct["amount_spent"]
        cap = acct["spend_cap"]
        line = (f"{account} age {acct['age_days'] if acct['age_days'] is not None else '?'} d, "
                f"spent {spent['major'] if spent else '?'} {acct['currency']}, "
                f"spend_cap {cap['major'] if cap and cap['major'] else 'none'}, "
                f"status {acct['account_status_name']}")
    else:
        line = f"{account}: account read failed"
    r.add("risk snapshot", PASS, line, report["snapshot"])
    for finding in findings:
        r.add("risk", PASS if finding["level"] == "info" else WARN,
              f"[{finding['level']}] {finding['code']}: {finding['message']}")
    r.add("risk findings", PASS,
          f"{counts['high']} high, {counts['warn']} warn, {counts['info']} info", findings)
    r.add("risk note", PASS, RISK_NOTE)
    if out_path:
        payload = graph.redact(json.dumps(report, indent=2, default=str))
        fd = os.open(out_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--account", help="act_<id>; omit for --whoami")
    ap.add_argument("--whoami", action="store_true",
                    help="token intake only: type, app, expiry, scopes, visible accounts, verdict on pipe/proxy")
    ap.add_argument("--page", help="Page id used as the ad identity")
    ap.add_argument("--dataset", help="Pixel/dataset id for the CAPI write probe")
    ap.add_argument("--create-pbia", action="store_true", help="Create the PBIA if absent")
    ap.add_argument("--attach-pixel", action="store_true",
                    help="Share the dataset to this ad account if it is not attached (needs --business)")
    ap.add_argument("--business", help="Business (BM) id that owns the pixel — for --attach-pixel")
    ap.add_argument("--catalog", help="Catalog id of the profile: only makes the token table list "
                                      "'catalog' among the capabilities this profile needs")
    ap.add_argument("--risk", action="store_true",
                    help="append the read-only account / pixel / Page / ads risk snapshot")
    ap.add_argument("--risk-config", help="JSON thresholds (workspace `risk` block, merged over the defaults)")
    ap.add_argument("--risk-out", help="write the risk snapshot and risk_findings here (JSON, 0600)")
    ap.add_argument("--json", help="Write the full report here")
    args = ap.parse_args()

    if not args.account and not args.whoami:
        ap.error("--account is required unless --whoami")
    if args.whoami and any((args.page, args.dataset, args.business, args.create_pbia, args.attach_pixel)):
        ap.error("--whoami is intake-only; do not combine it with account/Page/dataset mutations")
    if args.risk and (args.whoami or not args.account):
        ap.error("--risk reads one ad account: pass --account (metaops fills it from the profile)")
    try:
        risk_override = json.loads(args.risk_config) if args.risk_config else None
        meta_workspace.merge_risk(risk_override)
    except (ValueError, meta_workspace.WorkspaceError) as exc:
        ap.error(f"--risk-config: {exc}")
    tokens_out = os.environ.get("METAOPS_TOKENS_OUT") or None
    r = Report()
    if args.whoami:
        print(f"Graph {graph.API_VERSION} · token intake")
        gate_identity(r)
        gate_token_class(r)
        gate_token_debug(r)
        gate_token_table(r, needed_capabilities(None, None, None), tokens_out)
        gate_scopes(r)
        gate_visible_accounts(r, None)
        whoami_verdict(r)
        if args.json:
            with open(args.json, "w", encoding="utf-8") as fh:
                fh.write(graph.redact(json.dumps(r.rows, indent=2, default=str)))
        return 1 if r.failed else 0
    account = graph.normalize_account(args.account)

    print(f"Graph {graph.API_VERSION} · {account}")
    gate_identity(r)
    gate_token_class(r)
    gate_token_debug(r)
    gate_token_table(r, needed_capabilities(args.business, args.dataset, args.catalog), tokens_out)
    gate_scopes(r)
    gate_visible_accounts(r, account)
    gate_account(r, account)
    if args.page:
        gate_page_and_pbia(r, args.page, args.create_pbia)
    if args.dataset:
        gate_pixel_attached(r, account, args.dataset, args.business, args.attach_pixel)
        gate_dataset(r, args.dataset)
    gate_write(r, account)
    if args.risk:
        try:
            gate_risk(r, account, args.page,
                      [x for x in (args.dataset or "").split(",") if x.strip()],
                      risk_override, args.risk_out)
        except graph.GraphError as exc:  # a snapshot never changes the verdict
            r.add("risk snapshot", WARN, f"could not complete: {exc}")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            fh.write(graph.redact(json.dumps(r.rows, indent=2, default=str)))
        print(f"\nreport → {args.json}")

    if r.failed:
        print("\nBLOCKED — fix the FAIL gates before launching.", file=sys.stderr)
        return 1
    print("\nAll required gates passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

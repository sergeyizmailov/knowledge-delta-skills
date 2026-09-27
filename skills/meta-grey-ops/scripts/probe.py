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
"""

from __future__ import annotations

import argparse
import json
import sys

import graph

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


def gate_identity(r: Report) -> None:
    try:
        me = graph.get("me", params={"fields": "id,name"}, context="identity")
        r.add("token identity", PASS, f"{me.get('name', '?')} ({me['id']})", me)
    except graph.GraphError as e:
        r.add("token identity", FAIL, str(e), e.as_dict())


def gate_token_debug(r: Report) -> None:
    """/debug_token accepts the System User token as its own app token (live 2026-09-02):
    returns type, app, expires_at (0 = never), data_access_expires_at, scopes."""
    try:
        d = graph.get("debug_token", params={"input_token": graph.token()}, context="debug_token")["data"]
    except graph.GraphError as e:
        r.add("token debug", WARN, f"debug_token unavailable for this token: {e}")
        # Scraped first-party tokens can't self-debug; GET /app still names the minting app
        # (119211728144504 Power Editor = EAAB launch token; 515496645328243 Products = EAAH).
        try:
            app = graph.get("app", params={"fields": "id,name"}, context="token app")
            r.add("token app", PASS, f"{app.get('name')} ({app.get('id')})", app)
        except graph.GraphError as e2:
            r.add("token app", WARN, str(e2))
        return
    exp = d.get("expires_at")
    life = "never" if exp == 0 else str(exp)
    r.add("token debug", PASS if d.get("is_valid") else FAIL,
          f"type={d.get('type')} app={d.get('app_id')} ({d.get('application')}) expires={life} "
          f"data_access_expires={d.get('data_access_expires_at')}", d)


def gate_scopes(r: Report) -> None:
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
                     "explicitly confirmed direct egress for this BM (then META_ALLOW_NO_PROXY=1).")
    elif ttype == "USER":
        lines.append("USER token: it IS a persona session. Route every call through that persona's proxy "
                     "(META_PROXY=socks5h://…); it dies on logout/password change/checkpoint (190/460-467) "
                     "and cannot be revived — re-mint. No appsecret_proof for EAAB tokens from Ads Manager.")
        if exp:
            lines.append(f"expires_at={exp} — plan the re-mint; exchange to long-lived only if it came from "
                         "your own app (02 §4).")
    elif ttype == "PAGE":
        lines.append("PAGE token: comments/page edits only — no ad account writes.")
    else:
        lines.append(f"token type {ttype!r}: unknown to this probe; read 02 §4 before writing.")
    missing = {"ads_management", "business_management", "pages_read_engagement"} - scopes
    if missing:
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
                   idempotent=True)
        r.add("dataset CAPI write", WARN, "empty POST accepted — unexpected, verify manually")
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
    ap.add_argument("--json", help="Write the full report here")
    args = ap.parse_args()

    if not args.account and not args.whoami:
        ap.error("--account is required unless --whoami")
    if args.whoami and any((args.page, args.dataset, args.business, args.create_pbia, args.attach_pixel)):
        ap.error("--whoami is intake-only; do not combine it with account/Page/dataset mutations")
    r = Report()
    if args.whoami:
        print(f"Graph {graph.API_VERSION} · token intake")
        gate_identity(r)
        gate_token_debug(r)
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
    gate_token_debug(r)
    gate_scopes(r)
    gate_visible_accounts(r, account)
    gate_account(r, account)
    if args.page:
        gate_page_and_pbia(r, args.page, args.create_pbia)
    if args.dataset:
        gate_pixel_attached(r, account, args.dataset, args.business, args.attach_pixel)
        gate_dataset(r, args.dataset)
    gate_write(r, account)

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

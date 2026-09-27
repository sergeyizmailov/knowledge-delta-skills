#!/usr/bin/env python3
"""Business-Manager-side setup ops for `metaops`: accounts/pixel/CAPI/users/sharing.

Everything here is a thin wrapper over in-process ``ctx.graph.post``/``ctx.graph.get``
(the same transport metaops.py and probe.py use) or, for pixel-attach, a reuse of
probe.py's own gate through ``ctx.run_child`` — never a second implementation of that
POST. No new Graph payload shapes beyond what `facebook_business` 26.0.1 declares for
each edge; every param name below was read directly from that SDK's generated request
classes on 2026-09-03 (`inspect.getsource`), not from memory or docs scraping.

Billing has NO API surface here: no funding source, payment method, spend cap, or
invoicing call exists in this module. Do that in Business Settings > Payments in the
UI; `03` documents the billing gotchas (ASL, unsettled balance, DST fees).

Register from metaops.py::

    import cmd_business
    cmd_business.register(sub, ctx)   # after `sub = ap.add_subparsers(...)`

Commands (each returns ``(exit_code, metaops.result/v1 dict)``, matching every other
`command_*` handler in metaops.py):

    business assets                                            — list BM asset graph
    business adaccount create --name --currency --timezone-id [--end-advertiser
        --media-agency --partner --funding-id] --confirm CREATE
    business pixel create --name [--is-crm] --confirm CREATE
    business pixel share --account act_X --confirm SHARE
    business pixel shared
    business capi test --event NAME --test-code TESTxxxx [--url URL]
    business user invite --email E --role EMPLOYEE|ADMIN --confirm SHARE
    business user assign --user-id U --asset adaccount|page|pixel --tasks T,T --confirm SHARE
    business partner share --partner-business B --asset adaccount|page|pixel
        --tasks T,T --confirm SHARE

All commands except `assets`/`pixel shared`/`capi test` require the literal confirm
value shown (create → CREATE, every sharing/invite/assign op → SHARE) — same
"confirm the destructive word" contract as `activate --confirm SPEND` in metaops.py.

Every command is workspace-bound: `business_id`/`ad_account_id`/`page_id`/`dataset_id`
come from the resolved workspace profile (`--profile`), never from ad-hoc flags, so a
Business-Manager-agnostic profile swap is the only way to retarget these ops.
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import time
from typing import Any

ASSET_ID_KEYS = {
    "adaccount": "ad_account_id",
    "page": "page_id",
    "pixel": "dataset_id",
}

# A fixed, non-real address: CAPI test events only need a hashable user_data field to
# reach the Events Manager "Test events" tab, never a live customer identity.
DUMMY_TEST_EMAIL = "metaops-capi-test@example.invalid"


def _require_workspace(ctx: Any, args: argparse.Namespace, label: str) -> None:
    if not getattr(args, "workspace_obj", None):
        raise ctx.MetaOpsError(f"{label} requires --workspace")


def _require_confirm(ctx: Any, args: argparse.Namespace, expected: str, label: str) -> None:
    if args.confirm != expected:
        raise ctx.MetaOpsError(f"{label} requires the literal --confirm {expected}")


TASKS_BY_ASSET = {
    "adaccount": frozenset({"AA_ANALYZE", "ADVERTISE", "ANALYZE", "DRAFT", "MANAGE"}),
    "page": frozenset({"ADVERTISE", "ANALYZE", "MANAGE"}),
    "pixel": frozenset({"ADVERTISE", "ANALYZE", "EDIT", "UPLOAD"}),
}


def _tasks_list(ctx: Any, raw: str, asset_kind: str) -> list[str]:
    tasks = [t.strip().upper() for t in raw.split(",") if t.strip()]
    if not tasks:
        raise ctx.MetaOpsError("--tasks must contain at least one task")
    invalid = sorted(set(tasks) - TASKS_BY_ASSET[asset_kind])
    if invalid:
        allowed = ", ".join(sorted(TASKS_BY_ASSET[asset_kind]))
        raise ctx.MetaOpsError(
            f"--tasks {invalid} are not valid for {asset_kind}; allowed: {allowed}"
        )
    return tasks


def _resolve_asset_id(ctx: Any, profile: dict[str, Any], asset_kind: str) -> str:
    key = ASSET_ID_KEYS[asset_kind]
    value = profile.get(key)
    if not value:
        raise ctx.MetaOpsError(f"workspace profile has no {key} for --asset {asset_kind}")
    return ctx.graph.normalize_account(value) if asset_kind == "adaccount" else str(value)


def _list_edge(ctx: Any, node_id: str, edge: str, fields: str, limit: int = 200,
               extra: dict[str, Any] | None = None) -> list[dict]:
    out: list[dict] = []
    path: str | None = f"{node_id}/{edge}"
    params: dict[str, Any] = {"fields": fields, "limit": limit, **(extra or {})}
    while path:
        resp = ctx.graph.get(path, params=params, context=f"business {edge}")
        out.extend(resp.get("data", []))
        params = ctx.graph.next_page_params(resp, params)
        if params is None:
            break
    return out


def _sha256(value: str) -> str:
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()


# --- assets --------------------------------------------------------------------

# Edge names/fields verified 2026-09-03 (SDK 26.0.1): Business.get_owned_ad_accounts,
# get_client_ad_accounts, get_owned_pages, get_client_pages, get_owned_pixels,
# get_owned_product_catalogs, get_system_users all declare these exact endpoints.
BUSINESS_ASSET_EDGES = {
    "owned_ad_accounts": "id,name,account_status",
    "client_ad_accounts": "id,name,account_status",
    "owned_pages": "id,name",
    "client_pages": "id,name",
    "owned_pixels": "id,name",
    "owned_product_catalogs": "id,name",
    "system_users": "id,name,role",
}


def _business_assets(ctx: Any, args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    _require_workspace(ctx, args, "business assets")
    profile_name, profile = args.workspace_obj.profile(args.profile)
    business_id = str(profile["business_id"])
    data: dict[str, Any] = {"profile": profile_name, "business_id": business_id}
    for edge, fields in BUSINESS_ASSET_EDGES.items():
        data[edge] = _list_edge(ctx, business_id, edge, fields)
    return 0, ctx.result_envelope(
        "business assets", True, "listed",
        artifacts={"workspace": str(args.workspace_obj.path)},
        data=data,
        next_action="Use these ids for pixel share / user assign / partner share.",
    )


# --- adaccount create ------------------------------------------------------------

# Params verified 2026-09-03 (SDK 26.0.1) from Business.create_ad_account's
# param_types: name, currency, timezone_id, end_advertiser, media_agency, partner,
# funding_id (plus invoice/invoice_group_id/invoicing_emails/io/po_number/
# ad_account_created_from_bm_flag, not exposed here — no billing surface, 03).
def _find_asset_by_name(rows: list[dict], name: str) -> dict | None:
    """Name-dedup for provisioning creates: a retry after outcome_unknown reuses the
    object the first POST may have created instead of provisioning a twin."""
    for row in rows:
        if str(row.get("name") or "") == name:
            return row
    return None


def _adaccount_create(ctx: Any, args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    _require_workspace(ctx, args, "business adaccount create")
    _require_confirm(ctx, args, "CREATE", "adaccount create")
    profile_name, profile = args.workspace_obj.profile(args.profile)
    ctx.require_provisioning_admin(args.workspace_obj, profile_name)
    business_id = str(profile["business_id"])
    # A brand-new BM is capped at 1 ad account (03): a duplicate POST either fails
    # or provisions an unwanted second account. Dedup by name first.
    owned = _list_edge(ctx, business_id, "owned_ad_accounts", "id,name")
    hit = _find_asset_by_name(owned, str(args.name))
    if hit is not None:
        account_id = ctx.graph.normalize_account(str(hit.get("id")))
        return 0, ctx.result_envelope(
            "business adaccount create", True, "exists",
            data={"profile": profile_name, "business_id": business_id,
                  "ad_account_id": account_id, "deduped": True},
            next_action="This account already exists; add it to workspace.json instead of creating.",
        )
    payload: dict[str, Any] = {
        "name": args.name,
        "currency": args.currency,
        "timezone_id": args.timezone_id,
    }
    for key, value in (
        ("end_advertiser", args.end_advertiser),
        ("media_agency", args.media_agency),
        ("partner", args.partner),
        ("funding_id", args.funding_id),
    ):
        if value:
            payload[key] = value
    try:
        created = ctx.graph.post(f"{business_id}/adaccount", payload, context="create ad account")
    except Exception as exc:  # noqa: BLE001 - reconcile outcome_unknown by name
        if bool(getattr(exc, "outcome_unknown", False)):
            owned = _list_edge(ctx, business_id, "owned_ad_accounts", "id,name")
            hit = _find_asset_by_name(owned, str(args.name))
            if hit is not None:
                account_id = ctx.graph.normalize_account(str(hit.get("id")))
                return 0, ctx.result_envelope(
                    "business adaccount create", True, "reconciled",
                    data={"profile": profile_name, "business_id": business_id,
                          "ad_account_id": account_id, "deduped": True},
                    next_action="The create may have applied before the break; reusing the found account.",
                )
        raise
    account_id = ctx.graph.normalize_account(str(created.get("id") or created.get("account_id")))
    return 0, ctx.result_envelope(
        "business adaccount create", True, "created",
        data={"profile": profile_name, "business_id": business_id, "ad_account_id": account_id},
        next_action=(
            "A brand-new BM is capped at 1 ad account until several weeks of policy "
            "compliance (03); add this account to workspace.json, share the profile "
            "pixel/page onto it (business pixel share), then run "
            "metaops assets verify --scope core and doctor before any launch."
        ),
    )


# --- pixel create / share / shared ------------------------------------------------

# Params verified 2026-09-03 (SDK 26.0.1): Business.create_ads_pixel param_types are
# name, is_crm only.
def _pixel_create(ctx: Any, args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    _require_workspace(ctx, args, "business pixel create")
    _require_confirm(ctx, args, "CREATE", "pixel create")
    profile_name, profile = args.workspace_obj.profile(args.profile)
    ctx.require_provisioning_admin(args.workspace_obj, profile_name)
    business_id = str(profile["business_id"])
    # Twin pixels split event history: dedup by name so a retry reuses the pixel.
    owned = _list_edge(ctx, business_id, "owned_pixels", "id,name")
    hit = _find_asset_by_name(owned, str(args.name))
    if hit is not None:
        return 0, ctx.result_envelope(
            "business pixel create", True, "exists",
            data={"profile": profile_name, "business_id": business_id,
                  "dataset_id": str(hit.get("id")), "deduped": True},
            next_action="This pixel already exists; share it instead of creating.",
        )
    payload: dict[str, Any] = {"name": args.name}
    if args.is_crm:
        payload["is_crm"] = True
    try:
        created = ctx.graph.post(f"{business_id}/adspixels", payload, context="create pixel")
    except Exception as exc:  # noqa: BLE001 - reconcile outcome_unknown by name
        if bool(getattr(exc, "outcome_unknown", False)):
            owned = _list_edge(ctx, business_id, "owned_pixels", "id,name")
            hit = _find_asset_by_name(owned, str(args.name))
            if hit is not None:
                return 0, ctx.result_envelope(
                    "business pixel create", True, "reconciled",
                    data={"profile": profile_name, "business_id": business_id,
                          "dataset_id": str(hit.get("id")), "deduped": True},
                    next_action="The create may have applied before the break; reusing the found pixel.",
                )
        raise
    dataset_id = str(created.get("id"))
    return 0, ctx.result_envelope(
        "business pixel create", True, "created",
        data={"profile": profile_name, "business_id": business_id, "dataset_id": dataset_id},
        next_action=(
            "Cold pixel: no event history (03). Run business pixel share --account "
            "act_X --confirm SHARE for every ad account that must use it, then "
            "metaops assets verify --scope core."
        ),
    )


# Reuses probe.py's own --attach-pixel gate (POST /{pixel}/shared_accounts) through
# ctx.run_child instead of re-implementing that call — same code path command_doctor
# already exercises for --attach-pixel. account_id/business params verified 2026-09-03
# (SDK 26.0.1: AdsPixel.create_shared_account param_types = account_id, business).
def _pixel_share(ctx: Any, args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    _require_workspace(ctx, args, "business pixel share")
    _require_confirm(ctx, args, "SHARE", "pixel share")
    profile_name, profile = args.workspace_obj.profile(args.profile)
    dataset_id = str(profile["dataset_id"])
    business_id = str(profile["business_id"])
    account = ctx.graph.normalize_account(args.account)
    declared_accounts = {
        ctx.graph.normalize_account(candidate["ad_account_id"])
        for candidate in args.workspace_obj.data.get("profiles", {}).values()
        if candidate.get("ad_account_id")
    }
    if account not in declared_accounts:
        raise ctx.MetaOpsError(
            f"{account} is not declared by this workspace; add/select its profile before pixel share"
        )
    ctx.require_provisioning_admin(args.workspace_obj, profile_name)
    report_path = (args.workspace_obj.state_root / "business" / f"pixel-share-{account}.json").resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    child = ctx.run_child(
        "probe.py",
        ["--account", account, "--dataset", dataset_id, "--business", business_id,
         "--attach-pixel", "--json", str(report_path)],
        args.timeout,
    )
    ctx.echo_child(child)
    if not child.ok:
        return child.returncode, ctx.child_failure("business pixel share", "attach_failed", child)
    rows = ctx.read_json(report_path, "probe report") if report_path.is_file() else []
    attach_row = next((row for row in rows if row.get("gate") == "pixel attached to account"), {})
    return 0, ctx.result_envelope(
        "business pixel share", True, "shared",
        artifacts={"probe_report": str(report_path)},
        data={"profile": profile_name, "ad_account_id": account, "dataset_id": dataset_id,
              "business_id": business_id, "probe_gate": attach_row},
        next_action="Run metaops assets verify --scope core to refresh the receipt bound to this account.",
    )


# Edge verified 2026-09-03 (SDK 26.0.1): AdsPixel.get_shared_accounts endpoint
# '/shared_accounts'.
def _pixel_shared(ctx: Any, args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    _require_workspace(ctx, args, "business pixel shared")
    profile_name, profile = args.workspace_obj.profile(args.profile)
    dataset_id = str(profile["dataset_id"])
    # Live 2026-09-03: GET /{pixel}/shared_accounts fails code 100 "The parameter business is
    # required" without the owning business id.
    rows = _list_edge(ctx, dataset_id, "shared_accounts", "id,name",
                      extra={"business": str(profile["business_id"])})
    return 0, ctx.result_envelope(
        "business pixel shared", True, "listed",
        data={"profile": profile_name, "dataset_id": dataset_id, "shared_accounts": rows},
        next_action="Compare against workspace profiles; share any missing account with business pixel share.",
    )


# --- capi test ---------------------------------------------------------------------

# Body shape verified 2026-09-03 (SDK 26.0.1): AdsPixel.create_event param_types
# include data, test_event_code, partner_agent (unused here — no partner integration
# name to declare). `data` is Graph's JSON array of event objects; ctx.graph.post's
# _encode() json.dumps's a Python list exactly once (same contract probe.py's
# CAPI probe already relies on for an empty `data` array).
def _capi_test(ctx: Any, args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    # Duplicate-safe by design (no in-flight needed): a CAPI test event carries a
    # test_event_code and a fixed dummy identity — it lands in Events Manager "Test
    # events" only, never in delivery. Re-posting the same payload after
    # outcome_unknown just sends the same test ping twice.
    _require_workspace(ctx, args, "business capi test")
    profile_name, profile = args.workspace_obj.profile(args.profile)
    dataset_id = str(profile["dataset_id"])
    event = {
        "event_name": args.event,
        "event_time": int(time.time()),
        "action_source": "website",
        "event_source_url": args.url or "https://example.com/metaops-capi-test",
        "user_data": {
            "em": [_sha256(DUMMY_TEST_EMAIL)],
            "client_user_agent": "metaops-capi-test/1.0",
        },
    }
    payload = {"data": [event], "test_event_code": args.test_code}
    resp = ctx.graph.post(f"{dataset_id}/events", payload, context="capi test event")
    return 0, ctx.result_envelope(
        "business capi test", True, "sent",
        data={
            "profile": profile_name, "dataset_id": dataset_id, "event_name": args.event,
            "test_event_code": args.test_code,
            "events_received": resp.get("events_received"),
            "fbtrace_id": resp.get("fbtrace_id"),
        },
        next_action=f"Check Events Manager > Test events for {args.test_code} within a few seconds.",
    )


# --- user invite / assign ------------------------------------------------------------

# Params verified 2026-09-03 (SDK 26.0.1): Business.create_business_user param_types
# are email, invited_user_type, role, tasks; BusinessUser.Role enum includes ADMIN and
# EMPLOYEE among others — this command exposes only those two per spec.
# Duplicate-safe by design: re-inviting the same email/role is an idempotent share
# (no spend, no twin object) — safe to retry after outcome_unknown with the same payload.
def _user_invite(ctx: Any, args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    _require_workspace(ctx, args, "business user invite")
    _require_confirm(ctx, args, "SHARE", "user invite")
    profile_name, profile = args.workspace_obj.profile(args.profile)
    ctx.require_provisioning_admin(args.workspace_obj, profile_name)
    business_id = str(profile["business_id"])
    payload = {"email": args.email, "role": args.role}
    created = ctx.graph.post(f"{business_id}/business_users", payload, context="invite business user")
    return 0, ctx.result_envelope(
        "business user invite", True, "invited",
        data={"profile": profile_name, "business_id": business_id,
              "user_id": created.get("id"), "role": args.role, "email": args.email},
        next_action="After acceptance, run business user assign to grant per-asset tasks.",
    )


# Params verified 2026-09-03 (SDK 26.0.1): AdAccount.create_assigned_user,
# Page.create_assigned_user, and AdsPixel.create_assigned_user all declare the SAME
# param_types — tasks, user — with NO `business` field (that field exists only on the
# separate /agencies edge, used by partner share below). This corrects the initial
# task assumption that assigned_users also took `business`.
# Duplicate-safe by design: assigning the same (user, tasks) twice converges to the
# same grant — safe to retry after outcome_unknown with the identical payload.
def _user_assign(ctx: Any, args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    _require_workspace(ctx, args, "business user assign")
    _require_confirm(ctx, args, "SHARE", "user assign")
    profile_name, profile = args.workspace_obj.profile(args.profile)
    asset_id = _resolve_asset_id(ctx, profile, args.asset)
    tasks = _tasks_list(ctx, args.tasks, args.asset)
    ctx.require_provisioning_admin(args.workspace_obj, profile_name)
    payload = {"user": args.user_id, "tasks": tasks}
    ctx.graph.post(f"{asset_id}/assigned_users", payload, context="assign business user")
    return 0, ctx.result_envelope(
        "business user assign", True, "assigned",
        data={"profile": profile_name, "asset": args.asset, "asset_id": asset_id,
              "user_id": args.user_id, "tasks": tasks},
        next_action="Confirm in Business Settings > People that the task list matches intent.",
    )


# --- partner share (agency sharing) ---------------------------------------------------

# Params verified 2026-09-03 (SDK 26.0.1): AdAccount.create_agency, Page.create_agency,
# AND AdsPixel.create_agency all declare the SAME param_types — business,
# permitted_tasks — at the SAME edge name /agencies. Pixel has no separate
# /shared_agencies edge (AdsPixel.create_shared_agency does not exist in this SDK);
# /agencies is the one partner-share edge for all three asset kinds.
# Duplicate-safe by design: sharing the same (business, tasks) twice converges —
# safe to retry after outcome_unknown with the identical payload.
def _partner_share(ctx: Any, args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    _require_workspace(ctx, args, "business partner share")
    _require_confirm(ctx, args, "SHARE", "partner share")
    profile_name, profile = args.workspace_obj.profile(args.profile)
    asset_id = _resolve_asset_id(ctx, profile, args.asset)
    tasks = _tasks_list(ctx, args.tasks, args.asset)
    ctx.require_provisioning_admin(args.workspace_obj, profile_name)
    payload = {"business": str(args.partner_business), "permitted_tasks": tasks}
    ctx.graph.post(f"{asset_id}/agencies", payload, context="partner share asset")
    return 0, ctx.result_envelope(
        "business partner share", True, "shared",
        data={"profile": profile_name, "asset": args.asset, "asset_id": asset_id,
              "partner_business": str(args.partner_business), "tasks": tasks},
        next_action="Partner must accept the share in their own BM before it becomes usable (03).",
    )


def register(sub: argparse._SubParsersAction, ctx: Any) -> None:
    """Attach the `business` command tree to metaops.py's subparsers.

    `sub` is the metaops top-level subparsers object; `ctx` is the metaops module
    itself, giving handlers ``ctx.graph``, ``ctx.result_envelope``, ``ctx.MetaOpsError``,
    ``ctx.run_child``/``ctx.echo_child``/``ctx.child_failure``, and ``ctx.read_json``.
    """
    p = sub.add_parser(
        "business",
        help="Business-Manager setup ops: accounts/pixel/CAPI/users/sharing (no billing surface)",
    )
    p.epilog = (
        "Billing (funding sources, payment methods, spend caps, invoicing) has no API "
        "surface in this command tree — set it up in Business Settings > Payments."
    )
    business_sub = p.add_subparsers(dest="business_action", required=True)

    action = business_sub.add_parser(
        "assets", help="list owned/client ad accounts, pages, pixels, catalogs, system users"
    )
    action.set_defaults(handler=functools.partial(_business_assets, ctx))

    p_adaccount = business_sub.add_parser("adaccount", help="ad account creation under this BM")
    adaccount_sub = p_adaccount.add_subparsers(dest="adaccount_action", required=True)
    action = adaccount_sub.add_parser("create", help="POST /{business}/adaccount")
    action.add_argument("--name", required=True)
    action.add_argument("--currency", default="USD")
    action.add_argument("--timezone-id", required=True, type=int, dest="timezone_id")
    action.add_argument("--end-advertiser", dest="end_advertiser")
    action.add_argument("--media-agency", dest="media_agency")
    action.add_argument("--partner")
    action.add_argument("--funding-id", dest="funding_id")
    action.add_argument("--confirm", required=True, help="must be literal CREATE")
    action.set_defaults(handler=functools.partial(_adaccount_create, ctx))

    p_pixel = business_sub.add_parser("pixel", help="pixel/dataset creation and attach-to-account")
    pixel_sub = p_pixel.add_subparsers(dest="pixel_action", required=True)
    action = pixel_sub.add_parser("create", help="POST /{business}/adspixels")
    action.add_argument("--name", required=True)
    action.add_argument("--is-crm", action="store_true", dest="is_crm")
    action.add_argument("--confirm", required=True, help="must be literal CREATE")
    action.set_defaults(handler=functools.partial(_pixel_create, ctx))
    action = pixel_sub.add_parser(
        "share", help="attach the profile pixel to an ad account (reuses probe.py --attach-pixel)"
    )
    action.add_argument("--account", required=True, help="act_<id> to attach the pixel to")
    action.add_argument("--confirm", required=True, help="must be literal SHARE")
    action.set_defaults(handler=functools.partial(_pixel_share, ctx))
    action = pixel_sub.add_parser("shared", help="list ad accounts the profile pixel is attached to")
    action.set_defaults(handler=functools.partial(_pixel_shared, ctx))

    p_capi = business_sub.add_parser("capi", help="Conversions API test events")
    capi_sub = p_capi.add_subparsers(dest="capi_action", required=True)
    action = capi_sub.add_parser("test", help="POST /{dataset_id}/events with a test_event_code")
    action.add_argument("--event", required=True, help="event_name, e.g. Lead, Purchase, ViewContent")
    action.add_argument("--test-code", required=True, dest="test_code",
                        help="Events Manager test code, e.g. TESTxxxx")
    action.add_argument("--url", help="event_source_url; default a placeholder example.com URL")
    action.set_defaults(handler=functools.partial(_capi_test, ctx))

    p_user = business_sub.add_parser("user", help="business_users invite and per-asset assignment")
    user_sub = p_user.add_subparsers(dest="user_action", required=True)
    action = user_sub.add_parser("invite", help="POST /{business}/business_users")
    action.add_argument("--email", required=True)
    action.add_argument("--role", required=True, choices=("EMPLOYEE", "ADMIN"))
    action.add_argument("--confirm", required=True, help="must be literal SHARE")
    action.set_defaults(handler=functools.partial(_user_invite, ctx))
    action = user_sub.add_parser("assign", help="POST /{asset}/assigned_users")
    action.add_argument("--user-id", required=True, dest="user_id")
    action.add_argument("--asset", required=True, choices=("adaccount", "page", "pixel"))
    action.add_argument("--tasks", required=True, help="comma-separated tasks valid for the chosen asset")
    action.add_argument("--confirm", required=True, help="must be literal SHARE")
    action.set_defaults(handler=functools.partial(_user_assign, ctx))

    p_partner = business_sub.add_parser("partner", help="agency (partner BM) asset sharing")
    partner_sub = p_partner.add_subparsers(dest="partner_action", required=True)
    action = partner_sub.add_parser("share", help="POST /{asset}/agencies")
    action.add_argument("--partner-business", required=True, dest="partner_business")
    action.add_argument("--asset", required=True, choices=("adaccount", "page", "pixel"))
    action.add_argument("--tasks", required=True, help="comma-separated permitted_tasks")
    action.add_argument("--confirm", required=True, help="must be literal SHARE")
    action.set_defaults(handler=functools.partial(_partner_share, ctx))

"""Read-only verification of the asset graph declared in workspace.json."""

from __future__ import annotations

from typing import Any

import graph
from meta_workspace import Workspace

# Meta's own first-party apps. Tokens scraped from an Ads Manager session belong to these,
# and they are never owned by a customer business portfolio.
FIRST_PARTY_APP_IDS = {"119211728144504"}  # Power Editor (`02`)


def _ids(rows: list[dict[str, Any]]) -> set[str]:
    return {str(row.get("id")) for row in rows}


def _edge(
    path: str,
    fields: str = "id,name",
    max_rows: int | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    after: str | None = None
    while True:
        page_limit = min(200, max_rows - len(rows)) if max_rows is not None else 200
        params = {"fields": fields, "limit": page_limit}
        if after:
            params["after"] = after
        payload = graph.get(path, params=params, context=path)
        rows.extend(payload.get("data", []))
        if max_rows is not None and len(rows) >= max_rows:
            return rows[:max_rows]
        after = ((payload.get("paging") or {}).get("cursors") or {}).get("after")
        if not after or not (payload.get("paging") or {}).get("next"):
            return rows


def _edge_soft(path: str, fields: str = "id,name") -> list[dict[str, Any]] | None:
    """Same as _edge, but returns None instead of raising when Graph refuses the read.

    The System-User edges below describe the asset graph from the point of view of a
    System User. When the acting credential is a USER token (a scraped Ads Manager EAAB,
    `02`), those edges are not readable — `/{system_user_id}/assigned_product_catalogs`
    answers `(#10) Permission Denied` and the assigned_* edges come back empty — even
    though the very same token can read and write every asset involved. Treating that as
    a hard precondition made `assets verify` unpassable on any user-token setup
    (field-observed 2026-09-22). What actually gates a safe launch is checked separately
    and still blocks: the account is in `/me/adaccounts`, is active and funded, the
    dataset is attached to THAT account, the catalog is readable with products, and each
    product set belongs to that catalog.
    """
    try:
        return _edge(path, fields)
    except graph.GraphError:
        return None


def resolve_token_kind(business_id: str, profile: dict[str, Any]) -> str:
    """Resolve whether the acting credential is a System User or a plain user token.

    An explicit `profiles.<p>.token_kind` of `system_user`/`user` is trusted as-is — the
    operator handed the agent a specific credential and knows what it is. `auto` (the
    default, and the value of an undeclared key) inspects the token itself:

      1. `/debug_token?input_token=<same token>` — the fast path probe.py already uses
         (live 2026-09-02): `type: SYSTEM_USER` or `type: USER` answers it directly.
      2. If that is not readable with this credential, compare `/me`'s id against the
         Business Portfolio's `/system_users` listing — if the acting identity IS one of
         those System Users, it is a System User token; otherwise treat it as a user
         token (BM admin, third-party developer app, or scraped browser session, `02`).

    Never raises: an identity read failing here means the caller has bigger problems that
    the checks below will surface with a clearer message, so this defaults to `user` —
    the more conservative choice for THIS function, since it only downgrades two BM-
    ownership checks to warnings rather than removing a gate."""
    declared = str(profile.get("token_kind") or "auto")
    if declared in ("system_user", "user"):
        return declared
    try:
        data = graph.get(
            "debug_token", params={"input_token": graph.token()}, context="token kind debug_token"
        )["data"]
        ttype = str(data.get("type") or "").upper()
        if ttype == "SYSTEM_USER":
            return "system_user"
        if ttype == "USER":
            return "user"
    except graph.GraphError:
        pass
    try:
        me = graph.get("me", params={"fields": "id"}, context="token kind identity")
        me_id = str(me.get("id") or "")
    except graph.GraphError:
        return "user"
    users = _edge_soft(f"{business_id}/system_users")
    if users is not None and me_id and me_id in _ids(users):
        return "system_user"
    return "user"


def verify_assets(
    workspace: Workspace,
    requested_profile: str | None = None,
    scope: str = "all",
) -> dict[str, Any]:
    if scope not in {"core", "all"}:
        raise ValueError("asset scope must be 'core' or 'all'")
    name, profile = workspace.profile(requested_profile)
    checks: list[dict[str, Any]] = []

    def check(key: str, ok: bool, detail: str) -> None:
        checks.append({"check": key, "ok": bool(ok), "detail": detail})

    def soft_check(key: str, ok: bool, detail: str) -> None:
        """Like check(), but a failure is reported, not blocking: this token kind cannot
        prove BM ownership of the app/System User the way a System User token can, and
        that is a normal, supported setup (`02`) — not a misconfiguration."""
        checks.append({"check": key, "ok": True, "detail": detail, "warning": not ok})

    business_id = str(profile.get("business_id") or "")
    app_id = str(profile.get("app_id") or "")
    system_user_id = str(profile.get("system_user_id") or "")
    account_id = graph.normalize_account(profile["ad_account_id"])
    page_id = str(profile.get("page_id") or "")
    dataset_id = str(profile.get("dataset_id") or "")
    catalog_id = str(profile.get("catalog_id") or "")
    token_kind = resolve_token_kind(business_id, profile)

    business = graph.get(business_id, params={"fields": "id,name,verification_status"},
                         context="workspace business")
    check("business", business.get("id") == business_id,
          f"{business.get('name')} verification={business.get('verification_status')}")

    # Proof that THIS token can act on THIS account — independent of token kind. A
    # readable ad account node proves less than it looks like (00): the binding that
    # matters is the token's own /me/adaccounts membership with an ADVERTISE task.
    # The ad-account edge exposes the caller's role as `user_tasks`, not `tasks`
    # (live 2026-09-24: requesting `tasks` returns nothing and the gate fails).
    me_accounts = _edge("me/adaccounts", "id,name,user_tasks")
    me_account = next((row for row in me_accounts if str(row.get("id")) == account_id), None)
    me_tasks = set((me_account or {}).get("user_tasks") or (me_account or {}).get("tasks") or [])
    check("account_token_access", bool(me_account) and "ADVERTISE" in me_tasks,
          f"/me/adaccounts tasks={sorted(me_tasks)}" if me_account
          else f"{account_id} is not in /me/adaccounts for this token")

    if app_id:
        apps = _edge_soft(f"{business_id}/owned_apps") or []
        owned = app_id in _ids(apps)
        # A scraped Ads Manager EAAB belongs to Meta's OWN first-party app (Power Editor
        # 119211728144504, `02`). A first-party app is never owned by a customer business,
        # so requiring BM ownership makes every user-token profile unverifiable. Report it.
        first_party = app_id in FIRST_PARTY_APP_IDS
        app_ok = owned or first_party
        app_detail = (f"app {app_id} owned by business" if owned
                      else f"app {app_id} is a Meta first-party app, not BM-owned" if first_party
                      else f"app {app_id} NOT owned by business {business_id}")
        if token_kind == "system_user":
            check("app_owned", app_ok, app_detail)
        else:
            soft_check("app_owned", app_ok,
                       app_detail if app_ok else f"{app_detail} (non-blocking: token_kind={token_kind})")
    if system_user_id:
        users = _edge_soft(f"{business_id}/system_users")
        if users is None:
            check("system_user_assigned", True, "not readable with this credential (user token)")
        else:
            su_ok = system_user_id in _ids(users)
            su_detail = f"system user {system_user_id} assigned to business"
            if token_kind == "system_user":
                check("system_user_assigned", su_ok, su_detail)
            else:
                soft_check(
                    "system_user_assigned", su_ok,
                    su_detail if su_ok else
                    f"system user {system_user_id} NOT found on business {business_id} "
                    f"(non-blocking: token_kind={token_kind})",
                )
        assigned_accounts = _edge_soft(f"{system_user_id}/assigned_ad_accounts", "id,name,tasks")
        if not assigned_accounts:
            # Empty or refused: the acting credential is not this System User. The binding
            # that matters is account-to-token, and that is checked below via /me/adaccounts.
            check("account_assigned", True,
                  "System User assignment not visible to this credential; "
                  "account access is verified directly instead")
        else:
            check("account_assigned", account_id in _ids(assigned_accounts),
                  f"{account_id} assigned to system user")

    account = graph.get(
        account_id,
        params={"fields": "id,name,account_status,disable_reason,currency,timezone_name,"
                          "funding_source_details,business{id,name}"},
        context="workspace ad account",
    )
    account_business = str((account.get("business") or {}).get("id") or "")
    check("account_active", account.get("account_status") == 1,
          f"{account.get('name')} status={account.get('account_status')} "
          f"disable_reason={account.get('disable_reason')}")
    is_assigned = account_id in _ids(assigned_accounts or []) if system_user_id else False
    # An agency-assigned account reports no `business` at all. That is a normal supported
    # setup (agency accounts, `03`), not a misconfiguration, and the token's own access to
    # the account is proven by `/me/adaccounts` plus the live read above.
    agency_assigned = not account_business
    check("account_owned", account_business == business_id or is_assigned or agency_assigned,
          f"account business={account_business or 'agency_assigned'}")
    check("funding", bool(account.get("funding_source_details")), "funding source is set")
    expected_currency = profile.get("currency")
    check("currency", not expected_currency or account.get("currency") == expected_currency,
          f"live={account.get('currency')} expected={expected_currency}")
    expected_timezone = profile.get("timezone")
    check("timezone", not expected_timezone or account.get("timezone_name") == expected_timezone,
          f"live={account.get('timezone_name')} expected={expected_timezone}")

    if page_id:
        assigned_pages = _edge_soft(f"{system_user_id}/assigned_pages", "id,name,tasks")
        if not assigned_pages:
            # Not visible to a user token. Page access is proven instead by successfully
            # minting a Page access token immediately below, which fails loudly if the
            # acting credential has no role on the Page.
            check("page_assigned", True,
                  "System User page assignment not visible to this credential; "
                  "Page access is proven by minting a Page token")
        else:
            check("page_assigned", page_id in _ids(assigned_pages),
                  f"page {page_id} assigned to system user")
        page_access_token = graph.page_token(page_id)
        # The `page_backed_instagram_accounts` EDGE was dropped from the Page schema some time
        # after 2025-04 (its reference page is a 404 and the edge is absent from the live Page
        # node schema); Meta published no changelog entry and the older prose guide still tells
        # you to call it. Calling it now returns (#100) "Tried accessing nonexisting field" on
        # every version tested (v23.0 and v26.0), which made this check fail even on Pages that
        # DO have a PBIA. The schema replacement is a to-one FIELD,
        # `connected_page_backed_instagram_account`, alongside `instagram_business_account` and
        # `connected_instagram_account` — any one of the three makes the Page Instagram-ready.
        # Verified live 2026-09-22 on a Page whose PBIA the old edge could not see.
        ig = graph.get(
            page_id,
            params={"fields": "instagram_business_account,connected_instagram_account,"
                              "connected_page_backed_instagram_account"},
            token_override=page_access_token,
            context="workspace page instagram",
        )
        ig_keys = [k for k in ("instagram_business_account", "connected_instagram_account",
                               "connected_page_backed_instagram_account") if ig.get(k)]
        # Blocking: Instagram placements are mandatory (operator rule 2026-09-26).
        check("page_instagram", bool(ig_keys),
              ", ".join(ig_keys) if ig_keys else
              "no Instagram identity; create it in the UI (Ads Manager > ad draft > Identity > Instagram account > Use Facebook Page, then discard the draft, 18)")

    if dataset_id:
        pixels = _edge(f"{account_id}/adspixels")
        check("dataset_attached", dataset_id in _ids(pixels),
              f"dataset {dataset_id} attached to {account_id}")
        dataset = graph.get(dataset_id, params={"fields": "id,name"}, context="workspace dataset")
        check("dataset_read", dataset.get("id") == dataset_id, str(dataset.get("name")))

    product_sets: list[dict[str, Any]] = []
    if scope == "all" and catalog_id:
        if system_user_id:
            catalogs = _edge_soft(f"{system_user_id}/assigned_product_catalogs")
            if catalogs is None:
                check("catalog_assigned", True,
                      "System User catalog assignment not readable with this credential; "
                      "catalog readability is verified directly below")
            else:
                check("catalog_assigned", catalog_id in _ids(catalogs),
                      f"catalog {catalog_id} assigned to system user")
        catalog = graph.get(
            catalog_id,
            params={"fields": "id,name,vertical,product_count,business{id,name}"},
            context="workspace catalog",
        )
        catalog_business = str((catalog.get("business") or {}).get("id") or "")
        # A catalog shared ACROSS business portfolios is a normal setup: one BM holds the
        # catalog while ad accounts in other BMs run against it. Report the owner rather
        # than failing, since the launch-blocking facts are that the catalog reads, has
        # products, and that every declared product set belongs to it - all checked here.
        check("catalog_owned", bool(catalog_business),
              f"catalog business={catalog_business}"
              + ("" if catalog_business == business_id
                 else f" (CROSS-BM: profile business is {business_id})"))
        check("catalog_products", int(catalog.get("product_count") or 0) > 0,
              f"catalog product_count={catalog.get('product_count')}")
        for alias, set_id in (profile.get("product_sets") or {}).items():
            product_set = graph.get(
                str(set_id),
                params={"fields": "id,name,product_count,filter,product_catalog{id,name}"},
                context=f"workspace product set {alias}",
            )
            set_catalog = str((product_set.get("product_catalog") or {}).get("id") or "")
            count = int(product_set.get("product_count") or 0)
            ok = set_catalog == catalog_id and count > 0
            product_sets.append({
                "alias": alias,
                "id": str(set_id),
                "name": product_set.get("name"),
                "catalog_id": set_catalog,
                "product_count": count,
                "ready": ok,
            })
            check(f"product_set:{alias}", ok,
                  f"catalog={set_catalog} product_count={count}")

    failed = [row for row in checks if not row["ok"]]
    return {
        "workspace": str(workspace.path),
        "profile": name,
        "scope": scope,
        "account_id": account_id,
        "token_kind": token_kind,
        "checks": checks,
        "product_sets": product_sets,
        "ready": not failed,
        "failed_checks": [row["check"] for row in failed],
    }


def list_catalog_products(
    workspace: Workspace,
    requested_profile: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    name, profile = workspace.profile(requested_profile)
    catalog_id = str(profile.get("catalog_id") or "")
    if not catalog_id:
        raise ValueError(f"profile {name} has no catalog_id")
    rows = _edge(f"{catalog_id}/products", "id,retailer_id,name", max_rows=limit)
    return {
        "workspace": str(workspace.path),
        "profile": name,
        "catalog_id": catalog_id,
        "count": len(rows),
        "products": rows,
    }


def verify_product_set_binding(
    workspace: Workspace,
    requested_profile: str | None,
    alias: str,
) -> dict[str, Any]:
    """Verify catalog/set ownership for repair without requiring the set to be non-empty."""
    name, profile = workspace.profile(requested_profile)
    catalog_id = str(profile.get("catalog_id") or "")
    set_id = str((profile.get("product_sets") or {}).get(alias) or "")
    if not catalog_id or not set_id:
        raise ValueError(f"profile {name} has no declared product set {alias!r}")
    assigned = _edge(f"{profile['system_user_id']}/assigned_product_catalogs")
    catalog = graph.get(
        catalog_id,
        params={"fields": "id,business{id}"},
        context="repair catalog ownership",
    )
    product_set = graph.get(
        set_id,
        params={"fields": "id,product_catalog{id}"},
        context="repair product-set ownership",
    )
    actual_catalog = str((product_set.get("product_catalog") or {}).get("id") or "")
    actual_business = str((catalog.get("business") or {}).get("id") or "")
    checks = {
        "catalog_assigned": catalog_id in _ids(assigned),
        "catalog_owned": actual_business == str(profile["business_id"]),
        "product_set_catalog": actual_catalog == catalog_id,
    }
    return {
        "profile": name,
        "catalog_id": catalog_id,
        "product_set_id": set_id,
        "checks": checks,
        "ready": all(checks.values()),
    }

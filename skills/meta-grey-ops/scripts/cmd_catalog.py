"""Catalog lifecycle commands for `metaops`: create/list catalogs and product feeds,
product sets, and batch product upsert/delete — so an agent never writes raw Graph
payloads for Commerce Manager objects.

This module is imported and wired by metaops.py (not self-executable). Every write goes
through ctx.graph.post inside the already-authorized metaops process; ctx.graph enforces
write authority per workspace-bound ad account (graph.py require_write_authority) — catalog
writes are keyed by business_id/catalog_id, which are not account-scoped, so this module
additionally requires the workspace profile to declare the target catalog/business before
any create, and requires literal --confirm CREATE on every object-creating call.

Verified facts (SDK introspection, facebook_business 26.0.1, 2026-09-03):
- Business.create_owned_product_catalog: POST /{business_id}/owned_product_catalogs,
  params {name: string, vertical: vertical_enum} (plus optional fields unused here).
- ProductCatalog.create_product_feed: POST /{catalog_id}/product_feeds, params include
  name (string), schedule (string == JSON-encoded object), update_schedule (string, same
  shape), default_currency (string), deletion_enabled (bool), file_name (string).
  `schedule`/`update_schedule` are typed as opaque strings by the SDK's param checker,
  i.e. Graph expects the same JSON-encode-once convention as product_set `filter`
  (graph.py._encode already encodes a dict exactly once — do not pre-stringify it).
- ProductFeedSchedule fields (facebook_business/adobjects/productfeedschedule.py):
  interval (Interval enum: HOURLY/DAILY/WEEKLY/MONTHLY), interval_count, hour, minute,
  day_of_week, day_of_month, timezone, url, username. No documented password field in
  this SDK version — feed URL must be fetchable without auth (17).
- ProductCatalog.create_product_set: POST /{catalog_id}/product_sets, params {name,
  filter: Object, retailer_id: string (singular — a different, unrelated single-retailer
  binding, not the --retailer-ids list path), metadata, ordering_info, publish_to_shops}.
  This module always sends `filter` (a dict, encoded once), matching mutate_set.py.
- ProductCatalog.create_items_batch: POST /{catalog_id}/items_batch, top-level params
  {item_type: string (must be "PRODUCT_ITEM" per 04; omitting -> code 100), requests: map
  (JSON-encoded list of {method, data} objects), allow_upsert: bool, item_sub_type,
  version}. item_type is a top-level batch param, not per-request.
- ProductCatalog.get_check_batch_request_status: GET /{catalog_id}/check_batch_request_status
  params {handle: string, error_priority, load_ids_of_invalid_requests}. Response fields
  (CheckBatchRequestStatus): handle, status, errors, errors_total_count, warnings,
  warnings_total_count, ids_of_invalid_requests. UNVERIFIED: the exact `status` string
  values (SDK does not enumerate them) — this module polls case-insensitively and treats
  anything containing "progress"/"pending"/"queued" as still running.
- ProductItem.create (ProductCatalog.create_product, the direct /products edge): `price`
  and `sale_price` are typed `unsigned int` (minor units), confirming 04's "Catalog
  product create: price = integer minor units". This is DIFFERENT from the feed/
  items_batch format documented in 17, where `price` is the string "9.99 USD" — items_batch
  requests carry feed-format rows, not /products-edge fields. Do not mix the two shapes;
  this module's `products batch` sends whatever the input file contains verbatim and only
  documents the distinction (it does not convert one price shape to the other).
- Catalog "ad account can use it" check: no Graph edge directly answers this for a
  System-User-owned workspace. This module reuses the same evidence asset_graph.py's
  scope=all check already gathers: the catalog is assigned to the workspace System User
  (`/{system_user_id}/assigned_product_catalogs`) and the catalog's `business` matches the
  workspace business_id — the same two facts verify_assets uses to gate a catalog launch.
  UNVERIFIED beyond that: whether a catalog can be usable via `/{catalog_id}/agencies`
  cross-BM sharing without a System User assignment; that path is not exercised here.
"""

from __future__ import annotations

import argparse
import json
import time
from typing import Any

INTERVAL_MAP = {"hourly": "HOURLY", "daily": "DAILY", "weekly": "WEEKLY"}
BATCH_METHODS = {"UPDATE", "DELETE", "CREATE"}
TERMINAL_STOPWORDS = ("started", "progress", "pending", "queued", "processing")  # in-progress words
CATALOG_FIELDS = "id,name,vertical,product_count,business{id,name}"
FEED_FIELDS = "id,name,schedule,update_schedule,file_name,default_currency,deletion_enabled"
SET_FIELDS = "id,name,product_count,filter,product_catalog{id,name}"
BATCH_STATUS_FIELDS = (
    "handle,status,errors_total_count,warnings_total_count,errors,warnings,ids_of_invalid_requests"
)


def _profile(ctx: Any, args: argparse.Namespace) -> tuple[str, dict[str, Any]]:
    if not args.workspace_obj:
        raise ctx.MetaOpsError("catalog commands require --workspace")
    return args.workspace_obj.profile(args.profile)


def _catalog_id(profile: dict[str, Any], ctx: Any) -> str:
    catalog_id = str(profile.get("catalog_id") or "")
    if not catalog_id:
        raise ctx.MetaOpsError(
            "no catalog id: set profiles.<p>.catalog_id in workspace.json (see catalog create)"
        )
    return catalog_id


def _require_confirm(ctx: Any, args: argparse.Namespace) -> None:
    if args.confirm != "CREATE":
        raise ctx.MetaOpsError("this create requires the literal --confirm CREATE")


def _paginate(ctx: Any, path: str, fields: str, limit: int | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    after: str | None = None
    while True:
        page_limit = min(200, limit - len(rows)) if limit is not None else 200
        if limit is not None and page_limit <= 0:
            break
        params: dict[str, Any] = {"fields": fields, "limit": page_limit}
        if after:
            params["after"] = after
        payload = ctx.graph.get(path, params=params, context=path)
        rows.extend(payload.get("data", []))
        if limit is not None and len(rows) >= limit:
            return rows[:limit]
        after = ((payload.get("paging") or {}).get("cursors") or {}).get("after")
        if not after or not (payload.get("paging") or {}).get("next"):
            return rows


# --------------------------------------------------------------------------- catalog


def _find_by_name(rows: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    """Name-dedup: a retry after a transport break (outcome_unknown) must find the
    object the first POST may have created instead of posting a duplicate."""
    for row in rows:
        if str(row.get("name") or "") == name:
            return row
    return None


def command_catalog_create(args: argparse.Namespace, ctx: Any) -> tuple[int, dict[str, Any]]:
    profile_name, profile = _profile(ctx, args)
    _require_confirm(ctx, args)
    provisioning = ctx.require_provisioning_admin(args.workspace_obj, profile_name)
    business_id = str(profile.get("business_id") or "")
    if not business_id:
        raise ctx.MetaOpsError(f"profile {profile_name} has no business_id")
    # Dedup by name BEFORE posting: a second run after an outcome_unknown break
    # reuses the existing catalog instead of creating a twin asset.
    hit = _find_by_name(
        _paginate(ctx, f"{business_id}/owned_product_catalogs", CATALOG_FIELDS), str(args.name)
    )
    if hit is not None:
        catalog_id = str(hit.get("id"))
        return 0, ctx.result_envelope(
            "catalog create", True, "exists",
            data={"profile": profile_name, "business_id": business_id, "catalog_id": catalog_id,
                  "name": args.name, "vertical": args.vertical, "provisioning": provisioning,
                  "deduped": True},
            next_action=(
                f"Put \"catalog_id\": \"{catalog_id}\" into profiles.{profile_name} in workspace.json, "
                "then run assets verify --scope all."
            ),
        )
    data = {"name": args.name, "vertical": args.vertical}
    try:
        resp = ctx.graph.post(f"{business_id}/owned_product_catalogs", data, context="catalog create")
    except Exception as exc:  # noqa: BLE001 - reconcile outcome_unknown by name, else re-raise
        unknown = bool(getattr(exc, "outcome_unknown", False))
        if unknown:
            hit = _find_by_name(
                _paginate(ctx, f"{business_id}/owned_product_catalogs", CATALOG_FIELDS),
                str(args.name),
            )
            if hit is not None:
                catalog_id = str(hit.get("id"))
                return 0, ctx.result_envelope(
                    "catalog create", True, "reconciled",
                    data={"profile": profile_name, "business_id": business_id,
                          "catalog_id": catalog_id, "deduped": True},
                    next_action="The create may have applied before the break; reusing the found object.",
                )
        raise
    catalog_id = str(resp["id"])
    return 0, ctx.result_envelope(
        "catalog create", True, "created",
        data={"profile": profile_name, "business_id": business_id, "catalog_id": catalog_id,
              "name": args.name, "vertical": args.vertical, "provisioning": provisioning},
        next_action=(
            f"Put \"catalog_id\": \"{catalog_id}\" into profiles.{profile_name} in workspace.json, "
            "then run assets verify --scope all."
        ),
    )


def command_catalog_list(args: argparse.Namespace, ctx: Any) -> tuple[int, dict[str, Any]]:
    profile_name, profile = _profile(ctx, args)
    business_id = str(profile.get("business_id") or "")
    if not business_id:
        raise ctx.MetaOpsError(f"profile {profile_name} has no business_id")
    rows = _paginate(ctx, f"{business_id}/owned_product_catalogs", CATALOG_FIELDS)
    return 0, ctx.result_envelope(
        "catalog list", True, "listed",
        data={"profile": profile_name, "business_id": business_id, "count": len(rows), "catalogs": rows},
        next_action="Put a catalog id into profiles.<p>.catalog_id, then run catalog access.",
    )


def command_catalog_access(args: argparse.Namespace, ctx: Any) -> tuple[int, dict[str, Any]]:
    profile_name, profile = _profile(ctx, args)
    catalog_id = _catalog_id(profile, ctx)
    business_id = str(profile.get("business_id") or "")
    system_user_id = str(profile.get("system_user_id") or "")
    checks: dict[str, bool] = {}
    detail: dict[str, Any] = {}
    catalog = ctx.graph.get(catalog_id, params={"fields": CATALOG_FIELDS}, context="catalog access")
    catalog_business = str((catalog.get("business") or {}).get("id") or "")
    checks["catalog_owned_by_business"] = catalog_business == business_id
    detail["catalog_business_id"] = catalog_business
    if system_user_id:
        assigned = _paginate(ctx, f"{system_user_id}/assigned_product_catalogs", "id,name")
        assigned_ids = {str(row.get("id")) for row in assigned}
        checks["catalog_assigned_to_system_user"] = catalog_id in assigned_ids
    ready = all(checks.values())
    return (0 if ready else 1), ctx.result_envelope(
        "catalog access", ready, "usable" if ready else "not_usable",
        data={"profile": profile_name, "catalog_id": catalog_id, "checks": checks,
              "product_count": catalog.get("product_count"), **detail},
        error=None if ready else {"kind": "asset_gate", "message": f"failed checks: {sorted(k for k, v in checks.items() if not v)}"},
        next_action=("Run assets verify --scope all before a catalog launch." if ready else
                     "Assign the catalog to the workspace System User / Business Manager, then retry."),
    )


# --------------------------------------------------------------------------- feed


def command_catalog_feed_create(args: argparse.Namespace, ctx: Any) -> tuple[int, dict[str, Any]]:
    profile_name, profile = _profile(ctx, args)
    _require_confirm(ctx, args)
    catalog_id = _catalog_id(profile, ctx)
    interval = INTERVAL_MAP[args.schedule]
    schedule: dict[str, Any] = {"url": args.url, "interval": interval}
    if args.hour is not None:
        schedule["hour"] = args.hour
    # Twin feeds poll the same URL on the same schedule: dedup by name so a retry
    # after outcome_unknown reuses the feed instead of scheduling a second fetch.
    hit = _find_by_name(
        _paginate(ctx, f"{catalog_id}/product_feeds", FEED_FIELDS), str(args.name)
    )
    if hit is not None:
        feed_id = str(hit.get("id"))
        return 0, ctx.result_envelope(
            "catalog feed create", True, "exists",
            data={"profile": profile_name, "catalog_id": catalog_id, "feed_id": feed_id,
                  "schedule": schedule, "deduped": True},
            next_action=(
                f"Put \"feed_id\": \"{feed_id}\" into profiles.{profile_name} in workspace.json, "
                "then metaops feed sync to force an immediate fetch instead of waiting for the schedule."
            ),
        )
    data: dict[str, Any] = {"name": args.name, "schedule": schedule}
    if args.update_only:
        data["deletion_enabled"] = False
    try:
        resp = ctx.graph.post(f"{catalog_id}/product_feeds", data, context="catalog feed create")
    except Exception as exc:  # noqa: BLE001 - reconcile outcome_unknown by name
        if bool(getattr(exc, "outcome_unknown", False)):
            hit = _find_by_name(
                _paginate(ctx, f"{catalog_id}/product_feeds", FEED_FIELDS), str(args.name)
            )
            if hit is not None:
                return 0, ctx.result_envelope(
                    "catalog feed create", True, "reconciled",
                    data={"profile": profile_name, "catalog_id": catalog_id,
                          "feed_id": str(hit.get("id")), "deduped": True},
                    next_action="The create may have applied before the break; reusing the found feed.",
                )
        raise
    feed_id = str(resp["id"])
    return 0, ctx.result_envelope(
        "catalog feed create", True, "created",
        data={"profile": profile_name, "catalog_id": catalog_id, "feed_id": feed_id,
              "schedule": schedule, "deletion_enabled": not args.update_only},
        next_action=(
            f"Put \"feed_id\": \"{feed_id}\" into profiles.{profile_name} in workspace.json, "
            "then metaops feed sync to force an immediate fetch instead of waiting for the schedule."
        ),
    )


def command_catalog_feed_list(args: argparse.Namespace, ctx: Any) -> tuple[int, dict[str, Any]]:
    profile_name, profile = _profile(ctx, args)
    catalog_id = _catalog_id(profile, ctx)
    rows = _paginate(ctx, f"{catalog_id}/product_feeds", FEED_FIELDS)
    return 0, ctx.result_envelope(
        "catalog feed list", True, "listed",
        data={"profile": profile_name, "catalog_id": catalog_id, "count": len(rows), "feeds": rows},
        next_action="Use catalog feed uploads --feed-id to see recent fetch results.",
    )


def command_catalog_feed_uploads(args: argparse.Namespace, ctx: Any) -> tuple[int, dict[str, Any]]:
    profile_name, _profile_data, feed_id = ctx.feed_binding(args)
    import feed_upload
    rows = _paginate(ctx, f"{feed_id}/uploads", feed_upload.UPLOAD_FIELDS, limit=args.limit)
    return 0, ctx.result_envelope(
        "catalog feed uploads", True, "listed",
        data={"profile": profile_name, "feed_id": feed_id, "count": len(rows), "uploads": rows},
        next_action="metaops feed sync forces an immediate fetch instead of waiting for the next one.",
    )


# --------------------------------------------------------------------------- set


def command_catalog_set_create(args: argparse.Namespace, ctx: Any) -> tuple[int, dict[str, Any]]:
    profile_name, profile = _profile(ctx, args)
    _require_confirm(ctx, args)
    catalog_id = _catalog_id(profile, ctx)
    if bool(args.filter) == bool(args.retailer_ids):
        raise ctx.MetaOpsError("pass exactly one of --filter or --retailer-ids")
    if args.filter:
        filter_path = ctx.resolve_input(args.filter)
        with filter_path.open(encoding="utf-8") as fh:
            new_filter = json.load(fh)
        if not isinstance(new_filter, dict):
            raise ctx.MetaOpsError("--filter must contain a JSON object, not a string or array")
    else:
        ids = [value.strip() for value in args.retailer_ids.split(",") if value.strip()]
        if not ids:
            raise ctx.MetaOpsError("--retailer-ids must contain at least one retailer id")
        new_filter = {"retailer_id": {"is_any": ids}}
    # filter is a dict here; graph.py's _encode() JSON-encodes it exactly once on the
    # wire (double-encoding it ourselves would silently no-op the create's filter — 04).
    # Twin sets with the same name would split the catalog audience: dedup by name.
    hit = _find_by_name(
        _paginate(ctx, f"{catalog_id}/product_sets", SET_FIELDS), str(args.name)
    )
    if hit is not None:
        set_id = str(hit.get("id"))
        return 0, ctx.result_envelope(
            "catalog set create", True, "exists",
            data={"profile": profile_name, "catalog_id": catalog_id, "set_id": set_id,
                  "filter": new_filter, "deduped": True},
            next_action=(
                f"Put \"<alias>\": \"{set_id}\" into profiles.{profile_name}.product_sets, "
                "then assets verify --scope all."
            ),
        )
    data = {"name": args.name, "filter": new_filter}
    try:
        resp = ctx.graph.post(f"{catalog_id}/product_sets", data, context="catalog set create")
    except Exception as exc:  # noqa: BLE001 - reconcile outcome_unknown by name
        if bool(getattr(exc, "outcome_unknown", False)):
            hit = _find_by_name(
                _paginate(ctx, f"{catalog_id}/product_sets", SET_FIELDS), str(args.name)
            )
            if hit is not None:
                return 0, ctx.result_envelope(
                    "catalog set create", True, "reconciled",
                    data={"profile": profile_name, "catalog_id": catalog_id,
                          "set_id": str(hit.get("id")), "deduped": True},
                    next_action="The create may have applied before the break; reusing the found set.",
                )
        raise
    set_id = str(resp["id"])
    return 0, ctx.result_envelope(
        "catalog set create", True, "created",
        data={"profile": profile_name, "catalog_id": catalog_id, "set_id": set_id, "filter": new_filter},
        next_action=(
            f"Put \"<alias>\": \"{set_id}\" into profiles.{profile_name}.product_sets, "
            "then assets verify --scope all."
        ),
    )


def command_catalog_set_list(args: argparse.Namespace, ctx: Any) -> tuple[int, dict[str, Any]]:
    profile_name, profile = _profile(ctx, args)
    catalog_id = _catalog_id(profile, ctx)
    rows = _paginate(ctx, f"{catalog_id}/product_sets", SET_FIELDS)
    return 0, ctx.result_envelope(
        "catalog set list", True, "listed",
        data={"profile": profile_name, "catalog_id": catalog_id, "count": len(rows), "product_sets": rows},
        next_action="Use assets set-products to repair a declared set's filter.",
    )


# --------------------------------------------------------------------------- products


def command_catalog_products_list(args: argparse.Namespace, ctx: Any) -> tuple[int, dict[str, Any]]:
    profile_name, profile = _profile(ctx, args)
    catalog_id = _catalog_id(profile, ctx)
    path = f"{args.set_id}/products" if args.set_id else f"{catalog_id}/products"
    rows = _paginate(ctx, path, "id,retailer_id,name,availability,price", limit=args.limit)
    return 0, ctx.result_envelope(
        "catalog products list", True, "listed",
        data={"profile": profile_name, "catalog_id": catalog_id, "set_id": args.set_id,
              "count": len(rows), "products": rows},
        next_action="Use catalog products batch to upsert/delete items.",
    )


def _load_batch_items(path: str, ctx: Any) -> list[dict[str, Any]]:
    source_path = ctx.resolve_input(path)
    try:
        with source_path.open(encoding="utf-8") as fh:
            items = json.load(fh)
    except FileNotFoundError as exc:
        raise ctx.MetaOpsError(f"{source_path}: does not exist") from exc
    except json.JSONDecodeError as exc:
        raise ctx.MetaOpsError(f"{source_path}: not valid JSON: {exc}") from exc
    if not isinstance(items, list) or not items:
        raise ctx.MetaOpsError(f"{source_path}: must be a non-empty JSON array of item objects")
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ctx.MetaOpsError(f"{source_path}[{index}]: each item must be a JSON object")
        # Live 2026-09-03: items_batch rejects a request whose data lacks `id` ("Can not find
        # required field id") and returns no handle. `id` is the feed-format retailer id.
        if not item.get("id"):
            if item.get("retailer_id"):
                item["id"] = str(item.pop("retailer_id"))
            else:
                raise ctx.MetaOpsError(f"{source_path}[{index}]: item needs `id` (retailer id)")
    return items


def _batch_finished(status: str | None) -> bool:
    """Live 2026-09-03: a fresh handle reports status "started"; treat it and the usual
    in-progress words as not finished. Unknown/empty status counts as finished only after the
    deadline (caller)."""
    if not status:
        return False
    text = str(status).lower()
    return not any(word in text for word in TERMINAL_STOPWORDS)


def _batch_status_item(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalise the edge's Graph envelope, while tolerating a direct-object mock."""
    data = payload.get("data")
    if isinstance(data, list):
        return data[0] if data and isinstance(data[0], dict) else {}
    return payload


def command_catalog_products_batch(args: argparse.Namespace, ctx: Any) -> tuple[int, dict[str, Any]]:
    # Duplicate-safety (documented, no in-flight needed): items_batch is keyed by
    # item `id` (retailer id). Re-posting the same file with UPDATE+allow_upsert
    # rewrites the same rows, DELETE re-deletes them, CREATE with the same ids
    # collides on the same keys — no money moves, no twin objects. A retry after
    # outcome_unknown therefore reuses the same handle semantics: poll the returned
    # handle; if the POST itself broke unknown, re-post the identical payload and
    # the catalog converges to the same state.
    profile_name, profile = _profile(ctx, args)
    catalog_id = _catalog_id(profile, ctx)
    if args.confirm != "BATCH":
        raise ctx.MetaOpsError("catalog products batch changes catalog data: pass the literal --confirm BATCH")
    if args.method not in BATCH_METHODS:
        raise ctx.MetaOpsError(f"--method must be one of {sorted(BATCH_METHODS)}")
    items = _load_batch_items(args.file, ctx)
    # Same gate as assets swap / feed swap: an edited item shows on every set that holds it (and may
    # join rule-based sets). Hold only while an ad on such a set is in review; never wait for delivery.
    import swapgate
    gate = swapgate.item_gate(profile["ad_account_id"], [str(i["id"]) for i in items],
                              paused_ok=getattr(args, "paused_ok", False))
    if gate["verdict"] != "ready" and not getattr(args, "force", False):
        raise ctx.MetaOpsError(
            f"catalog products batch: swap gate {gate['verdict']}: {(gate['waiting'] + gate['blockers'])[:5]}. "
            "Wait for approval of the ads on those sets (then run at once), or --force."
        )
    requests = [{"method": args.method, "data": item} for item in items]
    data: dict[str, Any] = {
        "item_type": "PRODUCT_ITEM",
        "requests": requests,
    }
    if args.method == "UPDATE":
        data["allow_upsert"] = True
    resp = ctx.graph.post(f"{catalog_id}/items_batch", data, context="catalog products batch")
    handles = resp.get("handles") or ([resp["handle"]] if resp.get("handle") else [])
    if not handles:
        raise ctx.MetaOpsError(f"items_batch response carried no handle: {resp}")
    handle = str(handles[0])
    deadline = time.monotonic() + args.wait
    status_payload: dict[str, Any] = {}
    status_item: dict[str, Any] = {}
    while True:
        status_payload = ctx.graph.get(
            f"{catalog_id}/check_batch_request_status",
            params={"handle": handle, "fields": BATCH_STATUS_FIELDS},
            context="catalog products batch status",
        )
        status_item = _batch_status_item(status_payload)
        if _batch_finished(status_item.get("status")) or time.monotonic() >= deadline:
            break
        time.sleep(5)
    finished = _batch_finished(status_item.get("status"))
    errors_total = int(status_item.get("errors_total_count") or 0)
    ok = finished and errors_total == 0
    return (0 if ok else 1), ctx.result_envelope(
        "catalog products batch", ok, "finished" if finished else "still_running",
        data={
            "profile": profile_name, "catalog_id": catalog_id, "method": args.method,
            "items": len(items), "handle": handle, "finished": finished,
            "status": status_item.get("status"),
            "errors_total_count": errors_total,
            "errors": status_item.get("errors"),
            "warnings_total_count": status_item.get("warnings_total_count"),
            "ids_of_invalid_requests": status_item.get("ids_of_invalid_requests"),
        },
        error=None if ok else {
            "kind": "batch_incomplete" if not finished else "batch_errors",
            "message": (f"still running after {args.wait}s; re-check with the same handle"
                        if not finished else f"{errors_total} item error(s); see data.errors"),
        },
        next_action=(
            "Re-run catalog products batch status check (same handle) later." if not finished
            else ("catalog products list to confirm the change landed." if ok
                  else "Fix the reported per-item errors, then resubmit only the failed items.")
        ),
    )


def register(sub: Any, ctx: Any) -> None:
    p = sub.add_parser("catalog", help="catalog/feed/product-set/product lifecycle (no raw Graph)")
    catalog_sub = p.add_subparsers(dest="catalog_action", required=True)

    action = catalog_sub.add_parser("create", help="create an owned product catalog for the BM")
    action.add_argument("--name", required=True)
    action.add_argument("--vertical", default="commerce")
    action.add_argument("--confirm", required=True, help="must be literal CREATE")
    action.set_defaults(handler=lambda a: command_catalog_create(a, ctx))

    action = catalog_sub.add_parser("list", help="list owned catalogs of the workspace business")
    action.set_defaults(handler=lambda a: command_catalog_list(a, ctx))

    action = catalog_sub.add_parser("access", help="check the profile's catalog is usable")
    action.set_defaults(handler=lambda a: command_catalog_access(a, ctx))

    feed_p = catalog_sub.add_parser("feed", help="scheduled product feed lifecycle")
    feed_sub = feed_p.add_subparsers(dest="catalog_feed_action", required=True)

    action = feed_sub.add_parser("create", help="create a scheduled product feed")
    action.add_argument("--name", required=True)
    action.add_argument("--url", required=True, help="public CSV/Sheets-export URL Meta will poll")
    action.add_argument("--schedule", required=True, choices=sorted(INTERVAL_MAP))
    action.add_argument("--hour", type=int, help="UTC hour 0-23 for daily/weekly fetch")
    action.add_argument("--update-only", action="store_true",
                        help="never delete items missing from a fetch (deletion_enabled=False)")
    action.add_argument("--confirm", required=True, help="must be literal CREATE")
    action.set_defaults(handler=lambda a: command_catalog_feed_create(a, ctx))

    action = feed_sub.add_parser("list", help="list product feeds on the profile's catalog")
    action.set_defaults(handler=lambda a: command_catalog_feed_list(a, ctx))

    action = feed_sub.add_parser("uploads", help="recent fetches for one feed")
    action.add_argument("--feed-id", help="default profiles.<p>.feed_id")
    action.add_argument("--limit", type=int, default=25)
    action.set_defaults(handler=lambda a: command_catalog_feed_uploads(a, ctx))

    set_p = catalog_sub.add_parser("set", help="product set lifecycle")
    set_sub = set_p.add_subparsers(dest="catalog_set_action", required=True)

    action = set_sub.add_parser("create", help="create a filter-based product set")
    action.add_argument("--name", required=True)
    action.add_argument("--filter", help="path to a JSON file holding the filter object")
    action.add_argument("--retailer-ids", help="comma-separated retailer_id values")
    action.add_argument("--confirm", required=True, help="must be literal CREATE")
    action.set_defaults(handler=lambda a: command_catalog_set_create(a, ctx))

    action = set_sub.add_parser("list", help="list product sets on the profile's catalog")
    action.set_defaults(handler=lambda a: command_catalog_set_list(a, ctx))

    products_p = catalog_sub.add_parser("products", help="product listing and batch upsert/delete")
    products_sub = products_p.add_subparsers(dest="catalog_products_action", required=True)

    action = products_sub.add_parser("list", help="list catalog (or one set's) products")
    action.add_argument("--limit", type=int, default=100)
    action.add_argument("--set-id", help="list one product set's members instead of the whole catalog")
    action.set_defaults(handler=lambda a: command_catalog_products_list(a, ctx))

    action = products_sub.add_parser("batch", help="items_batch upsert/delete with status polling")
    action.add_argument("--file", required=True, help="JSON array of item objects")
    action.add_argument("--method", required=True, choices=sorted(BATCH_METHODS))
    action.add_argument("--wait", type=int, default=120, help="seconds to poll check_batch_request_status")
    action.add_argument("--force", action="store_true",
                        help="skip the review gate (ads on sets holding these items may be in review)")
    action.add_argument("--paused-ok", action="store_true", help="treat paused ads on affected sets as approved")
    action.add_argument("--confirm", required=True, help="must be literal BATCH")
    action.set_defaults(handler=lambda a: command_catalog_products_batch(a, ctx))

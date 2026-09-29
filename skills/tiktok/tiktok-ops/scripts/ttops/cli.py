"""ttops — agent-facing command surface for TikTok Ads.

One stable command set, one JSON result envelope. stdout carries exactly one
``ttops.result/v1`` object when --json is set; diagnostics go to stderr.

Never pass a token on the command line: it lands in shell history and process
listings. Set TIKTOK_ACCESS_TOKEN in the environment.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback

from . import errors as err_mod
from . import lifecycle, mcp as mcp_mod, operate, spec as spec_mod
from .api import Client, TikTokError, TransportError
from .workspace import Workspace, WorkspaceError

RESULT_SCHEMA = "ttops.result/v1"


def _emit(payload, as_json, exit_code=0):
    if as_json:
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n")
    else:
        _human(payload)
    sys.stdout.flush()
    return exit_code


def _human(payload):
    data = payload.get("data") or {}
    if not payload.get("ok"):
        error = payload.get("error") or {}
        print(f"FAILED: {payload.get('command')}", file=sys.stdout)
        for line in error.get("lines") or [error.get("message", "")]:
            if line:
                print("  " + line)
        if error.get("action"):
            print("  action: " + error["action"])
        for finding in (data.get("findings") or []):
            print(f"  [{finding.get('severity')}] {finding.get('object')}"
                  f".{finding.get('field')}: {finding.get('detail')}")
            if "expected" in finding or "on_platform" in finding:
                print(f"      expected={finding.get('expected')!r} "
                      f"on_platform={finding.get('on_platform')!r}")
        if data.get("verdict"):
            print("  " + data["verdict"])
        return
    print(f"OK: {payload.get('command')}")
    for key, value in data.items():
        if isinstance(value, list) and value and isinstance(value[0], str):
            print(f"  {key}:")
            for item in value:
                print(f"    {item}")
        elif isinstance(value, (dict, list)):
            print(f"  {key}: {json.dumps(value, default=str)[:2000]}")
        else:
            print(f"  {key}: {value}")


def _load_json(path):
    with open(path) as fh:
        return json.load(fh)


def _client(args, *, allow_writes):
    return Client(allow_writes=allow_writes, dry_run=getattr(args, "dry_run", False))


def _ws_profile(args):
    ws = Workspace.load(explicit=args.workspace)
    profile = ws.profile(args.profile)
    return ws, profile


def _profile_or_inline(args):
    """Profile from a workspace, or built from flags.

    MCP-only operators have no developer app and therefore no token and often no
    workspace. preflight and audit must still work for them, so --currency is
    enough to run every offline check.
    """
    if getattr(args, "currency", None):
        return {
            "_name": "inline",
            "advertiser_id": getattr(args, "advertiser_id", None) or "<advertiser_id>",
            "currency": args.currency.upper(),
            "timezone": getattr(args, "timezone", None) or "<account timezone>",
        }
    try:
        return _ws_profile(args)[1]
    except WorkspaceError as exc:
        raise CommandFailure(
            f"{exc}\n\nNo workspace? Pass --currency (the AD ACCOUNT's currency) and "
            "optionally --advertiser-id. Offline checks need nothing else."
        ) from exc


def _state(ws, profile):
    path = os.path.join(ws.state_dir(), f"state-{profile['advertiser_id']}.json")
    return path, lifecycle.State(path)


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------

def cmd_workspace_validate(args):
    ws = Workspace.load(explicit=args.workspace)
    profiles = {}
    for name in ws.data["profiles"]:
        p = ws.profile(name)
        profiles[name] = {k: p[k] for k in ("advertiser_id", "currency", "timezone")
                          if k in p}
    return {"workspace": ws.path, "fingerprint": ws.fingerprint()[:16],
            "profiles": profiles,
            "blocked": ws.data.get("blocked_advertiser_ids") or []}


def cmd_doctor(args):
    ws, profile = _ws_profile(args)
    _, state = _state(ws, profile)
    client = _client(args, allow_writes=False)
    result = lifecycle.doctor(client, profile, state, check_pixel=not args.no_pixel_check)
    if not result["ok"]:
        raise CommandFailure("doctor found fatal access problems", detail=result)
    return result


def cmd_plan(args):
    ws, profile = _ws_profile(args)
    _, state = _state(ws, profile)
    client = _client(args, allow_writes=False)
    spec_obj = _load_json(args.spec)
    plan_dir = os.path.join(ws.state_dir(), "plans")
    return lifecycle.plan(client, profile, state, spec_obj, plan_dir)


def cmd_apply(args):
    ws, profile = _ws_profile(args)
    state_path, state = _state(ws, profile)
    plan_obj = _load_json(args.plan)
    client = _client(args, allow_writes=True)
    with lifecycle.Lock(state_path):
        return lifecycle.apply(client, profile, state, plan_obj)


def cmd_verify(args):
    ws, profile = _ws_profile(args)
    _, state = _state(ws, profile)
    plan_obj = _load_json(args.plan)
    client = _client(args, allow_writes=False)
    result = lifecycle.verify(client, profile, state, plan_obj)
    if not result["ok"]:
        raise CommandFailure("verify found differences between spec and platform",
                             detail=result)
    return result


def cmd_activate(args):
    ws, profile = _ws_profile(args)
    state_path, state = _state(ws, profile)
    plan_obj = _load_json(args.plan)
    client = _client(args, allow_writes=True)
    with lifecycle.Lock(state_path):
        return lifecycle.activate(client, profile, state, plan_obj,
                                  confirm_reviewed=args.confirm_reviewed,
                                  confirm_spend=args.confirm)


def cmd_report(args):
    ws, profile = _ws_profile(args)
    client = _client(args, allow_writes=False)
    result = operate.report(client, profile, level=args.level, start=args.start,
                            end=args.end, days=args.days,
                            extra_metrics=args.metric or None)
    if args.csv:
        _write_csv(args.csv, result["rows"])
        result["csv"] = args.csv
    return result


def cmd_status(args):
    ws, profile = _ws_profile(args)
    client = _client(args, allow_writes=True)
    return operate.set_status(client, profile, level=args.level,
                              ids=args.ids.split(","), status=args.set,
                              confirm=args.confirm)


def cmd_budget(args):
    ws, profile = _ws_profile(args)
    client = _client(args, allow_writes=True)
    return operate.set_budget(client, profile, level=args.level, object_id=args.id,
                              budget=args.amount, confirm=args.confirm,
                              store_product_source=args.store_product_source)


def cmd_sweep(args):
    ws, profile = _ws_profile(args)
    client = _client(args, allow_writes=False)
    return operate.sweep(client, profile, stall_impressions=args.stall_impressions)


def cmd_review(args):
    ws, profile = _ws_profile(args)
    client = _client(args, allow_writes=False)
    return operate.review_status(client, profile,
                                 ad_ids=args.ids.split(",") if args.ids else None)


def cmd_explain(args):
    value = args.code
    if str(value).strip().isdigit():
        return err_mod.explain(int(value))
    return err_mod.explain_status(value)


def cmd_budget_check(args):
    """Offline budget sanity check — no token, no network. Use it before writing a spec."""
    from . import money
    out = {"currency": args.currency.upper()}
    info = money.currency_info(args.currency)
    out["verification_ratio"] = info["ratio"]
    out["precision"] = info["precision"]
    out["decimals_allowed"] = money.decimals_for(args.currency)
    for level in ("campaign", "adgroup"):
        low, high = money.bounds(args.currency, level, args.store_product_source)
        out[f"{level}_daily_min"] = money.describe(low, args.currency)
        out[f"{level}_daily_max"] = money.describe(high, args.currency)
    if args.amount is not None:
        try:
            value = money.validate(args.amount, args.currency, args.level,
                                   store_product_source=args.store_product_source)
            out["checked"] = f"{money.describe(value, args.currency)} is valid at {args.level} level"
        except money.BudgetError as exc:
            raise CommandFailure(str(exc))
    return out


def cmd_preflight(args):
    profile = _profile_or_inline(args)
    spec_obj = _load_json(args.spec)
    return mcp_mod.preflight(spec_obj, profile)


def cmd_audit(args):
    actual = _load_json(args.actual)
    spec_obj = profile = None
    if args.spec:
        spec_obj = _load_json(args.spec)
        profile = _profile_or_inline(args)
    elif getattr(args, "currency", None):
        profile = {"_name": "inline", "advertiser_id": "<advertiser_id>",
                   "currency": args.currency.upper(), "timezone": "<tz>"}
    result = mcp_mod.audit(actual, spec_obj, profile,
                           expect_paused=not args.expect_live)
    if not result["ok"]:
        raise CommandFailure(
            f"audit found {result['worst_severity']}-level problems", detail=result)
    return result


def cmd_tools(args):
    rows = []
    for step, (tool, endpoint) in sorted(mcp_mod.TOOL_MAP.items()):
        rows.append({"task": step, "mcp_tool": tool, "endpoint": endpoint or "(not an endpoint wrapper)"})
    return {"note": "MCP tool names for the common lifecycle steps. Full inventory: "
                    "references/01-mcp-server.md",
            "tools": rows}


def _write_csv(path, rows):
    import csv
    if not rows:
        open(path, "w").close()
        return
    keys = sorted({k for row in rows for k in row})
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


class CommandFailure(Exception):
    def __init__(self, message, detail=None):
        super().__init__(message)
        self.detail = detail or {}


# ---------------------------------------------------------------------------
# parser
# ---------------------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(
        prog="ttops",
        description="TikTok Ads deterministic launch/operate CLI. "
                    "Token comes from TIKTOK_ACCESS_TOKEN, never from argv.",
    )
    p.add_argument("--workspace", help="path to workspace.json or its directory")
    p.add_argument("--profile", help="profile name inside the workspace")
    p.add_argument("--json", action="store_true", help="emit one ttops.result/v1 object")
    p.add_argument("--dry-run", action="store_true",
                   help="validate and print payloads; make no write calls")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("workspace", help="workspace operations")
    ssub = s.add_subparsers(dest="sub", required=True)
    ssub.add_parser("validate").set_defaults(func=cmd_workspace_validate)

    s = sub.add_parser("doctor", help="prove access before building anything")
    s.add_argument("--no-pixel-check", action="store_true")
    s.set_defaults(func=cmd_doctor)

    s = sub.add_parser("plan", help="validate a spec and snapshot a plan")
    s.add_argument("--spec", required=True)
    s.set_defaults(func=cmd_plan)

    s = sub.add_parser("apply", help="create every object, DISABLED")
    s.add_argument("--plan", required=True)
    s.set_defaults(func=cmd_apply)

    s = sub.add_parser("verify", help="read every object back and diff it")
    s.add_argument("--plan", required=True)
    s.set_defaults(func=cmd_verify)

    s = sub.add_parser("activate", help="enable objects — THIS SPENDS MONEY")
    s.add_argument("--plan", required=True)
    s.add_argument("--confirm-reviewed", required=True, metavar="REVIEWED")
    s.add_argument("--confirm", required=True, metavar="SPEND")
    s.set_defaults(func=cmd_activate)

    s = sub.add_parser("report", help="pull an integrated report")
    s.add_argument("--level", default="ad", choices=["advertiser", "campaign", "adgroup", "ad"])
    s.add_argument("--start")
    s.add_argument("--end")
    s.add_argument("--days", type=int, default=1)
    s.add_argument("--metric", action="append", help="extra metric (repeatable)")
    s.add_argument("--csv")
    s.set_defaults(func=cmd_report)

    s = sub.add_parser("status", help="ENABLE/DISABLE/DELETE objects")
    s.add_argument("--level", required=True, choices=["campaign", "adgroup", "ad"])
    s.add_argument("--ids", required=True, help="comma-separated, max 20")
    s.add_argument("--set", required=True, choices=["ENABLE", "DISABLE", "DELETE"])
    s.add_argument("--confirm", required=True, metavar="SPEND|PAUSE|DELETE")
    s.set_defaults(func=cmd_status)

    s = sub.add_parser("budget", help="change a budget (105%%-of-spend floor enforced)")
    s.add_argument("--level", required=True, choices=["campaign", "adgroup"])
    s.add_argument("--id", required=True)
    s.add_argument("--amount", required=True, type=float, help="major units")
    s.add_argument("--store-product-source", action="store_true")
    s.add_argument("--confirm", required=True, metavar="SPEND")
    s.set_defaults(func=cmd_budget)

    s = sub.add_parser("sweep", help="delivery sweep: stalled, rejected, not delivering")
    s.add_argument("--stall-impressions", type=int, default=50)
    s.set_defaults(func=cmd_sweep)

    s = sub.add_parser("review", help="ad review / rejection reasons")
    s.add_argument("--ids")
    s.set_defaults(func=cmd_review)

    s = sub.add_parser("preflight",
                       help="validate a spec and emit exact MCP tool arguments (offline)")
    s.add_argument("--spec", required=True)
    s.add_argument("--currency", help="ad account currency; use instead of a workspace")
    s.add_argument("--advertiser-id")
    s.add_argument("--timezone")
    s.set_defaults(func=cmd_preflight)

    s = sub.add_parser("audit",
                       help="check what MCP actually created (offline; paste the tool JSON)")
    s.add_argument("--actual", required=True,
                   help="file holding campaign_get / adgroup_get / ad_get output")
    s.add_argument("--spec", help="optional: diff against the spec you intended")
    s.add_argument("--currency", help="ad account currency; enables budget checks")
    s.add_argument("--advertiser-id")
    s.add_argument("--timezone")
    s.add_argument("--expect-live", action="store_true",
                   help="objects are meant to be ENABLE (post-activation audit)")
    s.set_defaults(func=cmd_audit)

    s = sub.add_parser("tools", help="lifecycle step -> MCP tool name (offline)")
    s.set_defaults(func=cmd_tools)

    s = sub.add_parser("explain",
                       help="explain a TikTok return code OR a secondary_status (offline)")
    s.add_argument("code", metavar="CODE_OR_STATUS",
                   help="e.g. 40100, or AD_STATUS_AUDIT_DENY")
    s.set_defaults(func=cmd_explain)

    s = sub.add_parser("budget-check", help="offline currency/budget bounds (no token needed)")
    s.add_argument("--currency", required=True)
    s.add_argument("--level", default="adgroup", choices=["campaign", "adgroup"])
    s.add_argument("--amount", type=float)
    s.add_argument("--store-product-source", action="store_true")
    s.set_defaults(func=cmd_budget_check)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    command = args.command + (f" {args.sub}" if getattr(args, "sub", None) else "")
    try:
        data = args.func(args)
        return _emit({"schema": RESULT_SCHEMA, "ok": True, "command": command,
                      "data": data}, args.json, 0)
    except CommandFailure as exc:
        return _emit({"schema": RESULT_SCHEMA, "ok": False, "command": command,
                      "error": {"kind": "command", "message": str(exc)},
                      "data": exc.detail}, args.json, 1)
    except TikTokError as exc:
        lines = err_mod.format_error(exc).split("\n")
        print(err_mod.format_error(exc), file=sys.stderr)
        return _emit({"schema": RESULT_SCHEMA, "ok": False, "command": command,
                      "error": dict(exc.as_dict(), kind="tiktok", lines=lines,
                                    **err_mod.explain(exc.code))}, args.json, 2)
    except (WorkspaceError, spec_mod.SpecError) as exc:
        print(str(exc), file=sys.stderr)
        return _emit({"schema": RESULT_SCHEMA, "ok": False, "command": command,
                      "error": {"kind": type(exc).__name__, "message": str(exc),
                                "lines": str(exc).split("\n")}}, args.json, 3)
    except (TransportError, RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return _emit({"schema": RESULT_SCHEMA, "ok": False, "command": command,
                      "error": {"kind": type(exc).__name__, "message": str(exc),
                                "lines": str(exc).split("\n")}}, args.json, 4)
    except Exception as exc:  # noqa: BLE001 — last resort, keep the traceback off stdout
        traceback.print_exc(file=sys.stderr)
        return _emit({"schema": RESULT_SCHEMA, "ok": False, "command": command,
                      "error": {"kind": "unexpected", "message": str(exc)}}, args.json, 5)


if __name__ == "__main__":
    sys.exit(main())

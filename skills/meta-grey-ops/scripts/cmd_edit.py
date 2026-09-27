#!/usr/bin/env python3
"""Agent-facing `metaops edit|clone|rules` surface over edit.py / clone.py / rules.py.

An agent must never assemble Graph payloads for mass status/budget edits, in-account
duplication, or automated kill-ladder rules. This module wires the three internal
scripts behind the same workspace/profile binding, doctor gate, and literal-confirm
pattern the rest of `metaops` uses (`references/16`). It does not reimplement any
Graph call; every write still goes through `edit.py` / `clone.py` / `rules.py` via
`ctx.run_child`, which only a workspace-authorized `metaops` process may invoke
(`graph.require_write_authority`, `METAOPS_AUTH_FD`).

Call `register(sub, ctx)` once, where `sub` is the metaops top-level subparsers
object and `ctx` is the `metaops` module itself (for `run_child`, `echo_child`,
`child_failure`, `result_envelope`, `MetaOpsError`, `require_doctor`, `graph`,
`resolve_input`, `read_json`). Every handler returns `(exit_code, result_dict)`,
the same contract as every other `metaops` command.

Command surface:

    edit status    --ids a,b | --state PATH --level campaign|adset|ad | --all --level L
                   --status PAUSED|ACTIVE --confirm PAUSE|SPEND [--dry-run]
    edit budget    --ids a,b (--budget-minor N | --budget-pct +-N) [--force-step]
                   [--confirm SPEND] [--dry-run]
    edit rename    --ids a,b --prefix P [--suffix S] [--dry-run]
    edit ramp      --ids a,b --step 20 --confirm RAMP [--dry-run]
    edit targeting --ids a,b | --state PATH | --all --user-os iOS,Android
                   --confirm TARGETING [--dry-run]
    edit tags      --ids a,b | --state PATH | --all (--url-tags STR | --template-url URL)
                   --confirm TAGS [--dry-run]

    clone campaign|adset|ad ID [--times N] [--prefix P] [--suffix S] [--start ISO]
          [--into-campaign ID] [--into-adset ID] [--dry-run]

    rules ladder  --target-minor N --event E --level ADSET|AD [--rungs 0-6]
                  [--mode notify|pause] [--ids a,b] [--prefix P]
                  [--confirm RULES] [--dry-run]
    rules list
    rules history [--since S]
    rules execute --rule-id ID --confirm EXECUTE
    rules delete  --prefix P --confirm DELETE [--dry-run]

Every command is workspace-bound. The ad account comes from `args.profile`; state
files must name that account; and the child reads the `account_id` of every opaque
edit/clone object before it can mutate it. A raw id from another accessible account
is therefore refused rather than relying on its numeric shape.

Any action that sets ACTIVE (spend can start) or can raise a budget requires the
literal `--confirm SPEND`; PAUSED status changes require `--confirm PAUSE`.
`edit.py` receives its own status literal (`ACTIVATE`/`PAUSE`).
`edit ramp` requires the distinct literal `--confirm RAMP`; it applies exactly one
guarded budget raise per invocation. `rules ... --mode pause` requires `--confirm RULES` since an armed
pause rule can act unattended; `rules execute` requires `--confirm EXECUTE`; and
`rules delete` requires `--confirm DELETE`.
`edit targeting` requires the literal `--confirm TARGETING`, checked even under
`--dry-run` (matches every other confirm-gated edit above); `edit tags` requires the
literal `--confirm TAGS`, same rule.

API facts below were verified against the installed facebook_business SDK, not
against developers.facebook.com (verified 2026-09-03, SDK 26.0.1):

  · `AdSet.create_copy` param_types: campaign_id (string), create_dco_adset (bool),
    deep_copy (bool), end_time (datetime), rename_options (Object), start_time
    (datetime), status_option (status_option_enum: ACTIVE | PAUSED |
    INHERITED_FROM_SOURCE). Endpoint POST /{id}/copies.
  · `Ad.create_copy` param_types: adset_id (string), creative_parameters
    (AdCreative), rename_options (Object), status_option (status_option_enum).
    Endpoint POST /{id}/copies.
  · `Campaign.create_copy` exists and accepts `deep_copy`, but clone.py still copies a
    campaign level-by-level because Graph caps deep copies and that preserves PAUSED children.
  · `AdAccount.create_ad_rules_library` and `AdAccount.get_ad_rules_history` both
    exist (rules.py posts to `{account}/adrules_library` and reads
    `{account}/adrules_history`, matching these edges).
  · `AdRule.create_execute` exists (rules.py posts `{rule_id}/execute`).
  · `Targeting.Field.user_os` exists, typed `list<string>` in `AdSet.api_update`
    param_types, which also carries `targeting: Targeting` — confirming the ad-set
    whole-object POST target `edit_targeting.py` writes to (never a delta).
  · `AdCreative.api_update` param_types = `{account_id, adlabels, name, status}` —
    `url_tags`/`template_url_spec` are CREATE-only (present only in
    `AdAccount.create_ad_creative`'s param_types, alongside `object_story_spec`,
    `asset_feed_spec`, `product_set_id`, `degrees_of_freedom_spec`,
    `contextual_multi_ads`). `Ad.api_update` param_types include `creative: AdCreative`.
    Together these confirm `edit_tags.py`'s clone-a-new-creative-then-swap path is the
    only way to change a live ad's tags; there is no in-place PATCH.

edit.py, clone.py, rules.py, edit_targeting.py, and edit_tags.py each print exactly one
JSON line as the last line of stdout (schemas `edit.result/v1`, `clone.result/v1`,
`rules.result/v1`, `edit_targeting.result/v1`, `edit_tags.result/v1`); this module
parses that line and returns it under `data`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
from typing import Any

RAISE_CONFIRM = "SPEND"
PAUSE_CONFIRM = "PAUSE"
RAMP_CONFIRM = "RAMP"
RULES_PAUSE_CONFIRM = "RULES"
RULES_DELETE_CONFIRM = "DELETE"
RULES_EXECUTE_CONFIRM = "EXECUTE"
RAMP_STEP_LIMIT = 20
TARGETING_CONFIRM = "TARGETING"
TAGS_CONFIRM = "TAGS"
# dest names for `edit targeting`'s scalar flags. Add a matching add_argument() in
# register() and an entry in edit_targeting.py's SCALAR_FIELDS to support another one.
TARGETING_SCALAR_FLAGS = ["user_os", "publisher_platforms", "facebook_positions", "instagram_positions"]


def _parse_last_json_line(stdout: str) -> dict[str, Any]:
    for line in reversed((stdout or "").splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except ValueError:
                continue
    return {}


def _profile(args, ctx) -> tuple[str, dict[str, Any]]:
    if not args.workspace_obj:
        raise ctx.MetaOpsError(f"{args.command} requires a workspace")
    return args.workspace_obj.profile(args.profile)


def _account(profile: dict[str, Any], ctx) -> str:
    return ctx.graph.normalize_account(profile["ad_account_id"])


def _check_state_account(state_arg: str, account: str, ctx) -> None:
    """Refuse a --state file that was built for a different account (offline check)."""
    path = ctx.resolve_input(state_arg)
    state = ctx.read_json(path, "state")
    if not isinstance(state, dict):
        raise ctx.MetaOpsError(f"state is not a JSON object: {path}")
    spec_account = state.get("spec_account")
    if spec_account and ctx.graph.normalize_account(str(spec_account)) != account:
        raise ctx.MetaOpsError(
            f"state belongs to a different account ({spec_account} != {account}); "
            "refusing to edit outside the profile's ad account"
        )


def _run_child(ctx, args, command: str, script: str, child_args: list[str],
                phase_ok: str, next_action: str | None = None) -> tuple[int, dict[str, Any]]:
    child = ctx.run_child(script, child_args, args.timeout)
    ctx.echo_child(child)
    data = _parse_last_json_line(child.stdout)
    if not child.ok:
        out = ctx.child_failure(command, "failed", child)
        if data:
            out["data"] = {**data, "child_exit_code": child.returncode}
        return child.returncode, out
    return 0, ctx.result_envelope(command, True, phase_ok, data=data, next_action=next_action)


# --- edit ------------------------------------------------------------------


def handle_edit_status(args) -> tuple[int, dict[str, Any]]:
    ctx = ctx_module()
    _, profile = _profile(args, ctx)
    account = _account(profile, ctx)
    if bool(args.ids) + bool(args.state) + bool(args.all) != 1:
        raise ctx.MetaOpsError("edit status needs exactly one of --ids, --state, --all")
    if (args.state or args.all) and not args.level:
        raise ctx.MetaOpsError("--state / --all need --level")
    expected_confirm = {"ACTIVE": RAISE_CONFIRM, "PAUSED": PAUSE_CONFIRM,
                        "DELETED": "DELETE"}[args.status]
    if args.confirm != expected_confirm:
        raise ctx.MetaOpsError(
            f"--status {args.status} changes delivery: pass the literal --confirm {expected_confirm}"
        )
    child_args: list[str] = []
    if args.ids:
        child_args += ["--ids", args.ids]
    elif args.state:
        _check_state_account(args.state, account, ctx)
        child_args += ["--state", args.state, "--level", args.level]
    else:
        child_args += ["--account", account, "--level", args.level, "--all"]
    child_args += ["--status", args.status]
    child_args += ["--confirm", {"ACTIVE": "ACTIVATE", "PAUSED": "PAUSE", "DELETED": "DELETE"}[args.status]]
    child_args += ["--expected-account", account]
    if args.dry_run:
        child_args.append("--dry-run")
    return _run_child(ctx, args, "edit status", "edit.py", child_args, "edited")


def handle_edit_budget(args) -> tuple[int, dict[str, Any]]:
    ctx = ctx_module()
    _, profile = _profile(args, ctx)
    account = _account(profile, ctx)
    if not args.ids:
        raise ctx.MetaOpsError("edit budget requires --ids")
    if (args.budget_minor is None) == (args.budget_pct is None):
        raise ctx.MetaOpsError("edit budget needs exactly one of --budget-minor, --budget-pct")
    is_raise = True
    if args.budget_pct is not None:
        is_raise = not args.budget_pct.strip().startswith("-")
    if is_raise and args.confirm != RAISE_CONFIRM:
        raise ctx.MetaOpsError(
            f"a budget change that may raise spend requires the literal --confirm {RAISE_CONFIRM}"
        )
    child_args = ["--ids", args.ids, "--expected-account", account]
    if args.budget_minor is not None:
        child_args += ["--budget-minor", str(args.budget_minor)]
    else:
        child_args += ["--budget-pct", args.budget_pct]
    if args.force_step:
        child_args.append("--force-step")
    if args.dry_run:
        child_args.append("--dry-run")
    return _run_child(ctx, args, "edit budget", "edit.py", child_args, "edited")


def handle_edit_rename(args) -> tuple[int, dict[str, Any]]:
    ctx = ctx_module()
    _, profile = _profile(args, ctx)
    account = _account(profile, ctx)
    if not args.ids:
        raise ctx.MetaOpsError("edit rename requires --ids")
    child_args = ["--ids", args.ids, "--expected-account", account, "--rename-prefix", args.prefix]
    if args.suffix:
        child_args += ["--rename-suffix", args.suffix]
    if args.dry_run:
        child_args.append("--dry-run")
    return _run_child(ctx, args, "edit rename", "edit.py", child_args, "edited")


def handle_edit_ramp(args) -> tuple[int, dict[str, Any]]:
    ctx = ctx_module()
    _, profile = _profile(args, ctx)
    account = _account(profile, ctx)
    if not args.ids:
        raise ctx.MetaOpsError("edit ramp requires --ids")
    if args.confirm != RAMP_CONFIRM:
        raise ctx.MetaOpsError(f"edit ramp requires the literal --confirm {RAMP_CONFIRM}")
    step = args.step
    if not 0 < abs(step) <= RAMP_STEP_LIMIT:
        raise ctx.MetaOpsError(
            f"--step {step} exceeds edit.py's ±{RAMP_STEP_LIMIT}% per-edit guard"
        )
    child_args = [
        "--ids", args.ids, "--expected-account", account,
        "--budget-pct", f"+{step}" if step > 0 else str(step),
    ]
    if args.dry_run:
        child_args.append("--dry-run")
    child = ctx.run_child("edit.py", child_args, args.timeout)
    ctx.echo_child(child)
    data = _parse_last_json_line(child.stdout)
    if not child.ok:
        out = ctx.child_failure("edit ramp", "ramp_failed", child)
        out["data"] = {"step_pct": step, "data": data}
        return child.returncode, out
    return 0, ctx.result_envelope(
        "edit ramp", True, "ramped", data={"step_pct": step, "data": data},
        next_action="Wait 48–72 hours for delivery to stabilize before the next ramp invocation.",
    )


def handle_edit_targeting(args) -> tuple[int, dict[str, Any]]:
    ctx = ctx_module()
    _, profile = _profile(args, ctx)
    account = _account(profile, ctx)
    if bool(args.ids) + bool(args.state) + bool(args.all) != 1:
        raise ctx.MetaOpsError("edit targeting needs exactly one of --ids, --state, --all")
    provided = {name: getattr(args, name) for name in TARGETING_SCALAR_FLAGS if getattr(args, name)}
    if not provided:
        raise ctx.MetaOpsError(
            "edit targeting needs at least one scalar targeting flag (currently: --user-os)"
        )
    if args.confirm != TARGETING_CONFIRM:
        raise ctx.MetaOpsError(
            f"targeting changes reach: pass the literal --confirm {TARGETING_CONFIRM}"
        )
    child_args: list[str] = []
    if args.ids:
        child_args += ["--ids", args.ids]
    elif args.state:
        _check_state_account(args.state, account, ctx)
        child_args += ["--state", args.state]
    else:
        child_args += ["--account", account, "--all"]
    for name, value in provided.items():
        child_args += [f"--{name.replace('_', '-')}", value]
    child_args += ["--confirm", TARGETING_CONFIRM, "--expected-account", account]
    if args.dry_run:
        child_args.append("--dry-run")
    return _run_child(ctx, args, "edit targeting", "edit_targeting.py", child_args, "edited")


def handle_edit_tags(args) -> tuple[int, dict[str, Any]]:
    ctx = ctx_module()
    _, profile = _profile(args, ctx)
    account = _account(profile, ctx)
    if bool(args.ids) + bool(args.state) + bool(args.all) != 1:
        raise ctx.MetaOpsError("edit tags needs exactly one of --ids, --state, --all")
    if not args.url_tags and not args.template_url:
        raise ctx.MetaOpsError("edit tags needs --url-tags and/or --template-url")
    if args.confirm != TAGS_CONFIRM:
        raise ctx.MetaOpsError(
            f"rewriting live tracking tags requires the literal --confirm {TAGS_CONFIRM}"
        )
    child_args: list[str] = []
    if args.ids:
        child_args += ["--ids", args.ids]
    elif args.state:
        _check_state_account(args.state, account, ctx)
        child_args += ["--state", args.state]
    else:
        child_args += ["--account", account, "--all"]
    if args.url_tags:
        child_args += ["--url-tags", args.url_tags]
    if args.template_url:
        child_args += ["--template-url", args.template_url]
    child_args += ["--confirm", TAGS_CONFIRM, "--expected-account", account]
    if args.dry_run:
        child_args.append("--dry-run")
    return _run_child(
        ctx, args, "edit tags", "edit_tags.py", child_args, "edited",
        next_action=(
            "Name macros ({{campaign.name}}, {{adset.name}}, {{ad.name}}) resolve from a "
            "first-publish snapshot (04-mass-launch-api.md), so renaming an object never reaches "
            "the tracker; id macros are unaffected. Skipped ads were not cloned - see each row's "
            "reason."
        ),
    )


# --- clone -------------------------------------------------------------------


def default_clone_state(ctx, args, account: str) -> str:
    """Resume file keyed by the full clone request. Re-running the identical request resumes
    (completed copies are skipped, unknown outcomes stop) instead of duplicating; any change
    to kind/id/times/naming/start/target is a new request with its own file. Pass --state
    explicitly to force a fresh set of copies."""
    request = {
        "account": account, "kind": args.kind, "id": str(args.id), "times": args.times,
        "prefix": args.prefix, "suffix": args.suffix, "start": args.start,
        "into_campaign": args.into_campaign, "into_adset": args.into_adset,
    }
    sha = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()[:12]
    return str(pathlib.Path(ctx.launch.STATE_DIR) / "clones" / f"{args.kind}-{args.id}.{sha}.json")


def handle_clone(args) -> tuple[int, dict[str, Any]]:
    ctx = ctx_module()
    _, profile = _profile(args, ctx)
    account = _account(profile, ctx)
    child_args = [args.kind, args.id, "--times", str(args.times), "--expected-account", account]
    if args.prefix:
        child_args += ["--prefix", args.prefix]
    if args.suffix:
        child_args += ["--suffix", args.suffix]
    if args.start:
        child_args += ["--start", args.start]
    if args.into_campaign:
        child_args += ["--into-campaign", args.into_campaign]
    if args.into_adset:
        child_args += ["--into-adset", args.into_adset]
    if args.dry_run:
        child_args.append("--dry-run")
    else:
        child_args += ["--state", args.state or default_clone_state(ctx, args, account)]
    return _run_child(
        ctx, args, "clone", "clone.py", child_args, "cloned",
        next_action="Copies land PAUSED; review in Ads Manager, then edit status --confirm SPEND to activate.",
    )


# --- rules -------------------------------------------------------------------

def handle_rules_ladder(args) -> tuple[int, dict[str, Any]]:
    ctx = ctx_module()
    _, profile = _profile(args, ctx)
    account = _account(profile, ctx)
    if args.mode == "pause" and args.confirm != RULES_PAUSE_CONFIRM:
        raise ctx.MetaOpsError(
            f"--mode pause arms unattended pausing: pass the literal --confirm {RULES_PAUSE_CONFIRM}"
        )
    child_args = [
        "--account", account, "--target-minor", str(args.target_minor),
        "--event", args.event, "--level", args.level, "--rungs", args.rungs,
        "--mode", args.mode, "--prefix", args.prefix,
    ]
    if args.ids:
        child_args += ["--ids", args.ids]
    if args.dry_run:
        child_args.append("--dry-run")
    return _run_child(ctx, args, "rules ladder", "rules.py", child_args, "armed")


def handle_rules_list(args) -> tuple[int, dict[str, Any]]:
    ctx = ctx_module()
    _, profile = _profile(args, ctx)
    account = _account(profile, ctx)
    return _run_child(ctx, args, "rules list", "rules.py", ["--account", account, "--list"], "listed")


def handle_rules_history(args) -> tuple[int, dict[str, Any]]:
    ctx = ctx_module()
    _, profile = _profile(args, ctx)
    account = _account(profile, ctx)
    child_args = ["--account", account, "--history"]
    if args.since:
        child_args += ["--since", args.since]
    return _run_child(ctx, args, "rules history", "rules.py", child_args, "read")


def handle_rules_execute(args) -> tuple[int, dict[str, Any]]:
    ctx = ctx_module()
    _, profile = _profile(args, ctx)
    account = _account(profile, ctx)
    if not args.rule_id:
        raise ctx.MetaOpsError("rules execute requires --rule-id")
    if args.confirm != RULES_EXECUTE_CONFIRM:
        raise ctx.MetaOpsError(
            f"rules execute can trigger a live rule: pass the literal --confirm {RULES_EXECUTE_CONFIRM}"
        )
    child_args = ["--account", account, "--execute", args.rule_id, "--confirm", RULES_EXECUTE_CONFIRM]
    return _run_child(ctx, args, "rules execute", "rules.py", child_args, "executed")


def handle_rules_delete(args) -> tuple[int, dict[str, Any]]:
    ctx = ctx_module()
    _, profile = _profile(args, ctx)
    account = _account(profile, ctx)
    if not args.prefix:
        raise ctx.MetaOpsError("rules delete requires --prefix")
    if args.confirm != RULES_DELETE_CONFIRM:
        raise ctx.MetaOpsError(f"rules delete requires the literal --confirm {RULES_DELETE_CONFIRM}")
    child_args = ["--account", account, "--delete-prefix", args.prefix]
    if args.dry_run:
        child_args.append("--dry-run")
    return _run_child(ctx, args, "rules delete", "rules.py", child_args, "deleted")


# --- registration --------------------------------------------------------------

_CTX = None  # set by register(); avoids threading ctx through every argparse callback


def ctx_module():
    if _CTX is None:  # pragma: no cover - defensive; register() always runs first
        raise RuntimeError("cmd_edit.register(sub, ctx) has not run yet")
    return _CTX


def register(sub: argparse._SubParsersAction, ctx) -> None:
    global _CTX
    _CTX = ctx

    # edit ---------------------------------------------------------------
    p_edit = sub.add_parser("edit", help="mass status/budget/rename edits via edit.py")
    edit_sub = p_edit.add_subparsers(dest="edit_action", required=True)

    p = edit_sub.add_parser("status", help="pause/activate objects (read-back, guarded)")
    grp = p.add_mutually_exclusive_group(required=True)
    grp.add_argument("--ids", help="comma-separated object ids")
    grp.add_argument("--state", help="launch.py state file; needs --level")
    grp.add_argument("--all", action="store_true", help="every ACTIVE object at --level in the profile account")
    p.add_argument("--level", choices=["campaign", "adset", "ad"], help="needed with --state / --all")
    p.add_argument("--status", required=True, choices=["ACTIVE", "PAUSED", "DELETED"],
                   help="DELETED is irreversible (--confirm DELETE); allowed with spend (Meta keeps its insights)")
    p.add_argument("--confirm", help=f"literal {RAISE_CONFIRM} for ACTIVE or {PAUSE_CONFIRM} for PAUSED")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(handler=handle_edit_status)

    p = edit_sub.add_parser("budget", help="change daily_budget with the ±20%%/late-day guard")
    p.add_argument("--ids", required=True, help="comma-separated object ids")
    bgrp = p.add_mutually_exclusive_group(required=True)
    bgrp.add_argument("--budget-minor", type=int, help="new daily_budget, integer minor units")
    bgrp.add_argument("--budget-pct", help="relative change, e.g. +20 or -15")
    p.add_argument("--force-step", action="store_true", help="bypass the ±20%%/late-day guards")
    p.add_argument("--confirm", help=f"literal {RAISE_CONFIRM}, required when the change may raise spend")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(handler=handle_edit_budget)

    p = edit_sub.add_parser("rename", help="rename objects with a prefix/suffix")
    p.add_argument("--ids", required=True, help="comma-separated object ids")
    p.add_argument("--prefix", required=True)
    p.add_argument("--suffix")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(handler=handle_edit_rename)

    p = edit_sub.add_parser("ramp", help="one guarded +N%% budget step; wait before the next rung")
    p.add_argument("--ids", required=True, help="comma-separated object ids")
    p.add_argument("--step", required=True, type=int, help="one signed percentage, e.g. 20")
    p.add_argument("--confirm", help=f"literal {RAMP_CONFIRM}, required")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(handler=handle_edit_ramp)

    p = edit_sub.add_parser(
        "targeting", help="read-modify-write a narrow targeting change across many adsets"
    )
    grp = p.add_mutually_exclusive_group(required=True)
    grp.add_argument("--ids", help="comma-separated ad set ids")
    grp.add_argument("--state", help="launch.py state file; adset ids are pulled from it")
    grp.add_argument("--all", action="store_true", help="every ACTIVE ad set in the profile account")
    p.add_argument("--user-os", dest="user_os", help="comma-separated OS list, e.g. iOS,Android")
    p.add_argument("--publisher-platforms", dest="publisher_platforms", help="e.g. facebook,instagram (must include instagram)")
    p.add_argument("--facebook-positions", dest="facebook_positions", help="e.g. feed,story,facebook_reels")
    p.add_argument("--instagram-positions", dest="instagram_positions", help="e.g. stream,story,reels")
    p.add_argument("--confirm", help=f"literal {TARGETING_CONFIRM}, required (including --dry-run)")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(handler=handle_edit_targeting)

    p = edit_sub.add_parser(
        "tags", help="bulk-rewrite url_tags/template_url_spec on live ads (clone-and-swap creative)"
    )
    grp = p.add_mutually_exclusive_group(required=True)
    grp.add_argument("--ids", help="comma-separated ad ids")
    grp.add_argument("--state", help="launch.py state file; ad ids are pulled from it")
    grp.add_argument("--all", action="store_true", help="every ACTIVE ad in the profile account")
    p.add_argument("--url-tags", help="new url_tags string for non-catalog creatives")
    p.add_argument("--template-url", help="new template_url_spec.web.url for catalog/product-ad creatives")
    p.add_argument("--confirm", help=f"literal {TAGS_CONFIRM}, required (including --dry-run)")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(handler=handle_edit_tags)

    # clone ----------------------------------------------------------------
    p_clone = sub.add_parser("clone", help="duplicate a campaign/adset/ad inside the account (PAUSED)")
    p_clone.add_argument("kind", choices=["campaign", "adset", "ad"])
    p_clone.add_argument("id")
    p_clone.add_argument("--times", type=int, default=1)
    p_clone.add_argument("--prefix", help="rename prefix on the top object; {n} = copy index")
    p_clone.add_argument("--suffix", help="rename suffix on the top object; {n} = copy index")
    p_clone.add_argument("--start", help="ISO-8601 start_time for copied ad sets")
    p_clone.add_argument("--into-campaign", help="adset copies: target campaign id")
    p_clone.add_argument("--into-adset", help="ad copies: target ad set id")
    p_clone.add_argument("--dry-run", action="store_true")
    p_clone.add_argument("--state", help="clone resume file; default is keyed by the request "
                         "under the workspace state dir, so an identical re-run never duplicates")
    p_clone.set_defaults(handler=handle_clone)

    # rules ------------------------------------------------------------------
    p_rules = sub.add_parser("rules", help="automated kill-ladder rules via rules.py")
    rules_sub = p_rules.add_subparsers(dest="rules_action", required=True)

    p = rules_sub.add_parser("ladder", help="arm (or notify-test) the Poisson kill ladder")
    p.add_argument("--target-minor", type=int, required=True)
    p.add_argument("--event", default="results")
    p.add_argument("--level", default="ADSET", choices=["ADSET", "AD"])
    p.add_argument("--rungs", default="0-6")
    p.add_argument("--mode", default="notify", choices=["notify", "pause"])
    p.add_argument("--ids", help="scope to these object ids (comma-separated)")
    p.add_argument("--prefix", default="LADDER|")
    p.add_argument("--confirm", help=f"literal {RULES_PAUSE_CONFIRM}, required for --mode pause")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(handler=handle_rules_ladder)

    p = rules_sub.add_parser("list", help="list armed rules on the profile account")
    p.set_defaults(handler=handle_rules_list)

    p = rules_sub.add_parser("history", help="read adrules_history for the profile account")
    p.add_argument("--since", help="Unix timestamp or ISO-8601 datetime")
    p.set_defaults(handler=handle_rules_history)

    p = rules_sub.add_parser("execute", help="dry-fire one rule and read its history")
    p.add_argument("--rule-id", required=True)
    p.add_argument("--confirm", required=True, help=f"must be literal {RULES_EXECUTE_CONFIRM}")
    p.set_defaults(handler=handle_rules_execute)

    p = rules_sub.add_parser("delete", help="delete every rule whose name starts with --prefix")
    p.add_argument("--prefix", required=True)
    p.add_argument("--confirm", help=f"literal {RULES_DELETE_CONFIRM}, required")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(handler=handle_rules_delete)

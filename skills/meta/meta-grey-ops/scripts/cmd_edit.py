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
                   # --all = every LIVE object (ACTIVE, in review, WITH_ISSUES, under a paused parent)
    edit budget    --ids a,b (--budget-minor N | --budget-pct +-N) [--force-step]
                   [--confirm SPEND] [--dry-run]   # raises capped at +20%, cuts of any size allowed
    edit rename    (--ids a,b --prefix P [--suffix S] | --ids ID --name NAME | --set ID=NAME ...)
                   [--dry-run]                          # --name/--set = exact names, no review impact
    edit bid       --ids a,b --bid-minor N --confirm BID [--dry-run|--validate-only]  # ad-set bid/cost cap
    edit schedule  --ids a,b [--start-time ISO] [--end-time ISO] --confirm SCHEDULE [--dry-run]
    edit ramp      --ids a,b --step 20 --confirm RAMP [--dry-run]
    edit targeting --ids a,b | --state PATH | --all [--user-os ..] [--publisher-platforms ..]
                   [--facebook-positions ..] [--instagram-positions ..] [--device-platforms ..]
                   [--age-min N] [--age-max N] [--genders 1,2] [--geo-regions KEY,..]
                   [--advantage-audience 0|1] --confirm TARGETING [--dry-run]
                   # --all = ACTIVE ad sets only; --geo-regions is refused with --all; empty values refused
    edit tags|creative --ids a,b | --state PATH | --all   # --all = ACTIVE ads only
                   [--url-tags STR] [--template-url URL] [--headline T] [--cta TYPE]
                   [--message T | --message-file PATH] [--description T] [--caption DOMAIN]
                   [--link URL] [--image-hash H] [--allow-disapproved]
                   --confirm TAGS [--dry-run]          # clone-and-swap: text/image/link edits re-open review

    clone campaign|adset|ad ID [--times N] [--prefix P] [--suffix S] [--start ISO]
          [--into-campaign ID] [--into-adset ID] [--dry-run]

    rules ladder  --target-minor N --event E --level ADSET|AD [--rungs 0-6]
                  [--mode notify|pause] [--ids a,b | --all-adsets] [--prefix P]
                  [--time-preset LIFETIME|LAST_7D|..] [--impressions-floor N]
                  [--confidence 0.95] [--schedule SEMI_HOURLY|HOURLY|DAILY]
                  [--confirm RULES] [--dry-run]     # --mode pause needs --ids or --all-adsets
    rules list
    rules history [--since S]
    rules execute --rule-id ID --confirm EXECUTE [--live]   # --live for a rule that is not NOTIFICATION
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
pause rule can act unattended, and either `--ids` or the explicit `--all-adsets` (a pause ladder with
no scope would cover every object at the level); `rules execute` requires `--confirm EXECUTE`, and a
rule whose execution is not a NOTIFICATION (a PAUSE rule acts for real when fired) also needs
`--live`; `rules delete` requires `--confirm DELETE`.
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
import datetime as dt
import hashlib
import json
import math
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
BID_CONFIRM = "BID"
SCHEDULE_CONFIRM = "SCHEDULE"
NAME_LIMIT = 400
# dest names for `edit targeting`'s scalar flags. Add a matching add_argument() in
# register() and an entry in edit_targeting.py's SCALAR_FIELDS to support another one.
TARGETING_SCALAR_FLAGS = [
    "user_os", "publisher_platforms", "facebook_positions", "instagram_positions",
    "device_platforms", "age_min", "age_max", "genders", "geo_regions", "advantage_audience",
]
COPY_FLAGS = ("headline", "cta", "message", "message_file", "description", "caption", "link", "image_hash")


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
    if args.budget_minor is not None and args.budget_minor <= 0:
        raise ctx.MetaOpsError("--budget-minor must be a positive integer in minor units")
    if args.budget_pct is not None:
        pct = _parse_pct(ctx, args.budget_pct)
        is_raise = pct >= 0
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
    if getattr(args, "validate_only", False):
        child_args.append("--validate-only")
    return _run_child(ctx, args, "edit budget", "edit.py", child_args, "edited")


def _parse_pct(ctx, raw: str) -> float:
    """--budget-pct as a number: '' / 'abc' / nan / <= -100 are refused here, before a child runs."""
    try:
        value = float(str(raw).strip())
    except ValueError:
        raise ctx.MetaOpsError(f"--budget-pct must be a number such as +20 or -15, got {raw!r}") from None
    if not math.isfinite(value) or value <= -100:
        raise ctx.MetaOpsError(f"--budget-pct must be a finite number above -100, got {raw!r}")
    return value


def _parse_name_pairs(ctx, pairs: list[str]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for pair in pairs:
        oid, sep, name = pair.partition("=")
        oid, name = oid.strip(), name.strip()
        if not sep or not oid.isdigit() or not name:
            raise ctx.MetaOpsError(f"--set expects NUMERIC_ID=NEW_NAME, got {pair!r}")
        if len(name) > NAME_LIMIT:
            raise ctx.MetaOpsError(f"--set {oid}: name is {len(name)} chars; Meta allows {NAME_LIMIT}")
        out.append((oid, name))
    return out


def handle_edit_rename(args) -> tuple[int, dict[str, Any]]:
    ctx = ctx_module()
    _, profile = _profile(args, ctx)
    account = _account(profile, ctx)
    forms = [bool(args.prefix or args.suffix), args.name is not None, bool(args.set_names)]
    if sum(forms) != 1:
        raise ctx.MetaOpsError(
            "edit rename needs exactly one form: --prefix/--suffix, --name (one id), or --set ID=NAME"
        )
    if args.set_names:
        pairs = _parse_name_pairs(ctx, args.set_names)
        child_args = ["--ids", ",".join(oid for oid, _ in pairs), "--expected-account", account]
        for oid, name in pairs:
            child_args += ["--set", f"{oid}={name}"]
    else:
        if not args.ids:
            raise ctx.MetaOpsError("edit rename requires --ids")
        child_args = ["--ids", args.ids, "--expected-account", account]
        if args.name is not None:
            if len([i for i in args.ids.split(",") if i.strip()]) != 1:
                raise ctx.MetaOpsError("--name renames exactly one id; use --set ID=NAME for several")
            if not args.name.strip() or len(args.name) > NAME_LIMIT:
                raise ctx.MetaOpsError(f"--name must be 1-{NAME_LIMIT} characters")
            child_args += ["--name", args.name]
        else:
            if args.prefix:
                child_args += ["--rename-prefix", args.prefix]
            if args.suffix:
                child_args += ["--rename-suffix", args.suffix]
    if args.dry_run:
        child_args.append("--dry-run")
    if getattr(args, "validate_only", False):
        child_args.append("--validate-only")
    return _run_child(
        ctx, args, "edit rename", "edit.py", child_args, "edited",
        next_action=(
            "Name macros ({{ad.name}} etc.) in url_tags resolve from a first-publish snapshot, so the "
            "tracker keeps the OLD name; ids (sub6/sub12) always follow the object."
        ),
    )


def handle_edit_bid(args) -> tuple[int, dict[str, Any]]:
    ctx = ctx_module()
    _, profile = _profile(args, ctx)
    account = _account(profile, ctx)
    if not args.ids:
        raise ctx.MetaOpsError("edit bid requires --ids (ad sets)")
    if args.bid_minor <= 0:
        raise ctx.MetaOpsError("--bid-minor must be a positive integer in minor units")
    if args.confirm != BID_CONFIRM:
        raise ctx.MetaOpsError(f"a bid change moves spend: pass the literal --confirm {BID_CONFIRM}")
    child_args = ["--ids", args.ids, "--expected-account", account, "--bid-minor", str(args.bid_minor)]
    if args.dry_run:
        child_args.append("--dry-run")
    if getattr(args, "validate_only", False):
        child_args.append("--validate-only")
    return _run_child(ctx, args, "edit bid", "edit.py", child_args, "edited")


def _iso_with_offset(ctx, flag: str, raw: str) -> str:
    try:
        parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        raise ctx.MetaOpsError(f"{flag} must be ISO-8601, e.g. 2026-10-01T08:00:00-07:00 (got {raw!r})")
    if parsed.tzinfo is None:
        raise ctx.MetaOpsError(f"{flag} needs a UTC offset (an offsetless time is read in the wrong zone)")
    return raw


def handle_edit_schedule(args) -> tuple[int, dict[str, Any]]:
    ctx = ctx_module()
    _, profile = _profile(args, ctx)
    account = _account(profile, ctx)
    if not args.ids:
        raise ctx.MetaOpsError("edit schedule requires --ids (ad sets)")
    if not (args.start_time or args.end_time):
        raise ctx.MetaOpsError("edit schedule needs --start-time and/or --end-time")
    if args.confirm != SCHEDULE_CONFIRM:
        raise ctx.MetaOpsError(f"a schedule change moves delivery: pass the literal --confirm {SCHEDULE_CONFIRM}")
    child_args = ["--ids", args.ids, "--expected-account", account]
    if args.start_time:
        child_args += ["--start-time", _iso_with_offset(ctx, "--start-time", args.start_time)]
    if args.end_time:
        child_args += ["--end-time", _iso_with_offset(ctx, "--end-time", args.end_time)]
    if args.dry_run:
        child_args.append("--dry-run")
    if getattr(args, "validate_only", False):
        child_args.append("--validate-only")
    return _run_child(ctx, args, "edit schedule", "edit.py", child_args, "edited")


def handle_edit_ramp(args) -> tuple[int, dict[str, Any]]:
    ctx = ctx_module()
    _, profile = _profile(args, ctx)
    account = _account(profile, ctx)
    if not args.ids:
        raise ctx.MetaOpsError("edit ramp requires --ids")
    if args.confirm != RAMP_CONFIRM:
        raise ctx.MetaOpsError(f"edit ramp requires the literal --confirm {RAMP_CONFIRM}")
    step = args.step
    if step == 0 or step > RAMP_STEP_LIMIT or step <= -100:
        raise ctx.MetaOpsError(
            f"--step {step} is outside edit.py's guard: a raise is capped at +{RAMP_STEP_LIMIT}% per edit "
            f"(cuts of any size are allowed, but not 0 or -100 and below)"
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
    provided = {name: getattr(args, name) for name in TARGETING_SCALAR_FLAGS if getattr(args, name) is not None}
    if not provided:
        raise ctx.MetaOpsError(
            "edit targeting needs at least one targeting flag (see `edit targeting --help`)"
        )
    empty = [f"--{name.replace('_', '-')}" for name, value in provided.items() if not str(value).strip()]
    if empty:
        raise ctx.MetaOpsError(
            f"{', '.join(empty)} is empty: an empty value would erase the field, not keep it. Pass a value "
            f"or drop the flag"
        )
    if args.all and "geo_regions" in provided:
        raise ctx.MetaOpsError(
            "--geo-regions cannot be combined with --all: one region list would overwrite the geography of "
            "every active ad set. Pass explicit --ids (or a --state file)."
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
        child_args += [f"--{name.replace('_', '-')}", str(value)]
    child_args += ["--confirm", TARGETING_CONFIRM, "--expected-account", account]
    if args.dry_run:
        child_args.append("--dry-run")
    if getattr(args, "validate_only", False):
        child_args.append("--validate-only")
    return _run_child(ctx, args, "edit targeting", "edit_targeting.py", child_args, "edited")


def handle_edit_tags(args) -> tuple[int, dict[str, Any]]:
    ctx = ctx_module()
    _, profile = _profile(args, ctx)
    account = _account(profile, ctx)
    if bool(args.ids) + bool(args.state) + bool(args.all) != 1:
        raise ctx.MetaOpsError("edit tags needs exactly one of --ids, --state, --all")
    for flag in ("url_tags", "template_url", "headline", "cta", "link", "image_hash", "message_file"):
        value = getattr(args, flag)
        if value is not None and not value.strip():
            raise ctx.MetaOpsError(
                f"--{flag.replace('_', '-')} is empty; pass a value (only --description / --caption accept "
                f"\"\" to remove the field)"
            )
    if args.message is not None and not args.message.strip():
        raise ctx.MetaOpsError("primary text is empty; refusing to blank an ad's message")
    copy_given = any(getattr(args, name) is not None for name in COPY_FLAGS)
    if not (args.url_tags or args.template_url or copy_given or args.enhancements_off):
        raise ctx.MetaOpsError(
            "edit tags needs --url-tags, --template-url, or an ad-copy flag "
            "(--headline --cta --message --message-file --description --caption --link --image-hash)"
        )
    if args.confirm not in (TAGS_CONFIRM, "CREATIVE"):
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
    if args.url_tags is not None:
        child_args += ["--url-tags", args.url_tags]
    if args.template_url is not None:
        child_args += ["--template-url", args.template_url]
    if args.headline is not None:
        child_args += ["--headline", args.headline]
    if args.cta is not None:
        child_args += ["--cta", args.cta]
    if args.message is not None:
        child_args += ["--message", args.message]
    if args.message_file is not None:
        path = ctx.resolve_input(args.message_file)
        if not path.is_file():
            raise ctx.MetaOpsError(f"--message-file not found: {path}")
        child_args += ["--message-file", str(path)]
    if args.description is not None:
        child_args += ["--description", args.description]
    if args.caption is not None:
        child_args += ["--caption", args.caption]
    if args.link is not None:
        child_args += ["--link", args.link]
    if args.image_hash is not None:
        child_args += ["--image-hash", args.image_hash]
    if args.enhancements_off:
        child_args.append("--enhancements-off")
    if args.allow_disapproved:
        child_args.append("--allow-disapproved")
    child_args += ["--confirm", TAGS_CONFIRM, "--expected-account", account]
    if args.dry_run:
        child_args.append("--dry-run")
    if getattr(args, "validate_only", False):
        child_args.append("--validate-only")
    if getattr(args, "sourcing_mode", "drop") != "drop":
        child_args += ["--sourcing-mode", args.sourcing_mode]
    return _run_child(
        ctx, args, "edit tags", "edit_tags.py", child_args, "edited",
        next_action=(
            "Name macros ({{campaign.name}}, {{adset.name}}, {{ad.name}}) resolve from a "
            "first-publish snapshot (04-mass-launch-api.md), so renaming an object never reaches "
            "the tracker; id macros are unaffected. Skipped ads were not cloned - see each row's "
            "reason. Text/image/link/headline/CTA edits send the ad back to review; ads that were "
            "rejected (DISAPPROVED or with ad_review_feedback) are skipped unless --allow-disapproved."
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
    if args.ids is not None and args.all_adsets:
        raise ctx.MetaOpsError("pick one scope: --ids or --all-adsets")
    if args.mode == "pause" and not args.ids and not args.all_adsets:
        raise ctx.MetaOpsError(
            "--mode pause needs an explicit scope: --ids a,b (only those objects) or --all-adsets "
            "(every object at --level, no id filter)"
        )
    if args.confidence is not None and not 0 < args.confidence < 1:
        raise ctx.MetaOpsError(f"--confidence must be strictly between 0 and 1 (e.g. 0.95), got {args.confidence}")
    if args.impressions_floor is not None and args.impressions_floor <= 0:
        raise ctx.MetaOpsError("--impressions-floor must be a positive integer")
    if args.time_preset is not None and not args.time_preset.strip():
        raise ctx.MetaOpsError("--time-preset is empty; pass LIFETIME, LAST_7D, ... or drop the flag")
    child_args = [
        "--account", account, "--target-minor", str(args.target_minor),
        "--event", args.event, "--level", args.level, "--rungs", args.rungs,
        "--mode", args.mode, "--prefix", args.prefix,
    ]
    if args.ids:
        child_args += ["--ids", args.ids]
    if args.all_adsets:
        child_args.append("--all-adsets")
    if args.time_preset is not None:
        child_args += ["--time-preset", args.time_preset]
    if args.impressions_floor is not None:
        child_args += ["--impressions-floor", str(args.impressions_floor)]
    if args.confidence is not None:
        child_args += ["--confidence", str(args.confidence)]
    if args.schedule is not None:
        child_args += ["--schedule", args.schedule]
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
    if args.live:
        child_args.append("--live")
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
    grp.add_argument("--all", action="store_true",
                     help="every LIVE object at --level in the profile account: ACTIVE, in review, "
                          "WITH_ISSUES, or under a paused parent (kill-switch scope)")
    p.add_argument("--level", choices=["campaign", "adset", "ad"], help="needed with --state / --all")
    p.add_argument("--status", required=True, choices=["ACTIVE", "PAUSED", "DELETED"],
                   help="DELETED is irreversible (--confirm DELETE); allowed with spend (Meta keeps its insights)")
    p.add_argument("--confirm", help=f"literal {RAISE_CONFIRM} for ACTIVE or {PAUSE_CONFIRM} for PAUSED")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(handler=handle_edit_status)

    p = edit_sub.add_parser("budget", help="change daily_budget: raises capped at +20%% and blocked late in "
                                          "the account day, cuts of any size allowed")
    p.add_argument("--ids", required=True, help="comma-separated object ids")
    bgrp = p.add_mutually_exclusive_group(required=True)
    bgrp.add_argument("--budget-minor", type=int, help="new daily_budget, integer minor units")
    bgrp.add_argument("--budget-pct", help="relative change in percent, e.g. +20 or -15 (must be a number)")
    p.add_argument("--force-step", action="store_true",
                   help="bypass the +20%% raise cap and the late-day raise guard (cuts are never guarded)")
    p.add_argument("--confirm", help=f"literal {RAISE_CONFIRM}, required when the change may raise spend")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--validate-only", dest="validate_only", action="store_true",
                   help="dry-run plus a Meta validate_only POST per object: Meta checks the payload, nothing is applied")
    p.set_defaults(handler=handle_edit_budget)

    p = edit_sub.add_parser("rename", help="rename objects: exact name (--name / --set) or prefix/suffix")
    p.add_argument("--ids", help="comma-separated object ids (not needed with --set)")
    p.add_argument("--prefix")
    p.add_argument("--suffix")
    p.add_argument("--name", help="exact new name for the single id in --ids")
    p.add_argument("--set", dest="set_names", action="append", default=[], metavar="ID=NAME",
                   help="exact rename of one object, repeatable, e.g. --set 123=EN0039-<buyer>-1")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--validate-only", dest="validate_only", action="store_true",
                   help="dry-run plus a Meta validate_only POST per object: Meta checks the payload, nothing is applied")
    p.set_defaults(handler=handle_edit_rename)

    p = edit_sub.add_parser("bid", help="change the bid/cost cap (bid_amount) on ad sets (other levels are refused)")
    p.add_argument("--ids", required=True, help="comma-separated ad set ids")
    p.add_argument("--bid-minor", type=int, required=True, help="new bid_amount, integer minor units (cents)")
    p.add_argument("--confirm", help=f"literal {BID_CONFIRM}, required (including --dry-run)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--validate-only", dest="validate_only", action="store_true",
                   help="dry-run plus a Meta validate_only POST per object: Meta checks the payload, nothing is applied")
    p.set_defaults(handler=handle_edit_bid)

    p = edit_sub.add_parser("schedule", help="change start_time/end_time on ad sets (other levels are refused)")
    p.add_argument("--ids", required=True, help="comma-separated ad set ids")
    p.add_argument("--start-time", help="ISO-8601 with UTC offset, e.g. 2026-10-01T08:00:00-07:00")
    p.add_argument("--end-time", help="ISO-8601 with UTC offset; a past time is refused (pause instead)")
    p.add_argument("--confirm", help=f"literal {SCHEDULE_CONFIRM}, required (including --dry-run)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--validate-only", dest="validate_only", action="store_true",
                   help="dry-run plus a Meta validate_only POST per object: Meta checks the payload, nothing is applied")
    p.set_defaults(handler=handle_edit_schedule)

    p = edit_sub.add_parser("ramp", help="one guarded +N%% budget step; wait before the next rung")
    p.add_argument("--ids", required=True, help="comma-separated object ids")
    p.add_argument("--step", required=True, type=int,
                   help="one signed percentage, e.g. 20 (a raise is capped at 20; a cut may be larger)")
    p.add_argument("--confirm", help=f"literal {RAMP_CONFIRM}, required")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(handler=handle_edit_ramp)

    p = edit_sub.add_parser(
        "targeting", help="read-modify-write a narrow targeting change across many adsets"
    )
    grp = p.add_mutually_exclusive_group(required=True)
    grp.add_argument("--ids", help="comma-separated ad set ids")
    grp.add_argument("--state", help="launch.py state file; adset ids are pulled from it")
    grp.add_argument("--all", action="store_true",
                     help="every ACTIVE ad set in the profile account (effective_status ACTIVE only)")
    p.add_argument("--user-os", dest="user_os", help="comma-separated OS list, e.g. iOS,Android")
    p.add_argument("--publisher-platforms", dest="publisher_platforms", help="e.g. facebook,instagram (must include instagram)")
    p.add_argument("--facebook-positions", dest="facebook_positions", help="e.g. feed,story,facebook_reels")
    p.add_argument("--instagram-positions", dest="instagram_positions", help="e.g. stream,story,reels")
    p.add_argument("--device-platforms", dest="device_platforms", help="e.g. mobile or mobile,desktop")
    p.add_argument("--age-min", dest="age_min", help="minimum age, 13..65")
    p.add_argument("--age-max", dest="age_max", help="maximum age, 13..65")
    p.add_argument("--genders", help="1=male, 2=female, comma-separated")
    p.add_argument("--geo-regions", dest="geo_regions",
                   help="numeric Meta region keys, e.g. 3879 (Oklahoma); replaces the whole geo selection "
                        "(keeps only regions + location_types); refused with --all")
    p.add_argument("--advantage-audience", dest="advantage_audience",
                   help="0 or 1 (1 clamps age_min to <=25 and forces age_max to 65)")
    p.add_argument("--confirm", help=f"literal {TARGETING_CONFIRM}, required (including --dry-run)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--validate-only", dest="validate_only", action="store_true",
                   help="dry-run plus a Meta validate_only POST per object: Meta checks the payload, nothing is applied")
    p.set_defaults(handler=handle_edit_targeting)

    p = edit_sub.add_parser(
        "tags", aliases=["creative"],
        help="rewrite tags and/or ad copy (text, headline, description, CTA, display link, link, image) "
             "on live ads (clone-and-swap creative; copy edits re-open review)",
    )
    grp = p.add_mutually_exclusive_group(required=True)
    grp.add_argument("--ids", help="comma-separated ad ids")
    grp.add_argument("--state", help="launch.py state file; ad ids are pulled from it")
    grp.add_argument("--all", action="store_true",
                     help="every ACTIVE ad in the profile account (effective_status ACTIVE only)")
    p.add_argument("--url-tags", help="new url_tags string for non-catalog creatives")
    p.add_argument("--template-url", help="new template_url_spec.web.url for catalog/product-ad creatives")
    p.add_argument("--headline", help="new headline (link_data.name) for link ads")
    p.add_argument("--cta", help="new CTA type (link_data.call_to_action.type), e.g. SEE_DETAILS")
    tgrp = p.add_mutually_exclusive_group()
    tgrp.add_argument("--message", help="new primary text (link_data.message)")
    tgrp.add_argument("--message-file", dest="message_file", help="UTF-8 file with the new primary text")
    p.add_argument("--description", help='new description; "" removes it')
    p.add_argument("--caption", help='new display link, e.g. example.com; "" removes it')
    p.add_argument("--link", help="new destination URL")
    p.add_argument("--image-hash", dest="image_hash", help="new image hash (from `metaops media`)")
    p.add_argument("--enhancements-off", dest="enhancements_off", action="store_true",
                   help="clone without creative_sourcing_spec: switches off Ads Manager's default enrolments "
                        "(e.g. featured_offering_spec = 'Show spotlights'); re-opens review like any creative edit")
    p.add_argument("--allow-disapproved", dest="allow_disapproved", action="store_true",
                   help="also edit rejected ads: DISAPPROVED or with ad_review_feedback (default: skip them)")
    p.add_argument("--confirm", help=f"literal {TAGS_CONFIRM} (or CREATIVE), required (including --dry-run)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--validate-only", dest="validate_only", action="store_true",
                   help="dry-run plus a Meta validate_only POST of the new creative: nothing is created, the ad is untouched")
    p.add_argument("--sourcing-mode", dest="sourcing_mode", choices=["drop", "opt_out", "flag_only"], default="drop",
                   help="with --enhancements-off: how creative_sourcing_spec is sent (see edit_tags.py)")
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
    p.add_argument("--all-adsets", dest="all_adsets", action="store_true",
                   help="explicit scope for --mode pause without --ids: no id filter, the rules cover every "
                        "object at --level in the account")
    p.add_argument("--prefix", default="LADDER|")
    p.add_argument("--time-preset", dest="time_preset",
                   help="rule time window: LIFETIME (default) sticks on relaunch, LAST_7D avoids that; "
                        "also LAST_3D, TODAY, ...")
    p.add_argument("--impressions-floor", dest="impressions_floor", type=int,
                   help="only judge objects with more than N impressions (gate the verdict on delivery existing)")
    p.add_argument("--confidence", type=float,
                   help="Poisson confidence, default 0.95: 0.90 kills sooner, 0.99 is patient")
    p.add_argument("--schedule", choices=["SEMI_HOURLY", "HOURLY", "DAILY"],
                   help="how often Meta evaluates the rule (default SEMI_HOURLY)")
    p.add_argument("--confirm", help=f"literal {RULES_PAUSE_CONFIRM}, required for --mode pause "
                                     f"(which also needs --ids or --all-adsets)")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(handler=handle_rules_ladder)

    p = rules_sub.add_parser("list", help="list armed rules on the profile account")
    p.set_defaults(handler=handle_rules_list)

    p = rules_sub.add_parser("history", help="read adrules_history for the profile account")
    p.add_argument("--since", help="Unix timestamp or ISO-8601 datetime")
    p.set_defaults(handler=handle_rules_history)

    p = rules_sub.add_parser("execute", help="fire one NOTIFICATION rule and read its history")
    p.add_argument("--rule-id", required=True)
    p.add_argument("--confirm", required=True, help=f"must be literal {RULES_EXECUTE_CONFIRM}")
    p.add_argument("--live", action="store_true",
                   help="also fire a rule that is not a NOTIFICATION (a PAUSE rule pauses real objects)")
    p.set_defaults(handler=handle_rules_execute)

    p = rules_sub.add_parser("delete", help="delete every rule whose name starts with --prefix")
    p.add_argument("--prefix", required=True)
    p.add_argument("--confirm", help=f"literal {RULES_DELETE_CONFIRM}, required")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(handler=handle_rules_delete)

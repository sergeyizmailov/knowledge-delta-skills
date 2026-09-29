#!/usr/bin/env python3
"""Arm the Poisson kill ladder as native automated rules. Math: senior-buyer-ops/04.

    python3 rules.py --account act_1 --target-minor 1200 --event offsite_conversion.fb_pixel_complete_registration \
                     --level ADSET --rungs 0-6 --mode notify --prefix "LADDER|reg|"
    python3 rules.py ... --mode pause --ids 111,222          # the real thing, scoped to ad sets
    python3 rules.py ... --mode pause --all-adsets           # the real thing, no id filter (explicit)
    python3 rules.py ... --ids 111,222                       # scope to specific ad sets
    python3 rules.py --account act_1 --list
    python3 rules.py --account act_1 --execute <rule_id>     # dry-fire one NOTIFICATION rule, read history
    python3 rules.py --account act_1 --execute <rule_id> --live   # fire a rule that is not NOTIFICATION
    python3 rules.py --account act_1 --delete-prefix "LADDER|reg|"
    python3 rules.py --ladder-only --target-minor 1200 --rungs 0-10   # print thresholds, no API

Why a ladder and not "CPA > X → pause": Meta rejects cost/ratio conditions on ADSET/AD-scoped
rules for every action except budget/bid changes (2703/2490336; the message blames the action,
the cause is scope). Spend and conversion COUNT are allowed, so each rung is
`spent > multiplier(k) × target AND <count> < k+1` — and that inversion happens to be the
statistically right test: an on-target asset is silent through 3× target only 5% of the time.

Rung k (95%): 0→3.00× · 1→4.74× · 2→6.30× · 3→7.75× · 5→10.51× · 10→16.96× (computed here
exactly, any confidence). Strictness self-adjusts: with no data you must be 3× over to die, at
10 conversions 70% over is enough.

Platform rules encoded (field-observed, senior-buyer-ops/04):
  · `spent` is in minor units (cents) · `time_preset` LIFETIME matches a cumulative ladder,
    LAST_7D avoids the relaunch-stickiness trap · `attribution_window` is deprecated (error 11)
    · every rule needs entity_type or id · 250 rules per account · SEMI_HOURLY works
  · pausing at ADSET level triggers no creative re-review
  · dry run: create as NOTIFICATION, POST /{rule}/execute, read adrules_history (lags ~1-2 min)

Safety encoded here:
  · a rule name ends in a short hash of its full scope (level, event, ids, time_preset, account
    currency, confidence, mode), so two ladders that differ in scope never share a name and the
    second is never skipped as "already exists". A rule with the SAME name but different filters
    aborts the run before anything is created; an identical one is an idempotent skip. Rules armed
    before the hash existed (name without it) are recognised when their filters are identical.
  · `--mode pause` needs --ids or the explicit --all-adsets: no scope, no unattended pausing
  · `--execute` refuses any rule whose execution_type is not NOTIFICATION unless --live
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time

import graph


def poisson_cdf(k: int, lam: float) -> float:
    return sum(math.exp(-lam) * lam ** i / math.factorial(i) for i in range(k + 1))


def multiplier(k: int, confidence: float = 0.95) -> float:
    """Smallest λ (expected conversions = spend/target) at which observing ≤k is implausible
    at the given confidence, i.e. P(X ≤ k | λ) = 1 - confidence. Bisection, no scipy."""
    lo, hi, alpha = 0.0, 200.0, 1.0 - confidence
    for _ in range(80):
        mid = (lo + hi) / 2
        if poisson_cdf(k, mid) > alpha:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def parse_rungs(text: str) -> list[int]:
    out: list[int] = []
    for part in text.split(","):
        if "-" in part:
            a, b = part.split("-")
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return sorted(set(out))


def ladder(target_minor: int, rungs: list[int], confidence: float) -> list[dict]:
    rows = []
    for k in rungs:
        m = multiplier(k, confidence)
        rows.append({"k": k, "multiplier": round(m, 2), "spend_minor": round(m * target_minor),
                     "actual_cost_x_target": round(m / k, 2) if k else None})
    return rows


def build_rule(name: str, level: str, k: int, spend_minor: int, event: str, mode: str,
               time_preset: str, ids: list[str] | None, impressions_floor: int | None,
               schedule: str) -> dict:
    filters = [{"field": "entity_type", "value": level, "operator": "EQUAL"},
               {"field": "time_preset", "value": time_preset, "operator": "EQUAL"},
               {"field": "spent", "value": spend_minor, "operator": "GREATER_THAN"},
               {"field": event, "value": k + 1, "operator": "LESS_THAN"}]
    if ids:
        filters.insert(1, {"field": "id", "value": ids, "operator": "IN"})
    if impressions_floor:
        filters.append({"field": "impressions", "value": impressions_floor, "operator": "GREATER_THAN"})
    return {
        "name": name,
        "evaluation_spec": {"evaluation_type": "SCHEDULE", "filters": filters},
        "execution_spec": {"execution_type": "PAUSE" if mode == "pause" else "NOTIFICATION"},
        "schedule_spec": {"schedule_type": schedule},
        "status": "ENABLED",
    }


def scope_hash(level: str, event: str, ids: list[str] | None, time_preset: str, currency: str,
               confidence: float, mode: str) -> str:
    """8 hex chars over everything that decides WHAT a ladder rule watches and does."""
    scope = {"level": level, "event": event, "ids": sorted(ids) if ids else None,
             "time_preset": time_preset, "currency": currency or "", "confidence": float(confidence),
             "mode": mode}
    return hashlib.sha256(json.dumps(scope, sort_keys=True).encode("utf-8")).hexdigest()[:8]


def _norm_value(value):
    if isinstance(value, list):
        return sorted(str(v) for v in value)
    return str(value)


def rule_signature(rule: dict) -> tuple:
    """What makes two rules the same: filters (field/operator/value, order-free, Graph may return
    numbers as strings), execution type and schedule type."""
    filters = sorted(
        json.dumps({"field": f.get("field"), "operator": f.get("operator"), "value": _norm_value(f.get("value"))},
                   sort_keys=True)
        for f in ((rule.get("evaluation_spec") or {}).get("filters") or [])
    )
    return (tuple(filters), (rule.get("execution_spec") or {}).get("execution_type"),
            (rule.get("schedule_spec") or {}).get("schedule_type"))


def _same_rule(existing: dict, wanted_payload: dict) -> bool:
    """True when every filter we post is in the existing rule (Graph may add filters of its own to a
    returned rule) and the execution and schedule types match."""
    have, want = rule_signature(existing), rule_signature(wanted_payload)
    return set(want[0]) <= set(have[0]) and have[1:] == want[1:]


def match_existing(library: list[dict], name: str, legacy_name: str, payload: dict) -> str:
    """"none" | "identical" | "different" for a rule about to be created.

    Same name + same signature is an idempotent repeat; same name + different filters is a
    collision that must stop the run (skipping it would leave the operator believing the ladder
    they asked for is armed). A legacy-named rule (armed before names carried the scope hash) only
    counts when its signature is identical."""
    for rule in library:
        if rule.get("name") == name:
            return "identical" if _same_rule(rule, payload) else "different"
    for rule in library:
        if rule.get("name") == legacy_name and _same_rule(rule, payload):
            return "identical"
    return "none"


def list_rules(account: str) -> list[dict]:
    return _page(account, "adrules_library", "id,name,status,evaluation_spec,execution_spec,schedule_spec", "rules")


def needs_ladder(args) -> bool:
    """A ladder is built only for --ladder-only or a create run. --list / --execute /
    --delete-prefix / --history never need --target-minor, with or without --dry-run."""
    return bool(args.ladder_only or not (
        args.list or args.execute or args.delete_prefix or getattr(args, "history", False)
    ))


def history_rows(account: str, since: str | None, rule_id: str | None = None) -> list[dict]:
    rows = _page(account, "adrules_history", "rule_id,evaluation_type,exception_code,results,timestamp", "rules history")
    if rule_id:
        rows = [h for h in rows if str(h.get("rule_id")) == str(rule_id)]
    if since:
        cutoff = dt_parse_since(since)
        rows = [h for h in rows if h.get("timestamp") and float(h["timestamp"]) >= cutoff]
    return rows


def _page(account: str, edge: str, fields: str, context: str) -> list[dict]:
    rows: list[dict] = []
    params: dict = {"fields": fields, "limit": 250}
    path = f"{account}/{edge}"
    while True:
        response = graph.get(path, params=params, context=context)
        rows.extend(response.get("data", []))
        params = graph.next_page_params(response, params)
        if params is None:
            return rows


def dt_parse_since(value: str) -> float:
    """--since as a Unix timestamp, or an ISO-8601 datetime (naive = UTC)."""
    if value.isdigit():
        return float(value)
    import datetime as _dt
    parsed = _dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_dt.timezone.utc)
    return parsed.timestamp()


def require_ids_in_account(ids: list[str], account: str) -> None:
    """Refuse an opaque rule filter that names an object outside this account."""
    expected = graph.normalize_account(account)
    for object_id in ids:
        obj = graph.get(object_id, params={"fields": "id,account_id"}, context="rule target ownership")
        actual = obj.get("account_id")
        if not actual or graph.normalize_account(actual) != expected:
            sys.exit(
                f"rule target {object_id} belongs to {actual or '?'} not {expected}; "
                "refusing cross-profile rule"
            )


def existing_rule_names(account: str) -> set[str]:
    """Names already in the account library. A retry after a transport break
    (outcome_unknown: the POST may have applied before the connection dropped) must
    not blind-post again — it reconciles by name first. Rule names embed the rung
    (k/spend/count/mode), so a name hit is the same rule, not a coincidence."""
    return {str(r.get("name") or "") for r in list_rules(account) if r.get("name")}


def create_one_rule(account: str, name: str, payload: dict) -> str:
    """POST one ladder rung with name-dedup. Returns the rule id (existing or new).

    On outcome_unknown the call may have landed: re-list by name before giving up,
    so a retry never arms a duplicate pause rule (duplicate pause = double money
    action on the same kill condition)."""
    if name in existing_rule_names(account):
        print(f"  = {name} already exists — skipping (dedup by name, no duplicate)")
        existing = [r for r in list_rules(account) if r.get("name") == name]
        return str(existing[0].get("id")) if existing else "existing"
    try:
        resp = graph.post(f"{account}/adrules_library", payload, context=f"rule {name}")
    except graph.GraphError as exc:
        if exc.outcome_unknown and name in existing_rule_names(account):
            print(f"  = {name} appeared after an unknown outcome — reconciled, no retry",
                  file=sys.stderr)
            existing = [r for r in list_rules(account) if r.get("name") == name]
            return str(existing[0].get("id")) if existing else "reconciled"
        raise
    return str(resp["id"])


def main() -> int:
    """Every call of this script rides the rules token (META_TOKEN_RULES, else META_TOKEN when its
    class carries `rules`; tokens.py / graph.resolve_token)."""
    with graph.using_capability("rules"):
        return _main()


def _main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--account", help="act_<id>")
    ap.add_argument("--target-minor", type=int, help="target cost per payout-proxy event, minor units")
    ap.add_argument("--event", default="results",
                    help="count field: results | offsite_conversion.fb_pixel_lead | "
                         "offsite_conversion.fb_pixel_complete_registration | offsite_conversion.fb_pixel_purchase | link_click")
    ap.add_argument("--level", default="ADSET", choices=["CAMPAIGN", "ADSET", "AD"])
    ap.add_argument("--rungs", default="0-6", help="e.g. 0-6 or 0,1,2,3,5,10")
    ap.add_argument("--confidence", type=float, default=0.95, help="0.90 kills sooner, 0.99 is patient")
    ap.add_argument("--mode", choices=["notify", "pause"], default="notify")
    ap.add_argument("--time-preset", default="LIFETIME", help="LIFETIME | LAST_7D | LAST_3D | TODAY …")
    ap.add_argument("--schedule", default="SEMI_HOURLY", choices=["SEMI_HOURLY", "HOURLY", "DAILY"])
    ap.add_argument("--ids", help="scope to these object ids (comma-separated)")
    ap.add_argument("--all-adsets", action="store_true",
                    help="explicit scope for --mode pause without --ids: NO id filter, the rules cover every "
                         "object at --level in the account")
    ap.add_argument("--impressions-floor", type=int, help="gate the verdict on delivery existing")
    ap.add_argument("--prefix", default="LADDER|", help="rule name prefix; {k} available")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--execute", help="rule id: fire now and read adrules_history")
    ap.add_argument("--confirm", help="literal EXECUTE when using --execute")
    ap.add_argument("--live", action="store_true",
                    help="with --execute: also fire a rule whose execution_type is not NOTIFICATION "
                         "(a PAUSE rule pauses objects for real)")
    ap.add_argument("--delete-prefix", help="delete every rule whose name starts with this")
    ap.add_argument("--history", action="store_true", help="read adrules_history for the account")
    ap.add_argument("--since", help="--history filter: Unix timestamp or ISO-8601 datetime")
    ap.add_argument("--ladder-only", action="store_true", help="print thresholds, touch nothing")
    ap.add_argument("--dry-run", action="store_true", help="print payloads, create nothing")
    args = ap.parse_args()

    if needs_ladder(args):
        if not args.target_minor:
            sys.exit("--target-minor is required to build a ladder")
        if not 0 < args.confidence < 1:
            sys.exit(f"--confidence must be strictly between 0 and 1 (e.g. 0.95), got {args.confidence}")
        if not args.ladder_only:
            if args.ids is not None and args.all_adsets:
                sys.exit("pick one scope: --ids or --all-adsets")
            if args.mode == "pause" and not args.ids and not args.all_adsets:
                sys.exit("--mode pause arms unattended pausing and needs an explicit scope: pass --ids "
                         "a,b (only those objects) or --all-adsets (every object at --level, no id filter)")
        rows = ladder(args.target_minor, parse_rungs(args.rungs), args.confidence)
        print(f"ladder @ {args.confidence:.0%}, target {args.target_minor} minor, event {args.event}, {args.level}, {args.time_preset}")
        for r in rows:
            x = f"{r['actual_cost_x_target']}× target" if r["actual_cost_x_target"] else "—"
            print(f"  k={r['k']:<3} spent > {r['spend_minor']:>8}  ({r['multiplier']}×, actual cost at trigger {x})")
        if args.ladder_only:
            print(json.dumps({"schema": "rules.result/v1", "ok": True, "action": "ladder_only",
                              "ladder": rows}, ensure_ascii=False))
            return 0

    if not args.account:
        sys.exit("--account is required")
    account = graph.normalize_account(args.account)

    if args.list:
        rules = list_rules(account)
        for r in rules:
            ex = (r.get("execution_spec") or {}).get("execution_type")
            print(f"  {r['id']}  {r.get('status'):<8} {ex:<12} {r.get('name')}")
        print(json.dumps({"schema": "rules.result/v1", "ok": True, "action": "list",
                          "rules": rules}, ensure_ascii=False))
        return 0

    if args.delete_prefix:
        n = 0
        deleted = []
        for r in list_rules(account):
            if (r.get("name") or "").startswith(args.delete_prefix):
                if args.dry_run:
                    print(f"  would delete {r['id']} {r['name']}")
                else:
                    graph.call("DELETE", r["id"], context="delete rule", idempotent=True)
                    print(f"  deleted {r['id']} {r['name']}")
                deleted.append(r["id"])
                n += 1
        print(f"{n} rule(s)")
        print(json.dumps({"schema": "rules.result/v1", "ok": True, "action": "delete",
                          "dry_run": args.dry_run, "deleted": deleted}, ensure_ascii=False))
        return 0

    if args.history:
        hist = history_rows(account, args.since)
        for h in hist:
            print(json.dumps(h, indent=2))
        print(json.dumps({"schema": "rules.result/v1", "ok": True, "action": "history",
                          "since": args.since, "history": hist}, ensure_ascii=False))
        return 0

    if args.execute:
        if args.confirm != "EXECUTE":
            sys.exit("--execute can trigger a live rule: pass --confirm EXECUTE")
        target = next((rule for rule in list_rules(account) if str(rule.get("id")) == str(args.execute)), None)
        if target is None:
            sys.exit(f"rule {args.execute} is not in {account}'s rules library")
        execution_type = (target.get("execution_spec") or {}).get("execution_type")
        if execution_type != "NOTIFICATION" and not args.live:
            sys.exit(f"rule {args.execute} executes as {execution_type or 'an unknown action'}, not NOTIFICATION: "
                     f"firing it acts on real objects now (a PAUSE rule pauses them). Pass --live to fire it anyway")
        graph.post(f"{args.execute}/execute", {}, context="execute rule", idempotent=True)
        print("  fired; reading history (lags 1-2 min) …")
        time.sleep(20)
        hist = history_rows(account, None, args.execute)
        for h in hist:
            print(json.dumps(h, indent=2))
        print(json.dumps({"schema": "rules.result/v1", "ok": True, "action": "execute",
                          "rule_id": args.execute, "execution_type": execution_type, "live": bool(args.live),
                          "history": hist}, ensure_ascii=False))
        return 0

    ids = [i.strip() for i in args.ids.split(",") if i.strip()] if args.ids else None
    if args.ids and not ids:
        sys.exit("--ids must contain at least one object id")
    if ids:
        require_ids_in_account(ids, account)
    currency = str(graph.get(account, params={"fields": "currency"}, context="account currency").get("currency") or "")
    library = list_rules(account)
    if len(library) + len(rows) > 250:
        sys.exit(f"{len(library)} rules exist; adding {len(rows)} exceeds the 250/account cap")
    scope = scope_hash(args.level, args.event, ids, args.time_preset, currency, args.confidence, args.mode)
    plan = []
    for r in rows:
        legacy_name = f"{args.prefix.replace('{k}', str(r['k']))}k{r['k']}|>{r['spend_minor']}|<{r['k'] + 1}|{args.mode}"
        name = f"{legacy_name}|{scope}"
        payload = build_rule(name, args.level, r["k"], r["spend_minor"], args.event, args.mode,
                             args.time_preset, ids, args.impressions_floor, args.schedule)
        plan.append((name, legacy_name, payload))
    # Collisions are found BEFORE the first POST: the run either arms the whole ladder or none of it.
    clashes = [name for name, legacy_name, payload in plan
               if match_existing(library, name, legacy_name, payload) == "different"]
    if clashes:
        sys.exit(f"rule(s) already exist with the same name but DIFFERENT filters/action: {', '.join(clashes)}. "
                 f"Nothing was created. Delete them (`--delete-prefix`) or use another --prefix; "
                 f"a name is never reused for a rule that watches something else")
    created = []
    skipped: list[str] = []
    for name, legacy_name, payload in plan:
        if args.dry_run:
            if match_existing(library, name, legacy_name, payload) == "identical":
                print(f"  = would skip {name}: an identical rule already exists")
                skipped.append(name)
            else:
                print(f"  would POST /adrules_library {json.dumps(payload)}")
            continue
        # Dedup inside the loop (not just against the pre-fetched library): a rung created
        # earlier in THIS run, or landed during an outcome_unknown break, must not be posted twice.
        current = list_rules(account) if created else library
        state = match_existing(current, name, legacy_name, payload)
        if state == "different":
            sys.exit(f"rule {name} appeared with DIFFERENT filters/action while this run was arming; "
                     f"stopping. Check `rules list` before retrying")
        if state == "identical":
            print(f"  = {name} already exists with identical filters — skipping (idempotent)")
            skipped.append(name)
            continue
        try:
            rule_id = create_one_rule(account, name, payload)
        except graph.GraphError as exc:
            if exc.outcome_unknown:
                print(f"  x {name}: outcome unknown — reconcile `rules list` before retrying "
                      f"(refusing to blind-retry a pause rule)", file=sys.stderr)
            raise
        created.append(rule_id)
        print(f"  + {rule_id}  {name}")
    if created:
        print(f"\n{len(created)} rule(s) armed as {args.mode.upper()}.")
        if args.mode == "notify":
            print("Fire one with --execute <id> and read the history before switching to --mode pause. "
                  "Delete the notify set with --delete-prefix when the pause set is armed.")
        print("LIFETIME sticks on relaunch: a paused ad set keeps its lifetime counts. Duplicate the ad "
              "set (clone.py) or use --time-preset LAST_7D.")
    print(json.dumps({"schema": "rules.result/v1", "ok": True, "action": "create",
                      "dry_run": args.dry_run, "mode": args.mode, "scope_hash": scope, "created": created,
                      "skipped_existing": skipped},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

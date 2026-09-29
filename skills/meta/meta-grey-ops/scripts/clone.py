#!/usr/bin/env python3
"""Duplicate campaigns / ad sets / ads INSIDE an account via the /copies edge.

    python3 clone.py campaign 1234 --times 3 --prefix "S2|" --start 2026-09-04T07:00:00+03:00
    python3 clone.py adset 5678 --into-campaign 9999 --times 2
    python3 clone.py ad 4242 --into-adset 8888 --suffix "-v2"
    python3 clone.py campaign 1234 --dry-run

Cross-account "duplication" is NOT this: hashes, pixels and pages are account-scoped, so a
copy to another account is a rebuild — use bulk.py with the same template. This script is
the autolaunch-SaaS "duplicate ×N" button for the same account.

How it copies (live-verified 2026-09-02, v26.0):
  · `deep_copy=true` is capped — "the total number of ads, ad sets and campaigns copied at
    once must be less than 3" (code 100 / subcode 1885194); on a just-created tree it fails
    with a bare code 1. So a campaign is copied LEVEL BY LEVEL: shallow campaign copy → each
    ad set shallow-copied into it (`campaign_id`) → each ad copied into the new ad set
    (`adset_id`). Same result, no cap.
  · every copy lands PAUSED (status_option=PAUSED) — activation is activate.py's job
  · a DISAPPROVED / WITH_ISSUES ad is never copied: re-uploading a rejected creative into the
    same account is forbidden (operator rule). `campaign` / `adset` skip such ads and list them
    under `skipped` in the result (id, name, reason); `clone ad` on one refuses with exit 1
  · `campaign --times N` is paced exactly like launch.py: one campaign create per
    METAOPS_CREATE_GAP_HOURS (default 3) per ad account, checked before each copy and recorded
    after it (FIELD 2026-09-27 automation ban). Copy 2 of a `--times 2` run therefore stops
    with a pacing message unless METAOPS_PACE_OVERRIDE=1 (only if the operator explicitly asks)
  · a copied ad set keeps the source attribution_spec (immutable, 1504040); pass --start to
    refresh start_time on every copied ad set so the clone does not start in dead hours
  · rename via rename_options so the tracker split stays readable (03 → Naming); Meta
    appends " — Копия"/" – Copy" itself when NO_RENAME is used
  · /copies is not retried on transport failure (a copy may have applied); every id is
    printed and written to --json so nothing is lost
  · objects still IN_PROCESS (seconds after create) reject copies — wait for PAUSED
  · response keys seen live 2026-09-02: `copied_campaign_id` (campaign), `copied_adset_id`
    (ad set); the ad-level key `copied_ad_id` and the `ad_object_ids` fallback are from the
    reference, not yet observed (ad copies hit the rate limit that day)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile

import graph

UNCOPYABLE_STATUSES = {"ARCHIVED", "DELETED"}
# Ads Graph would copy but the operator rule forbids: a rejected creative must not be
# re-uploaded into the account that got it rejected.
REJECTED_AD_STATUSES = {"DISAPPROVED", "WITH_ISSUES"}


def load_clone_state(path: str | None) -> dict:
    """Resume log for /copies: {completed: {n: out}, in_flight: {n: label}}.

    /copies is NOT retried on transport failure (a copy may have applied), so a
    break with outcome_unknown leaves the copy's fate unknown. The next run with
    the same --state must NOT blind-post again — it stops and tells the operator
    to reconcile in Ads Manager. Without --state the script keeps its legacy
    behaviour (every id printed to --json, manual reconcile)."""
    if not path or not os.path.exists(path):
        return {"completed": {}, "in_flight": {}}
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        return {"completed": {}, "in_flight": {}}
    data.setdefault("completed", {})
    data.setdefault("in_flight", {})
    return data


def save_clone_state(path: str, data: dict) -> None:
    parent = os.path.dirname(path) or "."
    os.makedirs(parent, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".clone-state.", dir=parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(graph.redact(json.dumps(data, indent=2)))
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def rename_options(args, n: int) -> dict:
    if args.prefix or args.suffix:
        return {"rename_strategy": "ONLY_TOP_LEVEL_RENAME",
                "rename_prefix": (args.prefix or "").replace("{n}", str(n)),
                "rename_suffix": (args.suffix or "").replace("{n}", str(n))}
    return {"rename_strategy": "NO_RENAME"}


def copy_obj(obj_id: str, payload: dict, dry: bool, label: str) -> str | None:
    payload = dict(payload, status_option="PAUSED")
    # SDK 26.0.1's Ad.create_copy has no deep_copy parameter; campaigns/ad sets do.
    if label != "ad":
        payload["deep_copy"] = False
    if dry:
        print(f"  would POST /{obj_id}/copies {json.dumps(payload, ensure_ascii=False)}")
        return None
    r = graph.post(f"{obj_id}/copies", payload, context=f"copy {label} {obj_id}")
    new_id = r.get("copied_campaign_id") or r.get("copied_adset_id") or r.get("copied_ad_id")
    if not new_id:
        ids = r.get("ad_object_ids") or []
        new_id = next((x.get("copied_id") for x in ids if x.get("source_id") == obj_id), None)
    if not new_id:
        raise SystemExit(f"copy of {obj_id} returned no id: {json.dumps(r)[:300]}")
    return new_id


def _edge_rows(path: str, params: dict, context: str) -> list[dict]:
    rows = []
    while True:
        resp = graph.get(path, params=params, context=context)
        rows.extend(resp.get("data", []))
        params = graph.next_page_params(resp, params)
        if params is None:
            return rows


_PARENT_FILTER = {"adsets": "campaign.id", "ads": "adset.id"}


def children(edge: str, obj_id: str, account: str | None = None) -> list[dict]:
    """Children of a campaign (adsets) or an ad set (ads).

    Field 2026-09-29, CF1: `{adset}/ads` and `{campaign}/ads` answered EMPTY (or one row) for ads that
    `act_ID/ads` lists, so a clone driven by the per-parent edge alone copied ad sets with no ads. When the
    account is known the account-level edge is read too, filtered by the parent id, and the union is used;
    a difference is printed."""
    fields = {"fields": "id,name,status,effective_status", "limit": 200}
    rows = _edge_rows(f"{obj_id}/{edge}", dict(fields), edge)
    if not account or edge not in _PARENT_FILTER:
        return rows
    flt = json.dumps([{"field": _PARENT_FILTER[edge], "operator": "IN", "value": [obj_id]}])
    flat = _edge_rows(f"{graph.normalize_account(account)}/{edge}", dict(fields, filtering=flt), f"{edge} (account edge)")
    seen = {r["id"] for r in rows}
    extra = [r for r in flat if r["id"] not in seen]
    if extra:
        print(f"  ! {obj_id}/{edge} listed {len(rows)} but the account edge lists {len(rows) + len(extra)}: "
              f"using both (the per-parent edge is unreliable on this account)", file=sys.stderr)
    return rows + extra


def row_statuses(row: dict) -> set[str]:
    return {str(row.get(key) or "").upper() for key in ("status", "effective_status")}


def skip_reason(row: dict, label: str) -> str | None:
    """Why this entity must not be copied, or None. Deleted/archived rows Graph refuses on
    /copies; rejected ads (DISAPPROVED / WITH_ISSUES) it would accept but the operator rule
    forbids."""
    statuses = row_statuses(row)
    if statuses & UNCOPYABLE_STATUSES:
        return sorted(statuses & UNCOPYABLE_STATUSES)[0]
    if label == "ad" and statuses & REJECTED_AD_STATUSES:
        return sorted(statuses & REJECTED_AD_STATUSES)[0]
    return None


def split_copyable(rows: list[dict], label: str) -> tuple[list[dict], list[dict]]:
    """(copyable rows, skipped records). A skipped record is {kind, id, name, reason}."""
    out: list[dict] = []
    skipped: list[dict] = []
    for row in rows:
        reason = skip_reason(row, label)
        if reason is None:
            out.append(row)
            continue
        skipped.append({"kind": label, "id": row.get("id"), "name": row.get("name"), "reason": reason})
        note = (" - a rejected creative is never re-uploaded into the same account (operator rule)"
                if reason in REJECTED_AD_STATUSES else "")
        print(f"  ! skipping {label} {row.get('id')}: {reason}{note}")
    return out, skipped


def copyable(rows: list[dict], label: str) -> list[dict]:
    """Skip entities which Graph will refuse on /copies (or the operator rule forbids)
    rather than aborting a whole tree."""
    return split_copyable(rows, label)[0]


def require_expected_account(obj_id: str, expected_account: str | None) -> dict | None:
    """Object ids are opaque; prove the source/explicit destination belongs to the profile.
    Returns the node it read (id, account_id, status, effective_status), or None when no
    account binding was requested."""
    if not expected_account:
        return None
    obj = graph.get(
        obj_id, params={"fields": "id,account_id,status,effective_status"},
        context=f"clone ownership {obj_id}",
    )
    actual = obj.get("account_id")
    if not actual or graph.normalize_account(actual) != graph.normalize_account(expected_account):
        raise SystemExit(
            f"{obj_id} belongs to {actual or '?'} not {expected_account}; refusing cross-profile clone"
        )
    statuses = {str(obj.get(key) or "").upper() for key in ("status", "effective_status")}
    if statuses & UNCOPYABLE_STATUSES:
        raise SystemExit(f"{obj_id} is {sorted(statuses & UNCOPYABLE_STATUSES)[0]}; refusing to copy it")
    return obj


def source_ad_rejection(ad_id: str, node: object) -> dict | None:
    """`clone ad`: a skipped-record for a DISAPPROVED / WITH_ISSUES source ad, else None.
    Reuses the node require_expected_account already read; otherwise reads status itself."""
    if not isinstance(node, dict) or "effective_status" not in node:
        node = graph.get(ad_id, params={"fields": "id,name,status,effective_status"},
                         context=f"clone source ad {ad_id}")
    reason = skip_reason(node, "ad")
    if reason is None or reason not in REJECTED_AD_STATUSES:
        return None
    return {"kind": "ad", "id": ad_id, "name": node.get("name"), "reason": reason}


def campaign_account(args, node: object) -> str:
    """The ad account a campaign copy will be created in (for pacing): the metaops profile
    binding when given, else the source campaign's own account_id."""
    if args.expected_account:
        return graph.normalize_account(args.expected_account)
    account = node.get("account_id") if isinstance(node, dict) else None
    if not account:
        account = graph.get(args.id, params={"fields": "id,account_id"},
                            context=f"clone account {args.id}").get("account_id")
    if not account:
        raise SystemExit(f"cannot read the ad account of campaign {args.id}; refusing an unpaced clone")
    return graph.normalize_account(account)


def created_ids(out: dict) -> list[str]:
    """Every real id recorded for one copy (campaign/adset/ad, scalar or list)."""
    ids: list[str] = []
    for key, value in out.items():
        if key == "skipped":  # report records, not created objects
            continue
        for item in value if isinstance(value, list) else [value]:
            if item:
                ids.append(str(item))
    return ids


def copy_campaign_tree(cid: str, args, n: int, out: dict, account: str | None = None) -> None:
    new_c = copy_obj(cid, {"rename_options": rename_options(args, n)}, args.dry_run, "campaign")
    out["campaign"] = new_c
    print(f"  + campaign {cid} → {new_c or '<dry>'}")
    if new_c and account and not args.dry_run:
        # Same as launch.py: the create counts the moment it lands, even if a child copy
        # below fails, so the next campaign create on this account waits out the gap.
        graph.record_campaign_create(account)
    for aset in copyable(children("adsets", cid, account), "adset"):
        payload = {"campaign_id": new_c or "<new-campaign>", "rename_options": {"rename_strategy": "NO_RENAME"}}
        if args.start:
            payload["start_time"] = args.start
        if args.end:
            payload["end_time"] = args.end
        new_a = copy_obj(aset["id"], payload, args.dry_run, "adset")
        out.setdefault("adsets", []).append(new_a)
        print(f"    + adset {aset['id']} {aset.get('name', '')[:40]} → {new_a or '<dry>'}")
        ads, skipped = split_copyable(children("ads", aset["id"], account), "ad")
        if skipped:
            out.setdefault("skipped", []).extend(skipped)
        for ad in ads:
            new_ad = copy_obj(ad["id"], {"adset_id": new_a or "<new-adset>",
                                         "rename_options": {"rename_strategy": "NO_RENAME"}},
                              args.dry_run, "ad")
            out.setdefault("ads", []).append(new_ad)
            print(f"      + ad {ad['id']} {ad.get('name', '')[:40]} → {new_ad or '<dry>'}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kind", choices=["campaign", "adset", "ad"])
    ap.add_argument("id")
    ap.add_argument("--times", type=int, default=1)
    ap.add_argument("--prefix", help="rename prefix on the top object; {n} = copy index")
    ap.add_argument("--suffix", help="rename suffix on the top object; {n} = copy index")
    ap.add_argument("--into-campaign", help="adset copies: target campaign id")
    ap.add_argument("--into-adset", help="ad copies: target ad set id")
    ap.add_argument("--start", help="ISO8601 start_time for copied ad sets (never 00:00 for conversions)")
    ap.add_argument("--end", help="ISO8601 end_time for copied ad sets")
    ap.add_argument("--expected-account", help="internal metaops profile binding for opaque object ids")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", help="write all new ids here")
    ap.add_argument("--state", help="resume file: retrying with the same path never re-posts "
                    "a copy whose outcome is unknown (no duplicates after a transport break)")
    args = ap.parse_args()

    source_node = require_expected_account(args.id, args.expected_account)
    for destination in (args.into_campaign, args.into_adset):
        if destination:
            require_expected_account(destination, args.expected_account)

    if args.kind == "ad":
        rejected = source_ad_rejection(args.id, source_node)
        if rejected:
            print(f"  x ad {args.id} is {rejected['reason']}: refusing to copy it - a rejected "
                  "creative is never re-uploaded into the same account (operator rule)",
                  file=sys.stderr)
            print(json.dumps({"schema": "clone.result/v1", "ok": False, "dry_run": args.dry_run,
                              "kind": args.kind, "source_id": args.id, "times": args.times,
                              "completed": 0, "results": [], "skipped": [rejected]},
                             ensure_ascii=False))
            return 1

    if args.kind != "ad" and not args.start and not args.dry_run:
        print("  ! no --start: copies inherit the source start_time, which may be in the past → "
              "they would begin immediately on activation. Pass --start.", file=sys.stderr)

    results = []
    failed = False
    stopped: str | None = None
    pace_account: str | None = None
    clone_state = load_clone_state(getattr(args, "state", None))
    for n in range(1, args.times + 1):
        key = str(n)
        if not args.dry_run and key in clone_state.get("completed", {}):
            out = clone_state["completed"][key]
            print(f"  = copy {n} already completed — skipping (resume from --state, no duplicate)")
            results.append(out)
            continue
        if not args.dry_run and key in clone_state.get("in_flight", {}):
            print(f"  x copy {n} was attempted and its outcome is unknown "
                  f"(state {args.state}). An object may exist in the account. Reconcile in "
                  f"Ads Manager, then clear in_flight.{key} or reuse the recorded id — "
                  f"refusing to blind-retry /copies.", file=sys.stderr)
            results.append({})
            failed = True
            break
        if args.kind == "campaign" and pace_account is None:
            pace_account = campaign_account(args, source_node)  # also feeds children() (dry-run included)
        if args.kind == "campaign" and not args.dry_run:
            # launch.py's rule: one campaign create per METAOPS_CREATE_GAP_HOURS per account.
            # Checked BEFORE the in_flight marker is written, so a refusal leaves nothing to
            # reconcile; recorded in copy_campaign_tree once the campaign copy lands.
            try:
                graph.check_campaign_create_pace(pace_account)
            except graph.PacingError as exc:
                stopped = f"pacing: {exc}"
                print(f"  x copy {n} not started: {exc}", file=sys.stderr)
                failed = True
                break
        out: dict = {}
        if not args.dry_run and getattr(args, "state", None):
            clone_state.setdefault("in_flight", {})[key] = f"{args.kind}:{args.id}"
            save_clone_state(args.state, clone_state)
        try:
            if args.kind == "campaign":
                copy_campaign_tree(args.id, args, n, out, pace_account)
            elif args.kind == "adset":
                payload = {"rename_options": rename_options(args, n)}
                if args.into_campaign:
                    payload["campaign_id"] = args.into_campaign
                if args.start:
                    payload["start_time"] = args.start
                adset_account = campaign_account(args, source_node)
                new_a = copy_obj(args.id, payload, args.dry_run, "adset")
                out["adset"] = new_a
                print(f"  + adset {args.id} → {new_a or '<dry>'}")
                ads, skipped = split_copyable(children("ads", args.id, adset_account), "ad")
                if skipped:
                    out.setdefault("skipped", []).extend(skipped)
                for ad in ads:
                    new_ad = copy_obj(ad["id"], {"adset_id": new_a or "<new-adset>",
                                                 "rename_options": {"rename_strategy": "NO_RENAME"}},
                                      args.dry_run, "ad")
                    out.setdefault("ads", []).append(new_ad)
                    print(f"    + ad {ad['id']} → {new_ad or '<dry>'}")
            else:
                payload = {"rename_options": rename_options(args, n)}
                if args.into_adset:
                    payload["adset_id"] = args.into_adset
                out["ad"] = copy_obj(args.id, payload, args.dry_run, "ad")
                print(f"  + ad {args.id} → {out['ad'] or '<dry>'}")
        except graph.GraphError as e:
            print(f"  x copy {n} stopped: {e}", file=sys.stderr)
            if e.code == 1 or e.subcode == 99:
                print("    code 1 / sub 99 here has meant: source still IN_PROCESS (just created) — "
                      "wait a minute and retry", file=sys.stderr)
            if e.outcome_unknown and getattr(args, "state", None):
                print(f"    outcome unknown — copy {n} may have applied; kept in "
                      f"in_flight.{key}, will not blind-retry", file=sys.stderr)
            elif getattr(args, "state", None) and not args.dry_run and not created_ids(out):
                # Known rejection and no sub-copy of this tree exists: nothing to reconcile,
                # so clear the marker and let the next run retry this copy cleanly.
                clone_state.get("in_flight", {}).pop(key, None)
                save_clone_state(args.state, clone_state)
                print(f"    nothing was created for copy {n}; in_flight.{key} cleared, safe "
                      f"to re-run", file=sys.stderr)
            elif getattr(args, "state", None):
                # Known rejection: nothing was created by THIS call, but earlier
                # sub-copies in this tree exist — keep the marker so the retry
                # reconciles instead of duplicating the parents.
                print(f"    kept in in_flight.{key}: earlier sub-copies exist "
                      f"({created_ids(out)}); reconcile before retrying", file=sys.stderr)
            results.append(out)
            failed = True
            break
        if not args.dry_run and getattr(args, "state", None):
            clone_state.get("in_flight", {}).pop(key, None)
            clone_state.setdefault("completed", {})[key] = out
            save_clone_state(args.state, clone_state)
        results.append(out)
    if args.json:
        # Atomic + 0o600 like the resume state: a crash must not leave half a result.
        parent = os.path.dirname(args.json) or "."
        os.makedirs(parent, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".clone-json.", dir=parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(graph.redact(json.dumps(results, indent=2)))
            os.chmod(tmp, 0o600)
            os.replace(tmp, args.json)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
    if not args.dry_run:
        print("\nAll copies PAUSED. Copies have no spec, so activate.py (which needs a spec'd verify "
              "receipt) does not apply: check them in Ads Manager, then run metaops edit status "
              "--ids <ids> --status ACTIVE --confirm SPEND.")
    skipped_all: list[dict] = []
    for result in results:
        for record in result.get("skipped", []) if isinstance(result, dict) else []:
            if record not in skipped_all:
                skipped_all.append(record)
    summary = {"schema": "clone.result/v1", "ok": not failed, "dry_run": args.dry_run,
               "kind": args.kind, "source_id": args.id, "times": args.times,
               "completed": len(results), "results": results, "skipped": skipped_all}
    if stopped:
        summary["stopped"] = stopped
    print(json.dumps(summary, ensure_ascii=False))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

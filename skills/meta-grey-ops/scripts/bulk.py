#!/usr/bin/env python3
"""Internal bulk implementation for workspace-bound metaops.

accounts.json — one row per target, everything the template leaves as REPLACE_ME:

    [
      {"account_id": "act_1", "page_id": "111", "pixel_id": "999",
       "instagram_user_id": "auto", "tag": "J41-16"},
      {"account_id": "act_2", "page_id": "222", "pixel_id": "999", "tag": "J41-17",
       "overrides": {"campaign": {"daily_budget_minor": 6000}}}
    ]

Per account this script: substitutes account/page/pixel/IG, expands `{tag}` in every name
(campaign name = account tag is the tracker mapping contract, meta-grey-ops/03), applies
`overrides` (deep-merge), writes the resolved spec below workspace `.metaops/bulk/`,
then runs launch.run() with its own state file. One account failing does not stop the
others; the summary at the end names which trees exist and which need reconciling.

Rules this enforces:
  · the whole batch is dry-run before ANY account is built (--dry-run first is mandatory;
    a real run refuses to start unless a matching dry-run state marker exists)
  · same template + same account twice → resumes from state, never duplicates
  · one creative per account is the cross-account rule (03) — the template may name
    per-account media via `media` keys in the account row; identical creatives across
    accounts are allowed but WARNED about
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import pathlib
import sys
import tempfile
from typing import Any

import launch

BULK_DIR = os.environ.get("METAOPS_BULK_DIR", os.path.join(launch.STATE_DIR, "bulk"))


def atomic_write_text(path: pathlib.Path, text: str) -> None:
    """Crash-safe write with 0o600: mkstemp in the target dir + chmod + os.replace.

    A bare write_text can leave a half-written spec/marker after a crash, and a
    world-readable state file leaks account topology. Same contract as
    metaops.atomic_json / metaops.state_lock (0o600)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def deep_merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def expand_tags(obj: Any, tag: str) -> Any:
    if isinstance(obj, str):
        return obj.replace("{tag}", tag)
    if isinstance(obj, dict):
        return {k: expand_tags(v, tag) for k, v in obj.items()}
    if isinstance(obj, list):
        return [expand_tags(v, tag) for v in obj]
    return obj


def apply_media(spec: dict, media: dict) -> dict:
    """Per-account media: {"<ad name>": {"video_id": ..., "image_hash": ...}} — hashes are
    account-scoped (04 → Media), so a shared template cannot carry them."""
    for aset in spec["adsets"]:
        for ad in aset["ads"]:
            m = media.get(ad["name"])
            if m:
                ad["creative"].update(m)
    return spec


def resolve(template: dict, row: dict, run: str) -> tuple[dict, str]:
    tag = str(row.get("tag") or row["account_id"].replace("act_", ""))
    spec = copy.deepcopy(template)
    for key in ("account_id", "page_id", "pixel_id", "instagram_user_id"):
        if key in row:
            spec[key] = row[key]
    if row.get("overrides"):
        spec = deep_merge(spec, row["overrides"])
    if row.get("media"):
        spec = apply_media(spec, row["media"])
    spec = expand_tags(spec, tag)
    spec["run_id"] = f"{run}-{tag}"

    out_dir = pathlib.Path(BULK_DIR) / run
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{tag}.json"
    atomic_write_text(path, json.dumps(spec, indent=2, ensure_ascii=False))
    return launch.load_spec(str(path)), str(path)


def unresolved(spec: dict) -> list[str]:
    hits: list[str] = []

    def walk(o, trail):
        if isinstance(o, str) and "REPLACE_ME" in o:
            hits.append(trail)
        elif isinstance(o, dict):
            for k, v in o.items():
                walk(v, f"{trail}.{k}")
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{trail}[{i}]")

    walk(spec, "spec")
    return hits


def creative_fingerprints(spec: dict) -> set[str]:
    out = set()
    for aset in spec["adsets"]:
        for ad in aset["ads"]:
            c = ad["creative"]
            out.add(json.dumps({k: c.get(k) for k in ("video_id", "image_hash", "message", "headline")},
                               sort_keys=True))
    return out


def template_creative_kinds(template: dict) -> set[str]:
    return {(ad.get("creative") or {}).get("kind", "link_image")
            for aset in template.get("adsets") or [] for ad in aset.get("ads") or []}


def inputs_hash(template: dict, rows: list, only: set | None) -> str:
    """Fingerprint of everything a build depends on. The dry-run marker stores it, so a
    template/accounts edit after the dry run (budget, URL, creative, a new row) invalidates
    the marker instead of letting the old approval cover new inputs."""
    blob = json.dumps({"t": template, "r": rows, "only": sorted(only) if only else None},
                      sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def marker_stale(marker: pathlib.Path, inputs_sha: str) -> str | None:
    """None when the marker is valid for these inputs, else the reason."""
    if not marker.exists():
        return "No dry-run marker"
    try:
        data = json.loads(marker.read_text())
    except ValueError:
        return "Unreadable dry-run marker"
    if not isinstance(data, dict) or data.get("inputs_sha") != inputs_sha:
        return "Template/accounts changed since the dry run (marker hash mismatch)"
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--template", required=True)
    ap.add_argument("--accounts", required=True)
    ap.add_argument("--run", help="batch name; default = template basename")
    ap.add_argument("--only", help="comma-separated account_ids to include")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true", help="run verify.py on each built tree")
    ap.add_argument("--dlo-tested", action="store_true",
                    help="required for a real run of a DLO/catalog template on >1 account: you built ONE "
                         "such ad with launch.py, read it back, and it passed (04 → DLO)")
    args = ap.parse_args()

    with open(args.template, encoding="utf-8") as fh:
        template = json.load(fh)
    with open(args.accounts, encoding="utf-8") as fh:
        rows = json.load(fh)
    if not isinstance(rows, list) or not rows:
        sys.exit("accounts.json must be a non-empty list")
    for row in rows:
        launch.graph.require_write_authority(
            "POST", f"{launch.graph.normalize_account(row.get('account_id', ''))}/campaigns"
        )
    run = args.run or os.path.splitext(os.path.basename(args.template))[0]
    only = {launch.graph.normalize_account(a) for a in args.only.split(",") if a.strip()} if args.only else None
    if only:
        known = {launch.graph.normalize_account(r.get("account_id", "")) for r in rows}
        if not only & known:
            sys.exit(f"--only matched none of the accounts.json rows: {sorted(only)} vs {sorted(known)}")

    marker = pathlib.Path(BULK_DIR) / run / ".dry-run-ok"
    inputs_sha = inputs_hash(template, rows, only)
    if not args.dry_run:
        stale = marker_stale(marker, inputs_sha)
        if stale:
            sys.exit(f"{stale} for batch '{run}'. Run with --dry-run first; a batch is never built "
                     f"before every account's spec validated against the CURRENT template and accounts.")

    kinds = template_creative_kinds(template)
    risky = kinds & {"dlo", "catalog_collection", "catalog_single", "catalog_carousel"}
    if risky and not args.dry_run and len(rows) > 1 and not args.dlo_tested:
        sys.exit(f"Template uses {sorted(risky)} creatives on {len(rows)} accounts. A dry run cannot "
                 "prove the objective/creative combination is accepted (04 → DLO). Build ONE such ad "
                 "with launch.py, verify it, then re-run with --dlo-tested.")

    seen_fps: dict[str, str] = {}
    results: list[tuple[str, str, str]] = []
    statuses: set[str] = set()
    for row in rows:
        acct = launch.graph.normalize_account(row["account_id"])
        row["account_id"] = acct
        if only and acct not in only:
            continue
        print(f"\n=== {acct} ===")
        try:
            spec, path = resolve(template, row, run)
        except SystemExit as e:
            results.append((acct, "SPEC ERROR", str(e)))
            print(f"  x spec: {e}", file=sys.stderr)
            continue
        left = unresolved(spec)
        if left:
            results.append((acct, "SPEC ERROR", f"REPLACE_ME left at {left}"))
            print(f"  x unresolved placeholders: {left}", file=sys.stderr)
            continue
        for fp in creative_fingerprints(spec):
            if fp in seen_fps and seen_fps[fp] != acct:
                print(f"  ! identical creative also launched on {seen_fps[fp]} — one creative = one "
                      f"account (03); both hit the same auction pool", file=sys.stderr)
            seen_fps.setdefault(fp, acct)

        state_path = os.path.join(launch.STATE_DIR, f"{spec['run_id']}.json")
        print(f"  spec  → {path}\n  state → {state_path}")
        try:
            state = launch.State(state_path)
            launch.run(spec, state, args.dry_run)
            results.append((acct, "DRY OK" if args.dry_run else "BUILT", state_path))
            statuses.add(spec["create_status"])
        except (SystemExit, launch.graph.GraphError, OSError, ValueError) as e:
            # SpecError is a SystemExit; a bare GraphError (account read, PBIA lookup) or an
            # unreadable state file must fail THIS account only, not the whole batch.
            detail = launch.graph.redact(str(e))
            results.append((acct, "FAILED", f"{detail} (state {state_path})"))
            print(f"  x {acct}: {detail}", file=sys.stderr)
            continue
        if args.verify and not args.dry_run:
            import subprocess
            rc = subprocess.call([sys.executable, str(pathlib.Path(__file__).with_name("verify.py")),
                                  "--state", state_path, "--spec", path])
            results[-1] = (acct, "BUILT+VERIFIED" if rc == 0 else "BUILT, VERIFY FAILED", state_path)

    print("\n=== batch summary ===")
    for acct, status, detail in results:
        print(f"  {acct:<22} {status:<22} {detail}")
    failed = [r for r in results if r[1] not in ("DRY OK", "BUILT", "BUILT+VERIFIED")]

    if args.dry_run and not failed and results:
        atomic_write_text(
            marker, json.dumps({"inputs_sha": inputs_sha, "accounts": [r[0] for r in results]})
        )
        build = "PAUSED" if statuses == {"PAUSED"} else "ACTIVE (spends on create)"
        print(f"\nDry run passed for {len(results)} account(s): campaigns and creatives validated by "
              "the API, ad sets and ads locally (parents do not exist yet; the real run probes them). "
              f"Re-run without --dry-run to build {build}.")
    elif not args.dry_run and not failed:
        if statuses == {"PAUSED"}:
            print(f"\n{len(results)} tree(s) built PAUSED. Return to metaops for verification and "
                  f"per-account activation. Nothing spends until then.")
        else:
            print(f"\n{len(results)} tree(s) built and LIVE: campaigns, ad sets and ads ACTIVE "
                  f"(reused campaigns keep their status). Spend has started — run metaops "
                  f"verify/status on each tree now.")
    if failed:
        print(f"\n{len(failed)} account(s) need attention. Trees that did build are intact — "
              f"fix the failed rows and re-run; built accounts resume from state.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

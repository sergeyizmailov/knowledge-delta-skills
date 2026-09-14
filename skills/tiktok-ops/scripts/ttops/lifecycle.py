"""The launch lifecycle: doctor -> plan -> apply -> verify -> activate.

Two invariants this module exists to enforce:

1. Everything is created DISABLED. TikTok's ``operation_status`` defaults to
   ENABLE; omitting it creates a live, spending campaign. Activation is a
   separate command behind an explicit confirmation.
2. A successful create is not proof the object holds what you sent. TikTok
   ignores unknown keys and fills enum defaults silently, so ``verify`` reads
   every object back and diffs it before ``activate`` will run.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import time

from . import money, spec as spec_mod
from .api import TikTokError, TransportError
from .workspace import sha256_obj

DOCTOR_TTL_SECONDS = int(os.environ.get("TTOPS_DOCTOR_TTL", "86400"))   # 24h
VERIFY_TTL_SECONDS = int(os.environ.get("TTOPS_VERIFY_TTL", "3600"))    # 1h


def _now():
    return int(time.time())


def _iso(ts=None):
    return _dt.datetime.fromtimestamp(ts or _now(), _dt.timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# State: an append-safe record of what we tried and what came back.
# ---------------------------------------------------------------------------

class State:
    def __init__(self, path):
        self.path = path
        if os.path.exists(path):
            with open(path) as fh:
                self.data = json.load(fh)
        else:
            self.data = {"created": _iso(), "objects": {}, "in_flight": {}, "receipts": {}}

    def save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(self.data, fh, indent=2, sort_keys=True)
        os.replace(tmp, self.path)

    def mark_in_flight(self, key, payload):
        # Written BEFORE the POST. If the process dies mid-create we know an
        # object may exist, so the next run reconciles instead of duplicating.
        self.data["in_flight"][key] = {"at": _iso(), "payload_sha": sha256_obj(payload)}
        self.save()

    def clear_in_flight(self, key):
        self.data["in_flight"].pop(key, None)
        self.save()

    def record(self, key, obj):
        self.data["objects"][key] = obj
        self.data["in_flight"].pop(key, None)
        self.save()

    def get(self, key):
        return self.data["objects"].get(key)

    def receipt(self, name, payload):
        self.data["receipts"][name] = dict(payload, at=_now(), at_iso=_iso())
        self.save()

    def receipt_valid(self, name, ttl, **must_match):
        r = self.data["receipts"].get(name)
        if not r:
            return False, f"no {name} receipt — run `ttops {name}` first"
        age = _now() - int(r.get("at", 0))
        if age > ttl:
            return False, f"{name} receipt is {age}s old (max {ttl}s) — re-run `ttops {name}`"
        for key, value in must_match.items():
            if r.get(key) != value:
                return False, (f"{name} receipt was made for {key}={r.get(key)!r}, "
                               f"not {value!r} — re-run `ttops {name}`")
        return True, None


class Lock:
    """One writer per state file. A stale lock is reported, never silently removed."""

    def __init__(self, path):
        self.path = path + ".lock"
        self.fd = None

    def __enter__(self):
        try:
            self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(self.fd, json.dumps({"pid": os.getpid(), "at": _iso()}).encode())
        except FileExistsError:
            try:
                with open(self.path) as fh:
                    holder = fh.read()
            except OSError:
                holder = "<unreadable>"
            raise RuntimeError(
                f"Another ttops process owns this state: {holder}\n"
                f"Lock file: {self.path}\n"
                "Confirm no launcher is running before removing it. Removing a live lock "
                "is how you get duplicate campaigns."
            )
        return self

    def __exit__(self, *exc):
        if self.fd is not None:
            os.close(self.fd)
            try:
                os.unlink(self.path)
            except OSError:
                pass
        return False


# ---------------------------------------------------------------------------
# doctor — prove access before anything is built
# ---------------------------------------------------------------------------

def doctor(client, profile, state, *, check_pixel=True):
    """Read-only access preflight.

    **It does not prove you can write.** TikTok offers no validate-only write probe,
    so the first proof that the token's role can create objects is the first create —
    which is why `apply` builds everything DISABLED. Do not read a green doctor as
    write permission; the role matrix in `tiktok-ads/02` governs that, and an
    Operator can read everything here and still be unable to create an ad.
    """
    advertiser_id = profile["advertiser_id"]
    checks = []

    def check(name, fn, fatal=True):
        try:
            detail = fn()
            checks.append({"check": name, "ok": True, "detail": detail})
            return detail
        except (TikTokError, TransportError) as exc:
            checks.append({"check": name, "ok": False, "fatal": fatal,
                           "error": str(exc),
                           "code": getattr(exc, "code", None)})
            return None

    # 1. Is the token real, and which advertisers does it actually cover?
    authorized = check(
        "token_advertisers",
        lambda: [a.get("advertiser_id") for a in
                 (client.get("/oauth2/advertiser/get/", {}) or {}).get("list", [])],
    )
    if authorized is not None:
        ok = advertiser_id in authorized
        checks.append({
            "check": "advertiser_authorized_for_token", "ok": ok, "fatal": True,
            "detail": f"{advertiser_id} {'is' if ok else 'is NOT'} in the token's advertiser list "
                      f"({len(authorized)} authorized)",
        })

    # 2. Account identity: currency and timezone are permanent and drive all math.
    info = check(
        "advertiser_info",
        lambda: (client.get("/advertiser/info/",
                            {"advertiser_ids": [advertiser_id]}) or {}).get("list", [{}])[0],
    )
    if info:
        live_currency = info.get("currency")
        live_tz = info.get("timezone") or info.get("display_timezone")
        checks.append({
            "check": "currency_matches_workspace",
            "ok": (live_currency or "").upper() == profile["currency"].upper(),
            "fatal": True,
            "detail": f"account={live_currency} workspace={profile['currency']}",
        })
        checks.append({
            "check": "timezone_matches_workspace",
            "ok": str(live_tz) == str(profile["timezone"]),
            "fatal": False,
            "detail": f"account={live_tz} workspace={profile['timezone']} "
                      "(timezone is permanent; every daily number is in it)",
        })
        status = info.get("status")
        verdict = ADVERTISER_STATUS.get(str(status).upper()) if status else None
        checks.append({
            "check": "account_status",
            # Only STATUS_ENABLE can serve ads. Reporting ok:True regardless means a
            # suspended or unverified account passes preflight and fails at spend.
            "ok": verdict == "OK",
            "fatal": verdict in ("CLOSED", "PUNISHED", "REJECTED"),
            "detail": {"status": status,
                       "meaning": ADVERTISER_STATUS_TEXT.get(str(status).upper(),
                                                             "unknown status value"),
                       "role": info.get("role"),
                       "name": info.get("name"), "country": info.get("country"),
                       "rejection_reason": info.get("rejection_reason")},
        })

    # 3. Money: delivery stops dead at zero balance on prepay, with no grace.
    check("balance",
          lambda: client.get("/advertiser/balance/get/",
                             {"advertiser_ids": [advertiser_id]}),
          fatal=False)

    # 4. Pixel attached to THIS account — sharing it to the BC is not the same thing.
    if check_pixel and profile.get("pixel_id"):
        def _pixel():
            data = client.get("/pixel/list/", {"advertiser_id": advertiser_id,
                                               "page_size": 100}) or {}
            ids = {str(p.get("pixel_id")) for p in data.get("pixels", data.get("list", []))}
            codes = {str(p.get("pixel_code")) for p in data.get("pixels", data.get("list", []))}
            want = str(profile["pixel_id"])
            if want not in ids and want not in codes:
                raise TransportError(
                    f"pixel {want} is not on advertiser {advertiser_id}. Being shared to the "
                    "Business Center is NOT the same as being linked to this ad account."
                )
            return f"pixel {want} linked to this ad account"
        check("pixel_linked_to_account", _pixel, fatal=True)

    # 5. Identity — Spark/organic identities are authorized by their owner and revocable.
    if profile.get("identity_id"):
        check("identity_visible",
              lambda: client.get("/identity/get/",
                                 {"advertiser_id": advertiser_id,
                                  "identity_type": profile.get("identity_type", "TT_USER")}),
              fatal=False)

    fatal_failures = [c for c in checks if not c["ok"] and c.get("fatal")]
    ok = not fatal_failures
    if ok:
        state.receipt("doctor", {"advertiser_id": advertiser_id,
                                 "currency": profile["currency"],
                                 "profile": profile["_name"]})
    return {"ok": ok, "checks": checks,
            "receipt_written": ok,
            "advertiser_id": advertiser_id}


# ---------------------------------------------------------------------------
# plan — snapshot a validated, normalised spec
# ---------------------------------------------------------------------------

def plan(client, profile, state, spec_obj, plan_dir):
    ok, why = state.receipt_valid("doctor", DOCTOR_TTL_SECONDS,
                                  advertiser_id=profile["advertiser_id"],
                                  profile=profile["_name"])
    if not ok:
        raise RuntimeError(f"Refusing to plan: {why}")

    normalized = spec_mod.normalize(spec_obj, profile)
    plan_obj = {
        "schema": "ttops.plan/v1",
        "created": _iso(),
        "profile": profile["_name"],
        "advertiser_id": profile["advertiser_id"],
        "currency": profile["currency"],
        "timezone": profile["timezone"],
        "spec_sha": sha256_obj(spec_obj),
        "plan": normalized,
    }
    plan_obj["plan_sha"] = sha256_obj(normalized)
    os.makedirs(plan_dir, exist_ok=True)
    name = f"{_dt.datetime.now().strftime('%Y%m%dT%H%M%S')}-{normalized['campaign']['campaign_name'][:40]}"
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in name)
    path = os.path.join(plan_dir, safe + ".json")
    with open(path, "w") as fh:
        json.dump(plan_obj, fh, indent=2, sort_keys=True)

    return {
        "ok": True,
        "plan_path": path,
        "plan_sha": plan_obj["plan_sha"],
        "budgets": spec_mod.budget_summary(normalized),
        "total_daily": money.describe(spec_mod.total_daily(normalized), profile["currency"]),
        "objects": {
            "campaign": 1,
            "adgroups": len(normalized["adgroups"]),
            "ads": sum(len(a["creatives"]) for a in normalized["adgroups"]),
        },
        "note": "Nothing has been created. All objects will be created DISABLED.",
    }


# ---------------------------------------------------------------------------
# apply — create everything, paused, resumable
# ---------------------------------------------------------------------------

def apply(client, profile, state, plan_obj):
    ok, why = state.receipt_valid("doctor", DOCTOR_TTL_SECONDS,
                                  advertiser_id=profile["advertiser_id"],
                                  profile=profile["_name"])
    if not ok:
        raise RuntimeError(f"Refusing to apply: {why}")
    if plan_obj["advertiser_id"] != profile["advertiser_id"]:
        raise RuntimeError(
            f"Plan targets advertiser {plan_obj['advertiser_id']} but profile "
            f"{profile['_name']} is {profile['advertiser_id']}. Refusing."
        )

    if state.data["in_flight"]:
        raise RuntimeError(
            "State has in-flight creates whose outcome is unknown:\n  "
            + "\n  ".join(state.data["in_flight"])
            + "\nA create whose connection dropped may have applied. Check the account in "
              "Ads Manager, record the real IDs in the state file, then re-run. Never retry "
              "blindly — that is how you get duplicates."
        )

    p = plan_obj["plan"]
    created = {"campaign": None, "adgroups": [], "ads": []}
    advertiser_id = p["advertiser_id"]

    # -- campaign
    camp_key = "campaign:" + p["campaign"]["campaign_name"]
    existing = state.get(camp_key)
    if existing:
        campaign_id = existing["campaign_id"]
    else:
        state.mark_in_flight(camp_key, p["campaign"])
        data = client.post("/campaign/create/", p["campaign"])
        campaign_id = _require_id(data, "campaign_id", "/campaign/create/")
        state.record(camp_key, {"campaign_id": campaign_id,
                                "name": p["campaign"]["campaign_name"]})
    created["campaign"] = campaign_id

    # -- ad groups + ads
    for ag in p["adgroups"]:
        ag_key = f"adgroup:{campaign_id}:{ag['_name']}"
        existing = state.get(ag_key)
        if existing:
            adgroup_id = existing["adgroup_id"]
        else:
            body = dict(ag["payload"], campaign_id=campaign_id)
            state.mark_in_flight(ag_key, body)
            data = client.post("/adgroup/create/", body)
            adgroup_id = _require_id(data, "adgroup_id", "/adgroup/create/")
            state.record(ag_key, {"adgroup_id": adgroup_id, "name": ag["_name"],
                                  "campaign_id": campaign_id})
        created["adgroups"].append({"name": ag["_name"], "adgroup_id": adgroup_id})

        ad_key = f"ads:{adgroup_id}"
        existing = state.get(ad_key)
        if existing:
            created["ads"].extend(existing["ad_ids"])
            continue
        body = spec_mod.ad_payload(advertiser_id, adgroup_id, ag["creatives"])
        state.mark_in_flight(ad_key, body)
        data = client.post("/ad/create/", body)
        ad_ids = ad_ids_from_create(data)
        # Record before judging: the ads exist on TikTok whatever we think of the
        # response, and a re-run must never create them a second time.
        state.record(ad_key, {"ad_ids": ad_ids, "adgroup_id": adgroup_id})
        created["ads"].extend(ad_ids)
        want = len(ag["creatives"])
        if len(ad_ids) != want:
            raise RuntimeError(
                f"/ad/create/ for ad group {adgroup_id} returned {len(ad_ids)} ad id(s) for "
                f"{want} creative(s): {ad_ids or 'none'}. The ads that were created are "
                "recorded and will not be recreated. Reconcile in Ads Manager before "
                "re-running — some creatives may have been rejected at create time."
            )

    state.receipt("apply", {"plan_sha": plan_obj["plan_sha"], "campaign_id": campaign_id})
    return {"ok": True, "created": created, "status": "ALL OBJECTS DISABLED",
            "next": "ttops verify --plan <plan> , then ttops activate"}


# Advertiser Status (doc 1737174886619138). Only STATUS_ENABLE can run ads; everything
# else is a human problem, and three of them are terminal for this account.
ADVERTISER_STATUS = {
    "STATUS_ENABLE": "OK",
    "STATUS_DISABLE": "CLOSED",
    "STATUS_LIMIT": "PUNISHED",
    "STATUS_CONFIRM_FAIL": "REJECTED",
    "STATUS_CONFIRM_FAIL_END": "REJECTED",
    "STATUS_CONFIRM_MODIFY_FAIL": "REJECTED",
    "STATUS_PENDING_CONFIRM": "PENDING",
    "STATUS_PENDING_VERIFIED": "PENDING",
    "STATUS_PENDING_CONFIRM_MODIFY": "PENDING",
    "STATUS_WAIT_FOR_BPM_AUDIT": "PENDING",
    "STATUS_WAIT_FOR_PUBLIC_AUTH": "PENDING",
    "STATUS_SELF_SERVICE_UNAUDITED": "PENDING",
    "STATUS_CONTRACT_PENDING": "PENDING",
}

ADVERTISER_STATUS_TEXT = {
    "STATUS_ENABLE": "Approved — the only status that can serve ads",
    "STATUS_DISABLE": "The ad account has been closed. Nothing you launch here will run",
    "STATUS_LIMIT": "Ad account under punishment. Escalate; do not create objects",
    "STATUS_CONFIRM_FAIL": "Review failed",
    "STATUS_CONFIRM_FAIL_END": "CRM system review failed",
    "STATUS_CONFIRM_MODIFY_FAIL": "Review of modifications failed",
    "STATUS_PENDING_CONFIRM": "Application pending review",
    "STATUS_PENDING_VERIFIED": "Pending verification",
    "STATUS_PENDING_CONFIRM_MODIFY": "Modifications pending review",
    "STATUS_WAIT_FOR_BPM_AUDIT": "Pending CRM system review",
    "STATUS_WAIT_FOR_PUBLIC_AUTH": "Pending corporate bank account authentication",
    "STATUS_SELF_SERVICE_UNAUDITED": "Pending verification of self-service qualifications",
    "STATUS_CONTRACT_PENDING": "Contract has not taken effect",
}


# TikTok caps ID lists in a GET `filtering` block at 100 (return code 40011), and
# page_size at 1,000 on /adgroup/get/ and /ad/get/.
_GET_FILTER_IDS = 100
_PAGE_SIZE = 1000


def _chunks(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def _require_id(data, key, path):
    """Pull an object id out of a create response, or fail loudly.

    A create that returns code 0 with no id leaves an object on TikTok that this
    state file cannot name. Recording ``None`` is worse than failing: a re-run then
    believes the object exists, skips it, and `verify` has nothing to read back.
    """
    value = (data or {}).get(key)
    if value in (None, "", 0):
        raise RuntimeError(
            f"{path} returned success but no {key}. The object may exist on TikTok "
            "and cannot be recorded. Check Ads Manager, write the real id into the "
            "state file, then re-run — do not re-create blindly."
        )
    return str(value)


def ad_ids_from_create(data):
    """Pull ad ids out of a /ad/create/ response.

    TikTok documents ``data.ad_ids`` as an array of **strings** (doc
    1739953377508354). Treating those entries as objects raises AttributeError
    *after* the ads already exist, which is the worst possible moment to crash.
    The ``creatives`` fallback exists because some shopping-ad variants echo the
    creatives back instead.
    """
    ids = data.get("ad_ids")
    out = []
    if isinstance(ids, list):
        for item in ids:
            if isinstance(item, dict):
                value = item.get("ad_id")
            else:
                value = item
            if value not in (None, ""):
                out.append(str(value))
    if out:
        return out
    for item in data.get("creatives") or []:
        if isinstance(item, dict) and item.get("ad_id") not in (None, ""):
            out.append(str(item["ad_id"]))
    return out


# ---------------------------------------------------------------------------
# verify — read every object back and diff it
# ---------------------------------------------------------------------------

# Every field the spec can send is a field that must be diffed. A field that is
# sent but never compared is a silent drift channel: TikTok fills its own default,
# the create returns code 0, and "verify" reports green on a campaign that is not
# the one that was approved. Attribution and bid fields matter most here — both are
# permanent or price-setting, and neither can be fixed by editing afterwards.
_CAMPAIGN_FIELDS = ("objective_type", "budget_mode", "budget", "special_industries",
                    "budget_optimize_on", "app_promotion_type", "virtual_objective_type",
                    "sales_destination", "campaign_product_source", "campaign_type",
                    "catalog_enabled", "is_search_campaign", "app_id",
                    "operation_status")
_ADGROUP_FIELDS = ("optimization_goal", "billing_event", "bid_type", "bid_price",
                   "conversion_bid_price", "deep_bid_type", "deep_cpa_bid", "roas_bid",
                   "budget_mode", "budget", "pacing", "placement_type", "placements",
                   "schedule_type", "schedule_start_time", "schedule_end_time",
                   "pixel_id", "optimization_event", "secondary_optimization_event",
                   "promotion_type", "promotion_target_type", "product_source",
                   "product_set_id", "catalog_id", "store_id", "app_id",
                   "identity_id", "identity_type",
                   # Permanent once set — a wrong one means rebuilding the ad group.
                   "click_attribution_window", "view_attribution_window",
                   "engaged_view_attribution_window", "attribution_event_count",
                   # video_download_disabled is also permanent.
                   "comment_disabled", "video_download_disabled", "share_disabled",
                   "audience_ids", "excluded_audience_ids", "targeting_expansion",
                   "skip_learning_phase", "is_hfss", "is_lhf_compliance",
                   "operation_status")
# The ad is where the money actually points. Destination, creative asset and identity
# are the three that send spend somewhere other than where it was approved to go.
_AD_FIELDS = ("ad_format", "identity_type", "identity_id", "video_id", "image_ids",
              "ad_text", "call_to_action", "call_to_action_id", "landing_page_url",
              "display_name", "page_id", "tiktok_item_id", "music_id",
              "deeplink", "deeplink_type", "impression_tracking_url",
              "click_tracking_url", "utm_params", "item_group_ids",
              "creative_authorized", "creative_auto_enhancement_strategy_list",
              "operation_status")


def _diff(sent, got, fields, label):
    """Compare what was sent against what the platform reports.

    Two outcomes are NOT the same and must not be collapsed:

    * ``DRIFT`` — the platform reports a *different* value. TikTok stored something
      other than what was approved. This is the one that must never pass silently.
    * ``UNCONFIRMED`` — the platform did not report the field at all. Not proof of
      drift, but not verification either, so it is surfaced rather than skipped.
      Collapsing it into "fine" is how a permanent attribution window ends up
      unchecked; collapsing it into DRIFT makes verify cry wolf on every run.
    """
    problems = []
    for field in fields:
        if field not in sent:
            continue
        want, have = sent[field], got.get(field)
        if have is None or have == "":
            problems.append({"object": label, "field": field, "sent": want,
                             "on_platform": None, "severity": "UNCONFIRMED"})
            continue
        if isinstance(want, float) or isinstance(have, float):
            try:
                if abs(float(want) - float(have)) < 0.005:
                    continue
            except (TypeError, ValueError):
                pass
        if isinstance(want, list) and isinstance(have, list):
            if sorted(map(str, want)) == sorted(map(str, have)):
                continue
        if str(want) != str(have):
            problems.append({"object": label, "field": field, "sent": want,
                             "on_platform": have, "severity": "DRIFT"})
    return problems


def verify(client, profile, state, plan_obj):
    p = plan_obj["plan"]
    advertiser_id = p["advertiser_id"]
    problems, checked = [], {"campaign": 0, "adgroups": 0, "ads": 0}

    if state.data["in_flight"]:
        return {"ok": False,
                "reason": "state has in-flight creates; reconcile before verifying",
                "in_flight": list(state.data["in_flight"])}

    camp = state.get("campaign:" + p["campaign"]["campaign_name"])
    if not camp:
        return {"ok": False, "reason": "no campaign in state — run `ttops apply` first"}
    campaign_id = camp["campaign_id"]

    data = client.get("/campaign/get/", {
        "advertiser_id": advertiser_id,
        "filtering": {"campaign_ids": [campaign_id]},
    })
    rows = data.get("list", [])
    if not rows:
        return {"ok": False, "reason": f"campaign {campaign_id} not readable back"}
    problems += _diff(p["campaign"], rows[0], _CAMPAIGN_FIELDS, f"campaign:{campaign_id}")
    checked["campaign"] = 1
    if rows[0].get("operation_status") != "DISABLE":
        problems.append({"object": f"campaign:{campaign_id}", "field": "operation_status",
                         "sent": "DISABLE", "on_platform": rows[0].get("operation_status"),
                         "severity": "SPENDING"})

    adgroup_ids = []
    for ag in p["adgroups"]:
        rec = state.get(f"adgroup:{campaign_id}:{ag['_name']}")
        if not rec:
            problems.append({"object": f"adgroup:{ag['_name']}", "field": "_exists",
                             "sent": "created", "on_platform": "MISSING FROM STATE"})
            continue
        adgroup_ids.append(rec["adgroup_id"])

    if adgroup_ids:
        by_id = {}
        for chunk in _chunks(adgroup_ids, _GET_FILTER_IDS):
            for row in client.paged("/adgroup/get/", {
                "advertiser_id": advertiser_id,
                "filtering": {"adgroup_ids": chunk},
            }, page_size=_PAGE_SIZE):
                by_id[str(row.get("adgroup_id"))] = row
        for ag in p["adgroups"]:
            rec = state.get(f"adgroup:{campaign_id}:{ag['_name']}")
            if not rec:
                continue
            got = by_id.get(str(rec["adgroup_id"]))
            if not got:
                problems.append({"object": f"adgroup:{rec['adgroup_id']}", "field": "_exists",
                                 "sent": "created", "on_platform": "NOT READABLE"})
                continue
            sent = dict(ag["payload"])
            problems += _diff(sent, got, _ADGROUP_FIELDS, f"adgroup:{rec['adgroup_id']}")
            checked["adgroups"] += 1
            if got.get("operation_status") != "DISABLE":
                problems.append({"object": f"adgroup:{rec['adgroup_id']}",
                                 "field": "operation_status", "sent": "DISABLE",
                                 "on_platform": got.get("operation_status"),
                                 "severity": "SPENDING"})

        # Every ad group is read in full. "Verify every object" is the promise this
        # command makes; an unpaginated first page silently keeps that promise for
        # the first 100 and breaks it for the rest.
        # What the plan asked each ad to be, keyed by (adgroup_id, ad_name). The ad is
        # where spend actually points: an unchecked landing_page_url or video_id means
        # verify can pass while the money goes somewhere nobody approved.
        wanted_ads = {}
        for ag in p["adgroups"]:
            rec = state.get(f"adgroup:{campaign_id}:{ag['_name']}")
            if not rec:
                continue
            for creative in ag["creatives"]:
                wanted_ads[(str(rec["adgroup_id"]), creative["ad_name"])] = creative

        seen_ads = set()
        for chunk in _chunks(adgroup_ids, _GET_FILTER_IDS):
            for row in client.paged("/ad/get/", {
                "advertiser_id": advertiser_id,
                "filtering": {"adgroup_ids": chunk},
            }, page_size=_PAGE_SIZE):
                ad_id = str(row.get("ad_id"))
                if ad_id in seen_ads:
                    continue
                seen_ads.add(ad_id)
                checked["ads"] += 1
                label = f"ad:{ad_id}"
                if row.get("operation_status") != "DISABLE":
                    problems.append({"object": label, "field": "operation_status",
                                     "sent": "DISABLE",
                                     "on_platform": row.get("operation_status"),
                                     "severity": "SPENDING"})
                sent = wanted_ads.get((str(row.get("adgroup_id")), row.get("ad_name")))
                if sent is None:
                    problems.append({"object": label, "field": "_unexpected",
                                     "sent": "not in this plan",
                                     "on_platform": row.get("ad_name"),
                                     "severity": "DRIFT"})
                    continue
                problems += _diff(sent, row, _AD_FIELDS, label)

        # The plan knows how many ads it asked for. A shortfall means creatives were
        # rejected at create time or a read did not cover them — either way, not verified.
        expected_ads = sum(len(ag["creatives"]) for ag in p["adgroups"])
        recorded = []
        for ag in p["adgroups"]:
            rec = state.get(f"adgroup:{campaign_id}:{ag['_name']}")
            if not rec:
                continue
            ads_rec = state.get(f"ads:{rec['adgroup_id']}") or {}
            recorded.extend(str(x) for x in (ads_rec.get("ad_ids") or []))
        if len(recorded) != expected_ads:
            problems.append({"object": "ads", "field": "_count",
                             "sent": f"{expected_ads} from the plan",
                             "on_platform": f"{len(recorded)} recorded at create time",
                             "severity": "MISSING"})
        missing = [a for a in recorded if a not in seen_ads]
        if missing:
            problems.append({"object": "ads", "field": "_exists",
                             "sent": ",".join(missing),
                             "on_platform": "NOT READABLE",
                             "severity": "MISSING"})
        if checked["ads"] != expected_ads:
            problems.append({"object": "ads", "field": "_readback_count",
                             "sent": f"{expected_ads} from the plan",
                             "on_platform": f"{checked['ads']} read back",
                             "severity": "MISSING"})

    # UNCONFIRMED means "the platform did not echo this field", not "the platform
    # disagrees". It must be visible — several of those fields are permanent — but it
    # cannot block, or verify would never pass and the gate would be routed around.
    blocking = [x for x in problems if x.get("severity") != "UNCONFIRMED"]
    unconfirmed = [x for x in problems if x.get("severity") == "UNCONFIRMED"]
    ok = not blocking
    if ok:
        state.receipt("verify", {"plan_sha": plan_obj["plan_sha"],
                                 "campaign_id": campaign_id,
                                 "state_sha": sha256_obj(state.data["objects"])})
    note = ("verify reads every object back and diffs every field the spec sent. A "
            "successful create is not proof the object holds what you sent — TikTok "
            "drops unknown keys and fills enum defaults silently.")
    if unconfirmed:
        note += (f" {len(unconfirmed)} field(s) were not echoed by the platform and could "
                 "not be verified either way — listed under `unconfirmed`. Check the "
                 "permanent ones (attribution windows, video_download_disabled) in Ads "
                 "Manager before activating.")
    return {"ok": ok, "checked": checked, "problems": blocking,
            "unconfirmed": unconfirmed, "campaign_id": campaign_id, "note": note}


# ---------------------------------------------------------------------------
# activate — the only command that causes spend
# ---------------------------------------------------------------------------

def activate(client, profile, state, plan_obj, *, confirm_reviewed, confirm_spend):
    if confirm_reviewed != "REVIEWED":
        raise RuntimeError("activate requires --confirm-reviewed REVIEWED")
    if confirm_spend != "SPEND":
        raise RuntimeError("activate requires --confirm SPEND")

    ok, why = state.receipt_valid(
        "verify", VERIFY_TTL_SECONDS,
        plan_sha=plan_obj["plan_sha"],
        state_sha=sha256_obj(state.data["objects"]),
    )
    if not ok:
        raise RuntimeError(
            f"Refusing to activate: {why}. Re-run `ttops verify` immediately before "
            "activation — a receipt older than the TTL, or taken against a different "
            "state, is not evidence about what is live now."
        )

    p = plan_obj["plan"]
    advertiser_id = p["advertiser_id"]
    campaign_id = state.get("campaign:" + p["campaign"]["campaign_name"])["campaign_id"]

    ad_ids, adgroup_ids = [], []
    for ag in p["adgroups"]:
        rec = state.get(f"adgroup:{campaign_id}:{ag['_name']}")
        if not rec:
            continue
        adgroup_ids.append(rec["adgroup_id"])
        ads = state.get(f"ads:{rec['adgroup_id']}")
        if ads:
            ad_ids.extend(ads["ad_ids"])

    steps = []
    # Bottom-up: ads, then ad groups, then campaign. Enabling the campaign last
    # means nothing serves until every child is deliberately on.
    for level, path, ids in (
        ("ad", "/ad/status/update/", ad_ids),
        ("adgroup", "/adgroup/status/update/", adgroup_ids),
        ("campaign", "/campaign/status/update/", [campaign_id]),
    ):
        for batch in _chunks(ids, 20):   # TikTok caps status updates at 20 IDs
            if not batch:
                continue
            body = {"advertiser_id": advertiser_id, "operation_status": "ENABLE"}
            body[{"ad": "ad_ids", "adgroup": "adgroup_ids",
                  "campaign": "campaign_ids"}[level]] = batch
            client.post(path, body)
            steps.append({"level": level, "ids": batch, "status": "ENABLE"})

    state.receipt("activate", {"plan_sha": plan_obj["plan_sha"], "campaign_id": campaign_id})
    return {"ok": True, "activated": steps, "campaign_id": campaign_id,
            "spending": True,
            "next": "Check delivery in 15-40 min. Insights are empty before then — that is "
                    "not a delivery failure."}


def _chunks(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]

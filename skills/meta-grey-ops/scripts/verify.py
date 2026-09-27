#!/usr/bin/env python3
"""Internal read-back verifier for workspace-bound metaops.

A successful mutation is not proof the object holds what you sent: budgets land in
minor units, targeting gets replaced wholesale, and enum defaults fill silently. Objects
are ACTIVE by default (launch.py) — run this right after apply, since spend has already
started; under a spec's create_status: PAUSED override, run it before activate instead.
Exit 1 on any mismatch or any non-deliverable effective status.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone

import graph
import launch

CAMPAIGN_FIELDS = (
    "id,name,objective,status,effective_status,daily_budget,lifetime_budget,"
    "bid_strategy,buying_type,special_ad_categories,is_adset_budget_sharing_enabled"
)
ADSET_FIELDS = (
    "id,name,status,effective_status,optimization_goal,billing_event,bid_strategy,"
    "bid_amount,daily_budget,start_time,end_time,promoted_object,attribution_spec,"
    "targeting,dsa_beneficiary,dsa_payor,destination_type,is_dynamic_creative,"
    "regional_regulated_categories,regional_regulation_identities,daily_min_spend_target,"
    "daily_spend_cap,issues_info"
)
AD_FIELDS = (
    "id,name,status,effective_status,issues_info,conversion_domain,"
    "creative{id,object_story_spec,asset_feed_spec,template_url_spec,url_tags,product_set_id,"
    "degrees_of_freedom_spec,contextual_multi_ads}"
)

# effective_status values that mean "activating will not fix this".
BLOCKING = {"DISAPPROVED", "WITH_ISSUES", "DELETED", "ARCHIVED", "ADSET_DELETED",
            "CAMPAIGN_DELETED", "DISABLED"}
# Expected on a freshly built tree — reported, never counted as a failure. ACTIVE is the
# default create_status (launch.py); PAUSED/ADSET_PAUSED/CAMPAIGN_PAUSED cover the
# create_status: PAUSED override and re-paused objects.
# IN_PROCESS: Meta's transient state right after create (live 2026-09-02, every level of a
# fresh tree) — clears within minutes; not a defect.
EXPECTED = {"ACTIVE", "PAUSED", "ADSET_PAUSED", "CAMPAIGN_PAUSED", "PENDING_REVIEW", "PREAPPROVED", "IN_PROCESS"}


def _as_instant(v):
    """ISO8601 → aware datetime, or None if it is not a timestamp."""
    if not isinstance(v, str):
        return None
    txt = v.strip()
    # Graph returns +0000 / -0700; Python wants +00:00 before 3.11 and accepts both after.
    m = re.match(r"^(.*[+-]\d{2})(\d{2})$", txt)
    if m:
        txt = f"{m.group(1)}:{m.group(2)}"
    try:
        d = datetime.fromisoformat(txt)
    except ValueError:
        return None
    return d if d.tzinfo else None


def _equivalent(expected, actual) -> bool:
    """True when `actual` satisfies everything `expected` asserts."""
    e_dt, a_dt = _as_instant(expected), _as_instant(actual)
    if e_dt and a_dt:
        return abs((e_dt - a_dt).total_seconds()) <= 300
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        # Subset semantics: Graph adds keys of its own; only what the spec set matters.
        return all(_equivalent(v, actual.get(k)) for k, v in expected.items())
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(expected) != len(actual):
            return False
        remaining = list(actual)
        for item in expected:
            match = next((x for x in remaining if _equivalent(item, x)), None)
            if match is None:
                return False
            remaining.remove(match)
        return True
    return str(expected) == str(actual)


class Diff:
    def __init__(self) -> None:
        self.bad = 0

    def check(self, label: str, expected, actual) -> None:
        """Compare semantically, not textually.

        Two things made naive str() comparison produce false MISMATCH on correct builds:
        Graph normalises `start_time` to its own offset (a +03:00 spec comes back as
        +0000 for the same instant), and it returns `targeting` enriched with keys the
        spec never sent. So: timestamps compare as instants, dicts compare only on the
        keys the spec actually asserted, and lists compare order-insensitively."""
        if expected is None:
            return
        ok = _equivalent(expected, actual)
        if not ok:
            self.bad += 1
        mark = "ok  " if ok else "MISMATCH"
        print(f"    {mark}  {label}: expected {expected!r}, got {actual!r}")

    def status(self, label: str, value) -> None:
        """Report an effective_status. Blocking ones fail the run; anything neither
        blocking nor expected-on-a-fresh-tree is surfaced for a human to look at."""
        if value in BLOCKING:
            flag, self.bad = "   <-- BLOCKING, activating will not fix it", self.bad + 1
        elif value in EXPECTED:
            flag = ""
        else:
            flag = "   <-- unexpected on a fresh build, check it"
        print(f"    ..    {label}: {value}{flag}")

    def note(self, label: str, value) -> None:
        print(f"    ..    {label}: {value}")


def normalize_location_types(geo):
    """Graph stores location_types ["home", "recent"] as ["frequently_in", "home", "recent"]
    (field-observed 2026-09-22, v26.0): "living in or recently in" implies "frequently in".
    Mirror that so a correct build does not read back as MISMATCH."""
    if not isinstance(geo, dict):
        return geo
    types = geo.get("location_types")
    if isinstance(types, list) and {"home", "recent"} <= set(types) and "frequently_in" not in types:
        geo = {**geo, "location_types": ["frequently_in", *types]}
    return geo


def _kind_from_creative(story: dict, feed: dict, creative: dict) -> str:
    """Recover the creative kind from what Graph returned, for spec-less runs."""
    if feed.get("link_urls") or feed.get("asset_customization_rules"):
        return "dlo"
    if creative.get("template_url_spec") or story.get("template_data"):
        return "catalog"
    return "link"


def check_destination(d: Diff, want_c: dict | None, creative: dict) -> None:
    """Diff where the ad actually sends traffic.

    Every creative kind stores the destination somewhere else, and reading the wrong
    place fails a correct build:

      link_image / link_video   object_story_spec.{link_data,video_data}.link
      dlo                       asset_feed_spec.link_urls[].website_url — ONE PER LOCALE,
                                and object_story_spec carries no link at all
      catalog_*                 object_story_spec.template_data.link for the storefront,
                                plus template_url_spec.web.url for the per-card click URL

    `want_c` is None when verify runs without --spec: then this reports, never fails —
    including the kind, which is read off the built creative rather than assumed, or a
    spec-less run flags every DLO ad as broken.

    Nothing here is counted twice: when `d.check` had a spec value to compare against, it
    already recorded the failure, so the explanatory line below it is printed only.
    """
    story = creative.get("object_story_spec") or {}
    feed = creative.get("asset_feed_spec") or {}
    strict = want_c is not None
    want_c = want_c or {}
    kind = want_c.get("kind") or _kind_from_creative(story, feed, creative)

    if kind == "dlo":
        got = [u.get("website_url") for u in (feed.get("link_urls") or [])]
        want = [loc.get("link") for loc in want_c.get("locales") or []] or None
        d.check("        destination (per locale)", want, got)
        if want is None:
            print(f"        destination (per locale) {got or 'NONE'}")
        if not got:
            print("        MISSING  asset_feed_spec carries no link_urls")
            if strict and want is None:
                d.bad += 1
        return

    node = story.get("link_data") or story.get("video_data") or story.get("template_data") or {}
    dest = node.get("link") or ((node.get("call_to_action") or {}).get("value") or {}).get("link")
    want = want_c.get("link")
    d.check("        destination", want, dest)
    if want is None:
        print(f"        destination {dest}")
    if not dest:
        # A missing destination is a defect, not a note: it spends money into nothing.
        print("        MISSING  no destination resolved from the creative")
        if strict and want is None:
            d.bad += 1

    if kind.startswith("catalog"):
        got_t = ((creative.get("template_url_spec") or {}).get("web") or {}).get("url")
        want_t = want_c.get("template_url")
        d.check("        template_url_spec.web.url", want_t, got_t)
        if not got_t and want_t is None:
            print("        WARN  no template_url_spec — catalog card clicks resolve their "
                  "URL from the feed and carry no subids")


# Locale GROUP ids that Graph expands into member ids on read-back (04 → DLO): English (All),
# Spanish (All), and the third group seen live. Diffing raw id sets would flag every group.
LOCALE_GROUPS = {1001: {6, 24}, 1002: {7, 23}, 1005: {16, 31}}


def _expand_locales(ids) -> set[int]:
    out: set[int] = set()
    for raw in ids or []:
        try:
            n = int(raw)
        except (TypeError, ValueError):
            continue
        out |= LOCALE_GROUPS.get(n, {n})
    return out


def _label_names(asset: dict) -> set[str]:
    return {str(lab.get("name")) for lab in asset.get("adlabels") or [] if isinstance(lab, dict)}


def _text_for_label(assets, label: str):
    return next((a.get("text") for a in assets or [] if label in _label_names(a)), None)


def check_dlo_feed(d: Diff, wc: dict, feed: dict) -> None:
    """Diff the language rules, not just the body count.

    Per spec locale (matched by label): its rule exists, carries the expected locale ids
    (groups expanded on both sides; the age_min/age_max Graph injects into
    customization_spec are ignored), is_default sits on the right label, and the body/title
    text under that label is what the spec sent. Video ids are re-mapped on GET, so media is
    never compared by id here."""
    locales = wc.get("locales") or []
    rules = feed.get("asset_customization_rules") or []
    d.check("        dlo rules (count)", len(locales), len(rules))
    d.check("        dlo rules is_default (count)", 1, sum(1 for r in rules if r.get("is_default")))
    for loc in locales:
        label = str(loc.get("label"))
        rule = next((r for r in rules if str((r.get("body_label") or {}).get("name")) == label), None)
        if rule is None:
            print(f"        MISMATCH  dlo rule for label {label!r} missing on read-back")
            d.bad += 1
            continue
        got_ids = _expand_locales((rule.get("customization_spec") or {}).get("locales"))
        d.check(f"        dlo[{label}] locales", sorted(_expand_locales(loc.get("ids"))), sorted(got_ids))
        d.check(f"        dlo[{label}] is_default", bool(loc.get("is_default")), bool(rule.get("is_default")))
        d.check(f"        dlo[{label}] body", loc.get("body"), _text_for_label(feed.get("bodies"), label))
        d.check(f"        dlo[{label}] title", loc.get("title"), _text_for_label(feed.get("titles"), label))


def completeness(d: Diff, state: dict, spec: dict | None) -> None:
    """Refuse to bless a tree that did not finish building.

    An in-flight marker means a create's outcome is unknown (transport failure / 5xx without
    a Graph body) and an object may or may not exist — reconcile in Ads Manager first. A
    spec'd run must also hold every ad set and ad the spec describes: a tree that lost its
    ad to a 503 passes every field check and then spends nothing, or on the wrong subset.
    Live 2026-09-02: exactly that happened and the old verify wrote a receipt for it."""
    objects = state["objects"]
    pending = state.get("in_flight") or {}
    if pending:
        print(f"INCOMPLETE  unresolved in-flight creates: {sorted(pending)} — check Ads Manager for "
              f"the object, then put its id under objects.<key> or clear in_flight.<key> and re-run "
              f"launch.py to resume", file=sys.stderr)
        d.bad += 1
    if spec:
        missing = []
        for ai, aset in enumerate(spec["adsets"]):
            if f"adset[{ai}]" not in objects:
                missing.append(f"adset[{ai}]")
            missing += [f"ad[{ai}.{aj}]" for aj in range(len(aset["ads"])) if f"ad[{ai}.{aj}]" not in objects]
        if missing:
            print(f"INCOMPLETE  spec objects not in state: {missing} — re-run launch.py to resume",
                  file=sys.stderr)
            d.bad += 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", required=True)
    ap.add_argument("--spec", help="Diff against the spec that built this run")
    args = ap.parse_args()

    with open(args.state, encoding="utf-8") as fh:
        state = json.load(fh)
    objects = state["objects"]
    spec = launch.load_spec(args.spec) if args.spec else None
    d = Diff()

    completeness(d, state, spec)
    if spec and state.get("spec_sha") and state["spec_sha"] != launch.spec_hash(spec):
        print("MISMATCH  the spec file differs from the one that built this state (spec_sha) — "
              "verify against the spec that was launched", file=sys.stderr)
        d.bad += 1

    campaign_id = objects.get("campaign")
    if not campaign_id:
        sys.exit("state file holds no campaign id — nothing to verify")

    camp = graph.get(campaign_id, params={"fields": CAMPAIGN_FIELDS}, context="verify campaign")
    print(f"campaign {campaign_id}  {camp.get('name')}")
    if spec:
        c = spec["campaign"]
        d.check("objective", c["objective"], camp.get("objective"))
        if spec["budget_mode"] == "CBO":
            d.check("daily_budget (minor)", c["daily_budget_minor"], camp.get("daily_budget"))
            d.check("bid_strategy", c.get("bid_strategy", "LOWEST_COST_WITHOUT_CAP"), camp.get("bid_strategy"))
        elif camp.get("daily_budget"):
            print(f"    MISMATCH  campaign carries a budget ({camp['daily_budget']}) under ABO")
            d.bad += 1
        d.check("special_ad_categories", c["special_ad_categories"], camp.get("special_ad_categories"))
    # A reused campaign (spec.campaign.id) keeps whatever status it already had — nothing to
    # assert. A freshly built one is compared against the spec's create_status: default
    # ACTIVE means an actual PAUSED reads as a MISMATCH (launch.py creates it PAUSED and
    # flips it ACTIVE once the whole tree exists — PAUSED here means that flip never landed);
    # the create_status: PAUSED override means PAUSED is correct and ACTIVE would be the
    # surprise instead.
    if spec and spec.get("campaign", {}).get("id"):
        expected_status = camp.get("status")
    else:
        expected_status = (spec or {}).get("create_status", "ACTIVE")
    d.check("status", expected_status, camp.get("status"))
    d.status("effective_status", camp.get("effective_status"))

    i = 0
    while f"adset[{i}]" in objects:
        adset_id = objects[f"adset[{i}]"]
        a = graph.get(adset_id, params={"fields": ADSET_FIELDS}, context=f"verify adset {i}")
        print(f"\n  adset[{i}] {adset_id}  {a.get('name')}")
        if spec:
            if i >= len(spec.get("adsets") or []):
                print(f"    MISMATCH  state has adset[{i}] but the bound spec has no such ad set")
                d.bad += 1
                i += 1
                continue
            s = spec["adsets"][i]
            d.check("optimization_goal", s["optimization_goal"], a.get("optimization_goal"))
            d.check("billing_event", s.get("billing_event", "IMPRESSIONS"), a.get("billing_event"))
            start_expected = (state.get("start_overrides") or {}).get(f"adset[{i}]", s["start_time"])
            d.check("start_time", start_expected, a.get("start_time"))
            if s.get("end_time"):
                d.check("end_time", s["end_time"], a.get("end_time"))
            # promoted_object: the same precedence launch.py uses (explicit object, else
            # pixel + event). Subset semantics — Graph adds keys of its own.
            if s.get("promoted_object"):
                d.check("promoted_object", s["promoted_object"], a.get("promoted_object"))
            elif spec.get("pixel_id") and s.get("custom_event_type"):
                d.check("promoted_object",
                        {"pixel_id": str(spec["pixel_id"]), "custom_event_type": s["custom_event_type"]},
                        a.get("promoted_object"))
            for key in ("destination_type", "is_dynamic_creative"):
                if s.get(key) is not None:
                    d.check(key, s[key], a.get(key))
            # Whole targeting object, every key the spec asserted (subset semantics per key:
            # Graph enriches with location_types etc., lists compare order-insensitively).
            expected_t = launch.build_targeting(s)
            actual_t = a.get("targeting") or {}
            for key in expected_t:
                want = expected_t[key]
                if key == "geo_locations":
                    want = normalize_location_types(want)
                d.check(f"targeting.{key}", want, actual_t.get(key))
        if spec and spec["budget_mode"] == "ABO":
            d.check("daily_budget (minor)", s["daily_budget_minor"], a.get("daily_budget"))
            d.check("bid_strategy", s.get("bid_strategy", "LOWEST_COST_WITHOUT_CAP"), a.get("bid_strategy"))
            if s.get("bid_amount_minor"):
                d.check("bid_amount (minor)", s["bid_amount_minor"], a.get("bid_amount"))
        elif spec:
            if a.get("daily_budget"):
                print(f"    MISMATCH  ad set carries its own budget ({a['daily_budget']}) under CBO")
                d.bad += 1
            # CBO with a cap strategy (COST_CAP / LOWEST_COST_WITH_BID_CAP) still puts the
            # cap AMOUNT on the ad set (1815857) even though budget/bid_strategy live on
            # the campaign — read it back the same way ABO's bid_amount is diffed above.
            if s.get("bid_amount_minor"):
                d.check("bid_amount (minor)", s["bid_amount_minor"], a.get("bid_amount"))
        # Reading this back is not cosmetic: an unknown key inside attribution_spec is
        # ignored by Graph, so a wrong field name looks like a success and leaves the
        # account default in place. launch.py always sends one unless the spec opted into
        # "account_default", so it is diffed on every spec'd run.
        if spec:
            want = launch.build_attribution(s)
            got = a.get("attribution_spec")
            got_norm = [{"event_type": e.get("event_type"), "window_days": e.get("window_days")}
                        for e in (got or [])]
            if want is None:
                d.note("attribution_spec (account default)", got_norm)
            else:
                d.check("attribution_spec", want, got_norm)
        else:
            d.note("attribution_spec", a.get("attribution_spec"))
        if spec:
            countries = set(((s.get("targeting") or {}).get("geo_locations") or {}).get("countries") or [])
            for key in ("dsa_beneficiary", "dsa_payor"):
                if s.get(key):
                    d.check(key, s[key], a.get(key))
                elif countries & launch.DSA_COUNTRIES:
                    # spec relied on dsa_from_account_defaults: the field must still be non-empty
                    # on the ad set, or the EU ad is non-compliant and passes verify silently.
                    if a.get(key):
                        d.note(f"{key} (from account default)", a.get(key))
                    else:
                        print(f"    MISMATCH  {key} empty on an EU/EEA ad set — account defaults did "
                              "not fill it (Business Settings → default_dsa_*)")
                        d.bad += 1
        if spec:
            # Ad sets and ads are always created by this run (only the campaign can be
            # reused), so their configured status must equal create_status. launch.py never
            # flips them after create — only a reused-free campaign is flipped PAUSED→ACTIVE.
            d.check("status", spec.get("create_status", "ACTIVE"), a.get("status"))
        d.status("effective_status", a.get("effective_status"))
        if a.get("issues_info"):
            print(f"    ISSUES  {a['issues_info']}")
            d.bad += 1

        j = 0
        while f"ad[{i}.{j}]" in objects:
            ad_id = objects[f"ad[{i}.{j}]"]
            ad = graph.get(ad_id, params={"fields": AD_FIELDS}, context=f"verify ad {i}.{j}")
            creative = ad.get("creative") or {}
            story = creative.get("object_story_spec") or {}
            print(f"      ad[{i}.{j}] {ad_id}  {ad.get('name')}")
            print(f"        identity page={story.get('page_id')} ig={story.get('instagram_user_id')}")
            if spec:
                if i >= len(spec.get("adsets") or []) or j >= len(spec["adsets"][i].get("ads") or []):
                    print(f"        MISMATCH  state has ad[{i}.{j}] but the bound spec has no such ad")
                    d.bad += 1
                    j += 1
                    continue
                d.check("        page_id", str(spec.get("page_id")), story.get("page_id"))
                want_ig = spec.get("instagram_user_id")
                if want_ig and want_ig != "auto":
                    d.check("        instagram_user_id", str(want_ig), story.get("instagram_user_id"))
                wc = (spec["adsets"][i]["ads"][j].get("creative") or {})
                node = story.get("link_data") or story.get("video_data") or {}
                if wc.get("kind", "link_image") in ("link_image", "link_video"):
                    d.check("        message", wc.get("message", ""), node.get("message"))
                    headline = node.get("title") if wc.get("kind") == "link_video" else node.get("name")
                    d.check("        headline", wc.get("headline"), headline)
                    d.check("        cta", wc.get("cta", "LEARN_MORE"), (node.get("call_to_action") or {}).get("type"))
                    if wc.get("image_hash"):
                        d.check("        image_hash", wc["image_hash"], node.get("image_hash"))
                    if wc.get("video_id"):
                        d.check("        video_id", wc["video_id"], node.get("video_id"))
                elif wc.get("kind") == "link_carousel":
                    got_cards = node.get("child_attachments") or []
                    want_cards = [{k: v for k, v in {
                        "link": card.get("link", wc.get("link")),
                        "name": card.get("headline"),
                        "image_hash": card.get("image_hash"),
                        "video_id": card.get("video_id")}.items() if v is not None}
                        for card in wc.get("cards") or []]
                    d.check("        cards (count)", len(want_cards), len(got_cards))
                    d.check("        cards", want_cards, got_cards)
                    d.check("        message", wc.get("message", ""), node.get("message"))
                elif wc.get("kind") == "dlo":
                    feed = creative.get("asset_feed_spec") or {}
                    d.check("        dlo bodies (count)", len(wc.get("locales") or []), len(feed.get("bodies") or []))
                    check_dlo_feed(d, wc, feed)
                    if wc.get("ad_format") == "SINGLE_VIDEO":
                        # Video DLO: Graph keeps per-slot generated thumbnails, no feed images,
                        # and re-ids every video on read-back (04) — check slot count only.
                        d.check("        dlo videos (count)", len(wc.get("locales") or []),
                                len(feed.get("videos") or []))
                    else:
                        d.check("        dlo image_hash", wc.get("image_hash"),
                                next((im.get("hash") for im in feed.get("images") or []), None))
                elif str(wc.get("kind", "")).startswith("catalog"):
                    d.check("        product_set_id", str(wc.get("product_set_id")), creative.get("product_set_id"))
                    # Swap-safe texts (launch.py defaults): what the card shows after the swap.
                    td = story.get("template_data") or {}
                    d.check("        message", wc.get("message", "-----"), td.get("message"))
                    d.check("        headline", wc.get("headline", "{{product.name}}"), td.get("name"))
                    if wc.get("kind") == "catalog_carousel" and td.get("description") is None:
                        print("        ..    description: not stored on catalog carousels (cards render per product)")
                    else:
                        d.check("        description", wc.get("description", "{{product.description}}"),
                                td.get("description"))
                    d.check("        cta", wc.get("cta", "LEARN_MORE"), (td.get("call_to_action") or {}).get("type"))
                d.check("        name", spec["adsets"][i]["ads"][j].get("name"), ad.get("name"))
            if not story.get("instagram_user_id"):
                print("        WARN  no instagram_user_id — any IG placement will fail 1772103")
            # Printing it was not verification. The destination is the one field where a
            # wrong value spends real money into the wrong funnel, so diff it.
            want_c = (spec["adsets"][i]["ads"][j].get("creative") or {}) if spec else None
            check_destination(d, want_c, creative)
            want_tags = (want_c.get("url_tags", spec.get("url_tags")) if spec else None)
            if want_tags:
                d.check("        url_tags", want_tags, creative.get("url_tags"))
            else:
                print(f"        url_tags {creative.get('url_tags')}")
            # Multi-advertiser ads. OPT_OUT reads back on template_data/link creatives; on
            # FORMAT_AUTOMATION collection creatives the field is not readable, so the UI
            # checkbox is the only proof — say so instead of passing silently.
            cma = (creative.get("contextual_multi_ads") or {}).get("enroll_status")
            want_multi = bool(want_c.get("multi_advertiser")) if want_c else False
            if cma is None:
                print("        WARN  contextual_multi_ads not readable — confirm the Multi-advertiser "
                      "checkbox is OFF in Ads Manager now (before it spends)")
            elif not want_multi and cma != "OPT_OUT":
                print(f"        MISMATCH  contextual_multi_ads={cma}, expected OPT_OUT")
                d.bad += 1
            else:
                print(f"        ..    contextual_multi_ads {cma}")
            # Advantage+ enhancements: any key left OPT_IN that the spec opted out is a leak.
            feats = ((creative.get("degrees_of_freedom_spec") or {}).get("creative_features_spec") or {})
            opted_in = sorted(k for k, v in feats.items() if (v or {}).get("enroll_status") == "OPT_IN")
            wanted_out = set(launch.DEFAULT_OPT_OUT if not want_c or want_c.get("opt_out_features") is None
                             else want_c.get("opt_out_features") or [])
            leak = [k for k in opted_in if k in wanted_out]
            if leak:
                print(f"        MISMATCH  Advantage+ features still OPT_IN: {leak}")
                d.bad += 1
            else:
                print(f"        ..    enhancements OPT_IN: {opted_in or 'none'}")
            if spec:
                d.check("        status", spec.get("create_status", "ACTIVE"), ad.get("status"))
            d.status("        effective_status", ad.get("effective_status"))
            if ad.get("issues_info"):
                print(f"        ISSUES  {ad['issues_info']}")
                d.bad += 1
            j += 1
        i += 1

    if d.bad:
        print(f"\n{d.bad} problem(s). If this tree is create_status: PAUSED, do NOT activate. "
              "If it is ACTIVE (the default), it is already spending — pause it first "
              "(edit status --confirm PAUSE), diagnose second.", file=sys.stderr)
        return 1
    write_receipt(args.state, args.spec, spec)
    if spec:
        scope = ("the fields listed above (budgets, bid, attribution, targeting, promoted_object, DSA, "
                 "identity, copy/media per creative kind, destination, url_tags, enhancements, "
                 "multi-advertiser, statuses)")
    else:
        scope = "statuses and destinations only (no --spec) — this receipt does NOT satisfy activate.py"
    print(f"\nVerified {scope}; nothing is blocked. Receipt written next to the state file. "
          "Anything the spec did not set was not compared — preview each placement in Ads Manager "
          "(before activate.py under create_status: PAUSED; otherwise it is already live).")
    return 0


def write_receipt(state_path: str, spec_path: str | None, spec: dict | None) -> str:
    """`<state>.verified.json` — proof for activate.py that verify passed on THIS state file.
    The hash is of the state file bytes; a resume that adds objects voids the receipt."""
    with open(state_path, "rb") as fh:
        state_sha = hashlib.sha256(fh.read()).hexdigest()[:16]
    rp = state_path + ".verified.json"
    with open(rp, "w", encoding="utf-8") as fh:
        json.dump({"ok": True, "state_sha": state_sha, "spec": spec_path,
                   "spec_sha": launch.spec_hash(spec) if spec else None,
                   "ts": datetime.now(timezone.utc).isoformat(timespec="seconds")}, fh, indent=1)
    return rp


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Build a campaign from a JSON spec. Dry-run first, ACTIVE by default, resume-safe.

This is an internal implementation invoked by workspace-bound `metaops plan/apply`.
Direct Graph writes are rejected by graph.py.

The LLM writes the spec. This file writes the API calls. That split exists because
every recurring launch bug in this corpus is a payload bug — wrong nesting, wrong
unit, wrong field name, wrong order — and a payload assembled from prose is
re-derived, with fresh odds of being wrong, on every single run.

What this enforces so you cannot forget it:
  · every create is preceded by an `execution_options=['validate_only']` probe on the
    real run. In --dry-run only campaign and creative can be API-validated — ad sets and
    ads reference a parent that does not exist yet, so they are checked locally and
    validated for real at step 5 (that is also where `synchronous_ad_review` runs)
  · every object is created ACTIVE by default — except the campaign, which is created
    PAUSED and flipped ACTIVE in one call once every ad set and ad exists, so a run that
    dies halfway never spends on a partial tree (resume completes the tree, then flips).
    A reused campaign (campaign.id) keeps its status, and because it is already live its
    ad sets are created PAUSED and each one is flipped ACTIVE only after ITS ads exist
    (state.adsets_activated makes the resume skip finished flips). Set spec-level
    `"create_status": "PAUSED"` to keep the old paused-then-activate behavior, with
    activation left to activate.py behind a human
  · the ad account must be account_status=1 (read together with the currency, before any
    create); a disabled / unsettled / closed account is refused with its disable_reason
  · budgets are read from `*_minor` keys and must be int — no float dollars reach Graph
  · `targeting_automation` is nested inside `targeting`, never top-level  (1870227)
  · campaign create → budget/bid PATCH → budget-less adset, in that order  (4834011 / 1885737)
  · `instagram_user_id: "auto"` resolves the Page's PBIA                   (1772103)
  · `attribution_spec` uses `window_days`, not the non-existent `event_window_days`
  · Advantage+ creative features are opted OUT individually — there is no single switch,
    and `adapt_to_placement` is ON unless you name it
  · every created id is written to the state file before the next call, so a crashed
    run resumes instead of duplicating
  · attribution defaults to 1d click / 1d engaged-video-view / 1d view when the spec is
    silent — Meta's own default (7d click) silently inflates every CPL
  · `contextual_multi_ads` (Multi-advertiser ads) is OPT_OUT on every creative
  · `targeting.advantage_audience` must be explicit (v23+ rejects the omission on CREATE)
  · budget mode is CBO (campaign.daily_budget_minor) OR ABO (adsets[].daily_budget_minor),
    never both, never neither
  · EU/EEA geo without `dsa_beneficiary` + `dsa_payor` is rejected locally before Graph does
  · placements: ad set `placements` = "fb_ig_all" | "fb_ig_feeds" expands to explicit
    publisher_platforms + positions (Facebook + Instagram only). Explicit targeting keys win.
    Positions for a platform that is not targeted, or an empty positions list for a targeted
    one, are spec errors; an omitted publisher_platforms is a plan WARNING (= all placements
    incl. Audience Network / Messenger / Threads). Instagram is always required
  · bid policy: `bid_policy: "require_cap"` (campaign, or per ad set) makes a missing cap
    strategy / bid_amount_minor a spec error. Without it an uncapped conversion goal and a
    PURCHASE without explicit `attribution` are plan WARNINGS
  · longread lint: link_* headline > 40 chars and offer/casino words in headline or
    description are WARNINGS; top-level `"lint": "strict"` makes them errors and also requires
    a non-empty headline and message. The message body is never linted
  · `display_link` has nowhere to go on a link_video creative (video_data has no caption):
    error under lint strict, loud warning otherwise
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sys
import tempfile
from typing import Any

import graph

STATE_DIR = os.environ.get("METAOPS_STATE_DIR", ".metaops")

# Default attribution when the spec is silent. Meta's API default (FIELD 2026-09-27: silent
# ad set read back CLICK_THROUGH 7 only; the UI shows 7d click / 1d engage / 1d view),
# which reports more conversions than a 1-day funnel earned and desyncs from the tracker.
# ENGAGED_VIDEO_VIEW is the UI's middle "Engaged view" row; it only fires on >=10s video
# watches, harmless on image ad sets. Set `"attribution": "account_default"` on an ad set
# to send nothing and inherit the account default — then READ IT BACK (verify.py does); no
# ad-account field reliably reports that default (v26.0 reference, verified 2026-09-02).
DEFAULT_ATTRIBUTION = {"click_days": 1, "engaged_video_view_days": 1, "view_days": 1}

# Optimization goals that are not conversions: Meta rejects any view-through / engaged-view
# window for them (code 100 / subcode 1885501, "supported combination ... is (1, 0)").
# LINK_CLICKS verified live 2026-09-02; the rest are the same non-conversion family. When the
# spec is silent, build_attribution sends 1d click only for these instead of 1/1/1. An explicit
# `attribution` object is sent as written — Graph will reject it, which is the right outcome.
CLICK_ONLY_ATTRIBUTION_GOALS = {
    "LINK_CLICKS", "LANDING_PAGE_VIEWS", "REACH", "IMPRESSIONS", "THRUPLAY", "POST_ENGAGEMENT",
    "PAGE_LIKES", "AD_RECALL_LIFT",
    "PROFILE_VISIT", "VISIT_INSTAGRAM_PROFILE", "PROFILE_AND_PAGE_ENGAGEMENT", "REMINDERS_SET",
    "ENGAGED_USERS",
}

# Currencies Meta bills in WHOLE units — no minor-unit offset. For these, `*_minor` keys
# are the plain amount: TWD 300 → 300, not 30000. A verified incident (claude-code#62376,
# 2026): an agent assumed cents on a TWD account and set NT$30,000/day instead of NT$300 —
# 100x overspend. launch.py reads the account currency and prints every budget in major
# units so the operator sees "300 TWD", and refuses to run when spec.currency disagrees
# with the account. Source: Marketing API "Currencies" reference (offset column), re-read
# 2026-09-25: exactly these eleven carry offset 1 (UGX/XAF/XOF are not on that page).
NO_OFFSET_CURRENCIES = {
    "CLP", "COP", "CRC", "HUF", "ISK", "IDR", "JPY", "KRW", "PYG", "TWD", "VND",
}


def currency_offset(code: str) -> int:
    return 1 if code in NO_OFFSET_CURRENCIES else 100


def major(amount_minor: int, code: str) -> str:
    off = currency_offset(code)
    return f"{amount_minor / off:,.2f} {code}" if off == 100 else f"{amount_minor:,} {code}"


# Countries where an ad set must carry DSA beneficiary + payor (EU Digital Services Act).
# Graph rejects the ad set without them; failing locally names the fix instead of a code.
DSA_COUNTRIES = {
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT",
    "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE",  # EU-27
    "IS", "LI", "NO",  # EEA
}

class SpecError(SystemExit):
    pass


# Bid strategies that carry a cap. `bid_policy: "require_cap"` insists on one of these plus a
# bid_amount_minor on every ad set (LOWEST_COST_WITH_MIN_ROAS is a floor, not a cap).
CAP_STRATEGIES = ("COST_CAP", "LOWEST_COST_WITH_BID_CAP")

# Optimization goals that optimize for a conversion (a bid cap is meaningful for them). An ad
# set that carries a custom_event_type is treated as a conversion ad set as well.
CONVERSION_GOALS = {
    "OFFSITE_CONVERSIONS", "CONVERSIONS", "ONSITE_CONVERSIONS", "VALUE", "LEAD_GENERATION",
    "QUALITY_LEAD", "APP_INSTALLS", "IN_APP_VALUE",
}

# Ad set `placements` presets. Each expands to explicit publisher_platforms + positions, so
# nothing is left to Meta's "all placements" default (Audience Network, Messenger, Threads).
# Instagram stays mandatory (operator rule 2026-09-26). Keys that the spec's targeting sets
# itself always win over the preset.
PLACEMENT_PRESETS = {
    "fb_ig_all": {
        "device_platforms": ["mobile"],  # story / reels positions are mobile-only
        "publisher_platforms": ["facebook", "instagram"],
        "facebook_positions": [
            "feed", "instream_video", "marketplace", "story", "search", "biz_disco_feed",
            "facebook_reels", "facebook_reels_overlay", "profile_feed", "notification",
        ],
        "instagram_positions": [
            "stream", "story", "reels", "explore_home", "profile_feed", "ig_search",
        ],
    },
    "fb_ig_feeds": {
        "publisher_platforms": ["facebook", "instagram"],
        "facebook_positions": ["feed"],
        "instagram_positions": ["stream"],
    },
}
# publisher platform -> the targeting key that lists its positions.
POSITION_KEYS = {
    "facebook": "facebook_positions",
    "instagram": "instagram_positions",
    "messenger": "messenger_positions",
    "audience_network": "audience_network_positions",
    "threads": "threads_positions",
}
# Inventory the operator never buys; verify.py fails a read-back that carries any of them
# unless the spec listed it.
UNWANTED_PLATFORMS = ("audience_network", "messenger", "threads")

# Longread lint (the operator, 28/09): no direct offer in the headline / description of a link_*
# creative, and a headline the feed does not cut. The message body is never linted.
LINT_HEADLINE_MAX = 40
LINT_PHRASES = (
    ("welcome bonus", r"welcome\s+bonus"),
    ("get exclusive", r"get\s+exclusive"),
    ("offer valid", r"offer\s+valid"),
    ("valid until", r"valid\s+until"),
    ("play online", r"play\s+online"),
    ("free spins", r"free\s+spins?"),
    ("deposit match", r"deposit\s+match"),
    ("$<amount> ... bonus", r"\$\s?\d[\d,.]*.{0,20}?bonus"),
    ("casino", r"casino"),
    ("jackpot", r"jackpot"),
)
_LINT_RES = tuple((label, re.compile(rx, re.IGNORECASE | re.DOTALL)) for label, rx in LINT_PHRASES)

# Ad account account_status values, Ad Account reference. Only 1 lets ads run.
ACCOUNT_STATUS_NAMES = {
    1: "ACTIVE", 2: "DISABLED", 3: "UNSETTLED", 7: "PENDING_RISK_REVIEW",
    8: "PENDING_SETTLEMENT", 9: "IN_GRACE_PERIOD", 100: "PENDING_CLOSURE", 101: "CLOSED",
    201: "ANY_ACTIVE", 202: "ANY_CLOSED",
}
# disable_reason names as recalled from the Ad Account reference (not re-read on 2026-09-29):
# the numeric code Graph returned is always printed next to the name, trust that one.
DISABLE_REASON_NAMES = {
    0: "NONE", 1: "ADS_INTEGRITY_POLICY", 2: "ADS_IP_REVIEW", 3: "RISK_PAYMENT",
    4: "GRAY_ACCOUNT_SHUT_DOWN", 5: "ADS_AFC_REVIEW", 6: "BUSINESS_INTEGRITY_RAR",
    7: "PERMANENT_CLOSE", 8: "UNUSED_RESELLER_ACCOUNT", 9: "UNUSED_ACCOUNT",
    10: "UMBRELLA_AD_ACCOUNT", 11: "BUSINESS_MANAGER_INTEGRITY_POLICY",
    12: "MISREPRESENTED_AD_ACCOUNT", 13: "AOAB_DESHARE_LEGAL_ENTITY",
    14: "CTX_THREAD_REVIEW", 15: "COMPROMISED_AD_ACCOUNT",
}


# --------------------------------------------------------------------------- state


def spec_hash(spec: dict) -> str:
    """Stable fingerprint of a resolved spec (sorted keys). Stored in the state file so
    verify.py / activate.py can tell that the objects were built from THIS spec."""
    return hashlib.sha256(json.dumps(spec, sort_keys=True, default=str).encode()).hexdigest()[:16]


class State:
    """Resume log. Every id lands here before the next call goes out."""

    def __init__(self, path: str):
        self.path = path
        self.data: dict[str, Any] = {"objects": {}, "in_flight": {}, "errors": []}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                self.data = json.load(fh)

    def get(self, key: str) -> str | None:
        return self.data["objects"].get(key)

    def put(self, key: str, obj_id: str) -> None:
        self.data["objects"][key] = obj_id
        self.data.get("in_flight", {}).pop(key, None)
        self.save()

    def attempt(self, key: str, path: str) -> None:
        """Written before the create POST goes out. If a run dies here, the next run
        sees the marker, refuses to blind-retry, and tells you to reconcile — better a
        stop than a duplicate campaign."""
        pending = self.data.setdefault("in_flight", {})
        if key in pending:
            raise SpecError(
                f"{key} was already attempted and never confirmed (state: {self.path}). "
                f"An object may exist in the account. Check {path} in Ads Manager, then "
                f"either add its id to objects.{key} in the state file or clear "
                f"in_flight.{key} to retry."
            )
        pending[key] = path
        self.save()

    def fail(self, key: str, err: dict, outcome_known: bool = True) -> None:
        """Record a failure. `outcome_known` decides whether the in-flight marker clears.

        Graph answered with a rejection → nothing was created → clear the marker so the
        next run can retry after you fix the spec. The request never reached Graph, or
        the reply was lost → the outcome is genuinely unknown → keep the marker and make
        the next run stop and reconcile. Clearing it in both cases loses the crash guard;
        keeping it in both cases bricks the run on an ordinary validation error."""
        self.data["errors"].append({"key": key, **err})
        if outcome_known:
            self.data.get("in_flight", {}).pop(key, None)
        self.save()

    def save(self) -> None:
        # Atomic + 0o600 like metaops.atomic_json: a crash mid-write must not leave a
        # half-written resume log, and the state file lives next to workspace secrets.
        parent = os.path.dirname(self.path) or "."
        os.makedirs(parent, exist_ok=True)
        payload = graph.redact(json.dumps(self.data, indent=2, default=str))
        fd, tmp = tempfile.mkstemp(prefix=".state.", dir=parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
            os.chmod(tmp, 0o600)
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)


# ---------------------------------------------------------------------- validation


def _int_minor(value: Any, field: str) -> int:
    """Budgets and bids are integer minor units — cents, kuruş, paise.

    A float here is the single most expensive silent bug available: 60.0 dollars
    submitted as `60` is 0.60 in account currency, and the ad set quietly underdelivers
    all day. Reject anything that is not already an int."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise SpecError(
            f"{field} must be an INTEGER in minor units (cents). "
            f"Got {value!r} ({type(value).__name__}). $60.00 → 6000."
        )
    if value <= 0:
        raise SpecError(f"{field} must be > 0, got {value}")
    return value


def load_spec(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        spec = json.load(fh)

    for key in ("account_id", "page_id", "campaign", "adsets"):
        if key not in spec:
            raise SpecError(f"spec is missing required key: {key}")

    if not spec["account_id"].startswith("act_"):
        spec["account_id"] = "act_" + str(spec["account_id"])

    # Default create status is ACTIVE — apply spends the moment the create succeeds. A spec
    # that needs the old review-before-spend window sets create_status: PAUSED at the top
    # level and calls activate.py itself once it is reviewed.
    create_status = spec.get("create_status", "ACTIVE")
    if create_status not in ("ACTIVE", "PAUSED"):
        raise SpecError(
            f"spec.create_status must be \"ACTIVE\" (default) or \"PAUSED\", got {create_status!r}"
        )
    spec["create_status"] = create_status

    # Longread lint level. Read as written, never normalised into the spec: spec_hash covers
    # the loaded spec, and adding a key here would invalidate every state built before it.
    lint = spec.get("lint")
    if lint not in (None, "warn", "strict"):
        raise SpecError(f"spec.lint must be \"strict\" or \"warn\" (default), got {lint!r}")

    camp = spec["campaign"]
    for key in ("name", "objective"):
        if key not in camp:
            raise SpecError(f"campaign is missing required key: {key}")
    if "bid_amount_minor" in camp:
        raise SpecError(
            "campaign.bid_amount_minor is not a campaign field: Graph has no bid_amount on a "
            "campaign. Put the cap amount on EVERY ad set (adsets[i].bid_amount_minor) and the "
            "strategy on campaign.bid_strategy (CBO) or adsets[i].bid_strategy (ABO)."
        )
    _check_bid_policy(camp.get("bid_policy"), "campaign.bid_policy")

    # Budget mode. CBO = the campaign carries daily_budget_minor and ad sets carry none.
    # ABO = every ad set carries its own daily_budget_minor and the campaign carries none.
    # Mixed or absent is a spec bug, not a Graph question.
    cbo = "daily_budget_minor" in camp
    if cbo:
        _int_minor(camp["daily_budget_minor"], "campaign.daily_budget_minor")
    spec["budget_mode"] = "CBO" if cbo else "ABO"
    # Under CBO the campaign carries bid_strategy; a cap strategy still needs its cap
    # AMOUNT on every ad set (1815857) — Graph has nowhere else to put it once the ad sets
    # are budget-less. ABO's equivalent check lives in the per-adset loop below.
    camp_bid_strategy = camp.get("bid_strategy", "LOWEST_COST_WITHOUT_CAP")
    cbo_cap_strategy = cbo and camp_bid_strategy in CAP_STRATEGIES

    if "special_ad_categories" not in camp:
        raise SpecError(
            "campaign.special_ad_categories must be explicit. Use [] for none, or declare "
            "the real category (HOUSING / FINANCIAL_PRODUCTS_SERVICES / EMPLOYMENT / "
            "ISSUES_ELECTIONS_POLITICS / CREDIT / ONLINE_GAMBLING_AND_GAMING / NONE). "
            "A false declaration is a violation, not a bypass."
        )

    if not spec["adsets"]:
        raise SpecError("spec has no adsets")
    for i, aset in enumerate(spec["adsets"]):
        for key in ("name", "optimization_goal", "targeting", "start_time"):
            if key not in aset:
                raise SpecError(f"adsets[{i}] is missing required key: {key}")
        if cbo and ("daily_budget_minor" in aset or "bid_strategy" in aset):
            raise SpecError(
                f"adsets[{i}] carries its own budget/bid_strategy while the campaign has a "
                "budget (CBO). Under CBO the ad set must have neither. For ABO remove "
                "campaign.daily_budget_minor and give EVERY ad set daily_budget_minor. "
                "bid_amount_minor is the one exception — it is allowed under CBO to carry a "
                "cap amount for campaign.bid_strategy=COST_CAP/LOWEST_COST_WITH_BID_CAP."
            )
        # Validated here, before the campaign exists, in BOTH budget modes: a float or a string
        # cap used to surface only inside run(), after the campaign had already been created.
        if "bid_amount_minor" in aset:
            _int_minor(aset["bid_amount_minor"], f"adsets[{i}].bid_amount_minor")
        for money_key in ("daily_min_spend_target", "daily_spend_cap"):
            if aset.get(money_key) is not None:
                _int_minor(aset[money_key], f"adsets[{i}].{money_key}")
        if cbo_cap_strategy and not aset.get("bid_amount_minor"):
            raise SpecError(
                f"adsets[{i}]: campaign.bid_strategy={camp_bid_strategy} under CBO needs a cap "
                f"amount on EVERY ad set (adsets[{i}].bid_amount_minor) — Meta expects the bid "
                "cap per ad set even when the budget lives on the campaign (1815857)."
            )
        if not cbo:
            if "daily_budget_minor" not in aset:
                raise SpecError(
                    f"adsets[{i}] has no daily_budget_minor and the campaign has none either. "
                    "Pick one: campaign.daily_budget_minor (CBO) or a budget on every ad set (ABO)."
                )
            _int_minor(aset["daily_budget_minor"], f"adsets[{i}].daily_budget_minor")
            strat = aset.get("bid_strategy", "LOWEST_COST_WITHOUT_CAP")
            if strat in CAP_STRATEGIES and not aset.get("bid_amount_minor"):
                raise SpecError(f"adsets[{i}].bid_strategy={strat} needs bid_amount_minor (1815857)")
        _check_bid_policy(aset.get("bid_policy"), f"adsets[{i}].bid_policy")
        if bid_policy(spec, aset) == "require_cap":
            eff = camp_bid_strategy if cbo else aset.get("bid_strategy", "LOWEST_COST_WITHOUT_CAP")
            where = "campaign.bid_strategy" if cbo else f"adsets[{i}].bid_strategy"
            if eff not in CAP_STRATEGIES:
                raise SpecError(
                    f"bid_policy=require_cap but {where}={eff} carries no cap. Use COST_CAP or "
                    f"LOWEST_COST_WITH_BID_CAP with adsets[{i}].bid_amount_minor."
                )
            if not aset.get("bid_amount_minor"):
                raise SpecError(
                    f"bid_policy=require_cap but adsets[{i}] has no bid_amount_minor (the cap "
                    "amount must be on every ad set)."
                )
        if not aset.get("ads"):
            raise SpecError(f"adsets[{i}] has no ads")

        has_dlo = any(
            isinstance(ad.get("creative"), dict) and ad["creative"].get("kind") == "dlo"
            for ad in aset["ads"]
            if isinstance(ad, dict)
        )
        if has_dlo and aset.get("is_dynamic_creative") is not False:
            raise SpecError(
                f"adsets[{i}] contains creative.kind=dlo and must explicitly set "
                "is_dynamic_creative: false"
            )

        t = aset["targeting"]
        if "advantage_audience" not in t and "advantage_audience" not in (t.get("targeting_automation") or {}):
            raise SpecError(
                f"adsets[{i}].targeting.advantage_audience must be explicit (true/false). "
                "Since v23.0 Graph rejects an ad set CREATE that omits it for any non-default "
                "targeting, and since v26.0 for HEC-F categories as well."
            )

        # Assemble the whole targeting object now (advantage_audience type, placement presets and
        # consistency, Instagram rule, geo_locations) so a bad spec fails before the campaign exists.
        build_targeting(aset, label=f"adsets[{i}]")

        countries = set((t.get("geo_locations") or {}).get("countries") or [])
        has_b, has_p = bool(aset.get("dsa_beneficiary")), bool(aset.get("dsa_payor"))
        if has_b != has_p:
            raise SpecError(f"adsets[{i}]: dsa_beneficiary and dsa_payor must be set together")
        if countries & DSA_COUNTRIES and not (has_b and has_p) and not spec.get("dsa_from_account_defaults"):
            raise SpecError(
                f"adsets[{i}] targets {sorted(countries & DSA_COUNTRIES)} and must carry "
                "dsa_beneficiary + dsa_payor (EU DSA; Graph error 3858152 otherwise). If the ad "
                "account has default_dsa_beneficiary/default_dsa_payor set (Business Settings), put "
                "\"dsa_from_account_defaults\": true at spec top level to rely on them."
            )

        att = aset.get("attribution")
        if att is not None and att != "account_default" and not isinstance(att, dict):
            raise SpecError(f"adsets[{i}].attribution must be an object or \"account_default\"")

    for _ref, c in _link_creatives(spec):
        resolved_opt_out(c)  # validates creative.opt_in_features / opt_out_features shape
    if lint == "strict":
        problems = lint_findings(spec) + strict_lint_findings(spec)
        if problems:
            raise SpecError(
                "spec.lint=strict rejects this spec:\n  - " + "\n  - ".join(problems)
                + "\nFix the copy, or drop \"lint\": \"strict\" to get these as warnings."
            )

    spec.setdefault("run_id", os.path.splitext(os.path.basename(path))[0])
    return spec


def _check_bid_policy(value: Any, field: str) -> None:
    if value not in (None, "require_cap"):
        raise SpecError(f"{field} must be \"require_cap\" (or omitted), got {value!r}")


def bid_policy(spec: dict, aset: dict) -> str | None:
    """Effective bid policy of one ad set: the ad set's own key, else the campaign's."""
    if aset.get("bid_policy") is not None:
        return aset["bid_policy"]
    return (spec.get("campaign") or {}).get("bid_policy")


def _link_creatives(spec: dict):
    """(location, creative) for every dict creative in the spec, in order."""
    for i, aset in enumerate(spec.get("adsets") or []):
        for j, ad in enumerate(aset.get("ads") or []):
            c = ad.get("creative") if isinstance(ad, dict) else None
            if isinstance(c, dict):
                yield f"adsets[{i}].ads[{j}] ({ad.get('name', '?')})", c


def _banned_phrases(text: Any) -> list[str]:
    if not isinstance(text, str):
        return []
    return [label for label, rx in _LINT_RES if rx.search(text)]


def lint_findings(spec: dict) -> list[str]:
    """Longread copy problems that are warnings by default and errors under lint: strict.

    Applies to link_* creatives only (catalog / DLO texts follow the product or the locale).
    Headline: over 40 chars is cut in the feed. Headline and description: offer / casino
    phrases. The message body is deliberately not linted (the story may mention a bonus)."""
    out: list[str] = []
    for ref, c in _link_creatives(spec):
        if not str(c.get("kind", "link_image")).startswith("link_"):
            continue
        pieces = [("headline", c.get("headline")), ("description", c.get("description"))]
        for n, card in enumerate(c.get("cards") or []):
            if isinstance(card, dict):
                pieces += [(f"cards[{n}].headline", card.get("headline")),
                           (f"cards[{n}].description", card.get("description"))]
        for field, text in pieces:
            if field.endswith("headline") and isinstance(text, str) and len(text) > LINT_HEADLINE_MAX:
                out.append(f"{ref}: {field} is {len(text)} chars (over {LINT_HEADLINE_MAX}, cut in feed): {text!r}")
            hits = _banned_phrases(text)
            if hits:
                out.append(f"{ref}: {field} carries offer/banned wording {hits}: {text!r}")
    return out


def strict_lint_findings(spec: dict) -> list[str]:
    """Extra errors that only lint: strict raises: empty headline / message, dropped display_link."""
    out: list[str] = []
    for ref, c in _link_creatives(spec):
        kind = str(c.get("kind", "link_image"))
        if not kind.startswith("link_"):
            continue
        # Carousels carry their headlines per card; the single-headline rule is image / video.
        if kind in ("link_image", "link_video") and not str(c.get("headline") or "").strip():
            out.append(f"{ref}: headline is empty (Facebook fills it from the page title)")
        if not str(c.get("message") or "").strip():
            out.append(f"{ref}: message is empty")
        if kind == "link_video" and c.get("display_link"):
            out.append(f"{ref}: display_link has no place on a link_video creative (video_data "
                       "has no caption) and would be silently dropped")
    return out


def spec_warnings(spec: dict) -> list[str]:
    """Non-fatal findings of a loaded spec, printed by main() so `metaops plan` shows them.

    Recomputed from the spec on demand; nothing is stored in the spec (it is hashed)."""
    out: list[str] = []
    camp = spec["campaign"]
    cbo = spec.get("budget_mode") == "CBO"
    camp_strategy = camp.get("bid_strategy", "LOWEST_COST_WITHOUT_CAP")
    groups: dict[str, list[int]] = {}

    def add(text: str, i: int) -> None:
        groups.setdefault(text, []).append(i)

    for i, aset in enumerate(spec["adsets"]):
        if "publisher_platforms" not in build_targeting(aset):
            add("publisher_platforms is omitted: the ad set runs on ALL placements, including "
                "Audience Network, Messenger and Threads. Set the ad set `placements` to \"fb_ig_all\" "
                "or \"fb_ig_feeds\", or list targeting.publisher_platforms + positions", i)
        event = aset.get("custom_event_type") or (aset.get("promoted_object") or {}).get("custom_event_type")
        conversion = aset.get("optimization_goal") in CONVERSION_GOALS or bool(event)
        strategy = camp_strategy if cbo else aset.get("bid_strategy", "LOWEST_COST_WITHOUT_CAP")
        if conversion and strategy == "LOWEST_COST_WITHOUT_CAP" and bid_policy(spec, aset) != "require_cap":
            add(f"optimizing for {event or aset.get('optimization_goal')} with LOWEST_COST_WITHOUT_CAP "
                "(no cost / bid cap): Meta can spend the whole budget at any CPA. Use COST_CAP or "
                "LOWEST_COST_WITH_BID_CAP + bid_amount_minor, and \"bid_policy\": \"require_cap\" to "
                "enforce it", i)
        if event == "PURCHASE" and not aset.get("attribution"):
            add("PURCHASE without an explicit `attribution`: the launch default is 1d click / 1d "
                "engaged-view / 1d view, the casino playbook window is 7d click / 1d view "
                "(attribution: {\"click_days\": 7, \"view_days\": 1}). It cannot be changed after create", i)
    for text, idx in groups.items():
        where = f"adsets[{','.join(map(str, idx))}]" if len(idx) > 1 else f"adsets[{idx[0]}]"
        out.append(f"{where}: {text}")
    if spec.get("lint") != "strict":
        out += [f"lint: {msg}" for msg in lint_findings(spec)]
    return out


# ------------------------------------------------------------------------ builders


def _audience_flag(value: Any, field: str) -> int:
    """advantage_audience is a real boolean (or the 0/1 Graph stores). The string "false" is
    truthy: it used to turn Advantage audience ON, silently, on a spec that said false."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int) and value in (0, 1):
        return value
    raise SpecError(f"{field} must be true/false (or 0/1), got {value!r} ({type(value).__name__})")


def _expand_placements(aset: dict, t: dict, label: str) -> None:
    """Fill publisher_platforms / positions from aset["placements"] into targeting `t`.

    Only keys the targeting does not set itself are filled, and a position list only for a
    platform that ends up targeted, so `placements: fb_ig_all` + an explicit
    `publisher_platforms: [instagram]` narrows to Instagram instead of contradicting itself."""
    name = aset.get("placements")
    if name is None:
        return
    preset = PLACEMENT_PRESETS.get(name) if isinstance(name, str) else None
    if preset is None:
        raise SpecError(f"{label}.placements must be one of {sorted(PLACEMENT_PRESETS)}, got {name!r}")
    if "publisher_platforms" not in t:
        t["publisher_platforms"] = list(preset["publisher_platforms"])
    targeted = t["publisher_platforms"] if isinstance(t["publisher_platforms"], list) else []
    for platform, key in POSITION_KEYS.items():
        if key in preset and key not in t and platform in targeted:
            t[key] = list(preset[key])


def _check_placements(t: dict, label: str) -> None:
    """publisher_platforms / positions must agree, and Instagram must be in."""
    pubs = t.get("publisher_platforms")
    if pubs is not None:
        if not isinstance(pubs, list) or not pubs or not all(isinstance(p, str) for p in pubs):
            raise SpecError(f"{label}.targeting.publisher_platforms must be a non-empty list of names")
        # publisher_platforms=["facebook"] is the classic wrong fix for 1772103: it makes the
        # error vanish while silently deleting IG + Audience Network + Messenger inventory.
        # Operator rule (2026-09-26): Instagram placements are mandatory on every buy.
        if "instagram" not in pubs:
            raise SpecError("targeting.publisher_platforms must include 'instagram' (operator rule: "
                            "never launch without Instagram placements). Omit the key for all placements.")
    for platform, key in POSITION_KEYS.items():
        if key not in t:
            continue
        if pubs is None or platform not in pubs:
            raise SpecError(
                f"{label}.targeting.{key} is set but {platform!r} is not in publisher_platforms "
                f"({pubs if pubs is not None else 'omitted'}). Positions only apply to a targeted platform: "
                f"add {platform!r} to publisher_platforms or drop {key}."
            )
        if not isinstance(t[key], list) or not t[key] or not all(isinstance(p, str) for p in t[key]):
            raise SpecError(
                f"{label}.targeting.{key} must be a non-empty list of positions for a targeted "
                f"platform (got {t[key]!r}). Omit the key for every position of {platform}."
            )


def build_targeting(aset: dict, label: str | None = None) -> dict:
    """Whole targeting object, every time.

    A POST that carries one targeting field REPLACES the object and wipes the rest
    (field-observed, 04). So targeting is only ever assembled here, in full."""
    label = label or "adset"
    t = copy.deepcopy(aset["targeting"])

    # advantage_audience is a targeting_automation key nested INSIDE targeting.
    # Top-level it produces the misleading 1870227 "advantage audience" error.
    if "advantage_audience" in t:
        flag = _audience_flag(t.pop("advantage_audience"), f"{label}.targeting.advantage_audience")
        t.setdefault("targeting_automation", {})["advantage_audience"] = flag
    elif "advantage_audience" in (t.get("targeting_automation") or {}):
        _audience_flag(t["targeting_automation"]["advantage_audience"],
                       f"{label}.targeting.targeting_automation.advantage_audience")

    if "geo_locations" not in t:
        raise SpecError("targeting.geo_locations is required")

    _expand_placements(aset, t, label)
    _check_placements(t, label)
    return t


def build_attribution(aset: dict) -> list | None:
    """attribution_spec, set at ad-set CREATE.

    The sub-field is `window_days` — **not** `event_window_days`, which does not exist
    in the Marketing API (v26.0 ad set reference, verified 2026-08-31). This matters
    more than a typo: Graph ignores unknown keys inside a JSON object parameter rather
    than rejecting them, so a spec built with `event_window_days` is accepted, reports
    success, and leaves the ad set on the account default — 7-day click. Every CPL
    computed against a believed 1-day window is then wrong. verify.py reads the spec
    back for exactly this reason.

    Meta's API default is 7-day click only (FIELD 2026-09-27, silent ad set read back
    [CLICK_THROUGH 7]; the UI default adds 1d engage + 1d view). Field-observed 2026-09-01: the
    window is immutable after create (1504040 "attribution window update no longer
    supported") — a wrong window means a new ad set, so it is set here, every time."""
    att = aset.get("attribution")
    if att == "account_default":
        return None
    if not att:
        att = DEFAULT_ATTRIBUTION
        if aset.get("optimization_goal") in CLICK_ONLY_ATTRIBUTION_GOALS:
            # Live 2026-09-02 (1885501): for non-conversion optimization goals Meta accepts
            # only click 1 / view 0 — view-through and engaged-view windows are rejected.
            att = {"click_days": 1}
    spec = []
    if att.get("click_days"):
        spec.append({"event_type": "CLICK_THROUGH", "window_days": int(att["click_days"])})
    if att.get("view_days"):
        spec.append({"event_type": "VIEW_THROUGH", "window_days": int(att["view_days"])})
    if att.get("engaged_video_view_days"):
        spec.append({"event_type": "ENGAGED_VIDEO_VIEW",
                     "window_days": int(att["engaged_video_view_days"])})
    return spec or None


def resolve_identity(spec: dict, create: bool = True) -> str | None:
    """`instagram_user_id: "auto"` → the Page's page-backed Instagram account.

    Without an IG identity, POST /ads fails 1772103 whenever placements include
    Instagram. The tempting fix — publisher_platforms=['facebook'] — makes the error
    vanish while silently deleting IG + Audience Network + Messenger inventory. Fix the
    identity, never the placements."""
    ig = spec.get("instagram_user_id")
    if ig and ig != "auto":
        return str(ig)
    if ig != "auto":
        return None

    page_id = str(spec["page_id"])
    ptoken = graph.page_token(page_id)
    # The `page_backed_instagram_accounts` EDGE is gone from the Page schema (removed after
    # 2025-04, no changelog, reference page 404) and now answers (#100) "Tried accessing
    # nonexisting field" on every version, even for Pages that have a PBIA. Read the
    # schema's replacement fields instead. See `18`. Verified live 2026-09-22.
    node = graph.call(
        "GET", page_id,
        params={"fields": "instagram_business_account,connected_instagram_account,"
                          "connected_page_backed_instagram_account"},
        token_override=ptoken, context="pbia read",
    )
    for key in ("connected_page_backed_instagram_account", "instagram_business_account",
                "connected_instagram_account"):
        value = node.get(key) or {}
        if value.get("id"):
            return str(value["id"])
    # The API create (POST /{page_id}/page_backed_instagram_accounts) is deprecated since
    # v22.0 / 2025-04-21 and returns #10. Instagram placements are mandatory, so stop here.
    raise SystemExit(f"Page {page_id} has no Instagram identity. Create it in the UI "
                     f"(Ads Manager > ad draft > Identity > Instagram account > Use Facebook Page, then discard the draft), then re-run.")


# There is NO single switch that disables Advantage+ creative enhancements, and the
# `standard_enhancements` KEY IS REJECTED at create: validate_only on v26.0 returned
# code 100 / subcode 3858504 "standard enhancements field no longer supported, set individual
# features instead" (live, 2026-09-02). Every feature must be named individually.
#   · `adapt_to_placement` is OPT-IN BY DEFAULT — omit it and it stays on.
#   · `music_generation` IS a key here (live read-back); `asset_feed_spec.audios: []` is kept too.
# This list is the full creative_features_spec read back from a live v26.0 creative that was
# created with every feature OPT_OUT (83 keys, 2026-09-02) — not the shorter doc table. If a
# future version rejects one, --dry-run says which; drop it via `creative.opt_out_features`.
# Catalog creatives that want video/metadata automation keep `media_type_automation`,
# `product_metadata_automation`, `standard_enhancements_catalog` OPT_IN by passing a list
# without them.
DEFAULT_OPT_OUT = [
    "adapt_to_placement",
    "add_text_overlay",
    "ads_with_benefits",
    "advantage_plus_creative",
    "app_highlights",
    "audio",
    "auto_promotion_tag",
    "biz_ai",
    "carousel_to_video",
    "catalog_feed_tag",
    "creative_stickers",
    "customize_product_recommendation",
    "cv_transformation",
    "description_automation",
    "dha_optimization",
    "dynamic_cta_text",
    "dynamic_partner_content",
    "enable_ncs_testimonials",
    "enhance_cta",
    "fb_feed_tag",
    "fb_reels_tag",
    "fb_story_tag",
    "feed_caption_optimization",
    "generate_cta",
    "hide_price",
    "hyperlink_formatting",
    "ig_feed_tag",
    "ig_glados_feed",
    "ig_reels_tag",
    "ig_stream_tag",
    "ig_video_native_subtitle",
    "image_animation",
    "image_auto_crop",
    "image_background_gen",
    "image_banner",
    "image_brightness_and_contrast",
    "image_end_card",
    "image_enhancement",
    "image_templates",
    "image_text_translation",
    "image_touchups",
    "image_uncrop",
    "inline_comment",
    "local_store_extension",
    "media_liquidity_animated_image",
    "media_order",
    "media_type_automation",
    "multi_creative_post_carousel",
    "multi_photo_to_video",
    "music_generation",
    "pac_genai_recomposition",
    "pac_recomposition",
    "pac_relaxation",
    "product_browsing",
    "product_extensions",
    "product_metadata_automation",
    "product_tags",
    "profile_card",
    "profile_extension",
    "replace_media_text",
    "reveal_details_over_time",
    "show_destination_blurbs",
    "show_summary",
    "site_extensions",
    "standard_enhancements_catalog",
    "text_extraction_for_headline",
    "text_extraction_for_tap_target",
    "text_formatting_optimization",
    "text_generation",
    "text_optimizations",
    "text_overlay_translation",
    "text_translation",
    "translate_voiceover",
    "video_auto_crop",
    "video_filtering",
    "video_highlight",
    "video_highlights",
    "video_to_image",
    "video_uncrop",
    "video_uncrop_9x16_to_9x18",
    "video_voiceover",
    "wa_mm_image_filtering",
    "wa_mm_text_truncation_length",
]


def opt_out_enhancements(features: list[str]) -> dict:
    """Per-feature OPT_OUT. The single `enable_standard_enhancements` boolean and the
    `standard_enhancements` bundle stopped being settable at v22.0 — the field still
    exists in the schema, which is why toggling it looks like it worked (14)."""
    return {
        "creative_features_spec": {f: {"enroll_status": "OPT_OUT"} for f in features}
    }


def _prune(obj):
    """Drop None values at every depth.

    graph.call() strips top-level Nones, but object_story_spec is JSON-encoded whole,
    so a null nested inside it reaches Meta verbatim and can fail validation on a field
    you never meant to send."""
    if isinstance(obj, dict):
        return {k: _prune(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_prune(v) for v in obj]
    return obj


def build_dlo_feed(c: dict) -> dict:
    """asset_feed_spec for language customization.

    Spec shape expected (one entry per locale group):
        "locales": [{"label": "tr", "ids": [59], "is_default": false,
                     "body": "...", "title": "...", "description": "...",
                     "link": "https://..."}]

    Hard rules Meta enforces: exactly ONE ad format per feed; exactly one
    call_to_action_type when customization rules are present; every text asset carries an
    adlabel; exactly one rule is_default. The asset-customization-rules page additionally
    says a feed needs at least two rules — the autotranslate example ships one; assume two.
    The ad set must have is_dynamic_creative=false for a rule-based feed."""
    locales = c.get("locales")
    if not locales:
        raise SpecError("creative.kind=dlo requires a non-empty `locales` list")
    if sum(1 for loc in locales if loc.get("is_default")) != 1:
        raise SpecError("exactly one entry in `locales` must set is_default: true")

    # DLO accepts only these two formats — narrower than asset_feed_spec generally,
    # which also takes CAROUSEL and AUTOMATIC_FORMAT.
    fmt = c.get("ad_format", "SINGLE_IMAGE")
    if fmt not in ("SINGLE_IMAGE", "SINGLE_VIDEO"):
        raise SpecError(
            f"creative.kind=dlo supports ad_format SINGLE_IMAGE or SINGLE_VIDEO only, got {fmt!r}"
        )
    media_key = "image_hash" if fmt == "SINGLE_IMAGE" else "video_id"
    if not c.get(media_key):
        raise SpecError(f"creative.kind=dlo with ad_format={fmt} needs {media_key}")

    feed: dict[str, Any] = {
        "ad_formats": [fmt],
        "call_to_action_types": [c.get("cta", "LEARN_MORE")],
        "bodies": [], "titles": [], "descriptions": [], "link_urls": [],
        "asset_customization_rules": [],
    }
    # One media asset per locale label, so each rule can carry the label the docs
    # require: image_label for SINGLE_IMAGE, video_label for SINGLE_VIDEO. A rule
    # missing its media label is rejected.
    if fmt == "SINGLE_IMAGE":
        feed["images"] = []
    else:
        feed["videos"] = []

    for loc in locales:
        label = loc["label"]
        tag = [{"name": label}]
        feed["bodies"].append({"text": loc["body"], "adlabels": tag})
        feed["titles"].append({"text": loc["title"], "adlabels": tag})
        # `descriptions` is REQUIRED. The docs specify a single space for a blank one —
        # an omitted or empty list is not the same thing and is rejected.
        feed["descriptions"].append({"text": loc.get("description") or " ", "adlabels": tag})
        feed["link_urls"].append({"website_url": loc["link"], "adlabels": tag})

        if fmt == "SINGLE_IMAGE":
            feed["images"].append({"hash": loc.get("image_hash", c["image_hash"]), "adlabels": tag})
        else:
            feed["videos"].append(
                {"video_id": str(loc.get("video_id", c["video_id"])), "adlabels": tag}
            )

        rule: dict[str, Any] = {
            "customization_spec": {"locales": [int(x) for x in loc["ids"]]},
            "body_label": {"name": label},
            "title_label": {"name": label},
            "description_label": {"name": label},
            "link_url_label": {"name": label},
            ("image_label" if fmt == "SINGLE_IMAGE" else "video_label"): {"name": label},
        }
        if loc.get("is_default"):
            rule["is_default"] = True
        feed["asset_customization_rules"].append(rule)

    if len(feed["asset_customization_rules"]) < 2:
        raise SpecError(
            "DLO needs at least two customization rules (the default slot plus at least "
            "one added locale) — Meta's asset-customization-rules page requires it."
        )
    # Music is not opted out through creative_features_spec; an empty audios list is.
    feed.setdefault("audios", [])
    return feed


def resolved_opt_out(c: dict) -> list[str]:
    """The exact list of creative features this creative opts OUT of.

    One definition for launch.py (what it sends) and verify.py (what it expects back).
    `opt_out_features` replaces the default list. Without it the default list applies, minus
    `media_type_automation` on a catalog creative that wants product video
    (creative.product_video: true, implied by a video format_option). Whatever the spec names in
    `opt_in_features` is then removed from the list on purpose: it stays OPT_IN and verify.py
    accepts that instead of reporting a leak."""
    features = c.get("opt_out_features")
    if features is None:
        features = DEFAULT_OPT_OUT
        wants_video = c.get("product_video",
                            c.get("format_option") in ("single_video", "collection_video"))
        if wants_video and str(c.get("kind", "")).startswith("catalog"):
            features = [f for f in features if f != "media_type_automation"]
    elif not isinstance(features, list):
        raise SpecError(f"creative.opt_out_features must be a list of feature names, got {features!r}")
    allowed = c.get("opt_in_features")
    if allowed is not None:
        if not isinstance(allowed, list) or not all(isinstance(f, str) for f in allowed):
            raise SpecError(f"creative.opt_in_features must be a list of feature names, got {allowed!r}")
        features = [f for f in features if f not in allowed]
    return list(features)


def _finish(payload: dict, c: dict) -> dict:
    """Apply the enhancement opt-out to every creative shape, then prune nulls.

    Applies to catalog and DLO creatives too — that is the whole point of having one
    exit. `media_type_automation` is the one key worth overriding per shape: OPT_OUT for
    plain images (3858040), but on a catalog creative it is what ADDS video alongside
    images on the Dynamic Media path, so a catalog spec that wants video should pass
    `opt_out_features` without it (or name it in `opt_in_features`)."""
    features = resolved_opt_out(c)
    if features:
        payload["degrees_of_freedom_spec"] = opt_out_enhancements(features)
    # Multi-advertiser ads. ON by default; the API field is `contextual_multi_ads` with an
    # enroll_status. Field-verified 2026-09-01 on template_data catalog creatives (reads back
    # OPT_OUT, checkbox off in UI). On FORMAT_AUTOMATION collection creatives the read-back
    # says "nonexisting field" — the param is still sent, and verify.py tells you to check
    # the UI before it spends (immediately after create by default, or while PAUSED under
    # the create_status override). Override with `"multi_advertiser": true`.
    if not c.get("multi_advertiser"):
        payload["contextual_multi_ads"] = {"enroll_status": "OPT_OUT"}
    return _prune(payload)


# AdCreativeLinkData.format_option, v26 reference + SDK (verified 2026-09-26). The product-video guide
# also names single_video, which the enum does not list (warned, not refused).
FORMAT_OPTIONS = {"carousel_ar_effects", "carousel_images_multi_items", "carousel_images_single_item",
                  "carousel_slideshows", "collection_video", "single_image"}


def build_creative(spec: dict, ad: dict, ig_id: str | None) -> dict:
    """Assemble one adcreative payload. `kind` selects the shape."""
    c = ad.get("creative")
    if not isinstance(c, dict):
        raise SpecError(f"ad {ad.get('name', '?')}: missing a `creative` object")
    kind = c.get("kind", "link_image")

    # Fail on a readable message, not a KeyError traceback — the spec is agent-written.
    required = {
        "link_image": ("link", "image_hash"),
        "link_video": ("link", "video_id"),
        "link_carousel": ("link", "cards"),
        "dlo": ("locales",),
        "catalog_collection": ("link", "product_set_id"),
        "catalog_single": ("link", "product_set_id"),
        "catalog_carousel": ("link", "product_set_id"),
    }.get(kind)
    if required is None:
        raise SpecError(
            f"ad {ad.get('name', '?')}: unknown creative.kind {kind!r}. "
            "Known: link_image, link_video, link_carousel, dlo, catalog_collection, catalog_single, catalog_carousel."
        )
    missing = [f for f in required if not c.get(f)]
    if missing:
        raise SpecError(f"ad {ad.get('name', '?')}: creative.kind={kind} is missing {missing}")
    story: dict[str, Any] = {"page_id": str(spec["page_id"])}
    if ig_id:
        story["instagram_user_id"] = ig_id

    payload: dict[str, Any] = {"name": ad["name"]}
    # Per-creative url_tags win; otherwise the spec-level default applies to every ad, so
    # one forgotten creative does not land untracked.
    url_tags = c.get("url_tags", spec.get("url_tags"))
    if url_tags:
        payload["url_tags"] = url_tags

    cta = {"type": c.get("cta", "LEARN_MORE"),
           "value": {"link": c["link"]} if c.get("link") else {}}

    if kind == "link_image":
        story["link_data"] = {
            "link": c["link"],
            "message": c.get("message", ""),
            "name": c.get("headline"),
            "description": c.get("description"),
            "caption": c.get("display_link"),
            "image_hash": c["image_hash"],
            "call_to_action": cta,
        }
    elif kind == "link_carousel":
        # Manual carousel: 2-10 child_attachments; `link` + `message` become required on
        # link_data. Each card: image_hash XOR video_id, link, name, description.
        cards = c["cards"]
        if not isinstance(cards, list) or not 2 <= len(cards) <= 10:
            raise SpecError(f"creative {ad['name']}: link_carousel needs 2-10 cards, got "
                            f"{len(cards) if isinstance(cards, list) else type(cards).__name__}")
        children = []
        for n, card in enumerate(cards):
            if bool(card.get("image_hash")) == bool(card.get("video_id")):
                raise SpecError(f"creative {ad['name']}: cards[{n}] needs image_hash XOR video_id")
            child = {
                "link": card.get("link", c["link"]),
                "name": card.get("headline"),
                "description": card.get("description"),
                "image_hash": card.get("image_hash"),
                "video_id": card.get("video_id"),
                "call_to_action": {"type": card.get("cta", c.get("cta", "LEARN_MORE")),
                                   "value": {"link": card.get("link", c["link"])}},
            }
            children.append(child)
        story["link_data"] = {
            "link": c["link"],
            "message": c.get("message", ""),
            "caption": c.get("display_link"),
            "child_attachments": children,
            "multi_share_optimized": c.get("multi_share_optimized", False),
            "multi_share_end_card": c.get("multi_share_end_card", False),
        }
    elif kind == "link_video":
        if c.get("display_link"):
            # AdCreativeVideoData has no caption: the display link would be dropped without a
            # word and the ad would show the raw destination domain instead.
            msg = (f"creative {ad['name']}: display_link {c['display_link']!r} has no place on a "
                   "link_video creative (video_data has no caption) and would be dropped. Remove it, "
                   "or use a link_image creative if the display link matters.")
            if spec.get("lint") == "strict":
                raise SpecError(msg)
            print(f"    ! {msg}", file=sys.stderr)
        story["video_data"] = {
            "video_id": c["video_id"],
            "message": c.get("message", ""),
            "title": c.get("headline"),
            "link_description": c.get("description"),
            "call_to_action": cta,
        }
        # A video ad needs a thumbnail. Prefer image_hash: the AdCreativeVideoData
        # reference says not to feed FB CDN URLs into image_url, and media.py already
        # converts the /thumbnails uri into an owned hash. If you do pass a uri, pass it
        # WHOLE — truncating its signed query string fails creation with 2446603.
        if c.get("image_hash"):
            story["video_data"]["image_hash"] = c["image_hash"]
        elif c.get("thumbnail_url"):
            story["video_data"]["image_url"] = c["thumbnail_url"]
        else:
            raise SpecError(
                f"creative {ad['name']}: a video creative needs a thumbnail. Run media.py "
                "and use its thumbnail_image_hash, or supply thumbnail_url (whole uri)."
            )
    elif kind == "dlo":
        # Multi-language / Dynamic Language Optimization. Locales are NUMERIC ids from
        # GET /search?type=adlocale&q=<lang> — a string locale code is silently wrong.
        # Exactly one rule carries is_default:true; that is the "Default" slot.
        feed = build_dlo_feed(c)
        payload["asset_feed_spec"] = feed
        payload["object_story_spec"] = story
        return _finish(payload, c)

    elif kind in ("catalog_collection", "catalog_single", "catalog_carousel"):
        if not c.get("product_set_id"):
            raise SpecError(f"creative {ad['name']}: {kind} needs product_set_id")
        payload["product_set_id"] = str(c["product_set_id"])
        # Catalog card clicks resolve their URL from the product feed and bypass the
        # ad's url_tags, so subids never arrive. template_url_spec is the documented
        # override; without it a catalog launch is untracked (04 -> url_tags).
        if c.get("template_url"):
            payload["template_url_spec"] = {"web": {"url": c["template_url"]}}
        elif "{{" in c["link"]:
            # Field 2026-09-21..25 (KG, PWA Partners): macros in template_data.link DID reach
            # the tracker (Keitaro sub_id_5=Facebook_Mobile_Feed etc.), so no warning here.
            pass
        else:
            print("    ! catalog creative without template_url: card clicks will carry no "
                  "subids. Set creative.template_url, or capture the subid in the landing "
                  "builder.", file=sys.stderr)
        # A catalog ad is built to be swapped: only the product changes afterwards. So the
        # primary text must read fine next to BOTH the white and the target product, and the
        # headline/description must follow the product. Enforced, not advised (2026-09-26).
        message = c.get("message", "-----")
        if re.search(r"\w", message) and not c.get("allow_message"):
            raise SpecError(f"creative {ad['name']}: {kind} message {message!r} survives the swap "
                            "(shows next to the target product). Use a neutral one like '-----', "
                            "or set creative.allow_message: true on purpose.")
        for field, macro in (("headline", "{{product.name}}"), ("description", "{{product.description}}")):
            # Any documented product tag follows the swap ({{product.brand}}, custom_label_0..4, ...).
            if field in c and not re.search(r"\{\{\s*product\.\w+", str(c[field])) and not c.get("allow_static_text"):
                raise SpecError(f"creative {ad['name']}: {field} {c[field]!r} has no product tag like {macro}; it "
                                "would not follow the swap. Drop it (default is the macro) or set allow_static_text.")
        fmt = c.get("format_option")
        if fmt is not None and fmt not in FORMAT_OPTIONS and fmt != "single_video":
            raise SpecError(f"creative {ad['name']}: format_option {fmt!r} unknown. v26 enum: "
                            f"{sorted(FORMAT_OPTIONS)} (+ guide-only single_video).")
        if fmt == "single_video":
            print(f"    ! {ad['name']}: format_option single_video is guide-only (not in the v26 enum / SDK); "
                  "the real run's validate_only decides. Fallback: single_image + product video.",
                  file=sys.stderr)
        if not c.get("swap_to"):
            print(f"    ! {ad['name']}: no creative.swap_to — no target SKU is planned, so `apply` cannot "
                  "hand you the assets swap --watch command and the white product will spend until "
                  "someone swaps by hand.", file=sys.stderr)
        template: dict[str, Any] = {
            "link": c["link"],
            "message": message,
            "call_to_action": cta,
        }
        # Without explicit name/description Meta fills the card headline from the LINK's
        # scraped <title> (field 2026-09-26: the PWA white page title "Your Little Hero:
        # Kids Stories" showed under a swapped casino card). Product macros make the
        # headline/description follow the catalog item, so a set swap changes them too.
        template["name"] = c.get("headline", "{{product.name}}")
        template["description"] = c.get("description", "{{product.description}}")
        if c.get("display_link"):
            template["caption"] = c["display_link"]
        if kind == "catalog_collection":
            # COLLECTION needs >=4 items in the set (2490457 at build). The video hero
            # goes through asset_feed_spec, NOT video_data: link_data.video_data with a
            # product_set_id is an undocumented path and fails 1487832 "invalid repost".
            template["multi_share_end_card"] = c.get("multi_share_end_card", False)
            story["template_data"] = template
            payload["object_story_spec"] = story
            feed: dict[str, Any] = {
                "optimization_type": "FORMAT_AUTOMATION",
                "ad_formats": ["COLLECTION"],
            }
            if c.get("video_id"):
                feed["videos"] = [{"video_id": str(c["video_id"])}]
            payload["asset_feed_spec"] = feed
            # Multi-advertiser ads default ON for FORMAT_AUTOMATION catalog creatives. The
            # `contextual_multi_ads` OPT_OUT is sent by _finish, but on THIS format the
            # field is not readable back (field-observed 2026-09-01), so the UI checkbox is
            # the only proof. Check it before spend — immediately after create by default,
            # or while PAUSED under the create_status override — toggling post-approval is
            # re-moderation.
            print("    ! catalog_collection: contextual_multi_ads OPT_OUT is sent but is not "
                  "readable on FORMAT_AUTOMATION creatives. Confirm the Multi-advertiser "
                  "checkbox is OFF in Ads Manager BEFORE it spends.")
            if c.get("opt_out_features") is None and not c.get("product_video"):
                print("    ! catalog_collection: media_type_automation is being OPT_OUT by "
                      "default, which strips video from Dynamic Media. Set "
                      "creative.product_video: true if you want video cards.")
        elif kind == "catalog_carousel":
            # Multi-product carousel from the set: leaving force_single_link out makes a carousel,
            # "Facebook will choose the number of cards" (link-data reference v26). No documented
            # item minimum. Product videos serve only with media_type_automation ON: set
            # creative.product_video: true (the default opt-out list strips it). That is the
            # Tyver-seen KG winner shape: card 1 casino video + white cards.
            template["multi_share_end_card"] = c.get("multi_share_end_card", False)
            if fmt:
                template["format_option"] = fmt
            story["template_data"] = template
            payload["object_story_spec"] = story
            # Field 2026-09-27: a template_data carousel reads back as FORMAT_AUTOMATION with ad_formats
            # [CAROUSEL, COLLECTION] whether asset_feed_spec is omitted OR pinned to CAROUSEL only:
            # Meta may serve it as a collection grid (the operator: no grid). Sent anyway (documents intent);
            # only catalog_single (force_single_link) avoids the automation.
            payload["asset_feed_spec"] = {"optimization_type": "FORMAT_AUTOMATION",
                                          "ad_formats": list(c.get("ad_formats", ["CAROUSEL"]))}
            print(f"    ! {ad['name']}: catalog_carousel — Meta adds COLLECTION to the formats on its own "
                  "(field 2026-09-27); it may serve as a grid. Only catalog_single avoids that.",
                  file=sys.stderr)
        else:
            # One-product set renders as a single deep-linked card, no minimum item count.
            # force_single_link for an image card; format_option single_video for the
            # documented Dynamic Media video path (video attached to the PRODUCT).
            template["force_single_link"] = True
            if c.get("format_option"):
                template["format_option"] = c["format_option"]
            story["template_data"] = template
            payload["object_story_spec"] = story
        return _finish(payload, c)

    else:
        raise SpecError(
            f"unknown creative.kind: {kind}. "
            "Known: link_image, link_video, link_carousel, dlo, catalog_collection, catalog_single, catalog_carousel."
        )

    payload["object_story_spec"] = story
    return _finish(payload, c)


# -------------------------------------------------------------------------- create


# execution_options support, per the v26.0 reference (verified 2026-08-31):
#   POST /act_X/campaigns    validate_only, include_recommendations
#   POST /act_X/adsets       validate_only, include_recommendations
#   POST /act_X/ads          validate_only, synchronous_ad_review, include_recommendations
#   POST /act_X/adcreatives  validate_only ONLY
#   POST /{adcreative_id}    NOT supported — creatives can only be validated at create time
# `synchronous_ad_review` must be paired with validate_only; it additionally runs Ads
# Integrity checks (message language, image text rule) BEFORE the object exists — the
# cheapest possible read on whether a creative will survive review.
VALIDATE_OPTS = {
    "campaign": ["validate_only"],
    "adset": ["validate_only"],
    "creative": ["validate_only"],
    "ad": ["validate_only", "synchronous_ad_review"],
}


# Objects whose payload references a parent id. In --dry-run the parent was never
# created, so there is no real id to send and `validate_only` would fail on the foreign
# key rather than on your payload — a misleading failure, not a useful gate. These are
# validated locally in dry-run and by the API on the real run, where the parent exists.
PARENT_BOUND = ("adset", "ad")


def _create(node: str, path: str, payload: dict, state: State, dry: bool) -> str | None:
    """validate_only, then (unless --dry-run) the real create. Resumes from state."""
    cached = state.get(node)
    if cached:
        print(f"  = {node}: {cached} (from state, skipped)")
        return cached

    kind = node.split("[")[0]

    if dry and kind in PARENT_BOUND:
        print(f"  - {node}: built OK, API validation deferred (needs a real "
              f"{'campaign' if kind == 'adset' else 'ad set/creative'} id)")
        return None

    probe = dict(payload, execution_options=VALIDATE_OPTS.get(kind, ["validate_only"]))
    try:
        graph.post(path, probe, context=f"validate {node}", idempotent=True)
    except graph.GraphError as e:
        state.fail(node, e.as_dict())  # validate_only mutates nothing
        print(f"  x {node}: VALIDATION FAILED\n      {e}", file=sys.stderr)
        if e.blame_field:
            print(f"      offending field path: {e.blame_field}", file=sys.stderr)
        raise SystemExit(1) from e
    print(f"  ✓ {node}: payload valid")

    if dry:
        return None

    # Record the attempt BEFORE issuing it. A kill between a successful POST and the
    # state write would otherwise leave an orphan object that the next run recreates.
    state.attempt(node, path)
    try:
        obj_id = graph.post(path, payload, context=f"create {node}")["id"]
    except graph.GraphError as e:
        # graph.py decides this: a Graph-issued error means the call was rejected and
        # nothing was created; a transport failure or a non-Graph 5xx means the object
        # may or may not exist. A narrower local test missed HTML 502s from an edge.
        outcome_known = not e.outcome_unknown
        state.fail(node, e.as_dict(), outcome_known=outcome_known)
        print(f"  x {node}: CREATE FAILED\n      {e}", file=sys.stderr)
        if not outcome_known:
            print(f"      Outcome UNKNOWN — {node} may exist in the account. The next run "
                  f"will stop and ask you to reconcile.", file=sys.stderr)
        raise SystemExit(1) from e
    state.put(node, obj_id)
    print(f"  + {node}: {obj_id}")
    return obj_id


def account_currency(spec: dict, dry: bool = False) -> str:
    """Read the live account and gate the run on it; return the account currency.

    One GET carries currency, timezone, account_status and disable_reason. Anything but
    account_status=1 refuses the run before a single object is created: a disabled,
    unsettled or closed account cannot deliver, and the failure would otherwise surface as a
    confusing Graph error halfway through a tree.

    The currency check catches a mismatch that is not cosmetic: the same integer means 100x
    more money on a no-offset currency. Any spec meant for money should carry `currency` so a
    template copied to a differently-billed account fails here, not on the invoice."""
    acct = graph.get(spec["account_id"],
                     params={"fields": "currency,timezone_name,account_status,disable_reason"},
                     context="account currency")
    status = acct.get("account_status")
    if status is None:
        print(f"  ! {spec['account_id']}: account_status not returned, cannot confirm the account is ACTIVE",
              file=sys.stderr)
    elif status != 1 and dry:
        print(f"  ! {spec['account_id']}: account_status={status} "
              f"({ACCOUNT_STATUS_NAMES.get(status, 'unknown')}) - a real apply would refuse this account",
              file=sys.stderr)
    elif status != 1:
        reason = acct.get("disable_reason")
        raise SpecError(
            f"{spec['account_id']} is not active: account_status={status} "
            f"({ACCOUNT_STATUS_NAMES.get(status, 'unknown')}), disable_reason={reason} "
            f"({DISABLE_REASON_NAMES.get(reason, 'unknown') if isinstance(reason, int) else 'unknown'}). "
            "Nothing was created. Resolve it in Ads Manager / Business Settings first "
            "(payment, appeal, or a different account)."
        )
    code = acct.get("currency", "?")
    want = spec.get("currency")
    if want and want != code:
        raise SpecError(
            f"spec.currency={want} but {spec['account_id']} bills in {code}. Budgets in this spec "
            f"were written for {want}; re-express them for {code} (offset {currency_offset(code)})."
        )
    print(f"  account: {code} · tz {acct.get('timezone_name')} · budget unit "
          f"{'WHOLE units (no cents)' if currency_offset(code) == 1 else 'minor units (1/100)'}")
    return code


def run(spec: dict, state: State, dry: bool, start_override: str | None = None) -> None:
    account = spec["account_id"]
    h = spec_hash(spec)
    if state.data.get("spec_sha") and state.data["spec_sha"] != h and state.data["objects"]:
        raise SpecError(
            f"state {state.path} was built from a different spec (sha {state.data['spec_sha']} ≠ "
            f"{h}). Objects already exist; editing the spec and resuming would mix two builds. "
            "Use a new run_id/state, or delete the tree first."
        )
    # Gate on the live account BEFORE the state file is written or anything is created: a
    # disabled / unsettled / closed account is refused here, with its disable_reason.
    cur = account_currency(spec, dry)
    state.data["spec_sha"] = h
    state.data["spec_account"] = account
    if start_override:
        # Resume after a failure that outlived the spec's start_time: re-date only the ad
        # sets that do not exist yet. The spec (and its hash) stay untouched; the override
        # is recorded per ad set so verify.py compares against what was really sent.
        overrides = state.data.setdefault("start_overrides", {})
        for i, aset in enumerate(spec["adsets"]):
            if not state.get(f"adset[{i}]"):
                aset["start_time"] = start_override
                overrides[f"adset[{i}]"] = start_override
                print(f"  adset[{i}] start_time → {start_override} (refresh-start)")
    if not dry:
        state.save()
    camp = spec["campaign"]
    if spec["budget_mode"] == "CBO":
        print(f"  campaign daily budget: {major(camp['daily_budget_minor'], cur)}")
    else:
        for i, a in enumerate(spec["adsets"]):
            print(f"  adsets[{i}] daily budget: {major(a['daily_budget_minor'], cur)}")

    # Resolve in dry-run as well. Validating a creative without the IG identity is a
    # false pass: the real run would then fail 1772103 at POST /ads, which is exactly
    # the failure the dry run exists to catch. In dry-run we only READ the PBIA — we do
    # not create one — so a missing PBIA is reported, not silently fixed.
    ig_id = resolve_identity(spec, create=not dry)
    if ig_id:
        print(f"  identity: instagram_user_id={ig_id}")
    elif spec.get("instagram_user_id") == "auto":
        # resolve_identity raises when the Page has no Instagram identity, so this only guards a
        # future change to it. Instagram placements are mandatory, so there is no "skip" path.
        raise SpecError(
            "no PBIA exists for this Page and Instagram placements are mandatory. Create the "
            "identity in the UI (Ads Manager > ad draft > Identity > Instagram account > Use "
            "Facebook Page, then discard the draft), then re-run."
        )

    # Step 1 — campaign WITHOUT budget and WITHOUT bid_strategy.
    # bid_strategy on a campaign that has no budget yet fails 1885737;
    # omitting is_adset_budget_sharing_enabled fails 4834011 on OUTCOME_LEADS.
    if camp.get("id"):
        campaign_id = str(camp["id"])
        state.put("campaign", campaign_id)
        if spec["budget_mode"] == "CBO":
            state.put("campaign_budget", campaign_id)
        print(f"  = campaign: {campaign_id} (existing, reused)")
    else:
        # An ACTIVE build still creates its campaign PAUSED: ad sets and ads go in ACTIVE,
        # and the campaign is flipped ACTIVE in one call once the whole tree exists (step 6).
        # A run that dies halfway then leaves a PAUSED campaign — nothing spends on a
        # partial tree — and the resume performs the flip when it completes the tree.
        if not dry and not state.get("campaign"):
            graph.check_campaign_create_pace(account)
        resumed = bool(state.get("campaign"))
        campaign_id = _create(
            "campaign",
            f"{account}/campaigns",
            {
                "name": camp["name"],
                "objective": camp["objective"],
                "status": "PAUSED",
                "buying_type": camp.get("buying_type", "AUCTION"),
                "special_ad_categories": camp["special_ad_categories"],
                "is_adset_budget_sharing_enabled": False,
            },
            state, dry,
        )
        if not campaign_id:
            campaign_id = "<dry-run>"
        elif not dry and not resumed:
            graph.record_campaign_create(account)

    # Step 2 (CBO only) — budget and bid strategy onto the existing campaign.
    # No in-flight marker here, deliberately: re-POSTing the same daily_budget and
    # bid_strategy is idempotent, so a crash mid-PATCH costs a harmless repeat on the
    # next run. A marker would only turn that into a false "reconcile by hand" stop.
    # It DOES need the same error handling and dry-run probe as every other write —
    # without them a failure here surfaced as a bare traceback, and --dry-run never
    # checked the budget or bid strategy at all.
    # Under ABO the campaign stays budget-less (is_adset_budget_sharing_enabled=false was
    # sent at create, which is what v24+ requires) and each ad set carries its own.
    if spec["budget_mode"] == "CBO" and not camp.get("id") and not state.get("campaign_budget"):
        budget_payload = {
            "daily_budget": _int_minor(camp["daily_budget_minor"], "campaign.daily_budget_minor"),
            "bid_strategy": camp.get("bid_strategy", "LOWEST_COST_WITHOUT_CAP"),
        }
        # No campaign-level bid_amount: it is not a campaign field, load_spec rejects
        # campaign.bid_amount_minor and the cap amount goes on every ad set below.

        # POST /{campaign_id} does accept validate_only, but in a dry run the campaign
        # does not exist, so the call could only fail on the missing object — which says
        # nothing about the budget or bid strategy. Report the values and validate them
        # on the real run, where the campaign is there.
        if dry:
            print(f"  - campaign budget: {budget_payload['daily_budget']} minor units, "
                  f"{budget_payload['bid_strategy']} (validated on the real run — the "
                  f"campaign does not exist yet)")
        else:
            try:
                graph.post(
                    campaign_id,
                    dict(budget_payload, execution_options=["validate_only"]),
                    context="validate campaign budget", idempotent=True,
                )
                graph.post(campaign_id, budget_payload, context="campaign budget",
                           idempotent=True)
            except graph.GraphError as e:
                state.fail("campaign_budget", e.as_dict(), outcome_known=not e.outcome_unknown)
                print(f"  x campaign budget: FAILED\n      {e}", file=sys.stderr)
                print(f"      The campaign exists ({campaign_id}) but carries no budget, so "
                      f"its ad sets cannot be created. Fix and re-run — this step is "
                      f"idempotent.", file=sys.stderr)
                raise SystemExit(1) from e
            state.put("campaign_budget", campaign_id)
            print(f"  + campaign budget: {budget_payload['daily_budget']} minor units, "
                  f"{budget_payload['bid_strategy']}")

    # A reused campaign is already live: an ad set created ACTIVE under it would start spending
    # before its ads exist, and a mid-run failure would leave a live partial tree. So under a
    # reused campaign the ad sets are created PAUSED, their ads are created, and only then is
    # each ad set flipped ACTIVE (step 5). A new campaign is built PAUSED and flipped last.
    staged = spec["create_status"] == "ACTIVE" and bool(camp.get("id"))
    adset_status = "PAUSED" if staged else spec["create_status"]

    for i, aset in enumerate(spec["adsets"]):
        # Step 3 — ad set. CBO: NO budget and NO bid_strategy (the campaign owns both).
        # ABO: daily_budget + bid_strategy (+ bid_amount for cap strategies) live here.
        payload: dict[str, Any] = {
            "name": aset["name"],
            "campaign_id": campaign_id,
            "status": adset_status,
            "billing_event": aset.get("billing_event", "IMPRESSIONS"),
            "optimization_goal": aset["optimization_goal"],
            "targeting": build_targeting(aset),
            "start_time": aset["start_time"],
        }
        if spec["budget_mode"] == "ABO":
            payload["daily_budget"] = _int_minor(aset["daily_budget_minor"], f"adsets[{i}].daily_budget_minor")
            payload["bid_strategy"] = aset.get("bid_strategy", "LOWEST_COST_WITHOUT_CAP")
            if aset.get("bid_amount_minor"):
                payload["bid_amount"] = _int_minor(aset["bid_amount_minor"], f"adsets[{i}].bid_amount_minor")
        elif aset.get("bid_amount_minor"):
            # CBO: the campaign owns daily_budget/bid_strategy, but a cap strategy
            # (COST_CAP / LOWEST_COST_WITH_BID_CAP) still needs its cap amount on the ad
            # set — load_spec already enforced its presence when the campaign uses one.
            payload["bid_amount"] = _int_minor(aset["bid_amount_minor"], f"adsets[{i}].bid_amount_minor")
        if aset.get("end_time"):
            payload["end_time"] = aset["end_time"]
        # promoted_object: explicit object wins (custom_conversion_id, application_id +
        # object_store_url, page_id...); else the pixel + event shorthand.
        if aset.get("promoted_object"):
            payload["promoted_object"] = aset["promoted_object"]
        elif spec.get("pixel_id") and aset.get("custom_event_type"):
            payload["promoted_object"] = {
                "pixel_id": str(spec["pixel_id"]),
                "custom_event_type": aset["custom_event_type"],
            }
        # dsa_* = EU DSA. regional_regulated_categories + regional_regulation_identities =
        # Taiwan / Australia / Singapore financial-ads disclosure (a different mechanism,
        # present in the business SDK adset model; shapes in 04).
        for key in ("dsa_beneficiary", "dsa_payor", "destination_type", "is_dynamic_creative",
                    "regional_regulated_categories", "regional_regulation_identities"):
            if aset.get(key) is not None:
                payload[key] = aset[key]
        for key in ("daily_min_spend_target", "daily_spend_cap"):
            if aset.get(key) is not None:
                payload[key] = _int_minor(aset[key], f"adsets[{i}].{key}")
        att = build_attribution(aset)
        if att:
            payload["attribution_spec"] = att

        adset_id = _create(f"adset[{i}]", f"{account}/adsets", payload, state, dry) or "<dry-run>"

        for j, ad in enumerate(aset["ads"]):
            creative_payload = build_creative(spec, ad, ig_id)
            creative_id = _create(
                f"creative[{i}.{j}]", f"{account}/adcreatives", creative_payload, state, dry
            ) or "<dry-run>"
            ad_payload: dict[str, Any] = {
                "name": ad["name"],
                "adset_id": adset_id,
                "creative": {"creative_id": creative_id},
                "status": spec["create_status"],
            }
            if ad.get("conversion_domain", spec.get("conversion_domain")):
                ad_payload["conversion_domain"] = ad.get("conversion_domain", spec.get("conversion_domain"))
            _create(f"ad[{i}.{j}]", f"{account}/ads", ad_payload, state, dry)

        # Step 5 — this ad set's ads all exist (a failed create above raised): let it deliver.
        if staged:
            activate_adset(state, i, adset_id, dry)

    # Step 6 — the tree is complete; turn the campaign on. Every create above raises on
    # failure, so reaching this line means every ad set and ad of this spec exists.
    activate_campaign(spec, state, campaign_id, dry)


def activate_adset(state: State, index: int, adset_id: str, dry: bool) -> None:
    """Flip one ad set of a REUSED campaign from PAUSED to ACTIVE once its ads exist.

    Recorded in state.adsets_activated so a resume neither repeats nor skips a flip. A failure
    leaves the ad set PAUSED (nothing spends on it) and the run re-tries only this flip."""
    key = f"adset[{index}]"
    if dry:
        print(f"  - {key}: created PAUSED under the reused campaign, flipped ACTIVE once its ads "
              "exist (real run only)")
        return
    if (state.data.get("adsets_activated") or {}).get(key) == adset_id:
        print(f"  = {key} {adset_id}: ACTIVE (from state, skipped)")
        return
    try:
        # A status flip is safe to repeat, so a dropped connection may retry.
        graph.post(adset_id, {"status": "ACTIVE"}, context=f"activate {key}", idempotent=True)
    except graph.GraphError as e:
        state.fail(f"adset_activate[{index}]", e.as_dict())
        print(f"  x {key} {adset_id}: ACTIVATE FAILED\n      {e}", file=sys.stderr)
        print("      The ad set and its ads exist but the ad set is still PAUSED, so it does not "
              "spend. Re-run apply — it resumes from state and only retries this flip.",
              file=sys.stderr)
        raise SystemExit(1) from e
    state.data.setdefault("adsets_activated", {})[key] = adset_id
    state.save()
    print(f"  + {key} {adset_id}: ACTIVE")


def activate_campaign(spec: dict, state: State, campaign_id: str, dry: bool) -> None:
    """Flip a campaign this run created PAUSED to ACTIVE, once, after its tree is complete.

    Recorded as state.campaign_activated so a resume neither repeats nor skips it. A reused
    campaign (spec.campaign.id) and a create_status: PAUSED build are left untouched."""
    if spec["create_status"] != "ACTIVE" or spec["campaign"].get("id"):
        return
    if dry:
        print("  - campaign status: created PAUSED, flipped ACTIVE once every ad set and ad "
              "exists (real run only)")
        return
    if state.data.get("campaign_activated") == campaign_id:
        print(f"  = campaign {campaign_id}: ACTIVE (from state, skipped)")
        return
    try:
        # A status flip is safe to repeat, so a dropped connection may retry.
        graph.post(campaign_id, {"status": "ACTIVE"}, context="activate campaign",
                   idempotent=True)
    except graph.GraphError as e:
        state.fail("campaign_activate", e.as_dict())
        print(f"  x campaign {campaign_id}: ACTIVATE FAILED\n      {e}", file=sys.stderr)
        print("      Every ad set and ad exists (ACTIVE), but the campaign is still PAUSED, so "
              "nothing spends. Re-run apply — it resumes from state and only retries this flip.",
              file=sys.stderr)
        raise SystemExit(1) from e
    state.data["campaign_activated"] = campaign_id
    state.save()
    print(f"  + campaign {campaign_id}: ACTIVE")


def live_summary(spec: dict, state: State) -> str:
    """One line naming exactly what is live after an ACTIVE build."""
    objects = state.data.get("objects") or {}
    adsets = sum(1 for k in objects if k.startswith("adset["))
    ads = sum(1 for k in objects if k.startswith("ad["))
    campaign_id = objects.get("campaign")
    on = adsets
    if spec["campaign"].get("id"):
        camp = f"reused campaign {campaign_id} (status left as it was)"
        if spec.get("create_status") == "ACTIVE":
            # Ad sets under a reused campaign are created PAUSED and flipped one by one.
            on = len(state.data.get("adsets_activated") or {})
    elif state.data.get("campaign_activated") == campaign_id:
        camp = f"campaign {campaign_id} ACTIVE"
    else:
        camp = f"campaign {campaign_id} still PAUSED"
    tail = f" ({adsets - on} still PAUSED, re-run apply)" if on < adsets else ""
    return f"LIVE: {camp}, {on} ad set(s) ACTIVE{tail}, {ads} ad(s) ACTIVE."


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--dry-run", action="store_true", help="validate_only; create nothing")
    ap.add_argument("--state", help=f"default {STATE_DIR}/<run_id>.json")
    ap.add_argument("--start-override", help="future ISO-8601 start_time for ad sets not yet created (resume)")
    args = ap.parse_args()

    spec = load_spec(args.spec)
    for warning in spec_warnings(spec):
        print(f"WARNING: {warning}", file=sys.stderr)
    graph.require_write_authority("POST", f"{spec['account_id']}/campaigns")
    state_path = args.state or os.path.join(STATE_DIR, f"{spec['run_id']}.json")
    state = State(state_path)

    if args.dry_run:
        mode = "DRY RUN (validate_only)"
    elif spec["create_status"] == "ACTIVE" and not spec["campaign"].get("id"):
        mode = "CREATE (ad sets/ads ACTIVE; campaign PAUSED until the tree is complete, then ACTIVE)"
    elif spec["create_status"] == "ACTIVE":
        mode = "CREATE (reused campaign: ad sets created PAUSED, each flipped ACTIVE once its ads exist)"
    else:
        mode = f"CREATE (all objects {spec['create_status']})"
    print(f"Graph {graph.API_VERSION} · {spec['account_id']} · {mode} · {spec['budget_mode']}")
    print(f"state → {state_path}\n")

    run(spec, state, args.dry_run, args.start_override)

    if args.dry_run:
        print("\nDry run passed: campaign and creatives validated by the API (validate_only); "
              "ad sets and ads validated LOCALLY only — their parents do not exist yet. The real "
              "run validate_only-probes each of them against the live parent before creating it.")
    elif spec["create_status"] == "PAUSED":
        print(f"\nCreated PAUSED in {state_path}. Return to metaops verify.")
        print("Nothing spends until workspace-bound metaops activation with explicit approval.")
    else:
        print(f"\n{live_summary(spec, state)} State: {state_path}. Spend has started.")
        print("Read effective_status, spend, destination, and the tracker receipt within the hour.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

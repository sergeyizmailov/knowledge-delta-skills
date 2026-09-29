#!/usr/bin/env python3
"""Bulk-rewrite url_tags / template_url_spec / ad copy on LIVE ads, via clone-and-swap.

Besides tracking tags this edits everything a link ad shows: primary text (--message /
--message-file), headline, description (--description "" removes it), display link
(--caption), destination (--link) and image (--image-hash from `metaops media`). Any of
those changes the creative, so the ad goes back through review; an ad that was rejected
(effective_status DISAPPROVED, or any ad_review_feedback on it - a rejected ad that is paused,
or sits under a paused parent, shows the pause in effective_status instead) is left alone
(operator rule: never edit or resubmit after a rejection) unless --allow-disapproved. An edit
that would leave the creative byte-identical is skipped ("no change"): no clone, no swap, no
re-review. --all covers ACTIVE ads only.

    python3 edit_tags.py --ids 111,222 --url-tags "utm_campaign={{campaign.name}}" --confirm TAGS
    python3 edit_tags.py --ids 111 --message-file text.txt --headline "Read this" --confirm TAGS
    python3 edit_tags.py --state run.json --url-tags "sub1={{ad.id}}" \\
        --template-url "https://x.example/?id={{product.id}}" --confirm TAGS --dry-run
    python3 edit_tags.py --account act_1 --all --url-tags "sub1={{ad.id}}" --confirm TAGS

Why clone-and-swap, not an in-place PATCH: `url_tags` and `template_url_spec` are
CREATE-only fields on AdCreative (facebook_business SDK 26.0.1 — `AdCreative.api_update`
param_types = {account_id, adlabels, name, status}; url_tags/template_url_spec are absent
there, only present in `AdAccount.create_ad_creative`'s param_types). Meta simply does not
accept a POST that changes an existing creative's url_tags. So per ad this script: (1)
reads the ad's current creative, (2) if it carries ONLY fields this script knows are safe
to reproduce (CLONEABLE_CREATIVE_FIELDS below), creates a NEW creative that is a verbatim
copy of those plus the one tag change, via POST {account}/adcreatives, (3) swaps the ad
onto it via POST /{ad_id} data={"creative": {"creative_id": new_id}} — `Ad.api_update`
param_types include `'creative': 'AdCreative'`, same SDK, confirming this swap path
exists. The OLD creative is left in place, unused, never deleted. If the swap itself
fails after the clone succeeded, the new creative is left unattached — never deleted
automatically — and its id is printed/recorded so an operator can find and clean it up.

If the creative carries any field this script cannot faithfully reproduce
(UNCLONEABLE_REASONS below — a compliance disclosure, a reference to an existing post,
per-placement customization, ...), the ad is SKIPPED with the offending field(s) named,
never guessed at: a clone-and-swap that silently drops one of those fields ships an ad
that renders or discloses differently from the original, which is worse than not touching
it. This is a deliberate scope limit, not an oversight — see references/16.

Catalog / product-ad creatives (product_set_id set) do not read click URLs from
url_tags — Graph resolves catalog card clicks from the product feed and bypasses the
ad's url_tags entirely (04-mass-launch-api.md "url_tags scope"; launch.py build_creative
sets template_url_spec for exactly this reason, scripts/launch.py:707-713). So a catalog
ad here either gets a new template_url_spec (via --template-url) or is SKIPPED with a
clear reason — url_tags is never written to a catalog creative.

Printed on every run, dry or not: NAME macros ({{campaign.name}}, {{adset.name}},
{{ad.name}}) resolve from a snapshot taken at an ad's FIRST publish, so renaming an object
afterwards never reaches an already-set tag (developers.facebook.com/docs/instagram/ads-api/
guides/url-tags-for-tracking, fetched 2026-09-18; mechanism detailed in
references/04-mass-launch-api.md, not restated here). ID macros ({{campaign.id}},
{{adset.id}}, {{ad.id}}) are NOT affected by this — ids are immutable, so there is nothing
to go stale. Either way, this rewrite only changes where FUTURE clicks land.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys

import edit
import graph

TAGS_CONFIRM = "TAGS"

# Every field enumerated below is derived from facebook_business SDK 26.0.1's
# `AdCreative.Field` (adcreative.py), not hand-picked, so nothing on a live creative is
# missed by oversight. Three groups:
#
#   CLONEABLE_CREATIVE_FIELDS  — reproduced byte-for-byte on the clone. Each one is also in
#     `AdAccount.create_ad_creative`'s param_types (SDK 26.0.1), so it is actually
#     re-postable, not just readable.
#
#   UNCLONEABLE_REASONS  — any TRUTHY value on one of these means a clone-and-swap cannot be
#     faithful (see module docstring). The ad is SKIPPED, the field(s) named. This script
#     does not attempt to forward any of these into the CREATE call, on purpose: a wrong
#     guess ships a live ad that silently renders or discloses differently from the
#     original, which is worse than refusing.
#
#   Excluded from the read entirely (comment inline below) — not requested at all.
#
# `id` and `url_tags` are handled specially (id: always read, for logging; url_tags: the
# field this script itself rewrites) and belong to neither group.
CLONEABLE_CREATIVE_FIELDS = (
    "name", "object_story_spec", "asset_feed_spec", "template_url_spec", "product_set_id",
    "degrees_of_freedom_spec", "contextual_multi_ads", "adlabels",
)

# Grouped only for the reason text below; each field is still checked individually.
_SOURCED_FROM_EXISTING = (  # built from a post/media that already exists — no inline spec recreates it
    "existing_post_title", "instagram_permalink_url", "object_id", "object_store_url",
    "object_type", "object_url", "photo_album_source_object_story_id",
    "source_facebook_post_id", "source_instagram_media_id",
)
_DISCLOSURE = (  # a required disclosure/disclaimer a silent clone would drop
    "ad_disclaimer_spec", "authorization_category", "branded_content",
    "branded_content_sponsor_page_id", "facebook_branded_content", "instagram_branded_content",
    "regional_regulation_disclaimer_spec",
)
_ROUTING = (  # per-user/channel destination routing a silent clone would drop
    "applink_treatment", "destination_set_id", "destination_spec", "enable_direct_install",
    "enable_launch_instant_app", "link_deep_link_url", "link_destination_display_url",
    "omnichannel_link_spec", "wamo_whatsapp_identity_spec",
)
_IDENTITY = ("actor_id", "use_page_actor_override")  # overrides which entity the ad displays as
_LEGACY_FLAT = (  # the pre-object_story_spec creative format; this script only reads/clones
    "body", "call_to_action", "call_to_action_type", "image_hash", "image_url", "link_og_id",
    "link_url", "template_url", "thumbnail_id", "thumbnail_url", "title", "video_id",
)
_DYNAMIC_RENDERING = (  # rendering/behavior this script does not model
    "auto_update", "bundle_folder_id", "categorization_criteria", "category_media_source",
    "collaborative_ads_lsb_image_bank_id", "creative_sourcing_spec", "dynamic_ad_voice",
    "format_transformation_spec", "generative_asset_spec", "image_crops",
    "interactive_components_spec", "marketing_message_structured_spec", "media_sourcing_spec",
    "messenger_sponsored_message", "page_welcome_message", "place_page_set_id",
    "platform_customizations", "playable_asset_id", "portrait_customizations", "product_data",
    "product_suggestion_settings", "recommender_settings",
)

# field -> why its presence blocks the clone. object_story_id gets its own message: an ad
# built from an EXISTING organic post cannot be recreated by an inline object_story_spec
# clone at all (there is no post for the clone to point at) — rebuild the ad from the post,
# or set tags at ad creation, instead of running this script on it.
UNCLONEABLE_REASONS: dict[str, str] = {
    "object_story_id": (
        "promotes an EXISTING organic post via object_story_id; an inline object_story_spec "
        "clone cannot recreate a promoted post that already exists. Rebuild this ad from the "
        "post directly, or set url_tags/template_url at ad creation instead."
    ),
    **{f: f"was sourced from an existing post/media ({f}), which a fresh clone cannot recreate"
       for f in _SOURCED_FROM_EXISTING},
    **{f: f"carries a required disclosure field ({f}) a clone would silently drop"
       for f in _DISCLOSURE},
    **{f: f"carries a routing/destination field ({f}) a clone would silently drop, changing "
          f"where clicks land" for f in _ROUTING},
    **{f: f"carries an advertiser-identity override ({f}) a clone would silently drop"
       for f in _IDENTITY},
    **{f: f"uses the legacy top-level creative format ({f}) instead of object_story_spec, "
          f"which this script does not read" for f in _LEGACY_FLAT},
    **{f: f"carries a dynamic/interactive rendering field ({f}) a clone would silently drop "
          f"or misrender" for f in _DYNAMIC_RENDERING},
}

# Excluded from the read entirely, with why:
#   account_id     — belongs to the ad, already read from the ad itself.
#   status         — the CURRENT creative's review state; a new creative starts its own
#                     review, so this carries no cloning signal.
#   effective_authorization_category, effective_instagram_media_id,
#   effective_object_story_id  — mirror RESOLVED state Graph populates for essentially every
#                     live creative, including ordinary object_story_spec ones (Graph
#                     synthesizes a post behind any promotable creative). Using these as the
#                     block signal would flag the common case, not the exceptional one — the
#                     raw fields above (authorization_category, object_story_id) are the
#                     actual discriminators.
#   instagram_user_id  — redundant with object_story_spec.instagram_user_id, which
#                     CLONEABLE_CREATIVE_FIELDS already carries forward in full.
#   execution_options, image_file, is_dco_internal  — create-REQUEST parameters the SDK's
#                     generator also lists under Field; they are not persisted creative
#                     attributes. Requesting them on a GET is expected to error ("Unknown
#                     field") since Graph has nothing to return for them — unverified live
#                     (no live calls made per review scope), excluded defensively either way.
CREATIVE_READ_FIELDS = ",".join(
    ["id", "url_tags", *CLONEABLE_CREATIVE_FIELDS, *UNCLONEABLE_REASONS]
)

MACRO_WARNING = (
    "NAME macros ({{campaign.name}}, {{adset.name}}, {{ad.name}}) resolve from a snapshot "
    "taken at first publish — renaming an object afterwards never reaches an already-set tag "
    "(developers.facebook.com/docs/instagram/ads-api/guides/url-tags-for-tracking; mechanism "
    "detailed in 04-mass-launch-api.md). ID macros ({{campaign.id}}, {{adset.id}}, "
    "{{ad.id}}) are unaffected — ids are immutable. Either way, this rewrite only changes "
    "where FUTURE clicks land"
)


def _graph_mirrors(creative: dict) -> set[str]:
    """Fields Graph auto-populates on every object_story_spec link ad (field-checked live
    2026-09-28 on launch.py creatives): top-level copies of link_data, the page as actor,
    the auto-created IG post, rendered image URLs, a default OPT_OUT sourcing spec. They are
    ignored for blocking ONLY when they match object_story_spec exactly; any mismatch still
    blocks (it would then be a real override the clone would drop)."""
    oss = creative.get("object_story_spec") or {}
    ld = oss.get("link_data")
    if not isinstance(ld, dict):
        return set()
    cta = ld.get("call_to_action") or {}
    same = {
        "actor_id": creative.get("actor_id") == oss.get("page_id"),
        "body": creative.get("body") == ld.get("message"),
        "title": creative.get("title") == ld.get("name"),
        "image_hash": creative.get("image_hash") == ld.get("image_hash"),
        "call_to_action": creative.get("call_to_action") == cta,
        "call_to_action_type": creative.get("call_to_action_type") == cta.get("type"),
        "object_type": creative.get("object_type") == "SHARE",
        "image_url": True, "thumbnail_url": True, "instagram_permalink_url": True,
    }
    css = creative.get("creative_sourcing_spec")
    if isinstance(css, dict) and all(isinstance(v, dict) and v.get("enroll_status") == "OPT_OUT"
                                     for v in css.values()):
        same["creative_sourcing_spec"] = True
    return {k for k, ok in same.items() if ok}


def _opted_out(node) -> bool:
    """True when every enroll_status / status flag found anywhere inside `node` is OPT_OUT."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ("enroll_status", "status") and value != "OPT_OUT":
                return False
            if isinstance(value, (dict, list)) and not _opted_out(value):
                return False
        return True
    if isinstance(node, list):
        return all(_opted_out(item) for item in node)
    return True


def _inert_ui_fields(creative: dict) -> set[str]:
    """Fields Ads Manager writes on every creative it builds (field-checked 2026-09-29 on the CF1
    ads) that are all-OFF defaults: the clone may omit them without changing how the ad renders.
    Anything with an active flag or real content is NOT listed and still blocks the clone.
    Note: the UI also sets `enable_social_feedback_preservation`; a clone does not carry it."""
    oss = creative.get("object_story_spec") or {}
    ld = oss.get("link_data") if isinstance(oss.get("link_data"), dict) else {}
    out: set[str] = set()
    if creative.get("applink_treatment") == "web_only":
        out.add("applink_treatment")
    for name in ("destination_spec", "creative_sourcing_spec"):
        if isinstance(creative.get(name), dict) and _opted_out(creative[name]):
            out.add(name)
    fts = creative.get("format_transformation_spec")
    if isinstance(fts, list) and fts and all(isinstance(x, dict) and x.get("data_source") == ["none"] for x in fts):
        out.add("format_transformation_spec")
    ms = creative.get("media_sourcing_spec")
    if isinstance(ms, dict):
        titles = {t.get("text") for t in ms.get("titles") or [] if isinstance(t, dict)}
        bodies = {b.get("text") for b in ms.get("bodies") or [] if isinstance(b, dict)}
        others = [k for k, v in ms.items() if k not in ("titles", "bodies") and v]
        if not others and titles <= {ld.get("name")} and bodies <= {ld.get("message")}:
            out.add("media_sourcing_spec")
    return out


def _sourcing_opt_in(fields: dict) -> list[str]:
    """creative_sourcing_spec entries enrolled OPT_IN on this creative (what --enhancements-off clears)."""
    css = fields.get("creative_sourcing_spec")
    return sorted(k for k, v in css.items() if isinstance(v, dict) and v.get("enroll_status") == "OPT_IN") \
        if isinstance(css, dict) else []


def _sourcing_spec_for(mode: str, spec: dict) -> dict | None:
    """creative_sourcing_spec to send on an --enhancements-off clone. `drop` omits it (the API-built default,
    but it also loses enable_social_feedback_preservation, which Ads Manager sets)."""
    if mode == "drop":
        return None
    if mode == "opt_out":
        out = copy.deepcopy(spec)
        for node in out.values():
            if isinstance(node, dict) and node.get("enroll_status") == "OPT_IN":
                node["enroll_status"] = "OPT_OUT"
        return out
    out = {"featured_offering_spec": {"enroll_status": "OPT_OUT"}}
    if spec.get("enable_social_feedback_preservation"):
        out["enable_social_feedback_preservation"] = True
    return out


def _has_feedback(value) -> bool:
    """True when ad_review_feedback holds at least one non-empty leaf ({"global": {}} is not a rejection)."""
    if isinstance(value, dict):
        return any(_has_feedback(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(_has_feedback(v) for v in value)
    return bool(value)


REVIEW_WARNING = (
    "text / headline / description / CTA / link / image changes make Meta review the ad again "
    "(the ad goes back to PENDING_REVIEW). A rename was field-checked 2026-09-29 on 3 approved ads: "
    "ACTIVE -> IN_PROCESS -> ACTIVE in ~15 s, no review wait. A clone-and-swap creates a NEW "
    "creative and probably a new post, so likes / comments / moderation state of the old post are "
    "not carried over (unverified)"
)


def _non_empty(flag: str, value: str | None) -> str | None:
    """A value flag that is given must carry text: '' used to be ignored silently, which reads
    as "done" while nothing changed. Only --description / --caption take '' (meaning remove)."""
    if value is not None and not value.strip():
        sys.exit(f"{flag} is empty; pass a value (only --description / --caption accept \"\" to remove the field)")
    return value


def collect_link_edits(args) -> dict[str, str]:
    """Flags -> the link_data changes to make. Unset flags are absent; an empty string is a real
    value only for --description / --caption (it removes the field), every other flag rejects it."""
    edits: dict[str, str] = {}
    if _non_empty("--headline", args.headline) is not None:
        edits["name"] = args.headline
    if _non_empty("--cta", args.cta) is not None:
        edits["cta"] = args.cta
    message = args.message
    if _non_empty("--message-file", args.message_file) is not None:
        try:
            with open(args.message_file, encoding="utf-8") as fh:
                message = fh.read()
        except OSError as e:
            sys.exit(f"--message-file unreadable: {e}")
        if message.endswith("\n"):
            message = message[:-1]
    if message is not None:
        if not message.strip():
            sys.exit("primary text is empty; refusing to blank an ad's message")
        edits["message"] = message
    if args.description is not None:
        edits["description"] = args.description
    if args.caption is not None:
        edits["caption"] = args.caption
    if _non_empty("--link", args.link) is not None:
        edits["link"] = args.link
    if _non_empty("--image-hash", args.image_hash) is not None:
        edits["image_hash"] = args.image_hash
    return edits


def apply_link_edits(link_data: dict, edits: dict[str, str]) -> None:
    for key in ("name", "message"):
        if key in edits:
            link_data[key] = edits[key]
    for key in ("description", "caption"):
        if key in edits:
            if edits[key] == "":
                link_data.pop(key, None)
            else:
                link_data[key] = edits[key]
    if "cta" in edits:
        link_data.setdefault("call_to_action", {})["type"] = edits["cta"]
    if "link" in edits:
        link_data["link"] = edits["link"]
        value = (link_data.get("call_to_action") or {}).get("value")
        if isinstance(value, dict) and "link" in value:
            value["link"] = edits["link"]
    if "image_hash" in edits:
        link_data["image_hash"] = edits["image_hash"]
        for stale in ("picture", "image_url", "image_crops"):
            link_data.pop(stale, None)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--ids", help="comma-separated ad ids")
    src.add_argument("--state", help="launch.py state file (ad ids)")
    src.add_argument("--account", help="act_<id> with --all")
    ap.add_argument("--all", action="store_true", help="with --account: every ACTIVE ad (effective_status ACTIVE only)")
    ap.add_argument("--url-tags", help="new url_tags string for non-catalog creatives")
    ap.add_argument("--template-url", help="new template_url_spec.web.url for catalog/product-ad creatives")
    ap.add_argument("--headline", help="new link_data.name (headline next to the CTA) for link ads")
    ap.add_argument("--cta", help="new link_data.call_to_action.type (e.g. SEE_DETAILS) for link ads")
    txt = ap.add_mutually_exclusive_group()
    txt.add_argument("--message", help="new primary text (link_data.message) for link ads")
    txt.add_argument("--message-file", help="UTF-8 file holding the new primary text (one trailing newline stripped)")
    ap.add_argument("--description", help='new link_data.description; "" removes it')
    ap.add_argument("--caption", help='new display link (link_data.caption), e.g. example.com; "" removes it')
    ap.add_argument("--link", help="new destination URL (link_data.link, and the CTA value link if it has one)")
    ap.add_argument("--image-hash", help="new image (hash from `metaops media`); replaces link_data.image_hash")
    ap.add_argument("--enhancements-off", action="store_true",
                    help="clone WITHOUT creative_sourcing_spec, which turns off Ads Manager's default "
                         "enrolments (featured_offering_spec = 'Show spotlights'); API-built creatives read back OPT_OUT")
    ap.add_argument("--sourcing-mode", choices=["drop", "opt_out", "flag_only"], default="drop",
                    help="with --enhancements-off: drop = omit creative_sourcing_spec (default); opt_out = send it back "
                         "with every OPT_IN turned OPT_OUT; flag_only = send only the social-feedback flag + "
                         "featured_offering_spec OPT_OUT")
    ap.add_argument("--allow-disapproved", action="store_true",
                    help="also edit ads that were rejected: effective_status DISAPPROVED or ad_review_feedback "
                         "present (default: skip them)")
    ap.add_argument("--confirm", help=f"literal {TAGS_CONFIRM}, required (including --dry-run)")
    ap.add_argument("--expected-account", help="internal metaops profile binding for opaque object ids")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--validate-only", action="store_true",
                    help="like --dry-run, and also POST the new creative with execution_options=[validate_only]: Meta "
                         "checks it, nothing is created, no ad is touched")
    args = ap.parse_args()
    if args.validate_only:
        args.dry_run = True

    graph.require_write_authority(
        "POST", f"{graph.normalize_account(args.account)}/objects" if args.account else "object",
    )

    _non_empty("--url-tags", args.url_tags)
    _non_empty("--template-url", args.template_url)
    link_edits = collect_link_edits(args)
    if not (args.url_tags or args.template_url or link_edits or args.enhancements_off):
        sys.exit("nothing to do — pass --url-tags, --template-url, --enhancements-off, or an ad-copy flag "
                 "(--headline --cta --message --message-file --description --caption --link --image-hash)")
    if args.confirm != TAGS_CONFIRM:
        sys.exit(f"rewriting live tracking tags requires --confirm {TAGS_CONFIRM} (--dry-run too).")

    if args.ids:
        ids = [i.strip() for i in args.ids.split(",") if i.strip()]
    elif args.state:
        ids = edit.ids_from_state(args.state, "ad")
    else:
        if not args.all:
            sys.exit("--account needs --all")
        ids = edit.ids_from_account(graph.normalize_account(args.account), "ad",
                                    statuses=edit.ACTIVE_ONLY_STATUSES)
    if not ids:
        sys.exit("no ids")

    print(f"  ! {MACRO_WARNING}", file=sys.stderr)
    print(f"  ! {REVIEW_WARNING}", file=sys.stderr)

    bad = 0
    results: list[dict] = []
    for oid in ids:
        try:
            ad = graph.get(
                oid,
                params={"fields": f"name,account_id,effective_status,ad_review_feedback,issues_info,"
                                  f"creative{{{CREATIVE_READ_FIELDS}}}"},
                context=f"read {oid}",
            )
        except graph.GraphError as e:
            print(f"  x {oid}: GET failed — refusing to touch this ad: {e}", file=sys.stderr)
            bad += 1
            results.append({"id": oid, "ok": False, "error": f"GET failed: {e}"})
            continue
        if args.expected_account:
            actual = ad.get("account_id")
            if not actual or graph.normalize_account(actual) != graph.normalize_account(args.expected_account):
                print(
                    f"  x {oid}: belongs to {actual or '?'} not {args.expected_account}; refusing cross-profile edit",
                    file=sys.stderr,
                )
                bad += 1
                results.append({"id": oid, "ok": False, "error": "object outside profile account"})
                continue

        # A rejected ad that is also paused (or sits under a paused parent) reports the pause in
        # effective_status, not DISAPPROVED, so the review feedback is the second signal.
        rejected = ad.get("effective_status") == "DISAPPROVED" or _has_feedback(ad.get("ad_review_feedback"))
        if rejected and not args.allow_disapproved:
            why = ("effective_status DISAPPROVED" if ad.get("effective_status") == "DISAPPROVED"
                   else f"ad_review_feedback present (effective_status {ad.get('effective_status')})")
            print(f"  ! {oid} {ad.get('name')}: SKIPPED — ad was rejected ({why}); not editing or resubmitting "
                  f"after a rejection (pass --allow-disapproved to override)", file=sys.stderr)
            row = {"id": oid, "ok": True, "skipped": True,
                   "reason": "ad is DISAPPROVED / has ad_review_feedback; pass --allow-disapproved to edit it anyway",
                   "effective_status": ad.get("effective_status")}
            if ad.get("ad_review_feedback"):
                row["ad_review_feedback"] = ad["ad_review_feedback"]
            if ad.get("issues_info"):
                row["issues_info"] = ad["issues_info"]
            results.append(row)
            continue

        creative = ad.get("creative")
        if not isinstance(creative, dict) or not creative.get("id"):
            print(f"  x {oid} {ad.get('name')}: no readable creative — refusing to guess one", file=sys.stderr)
            bad += 1
            results.append({"id": oid, "ok": False, "error": "no readable creative"})
            continue

        # Refuse rather than degrade: any field here means a clone-and-swap cannot be
        # faithful (see UNCLONEABLE_REASONS / module docstring). Checked before the
        # catalog logic below — a catalog ad can carry one of these too.
        mirrors = _graph_mirrors(creative)
        inert = _inert_ui_fields(creative)
        if args.enhancements_off and creative.get("creative_sourcing_spec"):
            inert = inert | {"creative_sourcing_spec"}
        blocking = [f for f in UNCLONEABLE_REASONS if creative.get(f) and f not in mirrors and f not in inert]
        if blocking:
            print(
                f"  ! {oid} {ad.get('name')}: SKIPPED — creative {creative['id']} carries "
                f"field(s) a clone-and-swap cannot faithfully reproduce "
                f"({', '.join(blocking)}); refusing rather than ship a degraded ad. "
                + "; ".join(UNCLONEABLE_REASONS[f] for f in blocking),
                file=sys.stderr,
            )
            results.append({
                "id": oid, "ok": True, "skipped": True,
                "reason": f"creative carries non-cloneable field(s): {', '.join(blocking)}",
                "fields": blocking,
            })
            continue

        is_catalog = bool(creative.get("product_set_id"))
        if is_catalog and link_edits:
            print(f"  ! {oid} {ad.get('name')}: SKIPPED — catalog creative; ad-copy flags only apply to link ads",
                  file=sys.stderr)
            results.append({"id": oid, "ok": True, "skipped": True,
                            "reason": "catalog creative; ad-copy flags not applicable"})
            continue
        link_data = ((creative.get("object_story_spec") or {}).get("link_data"))
        if link_edits and not isinstance(link_data, dict):
            print(f"  ! {oid} {ad.get('name')}: SKIPPED — no object_story_spec.link_data to edit ad copy on",
                  file=sys.stderr)
            results.append({"id": oid, "ok": True, "skipped": True, "reason": "no link_data"})
            continue
        if is_catalog and not args.template_url:
            note = " (--url-tags given but ignored: does not apply to a catalog creative)" if args.url_tags else ""
            print(
                f"  ! {oid} {ad.get('name')}: SKIPPED — catalog/product-ad creative "
                f"(product_set_id={creative['product_set_id']}); url_tags does not reach catalog click "
                f"URLs (04-mass-launch-api.md 'url_tags scope'). Pass --template-url to set "
                f"template_url_spec on this ad instead.{note}",
                file=sys.stderr,
            )
            results.append({
                "id": oid, "ok": True, "skipped": True,
                "reason": "catalog creative; url_tags not applicable, no --template-url given",
            })
            continue
        if not is_catalog and not (args.url_tags or link_edits or args.enhancements_off):
            print(
                f"  ! {oid} {ad.get('name')}: SKIPPED — non-catalog creative but no --url-tags given "
                f"(--template-url only applies to catalog creatives)",
                file=sys.stderr,
            )
            results.append({
                "id": oid, "ok": True, "skipped": True,
                "reason": "non-catalog creative; no --url-tags given",
            })
            continue

        new_fields = {
            k: copy.deepcopy(creative[k]) for k in CLONEABLE_CREATIVE_FIELDS if creative.get(k) is not None
        }
        if "creative_sourcing_spec" in mirrors:  # keep the OPT_OUT on the clone
            new_fields["creative_sourcing_spec"] = copy.deepcopy(creative["creative_sourcing_spec"])
        elif args.enhancements_off and creative.get("creative_sourcing_spec"):
            spec = _sourcing_spec_for(args.sourcing_mode, creative["creative_sourcing_spec"])
            if spec:
                new_fields["creative_sourcing_spec"] = spec
        def _view(fields: dict) -> dict:
            ld = (fields.get("object_story_spec") or {}).get("link_data") or {}
            msg = ld.get("message")
            return {"url_tags": fields.get("url_tags"), "template_url_spec": fields.get("template_url_spec"),
                    "headline": ld.get("name"), "cta": (ld.get("call_to_action") or {}).get("type"),
                    "description": ld.get("description"), "caption": ld.get("caption"),
                    "link": ld.get("link"), "image_hash": ld.get("image_hash"),
                    "message": None if msg is None else f"{len(msg)} chars: {msg[:60]!r}",
                    "sourcing_opt_in": _sourcing_opt_in(fields)}
        before = _view(creative)
        if is_catalog:
            new_fields["template_url_spec"] = {"web": {"url": args.template_url}}
        else:
            # url_tags is not in CLONEABLE_CREATIVE_FIELDS: carry the live value forward unless replaced
            new_fields["url_tags"] = args.url_tags or creative.get("url_tags")
            if link_edits:
                apply_link_edits(new_fields["object_story_spec"]["link_data"], link_edits)
        after = _view(new_fields)

        # Nothing would change: skip before any clone / swap / re-review. Compared on the FULL
        # link_data (the _view above truncates the message), url_tags and template_url_spec.
        # url_tags is not compared on a catalog creative: it is never written there.
        def _content(fields: dict) -> dict:
            return {
                "url_tags": None if is_catalog else (fields.get("url_tags") or None),
                "template_url_spec": fields.get("template_url_spec") or None,
                "link_data": (fields.get("object_story_spec") or {}).get("link_data") or None,
                "sourcing_opt_in": _sourcing_opt_in(fields),
            }
        if _content(creative) == _content(new_fields):
            print(f"  = {oid} {ad.get('name')}: SKIPPED — no change (creative {creative['id']} already "
                  f"matches the requested values); no clone, no swap, no re-review", file=sys.stderr)
            results.append({"id": oid, "ok": True, "skipped": True, "reason": "no change"})
            continue

        if args.dry_run:
            print(f"  would clone creative {creative['id']} with the tag change and swap ad /{oid} onto it")
            print(f"    before: {json.dumps(before, sort_keys=True)}")
            print(f"    after:  {json.dumps(after, sort_keys=True)}")
            row = {"id": oid, "ok": True, "dry_run": True, "before": before, "after": after}
            if args.validate_only:
                try:
                    graph.post(f"{graph.normalize_account(ad['account_id'])}/adcreatives",
                               dict(new_fields, execution_options=["validate_only"]),
                               context=f"validate clone creative for {oid}", idempotent=True)
                    row["validated"] = True
                    print(f"  ✓ {oid}: Meta accepts this creative (validate_only, nothing created, ad untouched)")
                except graph.GraphError as e:
                    print(f"  x {oid}: Meta rejects this creative: {e}", file=sys.stderr)
                    row.update({"ok": False, "validated": False, "error": str(e)})
                    bad += 1
            results.append(row)
            continue

        # Tracked across the try block so a failure after the clone succeeded (swap or
        # readback) can report the new creative id instead of losing track of it — it is
        # never deleted automatically (module docstring), so the id is the only way an
        # operator finds it again.
        new_creative_id: str | None = None
        swapped = False
        try:
            created = graph.post(
                f"{graph.normalize_account(ad['account_id'])}/adcreatives", new_fields,
                context=f"clone creative for {oid}",
            )
            new_creative_id = created.get("id")
            if not new_creative_id:
                raise graph.GraphError(
                    0, {"error": {"message": "adcreatives POST returned no id", "code": -1}},
                    f"clone creative for {oid}",
                )
            graph.post(
                oid, {"creative": {"creative_id": new_creative_id}},
                context=f"swap creative on {oid}", idempotent=True,
            )
            swapped = True
            back = graph.get(
                oid, params={"fields": f"name,effective_status,creative{{{CREATIVE_READ_FIELDS}}}"},
                context="readback",
            )
            back_creative = back.get("creative") or {}
            print(
                f"  ✓ {oid} {back.get('name')}: creative {creative['id']} -> {new_creative_id} "
                f"effective_status={back.get('effective_status')} "
                f"(url_tags={back_creative.get('url_tags')!r} "
                f"template_url_spec={back_creative.get('template_url_spec')}) — {MACRO_WARNING}"
            )
            results.append({
                "id": oid, "ok": True, "name": back.get("name"),
                "effective_status": back.get("effective_status"),
                "old_creative_id": creative["id"], "new_creative_id": new_creative_id,
                "url_tags": back_creative.get("url_tags"),
                "template_url_spec": back_creative.get("template_url_spec"),
            })
        except graph.GraphError as e:
            bad += 1
            if new_creative_id and not swapped:
                # The clone (adcreatives POST) succeeded but the swap onto {oid} did not:
                # the new creative exists, unattached to any ad, and is NOT cleaned up here.
                print(
                    f"  x {oid}: {e}\n"
                    f"  ! {oid}: creative {new_creative_id} was created and left UNATTACHED "
                    f"(the swap onto /{oid} failed after cloning) — find and clean it up "
                    f"manually, it is not deleted automatically.",
                    file=sys.stderr,
                )
                results.append({
                    "id": oid, "ok": False, "error": str(e),
                    "orphaned_creative_id": new_creative_id,
                })
            elif new_creative_id and swapped:
                # The swap itself went through — the ad IS on the new creative — only the
                # read-back that confirms it failed. Not an orphan: do not call it one.
                print(
                    f"  x {oid}: swap to creative {new_creative_id} likely succeeded but the "
                    f"read-back failed to confirm it: {e}",
                    file=sys.stderr,
                )
                results.append({
                    "id": oid, "ok": False, "error": str(e),
                    "new_creative_id": new_creative_id, "swap_unconfirmed": True,
                })
            else:
                print(f"  x {oid}: {e}", file=sys.stderr)
                results.append({"id": oid, "ok": False, "error": str(e)})

    print(json.dumps({
        "schema": "edit_tags.result/v1", "dry_run": args.dry_run, "validate_only": args.validate_only, "ok": bad == 0,
        "count": len(ids), "failed": bad, "warning": MACRO_WARNING, "results": results,
    }, ensure_ascii=False))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

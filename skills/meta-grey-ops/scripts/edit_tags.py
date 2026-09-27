#!/usr/bin/env python3
"""Bulk-rewrite url_tags / template_url_spec on LIVE ads, via clone-and-swap.

    python3 edit_tags.py --ids 111,222 --url-tags "utm_campaign={{campaign.name}}" --confirm TAGS
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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--ids", help="comma-separated ad ids")
    src.add_argument("--state", help="launch.py state file (ad ids)")
    src.add_argument("--account", help="act_<id> with --all")
    ap.add_argument("--all", action="store_true", help="with --account: every ACTIVE ad")
    ap.add_argument("--url-tags", help="new url_tags string for non-catalog creatives")
    ap.add_argument("--template-url", help="new template_url_spec.web.url for catalog/product-ad creatives")
    ap.add_argument("--confirm", help=f"literal {TAGS_CONFIRM}, required (including --dry-run)")
    ap.add_argument("--expected-account", help="internal metaops profile binding for opaque object ids")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    graph.require_write_authority(
        "POST", f"{graph.normalize_account(args.account)}/objects" if args.account else "object",
    )

    if not args.url_tags and not args.template_url:
        sys.exit("nothing to do — pass --url-tags and/or --template-url")
    if args.confirm != TAGS_CONFIRM:
        sys.exit(f"rewriting live tracking tags requires --confirm {TAGS_CONFIRM} (--dry-run too).")

    if args.ids:
        ids = [i.strip() for i in args.ids.split(",") if i.strip()]
    elif args.state:
        ids = edit.ids_from_state(args.state, "ad")
    else:
        if not args.all:
            sys.exit("--account needs --all")
        ids = edit.ids_from_account(graph.normalize_account(args.account), "ad")
    if not ids:
        sys.exit("no ids")

    print(f"  ! {MACRO_WARNING}", file=sys.stderr)

    bad = 0
    results: list[dict] = []
    for oid in ids:
        try:
            ad = graph.get(
                oid,
                params={"fields": f"name,account_id,creative{{{CREATIVE_READ_FIELDS}}}"},
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

        creative = ad.get("creative")
        if not isinstance(creative, dict) or not creative.get("id"):
            print(f"  x {oid} {ad.get('name')}: no readable creative — refusing to guess one", file=sys.stderr)
            bad += 1
            results.append({"id": oid, "ok": False, "error": "no readable creative"})
            continue

        # Refuse rather than degrade: any field here means a clone-and-swap cannot be
        # faithful (see UNCLONEABLE_REASONS / module docstring). Checked before the
        # catalog logic below — a catalog ad can carry one of these too.
        blocking = [f for f in UNCLONEABLE_REASONS if creative.get(f)]
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
        if not is_catalog and not args.url_tags:
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
        before = {"url_tags": creative.get("url_tags"), "template_url_spec": creative.get("template_url_spec")}
        if is_catalog:
            new_fields["template_url_spec"] = {"web": {"url": args.template_url}}
        else:
            new_fields["url_tags"] = args.url_tags
        after = {"url_tags": new_fields.get("url_tags"), "template_url_spec": new_fields.get("template_url_spec")}

        if args.dry_run:
            print(f"  would clone creative {creative['id']} with the tag change and swap ad /{oid} onto it")
            print(f"    before: {json.dumps(before, sort_keys=True)}")
            print(f"    after:  {json.dumps(after, sort_keys=True)}")
            results.append({"id": oid, "ok": True, "dry_run": True, "before": before, "after": after})
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
                oid, params={"fields": f"name,creative{{{CREATIVE_READ_FIELDS}}}"}, context="readback",
            )
            back_creative = back.get("creative") or {}
            print(
                f"  ✓ {oid} {back.get('name')}: creative {creative['id']} -> {new_creative_id} "
                f"(url_tags={back_creative.get('url_tags')!r} "
                f"template_url_spec={back_creative.get('template_url_spec')}) — {MACRO_WARNING}"
            )
            results.append({
                "id": oid, "ok": True, "name": back.get("name"),
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
        "schema": "edit_tags.result/v1", "dry_run": args.dry_run, "ok": bad == 0,
        "count": len(ids), "failed": bad, "warning": MACRO_WARNING, "results": results,
    }, ensure_ascii=False))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

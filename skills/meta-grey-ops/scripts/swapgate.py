"""White->target catalog swap gate, shared by every path that changes what a catalog ad shows:
`assets swap` (one set's filter), `assets set-products`, `feed swap` (sheet rows) and
`catalog products batch` (items_batch). Read-only; the callers do the writes.

Rules (operator 2026-09-26, field lessons 26.09):
- Swap THE MOMENT the ads on a set are approved. Never wait for first delivery: every white
  impression is wasted spend. Each set is judged on its OWN ads: a rejected or in-review ad on
  another set never holds this one.
- Hold only while an ad that shows the changed content is still in review (the reviewer would
  see the target product). A rejected ad on the same set is reported, not blocking: it serves
  nothing, but a later "request review" would show the target (warn).
- Catalog-level edits (feed / items_batch) reach every set whose members include the edited
  items, plus every rule-based set (its membership can shift with the new rows).
- After the swap only the product changes: headline/description must be product macros and the
  primary text neutral, or the white text stays under the target card.
"""

from __future__ import annotations

import functools
import json
import re
from typing import Any

import graph


def _catalog_token(fn):
    """The wrapped function reads catalog objects: use the catalog token (tokens.py)."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with graph.using_capability("catalog"):
            return fn(*args, **kwargs)
    return wrapper

# Ad under review: the reviewer would see whatever the set holds right now.
REVIEW = {"PENDING_REVIEW", "IN_PROCESS"}
# Approved and serving (or allowed to serve).
APPROVED = {"ACTIVE"}
# Rejected / broken: serves nothing, reported only.
REJECTED = {"DISAPPROVED", "WITH_ISSUES"}
# Ad reference (v26): a new ad "will have the ad status PENDING_REVIEW before it finishes review and
# reverts back to your selected status of ACTIVE or PAUSED" -> an ad-level PAUSED is reviewed and, with
# no DISAPPROVED, approved. What ADSET_PAUSED / CAMPAIGN_PAUSED show during review is NOT documented, so
# those need --paused-ok. PREAPPROVED / IN_PROCESS are undocumented -> treated like review.
APPROVED = APPROVED | {"PAUSED"}
PAUSED = {"ADSET_PAUSED", "CAMPAIGN_PAUSED"}
PRE = {"PREAPPROVED"}
GONE = {"DELETED", "ARCHIVED"}

NEUTRAL_MESSAGE = re.compile(r"^[\W_]*$")  # dashes/emoji only: nothing white OR casino survives
# Any documented catalog template tag follows the product: name, description, brand, price,
# current_price, retailer_id, url, custom_label_0..4 (+ options/transforms inside the braces).
PRODUCT_TAG = re.compile(r"\{\{\s*product\.\w+")
ID_FILTER_OPS = {"eq", "is_any"}

AD_FIELDS = ("id,name,effective_status,adset{promoted_object{product_set_id}},"
             "creative{product_set_id,asset_feed_spec{ad_formats},"
             "object_story_spec{template_data{name,description,message,force_single_link}}}")
COLLECTION_MIN = 4  # 2490457: a COLLECTION creative needs >= 4 items in its set


def classify(status: str | None, paused_ok: bool = False) -> str:
    s = str(status or "")
    if s in APPROVED:
        return "approved"
    if s in REVIEW or s in PRE:
        return "review"
    if s in REJECTED:
        return "rejected"
    if s in GONE:
        return "gone"
    if s in PAUSED:
        return "approved" if paused_ok else "paused"
    return "other"


def catalog_ads(account: str) -> list[dict[str, Any]]:
    """Every catalog ad in the account with its product set, status and card texts."""
    rows: list[dict[str, Any]] = []
    params: dict[str, Any] = {"fields": AD_FIELDS, "limit": 500}
    while True:
        resp = graph.get(f"{account}/ads", params=params, context="swap gate ads")
        for ad in resp.get("data", []):
            creative = ad.get("creative") or {}
            set_id = str(creative.get("product_set_id")
                         or (((ad.get("adset") or {}).get("promoted_object") or {}).get("product_set_id"))
                         or "")
            if not set_id:
                continue
            td = ((creative.get("object_story_spec") or {}).get("template_data") or {})
            formats = (creative.get("asset_feed_spec") or {}).get("ad_formats") or []
            # Field 2026-09-27: Meta rewrites a template_data carousel to FORMAT_AUTOMATION
            # [CAROUSEL, COLLECTION] even when only CAROUSEL is sent -> "carousel_auto".
            fmt = ("carousel_auto" if {"COLLECTION", "CAROUSEL"} <= set(formats) else
                   "collection" if "COLLECTION" in formats else
                   "single" if td.get("force_single_link") else "carousel")
            rows.append({"ad": str(ad["id"]), "name": ad.get("name"), "set": set_id, "format": fmt,
                         "status": ad.get("effective_status"),
                         "headline": td.get("name"), "description": td.get("description"),
                         "message": td.get("message")})
        params = graph.next_page_params(resp, params)
        if params is None:
            return rows


def lifetime_impressions(account: str) -> dict[str, int]:
    """One account-level call (not one per ad); for the report only, never a gate."""
    out: dict[str, int] = {}
    params: dict[str, Any] = {"level": "ad", "fields": "ad_id,impressions", "date_preset": "maximum",
                              "limit": 500}
    while True:
        resp = graph.get(f"{account}/insights", params=params, context="swap gate delivery")
        for r in resp.get("data", []):
            out[str(r.get("ad_id"))] = int(r.get("impressions") or 0)
        params = graph.next_page_params(resp, params)
        if params is None:
            return out


def text_blockers(row: dict[str, Any], allow_message: bool = False) -> list[str]:
    """After a swap only the product changes. Headline/description must come from the product
    ({{product.name}}/{{product.description}}): otherwise Meta keeps a fixed text or scrapes the
    LINK's <title> (field 2026-09-26: PWA white page "Your Little Hero: Kids Stories" under a
    casino card). Primary text never follows a swap, so it must be neutral (e.g. `-----`)."""
    out = []
    tag = f"{row['ad']} {row.get('name')}"
    if not PRODUCT_TAG.search(row.get("headline") or ""):
        out.append(f"{tag}: headline {row.get('headline')!r} has no product tag like {{{{product.name}}}} "
                   "(stays white / page title after swap; rebuild the ad with the current launch.py)")
    # Field 2026-09-27: on a catalog CAROUSEL creative Meta stores no template_data.description (the
    # create sends {{product.description}}, the read-back is empty); cards render per product. Only a
    # FIXED description is a problem there.
    if row.get("format") in ("carousel", "carousel_auto") and row.get("description") is None:
        pass
    elif not PRODUCT_TAG.search(row.get("description") or ""):
        out.append(f"{tag}: description {row.get('description')!r} has no product tag like {{{{product.description}}}}")
    if not allow_message and not NEUTRAL_MESSAGE.match(row.get("message") or ""):
        out.append(f"{tag}: primary text {row.get('message')!r} stays after swap; use a neutral one like "
                   "'-----' (new ad) or pass --allow-message")
    return out


@_catalog_token
def target_items(catalog_id: str, rids: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
    """The swapped-in items are what renders: each must exist, be published and carry a real
    title, description and image."""
    resp = graph.get(f"{catalog_id}/products", params={
        "filter": json.dumps({"retailer_id": {"is_any": rids}}),
        "fields": "retailer_id,name,description,image_url,visibility,review_status", "limit": 500},
        context="swap target items")
    by_rid = {i.get("retailer_id"): i for i in resp.get("data") or []}
    items, bad = [], []
    for rid in rids:
        item = by_rid.get(rid)
        if not item:
            items.append({"retailer_id": rid})
            bad.append(f"target {rid}: not in catalog {catalog_id}")
            continue
        items.append(item)
        bad += [f"target {rid}: empty {k}" for k in ("name", "description", "image_url")
                if not str(item.get(k) or "").strip()]
        if item.get("visibility") not in (None, "published"):
            bad.append(f"target {rid}: visibility {item.get('visibility')}")
        review = str(item.get("review_status") or "").lower()  # "", pending, rejected, approved, outdated
        if review == "rejected":
            bad.append(f"target {rid}: item review_status rejected (the card would not render)")
        elif review in ("pending", "outdated"):
            item["warning"] = f"target {rid}: item review_status {review}; it may not serve until approved"
    return items, bad


# Words a reviewer reads as gambling. White items are what review sees, so none of these may appear
# in a white item's name/description (ru / ky / en / tr + brands we run). Target items may carry them.
TARGET_WORDS = re.compile(
    r"казино|casino|кумар|слот|slot|джекпот|jackpot|ставк|беттинг|букмекер|рулетк|roulette|фриспин|вращени|"
    r"free ?spins?|\bfs\b|бонус|bonus|депозит|deposit|выигр|утуш|\bwin(s|ning)?\b|kazan|bahis|"
    r"1win|1xbet|mostbet|pinco|pin-up|boostwin|zazino|mplay|мплей", re.I)


@_catalog_token
def white_item_problems(set_id: str) -> list[str]:
    """The set's CURRENT items are what review sees. Each must have its own name + description
    (an empty one leaves Meta to fill the card from the link page) and no gambling words."""
    out = []
    resp = graph.get(f"{set_id}/products", params={"fields": "retailer_id,name,description,image_url",
                                                  "limit": 50}, context="white items")
    items = resp.get("data") or []
    if not items:
        return [f"set {set_id}: empty (the ad will not deliver)"]
    for it in items:
        rid = it.get("retailer_id")
        for k in ("name", "description", "image_url"):
            if not str(it.get(k) or "").strip():
                out.append(f"white {rid} in set {set_id}: empty {k}")
        hit = TARGET_WORDS.search(f"{it.get('name') or ''} {it.get('description') or ''}")
        if hit:
            out.append(f"white {rid} in set {set_id}: {hit.group(0)!r} in name/description (review reads it "
                       "under the white card; target wording belongs in the TARGET item)")
    return out


@_catalog_token
def set_state(set_id: str) -> dict[str, Any]:
    """Filter + current members of one set."""
    info = graph.get(set_id, params={"fields": "id,name,filter,product_count"}, context="swap set")
    raw = info.get("filter")
    try:
        filt = json.loads(raw) if isinstance(raw, str) else (raw or {})
    except ValueError:
        filt = {}
    members: list[str] = []
    params: dict[str, Any] = {"fields": "retailer_id", "limit": 500}
    while True:
        resp = graph.get(f"{set_id}/products", params=params, context="swap set products")
        members += [str(p.get("retailer_id")) for p in resp.get("data", [])]
        params = graph.next_page_params(resp, params)
        if params is None or len(members) >= 5000:
            break
    return {"set": set_id, "name": info.get("name"), "filter": filt, "members": members,
            "product_count": info.get("product_count"), "rule_based": not id_only_filter(filt)}


def id_only_filter(filt: Any) -> bool:
    """True when membership is a fixed retailer_id list (eq / is_any), so new catalog rows can't
    slip in. Anything else (product_type, custom_label, and/or trees) is rule-based."""
    if isinstance(filt, dict) and set(filt) <= {"and", "or"} and len(filt) == 1:
        parts = next(iter(filt.values()))  # and/or wrap of id-only parts (duplicate-filter workaround)
        return isinstance(parts, list) and bool(parts) and all(id_only_filter(p) for p in parts)
    if not isinstance(filt, dict) or set(filt) != {"retailer_id"}:
        return False
    cond = filt["retailer_id"]
    return isinstance(cond, dict) and bool(cond) and set(cond) <= ID_FILTER_OPS


def judge_set(set_id: str, ads: list[dict[str, Any]], *, paused_ok: bool = False,
              allow_message: bool = False, check_texts: bool = True, revert: bool = False,
              n_items: int | None = None) -> dict[str, Any]:
    """Verdict for one set: ready (swap now) | waiting (an ad on it is still in review) |
    blocked (fix needed: texts, unused set, only paused ads with unknown review, too few items).
    revert=True (target -> white): showing white to a reviewer is the point, so review never
    holds it and texts are not checked."""
    own = [a for a in ads if a["set"] == str(set_id)]
    hard, wait, warn = [], [], []
    if n_items is not None:
        if n_items < COLLECTION_MIN and any(a.get("format") in ("collection", "carousel_auto") for a in own):
            hard.append(f"set {set_id}: a COLLECTION ad uses it, needs >= {COLLECTION_MIN} items, got {n_items} "
                        "(2490457, delivery breaks)")
        if n_items > 1 and own and all(a.get("format") == "single" for a in own):
            warn.append(f"set {set_id}: {n_items} items behind single-card ads; Meta picks which one shows")
    if revert:
        live = [a for a in own if classify(a["status"], True) != "gone"]
        if not live:
            hard.append(f"set {set_id}: no ad in this account uses it (wrong alias, or ads deleted)")
        return {"set": str(set_id), "verdict": "blocked" if hard else "ready", "ads": own,
                "blockers": hard, "waiting": [], "warnings": warn}
    live = [a for a in own if classify(a["status"], paused_ok) not in ("gone",)]
    if not live:
        hard.append(f"set {set_id}: no ad in this account uses it (wrong alias, or ads deleted)")
    for a in live:
        kind = classify(a["status"], paused_ok)
        tag = f"{a['ad']} {a.get('name')}"
        if kind == "review":
            wait.append(f"{tag}: {a['status']} (swap fires once it is approved)")
        elif kind == "rejected":
            warn.append(f"{tag}: {a['status']} on this set (serves nothing; a later review request "
                        "would show the target)")
        elif kind == "paused":
            hard.append(f"{tag}: {a['status']} hides whether it was approved; pass --paused-ok if it "
                        "was ACTIVE after review, or activate it first")
        elif kind == "other":
            hard.append(f"{tag}: unexpected status {a['status']}")
        if check_texts and kind in ("approved", "review", "paused"):
            hard += text_blockers(a, allow_message)
    if live and all(classify(a["status"], paused_ok) == "rejected" for a in live):
        hard.append(f"set {set_id}: every ad on it is rejected; swapping serves nothing")
    verdict = "blocked" if hard else "waiting" if wait else "ready"
    return {"set": str(set_id), "verdict": verdict, "ads": own, "blockers": hard, "waiting": wait,
            "warnings": warn}


def item_scope(account: str, rids: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Catalog-level edit of `rids`: which sets (and their ads) show the change."""
    ads = catalog_ads(account)
    touched = []
    want = set(rids)
    for set_id in sorted({a["set"] for a in ads}):
        st = set_state(set_id)
        hit = sorted(want & set(st["members"]))
        if hit or st["rule_based"]:
            st["hit"] = hit
            touched.append(st)
    return touched, ads


def item_gate(account: str, rids: list[str], paused_ok: bool = False) -> dict[str, Any]:
    """Gate for feed swap / items_batch: every ad on an affected set must be out of review.
    Unrelated ads (other sets, other items) never hold it."""
    touched, ads = item_scope(account, rids)
    waiting, warnings, blockers = [], [], []
    for st in touched:
        v = judge_set(st["set"], ads, paused_ok=paused_ok, check_texts=False)
        waiting += v["waiting"]
        warnings += v["warnings"]
        blockers += [b for b in v["blockers"] if "no ad in this account" not in b]
        if st["rule_based"] and not st["hit"]:
            warnings.append(f"set {st['set']} {st['name']}: rule-based filter, the new rows may join it")
    return {"sets": [{k: st[k] for k in ("set", "name", "hit", "rule_based", "product_count")}
                     for st in touched],
            "waiting": waiting, "warnings": warnings, "blockers": blockers,
            "verdict": "blocked" if blockers else "waiting" if waiting else "ready"}

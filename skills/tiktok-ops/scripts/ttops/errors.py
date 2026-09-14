"""TikTok API return codes: cause and what to do.

Source: TikTok "Return Codes" appendix (doc 1737172488964097), fetched 2026-09-14.
Only codes with an action that differs from "read the message" are listed; the
value of this table is the *response*, not the restatement.
"""

from __future__ import annotations

# code -> (short cause, what to do)
CODES = {
    0: ("Success", ""),
    20001: ("Partial success", "Inspect the per-item results; some items failed."),

    40000: ("Invalid parameters", "Check the endpoint reference for correct usage."),
    40001: ("No permission for this operation",
            "Your role on the asset is insufficient. Operator cannot touch account settings, "
            "pixels or identities — you need ad-account Admin. Escalate to the BC admin."),
    40002: ("Parameter error (missing/format/incompatible)",
            "Read the message: it names the field. Common: audience size 0, audience still "
            "processing, or a time not in %Y-%m-%d %H:%M:%S form."),
    40006: ("API version incompatible with these parameters",
            "You are using a newer product on an older version. Use v1.3."),
    40007: ("Object does not exist",
            "The campaign/ad group/ad ID is wrong, deleted, or belongs to another advertiser."),
    40008: ("Endpoint not implemented",
            "Wrong path, or an endpoint unsupported in the sandbox."),
    40009: ("Parameter unsupported in sandbox", "Test this in production or drop the parameter."),
    40010: ("Domain not supported",
            "base_url must be https://business-api.tiktok.com/open_api"),
    40011: ("Too many IDs in one request",
            "Status updates cap at 20 IDs; GET filters at 100. Batch smaller."),
    40013: ("Sandbox account does not exist", "Create one in My Apps first."),
    40014: ("Not supported in sandbox", "Move this test to production."),
    40016: ("Throttled (endpoint, app level)",
            "Back off. QPM breach: wait 5 minutes. QPD: wait until 00:00 UTC+0."),
    40050: ("Duplicate request",
            "request_id deduplicates within 10 seconds. Vary it, or accept the earlier result."),
    40051: ("Invalid API version", "Use v1.3."),
    40052: ("ACO material already exists", "Reuse the existing material or change it."),
    40053: ("Invalid video ID",
            "Get a real one from /file/video/ad/info/ or /file/video/ad/search/. A video "
            "still transcoding is not yet usable."),
    40065: ("Targeting unsupported for US 13-17 age group",
            "Either restrict age_groups to exclude AGE_13_17 or use only supported options."),

    40100: ("Throttled (app level)",
            "Back off. QPM breach: wait 5 minutes. QPD: wait until 00:00 UTC+0. "
            "Note this arrives as HTTP 200 with code 40100, not HTTP 429."),
    40101: ("Invalid authentication parameters",
            "app id/secret mismatch, or a reused auth_code. auth_code is single-use and "
            "expires in 1 hour for Marketing API."),
    40102: ("Access token expired",
            "Marketing API advertiser tokens do NOT expire — if you see this, you are "
            "holding a TikTok-account/creator token (1 day), not an advertiser token."),
    40103: ("Refresh token expired", "The user must re-authorize."),
    40104: ("Access token empty", "TIKTOK_ACCESS_TOKEN is unset or blank."),
    40105: ("Invalid access token", "Token is wrong or revoked. Re-mint; do not retry."),
    40106: ("Core user invalid",
            "This token is not valid for this advertiser_id. Confirm the token was "
            "authorized for THIS ad account."),
    40107: ("Invalid refresh token",
            "You cannot refresh a Marketing API long-term token — it has no refresh flow."),
    40110: ("Invalid authorization code",
            "auth_code is cancelled, used, or expired. Re-run the authorization."),
    40113: ("App blocked or does not exist", "Check App ID and secret in My Apps."),
    40115: ("Authentication timestamp expired", "Re-run authorization; auth_code went stale."),
    40118: ("App or advertiser not on the allowlist",
            "This endpoint or feature is allowlist-only, or unavailable in this country. "
            "Contact the TikTok rep — do not work around it."),
    40119: ("Developer and advertiser are different companies",
            "Token/advertiser mismatch at the company level."),
    40124: ("Developer profile not filled in or not approved",
            "Complete developer registration. Note TikTok requires a company-domain email "
            "and a company-owned public website — individuals cannot register."),
    40125: ("Developer lacks the permission",
            "Missing scope on the app, or an unsupported field."),
    40132: ("Throttled on a specific field value (usually pixel_code)",
            "One pixel is being hammered, or the token leaked. Rotate usage; if unexplained, "
            "treat token compromise as the working hypothesis."),
    40133: ("Throttled (advertiser level)",
            "Lower calls per second against this advertiser. Serialize."),

    40200: ("Task error", "Check the task parameters."),
    40201: ("Task not ready", "Poll again; async report/task still running."),
    40202: ("Write/update entity conflict",
            "Concurrent write on the same object. Retry once, serialized."),
    40300: ("Advertiser does not exist or was deleted", "Wrong advertiser_id."),
    40301: ("Advertiser cannot be matched", "Wrong advertiser_id."),
    40502: ("Max ad limit reached",
            "Create in another ad group/campaign, or delete unused ads."),
    40700: ("Internal service validation error", "Usually a bad parameter combination."),

    40900: ("File signature mismatch", "Recompute the hash for the file you are sending."),
    40901: ("Video transcoding in progress",
            "Not an error — poll /file/video/ad/info/ until the video is ready."),
    40902: ("Cannot fetch URL", "Transient; retry."),
    40903: ("Image URL unavailable", "Transient; retry."),
    40904: ("Illegal image content", "Unsupported image format."),
    40905: ("File does not exist", "Bad path or URL."),
    40906: ("File is empty", "Bad path or URL."),
    40907: ("File too large", "Reduce below the endpoint's size limit."),
    40908: ("Unsupported file type", "Use a supported format."),
    40909: ("Unsupported encryption type", "Fix calculate_type."),
    40910: ("File expired", "Re-upload."),
    40911: ("Duplicate material name",
            "Check with /file/name/check/ and pick another name."),
    40912: ("Image URL unavailable", "Get a valid one from /file/image/ad/info/."),
    40913: ("Cannot fetch image", "Transient; retry."),
    40914: ("Invalid file", "Bad path or URL."),
    40915: ("File does not meet specifications",
            "Check the format/ratio/duration requirements for this endpoint."),

    41001: ("Endpoint is offline", "Path is retired for this API version."),
    41002: ("Fields not in use", "Remove the unrecognised fields."),
}

# Codes where the right move is to stop and get a human, not to retry or adapt.
ESCALATE = {40001, 40105, 40106, 40118, 40119, 40124, 40125, 40132}


def explain(code):
    cause, fix = CODES.get(code, ("Unknown code", "Not in the local catalog — check "
                                 "TikTok's Return Codes appendix (doc 1737172488964097)."))
    return {"code": code, "cause": cause, "action": fix, "escalate": code in ESCALATE}


def format_error(exc):
    info = explain(getattr(exc, "code", None))
    parts = [f"TikTok error {info['code']}: {info['cause']}"]
    msg = getattr(exc, "message", "")
    if msg:
        parts.append(f"  message: {msg}")
    if info["action"]:
        parts.append(f"  action:  {info['action']}")
    rid = getattr(exc, "request_id", None)
    if rid:
        parts.append(f"  request_id: {rid}  (TikTok support asks for this)")
    if info["escalate"]:
        parts.append("  ESCALATE: this is an access/permission/allowlist problem. "
                     "A human with BC Admin has to act; retrying will not help.")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Secondary statuses — what TikTok actually returns on a non-delivering object.
# Source: Enumerations doc 1737174886619138 ("Ad status - secondary status",
# "Ad group status - secondary status", "Campaign Status - Secondary Status"),
# fetched 2026-09-14.
#
# These matter because a create can return code 0 and the object still never
# serves. The string is cryptic and several look alike: AD_STATUS_AUDIT is "in
# review", AD_STATUS_AUDIT_DENY is "rejected". Substring-matching on "AUDIT"
# reads a rejection as a pending review.
# ---------------------------------------------------------------------------

# severity: BLOCKED (will not serve until a human acts) | MONEY | REVIEW | LIVE | INFO
SECONDARY_STATUS = {
    # -- rejected / qualification ------------------------------------------
    "AUDIT_DENY": ("BLOCKED", "Rejected in review. A rejected ad cannot be enabled into "
                              "life — build a new one. Appeal re-reviews the WHOLE ad group "
                              "and you get ONE appeal, so fix everything first."),
    "ADVERTISER_AUDIT_DENY": ("BLOCKED", "The ADVERTISER, not the ad, failed review. "
                                         "Account-level problem — escalate to a human."),
    "INDUSTRY_QUALIFICATION_DENY": ("BLOCKED", "Industry certification refused for this "
                                               "vertical/market. Not fixable by editing the ad."),
    "INDUSTRY_QUALIFICATION_MISSING": ("BLOCKED", "No industry certification on file. File it "
                                                  "BEFORE ads exist; it binds to the verified "
                                                  "entity and this ad account."),
    "INDUSTRY_QUALIFICATION_EXPIRED": ("BLOCKED", "Industry certification expired. Renew it — "
                                                  "delivery will not resume by itself."),
    # -- authorization lost -------------------------------------------------
    # Level-dependent. TikTok's ad-group wording is "Authorization for the asset or
    # assets IN THE AD GROUP is missing" — it does not name which one, so identify
    # the asset before assuming it is a Spark code.
    "ASSET_AUTHORIZATION_LOST": ("BLOCKED", "An asset's authorization is missing or expired. "
                                            "On an AD this is usually the Spark video code: "
                                            "delivery stops immediately, no grace period, the old "
                                            "code cannot be revived — get a fresh one. On an AD "
                                            "GROUP, TikTok says only 'the asset or assets in the "
                                            "ad group' — it could be the identity, a Spark video, "
                                            "the pixel, music, or a catalog. Identify WHICH before "
                                            "acting: check the ads under it, then identity_get / "
                                            "tt_video_info_get / pixel_list_get. This status cannot "
                                            "be used as a GET filter."),
    "MUSIC_AUTHORIZATION_MISSING": ("BLOCKED", "Track not licensed for this use. Note the "
                                               "Commercial Music Library does NOT cover Pangle."),
    "NO_AUTHORIZATION_OF_SHOWCASE": ("BLOCKED", "Showcase access not authorized for this account."),
    "PIXEL_UNBIND": ("BLOCKED", "The pixel is no longer bound. Shared to the Business Center is "
                                "NOT the same as linked to this ad account."),
    "TRANSCODING_FAIL": ("BLOCKED", "Video transcoding failed. Re-encode and re-upload; "
                                    "video_fix_task_create can repair some files."),
    "ANCHOR_UNAVAILABLE": ("BLOCKED", "The anchor is unavailable."),
    "PRODUCT_UNAVAILABLE": ("BLOCKED", "The promoted product is unavailable — check the catalog "
                                       "or Shop listing."),
    # -- money / limits -----------------------------------------------------
    "BALANCE_EXCEED": ("MONEY", "Account balance is exhausted. Prepay stops delivery dead with "
                                "no grace period. The agent CANNOT top up — escalate."),
    "BUDGET_EXCEED": ("MONEY", "Budget spent for the period."),
    "CAMPAIGN_EXCEED": ("MONEY", "Campaign budget spent."),
    "AD_QUOTA_LIMIT": ("MONEY", "Ad quota reached. Create elsewhere or delete unused ads (40502)."),
    "ADVERTISER_ACCOUNT_PUNISH": ("BLOCKED", "The AD ACCOUNT is penalised/suspended. First "
                                             "violation: 30 days to fix or appeal, then permanent "
                                             "and non-appealable. A suspended agency account also "
                                             "cannot create or fund other ad accounts. Fix the "
                                             "violation BEFORE appealing."),
    "ADVERTISER_CONTRACT_PENDING": ("BLOCKED", "Contract not yet in effect."),
    # -- in review ----------------------------------------------------------
    "REAUDIT": ("REVIEW", "Back in review after an edit. Wait; do not keep editing."),
    "ADVERTISER_AUDIT": ("REVIEW", "Advertiser under review."),
    "PROMOTE_AD_OFFLINE_AUDIT": ("REVIEW", "Promoted post under review."),
    "PARTIAL_AUDIT_NO_DELIVERY": ("REVIEW", "Partially approved and NOT delivering."),
    "REVIEW_PARTIALLY_APPROVED": ("REVIEW", "Partially approved — some placements only."),
    "AUDIT": ("REVIEW", "In review. Normal for a new ad; nothing to do but wait."),
    # -- parent state -------------------------------------------------------
    "ADGROUP_DISABLE": ("INFO", "Parent ad group is paused."),
    "CAMPAIGN_DISABLE": ("INFO", "Parent campaign is paused."),
    "ADGROUP_DELETE": ("INFO", "Parent ad group deleted."),
    "CAMPAIGN_DELETE": ("INFO", "Parent campaign deleted."),
    "ADGROUP_CLOSED": ("INFO", "Ad group closed."),
    "FROZEN": ("INFO", "Frozen (Reach & Frequency)."),
    # -- fine ---------------------------------------------------------------
    "PARTIAL_AUDIT_DELIVERY_OK": ("LIVE", "Partially approved and delivering."),
    "DELIVERY_OK": ("LIVE", "Delivering."),
    "PRE_ONLINE": ("INFO", "Scheduled, not started yet."),
    "NOT_START": ("INFO", "Schedule has not begun."),
    "PROCESS_AUDIO": ("INFO", "Audio processing."),
    "DONE": ("INFO", "Finished (schedule ended)."),
    "DISABLE": ("INFO", "Paused."),
    "DELETE": ("INFO", "Deleted."),
}

# Longest key first, so AUDIT_DENY wins over AUDIT and INDUSTRY_QUALIFICATION_DENY
# wins over both. Ordering here is the whole correctness of the lookup.
_STATUS_KEYS = sorted(SECONDARY_STATUS, key=len, reverse=True)


def explain_status(value):
    """Map a secondary_status string to (severity, what to do)."""
    if not value:
        return {"status": value, "severity": "UNKNOWN",
                "action": "No status returned.", "matched": None}
    text = str(value).upper().replace("STAUS", "STATUS")  # TikTok's own typo: AD_STAUS_PIXEL_UNBIND
    for key in _STATUS_KEYS:
        if key in text:
            severity, action = SECONDARY_STATUS[key]
            return {"status": value, "severity": severity, "action": action, "matched": key}
    return {"status": value, "severity": "UNKNOWN",
            "action": "Not in the local table — check the Enumerations doc (1737174886619138).",
            "matched": None}

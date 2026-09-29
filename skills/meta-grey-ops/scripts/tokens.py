"""Token classes: the single source of truth for what each token can do (references/02 §5).

One table, keyed by the 4-char prefix of a scraped first-party token, plus the three classes a
prefix cannot name (System User and user tokens from your own app, and unknown). graph.py routes
by capability from it, probe.py (`doctor`) and cmd_token.py (`token import`) print and gate from it.

Facts only from references/02 and the FB Helper review (the operator's research notes);
every capability carries its evidence level and nothing is listed without evidence:

    verified    read back live by this skill or by the operator (date in the note)
    claimed     extension notes or a practitioner report, not re-run by this skill
    unverified  plausible from a granted scope or the app's purpose, never run

A prefix names the minting app only loosely: it encodes the magnitude of the app id, so an own-app
token can start with the same 4 chars as a first-party one. A class is CONFIRMED only when
`GET /app` returned the class's app id (`token import` records it as `<VAR>_APP_ID`); a prefix-only
answer is a guess and says so (`Classification.confirmed`).

Live probe 2026-09-29 (operator, read-only, one user, all five tokens, Mac, no proxy, shared
cookies): GET /me and GET /app answer for all five; GET act_ID reads for all five; a validate_only
POST on an ad set is ACCEPTED by EAAB, EAAI, EAAG and EAAH (a validation, not a real write; real
writes are unverified for EAAI and EAAH, one PAUSED create + delete worked with EAAG); EAAd cannot
read the ad set node (code 10). Second round the same day: a REAL reversible ad-set rename (write,
read back, restored) succeeded with EAAI, EAAG, EAAH and EAAB; without cookies EAAB, EAAI, EAAG and
EAAH answer code 1 while EAAd still reads; EAAB reads with a default or another browser's User-Agent
(same IP, no proxy); the empty-batch CAPI probe ("must be non-empty" = auth passed) succeeded with
EAAB and EAAd, no event was posted. Not probed: /me/permissions, a real CAPI event, any
cross-IP behaviour. `ads_write_policy` follows from that: EAAd is refused, the rest allowed.

No imports from graph.py: graph.py imports this module.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

CAPABILITIES = ("ads_read", "ads_write", "business_read", "catalog", "events_write", "rules")
VERIFIED, CLAIMED, UNVERIFIED = "verified", "claimed", "unverified"

# capability -> the env var holding its token by default. Ads reads and writes share META_TOKEN,
# the variable every existing script and workspace already uses.
CAPABILITY_VARS: dict[str, str] = {
    "ads_read": "META_TOKEN",
    "ads_write": "META_TOKEN",
    "business_read": "META_TOKEN_BUSINESS",
    "catalog": "META_TOKEN_CATALOG",
    "events_write": "META_TOKEN_EVENTS",
    "rules": "META_TOKEN_RULES",
}
# Capabilities that get a variable of their own (workspace `defaults.token_envs` keys).
ROUTED_CAPABILITIES = ("business_read", "catalog", "events_write", "rules")
COOKIE_SUFFIX = {"business_read": "BUSINESS", "catalog": "CATALOG", "events_write": "EVENTS",
                 "rules": "RULES"}
TOKEN_VARS = tuple(dict.fromkeys(CAPABILITY_VARS.values()))
ENV_NAME = re.compile(r"^[A-Z_][A-Z0-9_]*$")


@dataclass(frozen=True)
class TokenClass:
    key: str                      # EAAB | EAAI | EAAG | EAAH | EAAd | system_user | user | unknown
    name: str
    app_id: str | None            # the minting app of a first-party class
    surface: str                  # where the token is taken from
    capabilities: dict[str, tuple[str, str]]   # capability -> (evidence, note)
    session: tuple[str, str]      # (required | not_needed | unknown, evidence) for cookies+UA+proxy
    default_var: str              # where `token import` writes it
    ads_write_policy: str         # allow | warn | refuse: graph.py's rule for it as an ads writer
    known_failures: dict[str, str] = field(default_factory=dict)
    hint: str = ""
    graph_name: str = ""          # the name GET /app answers with (2026-09-29)

    @property
    def first_party(self) -> bool:
        return self.app_id is not None

    @property
    def needs_cookies(self) -> bool:
        """Verified 2026-09-29: without the session cookies EAAB, EAAI, EAAG and EAAH answer code 1;
        EAAd reads without them."""
        return self.session[0] == "required"


def _caps(*rows: tuple[str, str, str]) -> dict[str, tuple[str, str]]:
    return {cap: (evidence, note) for cap, evidence, note in rows}


_OWN_APP_NOTE = "scope-dependent: read /me/permissions or debug_token"

TOKEN_CLASSES: dict[str, TokenClass] = {
    "EAAB": TokenClass(
        "EAAB", "Ads Manager (Power Editor)", "119211728144504",
        "Ads Manager page source (accessToken=\" / window.__accessToken)",
        _caps(
            ("ads_read", VERIFIED, "live 2026-09-14, 2026-09-29"),
            ("ads_write", VERIFIED, "the launch token; a real ad-set rename + restore and a "
                                    "validate_only write passed 2026-09-29; 190/459 on 2026-09-14 "
                                    "without the session"),
            ("business_read", VERIFIED, "business_management granted live 2026-09-14"),
            ("catalog", VERIFIED, "content only: items_batch, product_sets, set filter edits "
                                  "(2026-09-22); feeds and uploads fail #10"),
            ("events_write", CLAIMED, "empty-batch CAPI probe passed 2026-09-29 (auth only, no event posted)"),
            ("rules", UNVERIFIED, "adrules_library sits under ads_management; not run with an EAAB"),
        ),
        ("required", "verified 2026-09-29: cookies required (no cookies -> code 1), the User-Agent is not "
                     "(default and another browser's UA both passed) on the same IP without a proxy; a "
                     "different IP is untested"),
        "META_TOKEN", "allow",
        {"debug_token": "self-debug returns #100",
         "scopes": "no catalog_management, ads_mcp_management or instagram_basic"},
        "Ads reads and writes. Needs the browser session's cookies (c_user/xs; no cookies -> code 1). "
        "The User-Agent is not required on the same IP (default and another browser's UA both "
        "passed 2026-09-29, no proxy); a different IP is untested, so keep the proxy of the "
        "profile. Dies on logout, password change or checkpoint (190 / 459-467).",
        "Power editor",
    ),
    "EAAI": TokenClass(
        "EAAI", "Automated Rules", "624541620938530",
        "rules management page (extension); practitioner: Billing page, search access_token:",
        _caps(
            ("ads_read", VERIFIED, "GET act_ID 2026-09-29"),
            ("ads_write", VERIFIED, "real ad-set rename + restore 2026-09-29 (activity log: 'via "
                                    "Ads Manager'); one field test, not a record"),
            ("rules", CLAIMED, "GET adrules_library answered (empty list) 2026-09-29; rule "
                               "create / execute not run"),
        ),
        ("required", "verified 2026-09-29: no cookies -> code 1"),
        "META_TOKEN_RULES", "allow",
        {},
        "Rules management. Reads and a real ad-set write work (2026-09-29, needs the cookies). Keep it "
        "in META_TOKEN_RULES; rule create / execute are still unrun.",
        "Ads Manager",
    ),
    "EAAG": TokenClass(
        "EAAG", "Business Manager", "436761779744620",
        "business.facebook.com/settings/people; FB Helper grabs it when no EAAB is present",
        _caps(
            ("ads_read", VERIFIED, "GET act_ID 2026-09-29; 81 scopes granted live 2026-09-27"),
            ("ads_write", VERIFIED, "one live PAUSED create + delete (extension notes) and a real "
                                    "ad-set rename + restore 2026-09-29 (activity log: 'via "
                                    "Business Manager'); single tests, not a field record"),
            ("business_read", VERIFIED, "GET /me/businesses 2026-09-29; business_management "
                                        "granted 2026-09-27"),
        ),
        ("required", "verified 2026-09-29: no cookies -> code 1"),
        "META_TOKEN_BUSINESS", "allow",
        {},
        "Business-surface token, 81 scopes incl. business_management and ads_management; needs the "
        "cookies (no cookies -> code 1). Ad-set writes work (2026-09-29). Not the Events Manager "
        "CAPI token; catalog, events and rules are not evidenced, so nothing is claimed for them.",
        "Business Manager",
    ),
    "EAAH": TokenClass(
        "EAAH", "Commerce Manager", "515496645328243",
        "Commerce Manager (business.facebook.com/commerce/..., F12 graph.facebook.com request)",
        _caps(
            ("catalog", VERIFIED, "catalog content writes (`catalog products batch`, `catalog set "
                                  "create`, 2026-09-26); GET {business}/owned_product_catalogs "
                                  "2026-09-29"),
            ("ads_read", VERIFIED, "GET act_ID 2026-09-29; campaign reads 2026-09-26"),
            ("business_read", VERIFIED, "GET /me/businesses 2026-09-29"),
            ("ads_write", VERIFIED, "real ad-set rename + restore 2026-09-29 on the own BM; an older "
                                    "report says ads writes fail #10 (other BM, 2026-09-26), so "
                                    "it depends on the BM"),
        ),
        ("required", "verified 2026-09-26 and 2026-09-29: needs cookies (no cookies -> code 1)"),
        "META_TOKEN_CATALOG", "allow",
        {"permissions": "/me/permissions -> #10 on two farm BMs 2026-09-26 (not probed "
                        "2026-09-29); doctor skips it for this class",
         "debug_token": "self-debug returns #100"},
        "Catalog and commerce reads/writes plus account and business reads; needs the cookies. Keep it "
        "in META_TOKEN_CATALOG. An ad-set write worked on the own BM 2026-09-29; an older report on "
        "another BM says #10, so it depends on the BM. Doctor skips its scope gate (/me/permissions).",
        "Products",
    ),
    "EAAd": TokenClass(
        "EAAd", "Events Manager", "2094176354154603",
        "events_manager2 (business.facebook.com)",
        _caps(
            ("events_write", VERIFIED, "POST /{dataset}/events with test_event_code: events_received=1 "
                                       "(business capi test, 2026-09-29, twice); the pixel node reads"),
        ),
        ("not_needed", "verified for reads 2026-09-29: /me and the ad account answer with no cookies "
                       "and no UA (the only scraped class that does)"),
        "META_TOKEN_EVENTS", "refuse",
        {"ads_objects": "GET on the ad set node -> code 10 (2026-09-29) although the ad account "
                        "node reads: no ad-object access"},
        "Events only; the one scraped class that needs no cookies for reads. Not the manual CAPI "
        "dataset token (Events Manager 'Generate access token'). Ads writes with it are refused "
        "(no ad-object access).",
        "Ads Events Manager",
    ),
    "system_user": TokenClass(
        "system_user", "System User token (your own app)", None,
        "Business Settings > System users > Generate token",
        _caps(
            ("ads_read", VERIFIED, "02 §3"), ("ads_write", VERIFIED, "02 §3"),
            ("business_read", VERIFIED, "business_management"),
            ("catalog", VERIFIED, "catalog_management, own-BM catalogs"),
            ("events_write", VERIFIED, "02 §5: Full control on the dataset POSTs /events"),
            ("rules", UNVERIFIED, "ads_management"),
        ),
        ("not_needed", "verified: session-independent; proxy discipline still applies"),
        "META_TOKEN", "allow", {}, "Preferred launch token. " + _OWN_APP_NOTE + ".",
    ),
    "user": TokenClass(
        "user", "User token (your own developer app)", None,
        "Graph API Explorer or Facebook Login with your app",
        _caps(
            ("ads_read", VERIFIED, "02 §5"), ("ads_write", VERIFIED, "02 §5"),
            ("business_read", CLAIMED, "business_management if granted"),
            ("catalog", CLAIMED, "catalog_management if granted"),
            ("events_write", CLAIMED, "dataset access if granted"),
            ("rules", UNVERIFIED, "ads_management"),
        ),
        ("not_needed", "claimed: an own-app token needs no cookies; the persona proxy rule holds"),
        "META_TOKEN", "allow", {}, _OWN_APP_NOTE + ".",
    ),
    "unknown": TokenClass(
        "unknown", "Unknown token class", None, "unknown",
        _caps(*((cap, UNVERIFIED, "class not derivable; scopes decide") for cap in CAPABILITIES)),
        ("unknown", "unverified"),
        "META_TOKEN", "allow", {}, "Not a known first-party prefix; read /me/permissions.",
    ),
}
FIRST_PARTY = {key: cls for key, cls in TOKEN_CLASSES.items() if cls.first_party}
# The class recommended when a capability's token is missing (message text only).
FIT_CLASS = {"ads_read": "EAAB", "ads_write": "EAAB", "business_read": "EAAG", "catalog": "EAAH",
             "events_write": "EAAd", "rules": "EAAI"}


@dataclass(frozen=True)
class Classification:
    cls: TokenClass
    source: str        # "app_id" (confirmed by GET /app), "prefix" (a guess), "none"
    confirmed: bool


def by_prefix(token: str | None) -> TokenClass | None:
    return FIRST_PARTY.get((token or "").strip()[:4])


def by_app_id(app_id: str | None) -> TokenClass | None:
    wanted = str(app_id or "").strip()
    return next((cls for cls in FIRST_PARTY.values() if cls.app_id == wanted), None) if wanted else None


def classify(token: str | None, app_id: str | None = None) -> Classification:
    """app id (authoritative) > prefix (a guess). An app id outside the table means an own-app or
    otherwise unknown token whatever its prefix says."""
    if str(app_id or "").strip():
        hit = by_app_id(app_id)
        if hit:
            return Classification(hit, "app_id", True)
        return Classification(TOKEN_CLASSES["unknown"], "app_id", True)
    hit = by_prefix(token)
    if hit:
        return Classification(hit, "prefix", False)
    return Classification(TOKEN_CLASSES["unknown"], "none", False)


def carries(cls: TokenClass, capability: str) -> bool:
    """Does the class provide the capability at any evidence level? Unknown and own-app classes
    carry everything: the granted scopes decide, and that is what the old single-token flow did."""
    return capability in cls.capabilities


def provided(cls: TokenClass) -> list[str]:
    return [cap for cap in CAPABILITIES if cap in cls.capabilities]


def cookie_var(token_var: str, capability: str | None = None) -> str:
    """The cookie variable that goes with a token variable: META_TOKEN -> META_COOKIES,
    META_TOKEN_CATALOG -> META_COOKIES_CATALOG. A custom-named variable uses its capability's
    suffix, else the shared META_COOKIES."""
    if token_var == "META_TOKEN":
        return "META_COOKIES"
    if token_var.startswith("META_TOKEN_"):
        return "META_COOKIES_" + token_var[len("META_TOKEN_"):]
    suffix = COOKIE_SUFFIX.get(capability or "")
    return f"META_COOKIES_{suffix}" if suffix else "META_COOKIES"


def app_id_var(token_var: str) -> str:
    return f"{token_var}_APP_ID"


def mask(token: str) -> str:
    """`EAAB…wxyz`: the only form of a token that is ever printed."""
    return f"{token[:4]}…{token[-4:]}" if len(token) > 8 else "…"


def describe(cls: TokenClass) -> dict[str, Any]:
    return {
        "class": cls.key, "name": cls.name, "app_id": cls.app_id, "surface": cls.surface,
        "capabilities": {cap: {"evidence": ev, "note": note}
                         for cap, (ev, note) in cls.capabilities.items()},
        "session": {"need": cls.session[0], "evidence": cls.session[1]},
        "known_failures": dict(cls.known_failures),
        "ads_write_policy": cls.ads_write_policy, "default_var": cls.default_var,
        "graph_name": cls.graph_name, "hint": cls.hint,
    }

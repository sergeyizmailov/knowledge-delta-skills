#!/usr/bin/env python3
"""Offline regression suite. No network, no token, no account.

    python3 selftest.py

Covers the behaviours that have silently regressed at least once: retry policy on
non-idempotent writes, the unknown-outcome heuristic, credential redaction, per-locale
DLO assembly, the destination diff for every creative kind, and that every shipped spec
in specs/ still builds. Run it after touching graph.py, launch.py or verify.py — a
one-off manual check proved nothing the next edit could not undo.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile

os.environ.setdefault("META_TOKEN", "TESTTOKEN/with+chars")
os.environ.setdefault("META_PROXY", "socks5h://puser:ppass@1.2.3.4:1080")
# Pacing state is global (~/.metaops) — never let a selftest read or write the real one.
os.environ["METAOPS_PACE_DIR"] = tempfile.mkdtemp(prefix="metaops-selftest-pace-")
os.environ.pop("METAOPS_ACCOUNT_CONTEXT", None)

import graph
import launch
import verify

graph.authorize_writes({"act_1"})

HERE = pathlib.Path(__file__).resolve().parent
FAILED: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if cond else 'FAIL'}  {name}{'' if cond else '  ' + detail}")
    if not cond:
        FAILED.append(name)


class FakeResponse:
    def __init__(self, status: int, body, headers=None):
        self.status_code = status
        self.ok = 200 <= status < 300
        self._body = body
        self.headers = headers or {}
        self.text = body if isinstance(body, str) else json.dumps(body)

    def json(self):
        if isinstance(self._body, str):
            raise ValueError("not json")  # noqa: TRY004 - mimics requests
        return self._body


class FakeSession:
    """Replays a scripted list of responses/exceptions and counts attempts."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def request(self, *_a, **_kw):
        self.calls += 1
        self.last_kw = _kw
        item = self.script[min(self.calls - 1, len(self.script) - 1)]
        if isinstance(item, Exception):
            raise item
        return item


def with_session(script):
    graph._SESSION = FakeSession(script)
    return graph._SESSION


def no_sleep():
    graph.time.sleep = lambda _s: None


# --- transport ------------------------------------------------------------------

def test_transport() -> None:
    print("transport")
    no_sleep()
    boom = ConnectionError("proxy died https://graph.facebook.com/x?access_token=TESTTOKEN%2Fwith%2Bchars")
    ok = FakeResponse(200, {"id": "1"})

    s = with_session([boom] * 9)
    try:
        graph.call("POST", "act_1/campaigns", data={"name": "x"}, retries=4)
        check("create is not retried", False, "no error raised")
    except graph.GraphError as e:
        check("create is not retried", s.calls == 1, f"calls={s.calls}")
        check("create transport error is outcome_unknown", e.outcome_unknown is True)
        check("token redacted in transport error", "TESTTOKEN" not in str(e), str(e))

    s = with_session([boom, boom, ok])
    graph.call("GET", "me", retries=4)
    check("GET retries transport errors", s.calls == 3, f"calls={s.calls}")

    s = with_session([boom, boom, ok])
    graph.call("POST", "1/status", data={"status": "ACTIVE"}, idempotent=True, retries=4)
    check("idempotent write retries", s.calls == 3, f"calls={s.calls}")

    html502 = FakeResponse(502, "<html>Bad Gateway</html>")
    s = with_session([html502, html502, ok])
    graph.call("GET", "me", retries=4)
    check("GET retries a bodyless 5xx", s.calls == 3, f"calls={s.calls}")

    s = with_session([html502] * 9)
    try:
        graph.call("POST", "act_1/campaigns", data={"name": "x"}, retries=2)
        check("create is not retried on a bodyless 5xx", False, "no error raised")
    except graph.GraphError as e:
        check("create is not retried on a bodyless 5xx", s.calls == 1, f"calls={s.calls}")
        check("bodyless 5xx is outcome_unknown", e.outcome_unknown is True)

    rejected = FakeResponse(400, {"error": {"message": "bad", "code": 100,
                                            "error_subcode": 1487390, "type": "OAuthException"}})
    s = with_session([rejected] * 9)
    try:
        graph.call("POST", "act_1/campaigns", data={"name": "x"}, retries=4)
        check("a Graph rejection is not retried", False, "no error raised")
    except graph.GraphError as e:
        check("a Graph rejection is not retried", s.calls == 1, f"calls={s.calls}")
        check("a Graph rejection is a KNOWN outcome", e.outcome_unknown is False)
        check("subcode is parsed", e.subcode == 1487390)


def test_encoding() -> None:
    print("encoding")
    check("bool → true/false", graph._encode(True) == "true" and graph._encode(False) == "false")
    check("dict → compact json", graph._encode({"a": [1, 2]}) == '{"a":[1,2]}')
    check("str passes through", graph._encode("x") == "x")

    old_cookies = os.environ.get("META_COOKIES")
    os.environ["META_COOKIES"] = "c_user=1234567; xs=secretxsvalue"
    try:
        txt = graph.redact("access_token=TESTTOKEN/with+chars enc=TESTTOKEN%2Fwith%2Bchars "
                           "proxy=socks5h://puser:ppass@1.2.3.4 "
                           "cookie=c_user=1234567; xs=secretxsvalue partial=secretxsvalue")
        check("raw token redacted", "TESTTOKEN/with+chars" not in txt, txt)
        check("url-encoded token redacted", "TESTTOKEN%2F" not in txt, txt)
        check("proxy creds redacted", "ppass" not in txt, txt)
        check("cookies redacted", "secretxsvalue" not in txt and "1234567" not in txt, txt)
    finally:
        if old_cookies is not None:
            os.environ["META_COOKIES"] = old_cookies
        else:
            os.environ.pop("META_COOKIES", None)


def test_redact_vectors() -> None:
    """Central redact must cover every secret kind, not only META_TOKEN."""
    print("redact vectors")
    # Page-token set (the real hole: Page tokens never lived in META_TOKEN).
    page_token = "PAGE_SELFTEST_TOKEN_ABC123"
    graph.register_secret(page_token)
    old_token = os.environ.get("META_TOKEN")
    os.environ["META_TOKEN"] = "TESTTOKEN/with+chars"
    try:
        txt = graph.redact(f"page call failed with {page_token} and TESTTOKEN/with+chars")
        check("Page token masked", page_token not in txt and "<TOKEN>" in txt, txt)
    finally:
        if old_token is not None:
            os.environ["META_TOKEN"] = old_token
    old_secret = os.environ.get("META_APP_SECRET")
    os.environ["META_APP_SECRET"] = "SELFTEST_APP_SECRET_XYZ"
    try:
        txt = graph.redact("leak SELFTEST_APP_SECRET_XYZ here")
        check("META_APP_SECRET masked", "SELFTEST_APP_SECRET_XYZ" not in txt
              and "<APP_SECRET>" in txt, txt)
    finally:
        if old_secret is not None:
            os.environ["META_APP_SECRET"] = old_secret
        else:
            os.environ.pop("META_APP_SECRET", None)
    old_tg = os.environ.get("TG_BOT_TOKEN")
    os.environ["TG_BOT_TOKEN"] = "SELFTEST_TG_123:FAKE"
    try:
        txt = graph.redact("https://api.telegram.org/botSELFTEST_TG_123:FAKE/sendMessage boom")
        check("TG_BOT_TOKEN masked", "SELFTEST_TG_123:FAKE" not in txt
              and "<TG_TOKEN>" in txt, txt)
    finally:
        if old_tg is not None:
            os.environ["TG_BOT_TOKEN"] = old_tg
        else:
            os.environ.pop("TG_BOT_TOKEN", None)


def test_version_window() -> None:
    """N/N-1 accepted (N-1 warns), outside hard-fails. Sunset table minimum."""
    print("version window")
    check("SUPPORTED_VERSIONS is N/N-1", tuple(graph.SUPPORTED_VERSIONS) == ("v26.0", "v25.0"),
          str(graph.SUPPORTED_VERSIONS))
    check("v24 sunset duplicated", graph.VERSION_SUNSET.get("v24.0") == "2026-10-06",
          str(graph.VERSION_SUNSET))
    check("current is current", graph.version_status(graph.API_VERSION) == "current")
    check("v25 is previous", graph.version_status("v25.0") == "previous")
    check("v24 is unsupported", graph.version_status("v24.0") == "unsupported")
    check("N-1 warns", graph.version_warning("v25.0") is not None
          and "2026-10-06" in graph.version_warning("v25.0"))
    check("current does not warn", graph.version_warning(graph.API_VERSION) is None)


# --- builders -------------------------------------------------------------------

def test_specs() -> None:
    print("specs")
    for path in sorted((HERE / "specs").glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        if "accounts" in path.name or document.get("schema") == "metaops.workspace/v1":
            continue  # bulk/workspace examples are covered by their dedicated tests
        try:
            spec = launch.load_spec(str(path))
            for aset in spec["adsets"]:
                launch.build_targeting(aset)
                launch.build_attribution(aset)
                for ad in aset["ads"]:
                    launch.build_creative(spec, ad, "17841400000000000")
            check(f"{path.name} builds", True)
        except SystemExit as e:
            check(f"{path.name} builds", False, str(e))


def test_attribution() -> None:
    print("attribution")
    got = launch.build_attribution({"attribution": {"click_days": 1, "view_days": 1}})
    keys = {k for entry in got for k in entry}
    check("emits window_days, never event_window_days",
          "window_days" in keys and "event_window_days" not in keys, str(got))
    click_only = launch.build_attribution({"optimization_goal": "LINK_CLICKS"})
    check("click-only goals default to 1d click (1885501)",
          click_only == [{"event_type": "CLICK_THROUGH", "window_days": 1}])
    conv = launch.build_attribution({"optimization_goal": "OFFSITE_CONVERSIONS"})
    check("conversion goals keep 1/1/1", len(conv) == 3)
    dflt = launch.build_attribution({})
    types = {e["event_type"] for e in dflt}
    check("silent spec → 1/1/1 default",
          types == {"CLICK_THROUGH", "ENGAGED_VIDEO_VIEW", "VIEW_THROUGH"}
          and all(e["window_days"] == 1 for e in dflt), str(dflt))
    check("account_default → nothing sent",
          launch.build_attribution({"attribution": "account_default"}) is None)
    click7view1 = launch.build_attribution(
        {"optimization_goal": "OFFSITE_CONVERSIONS", "attribution": {"click_days": 7, "view_days": 1}}
    )
    check("click_days=7/view_days=1 -> CLICK_THROUGH 7 + VIEW_THROUGH 1",
          click7view1 == [{"event_type": "CLICK_THROUGH", "window_days": 7},
                          {"event_type": "VIEW_THROUGH", "window_days": 1}], str(click7view1))


def _spec_from(obj: dict) -> dict:
    tmp = HERE / ".selftest-spec.json"
    tmp.write_text(json.dumps(obj))
    try:
        return launch.load_spec(str(tmp))
    finally:
        tmp.unlink(missing_ok=True)


def _base_spec(**over) -> dict:
    spec = {
        "account_id": "act_1", "page_id": "2", "pixel_id": "3",
        "campaign": {"name": "c", "objective": "OUTCOME_LEADS", "special_ad_categories": [],
                     "daily_budget_minor": 1000},
        "adsets": [{
            "name": "a", "optimization_goal": "OFFSITE_CONVERSIONS", "start_time": "2026-09-03T07:00:00+03:00",
            "targeting": {"geo_locations": {"countries": ["TR"]}, "advantage_audience": False},
            "ads": [{"name": "ad", "creative": {"kind": "link_image", "image_hash": "h", "link": "https://x.tld/"}}],
        }],
    }
    for k, v in over.items():
        spec[k] = v
    return spec


def test_spec_rules() -> None:
    print("spec rules")
    ok = _spec_from(_base_spec())
    check("CBO detected", ok["budget_mode"] == "CBO")

    abo = _base_spec()
    abo["campaign"].pop("daily_budget_minor")
    abo["adsets"][0]["daily_budget_minor"] = 500
    check("ABO detected", _spec_from(abo)["budget_mode"] == "ABO")

    both = _base_spec()
    both["adsets"][0]["daily_budget_minor"] = 500
    try:
        _spec_from(both)
        check("CBO + adset budget rejected", False, "accepted")
    except SystemExit:
        check("CBO + adset budget rejected", True)

    neither = _base_spec()
    neither["campaign"].pop("daily_budget_minor")
    try:
        _spec_from(neither)
        check("no budget anywhere rejected", False, "accepted")
    except SystemExit:
        check("no budget anywhere rejected", True)

    cap = _base_spec()
    cap["campaign"].pop("daily_budget_minor")
    cap["adsets"][0].update({"daily_budget_minor": 500, "bid_strategy": "COST_CAP"})
    try:
        _spec_from(cap)
        check("COST_CAP without bid_amount rejected", False, "accepted")
    except SystemExit:
        check("COST_CAP without bid_amount rejected", True)

    noaa = _base_spec()
    noaa["adsets"][0]["targeting"].pop("advantage_audience")
    try:
        _spec_from(noaa)
        check("missing advantage_audience rejected", False, "accepted")
    except SystemExit:
        check("missing advantage_audience rejected", True)

    eu = _base_spec()
    eu["adsets"][0]["targeting"]["geo_locations"] = {"countries": ["DE"]}
    try:
        _spec_from(eu)
        check("EU geo without DSA rejected", False, "accepted")
    except SystemExit:
        check("EU geo without DSA rejected", True)
    eu["adsets"][0].update({"dsa_beneficiary": "X GmbH", "dsa_payor": "X GmbH"})
    check("EU geo with DSA accepted", _spec_from(eu)["budget_mode"] == "CBO")

    cbo_cap = _base_spec()
    cbo_cap["campaign"]["bid_strategy"] = "LOWEST_COST_WITH_BID_CAP"
    try:
        _spec_from(cbo_cap)
        check("CBO bid cap without adset bid_amount_minor rejected", False, "accepted")
    except SystemExit:
        check("CBO bid cap without adset bid_amount_minor rejected", True)
    # bid_amount_minor is the one field CBO ad sets are allowed to carry (still no
    # daily_budget_minor/bid_strategy) — used to send the cap amount per ad set (1815857).
    cbo_cap["adsets"][0]["bid_amount_minor"] = 250
    loaded_cbo_cap = _spec_from(cbo_cap)
    check("CBO bid cap with adset bid_amount_minor accepted",
          loaded_cbo_cap["adsets"][0]["bid_amount_minor"] == 250)

    cbo_no_cap = _base_spec()
    cbo_no_cap["adsets"][0]["bid_amount_minor"] = 250
    check("CBO without a cap strategy still accepts a stray bid_amount_minor (not required)",
          _spec_from(cbo_no_cap)["adsets"][0]["bid_amount_minor"] == 250)

    cbo_cap_budget = _base_spec()
    cbo_cap_budget["campaign"]["bid_strategy"] = "COST_CAP"
    cbo_cap_budget["adsets"][0]["daily_budget_minor"] = 500
    try:
        _spec_from(cbo_cap_budget)
        check("CBO ad set still forbids daily_budget_minor even with a cap strategy", False, "accepted")
    except SystemExit:
        check("CBO ad set still forbids daily_budget_minor even with a cap strategy", True)

    # float budget stays rejected
    fl = _base_spec()
    fl["campaign"]["daily_budget_minor"] = 60.0
    try:
        _spec_from(fl)
        check("float budget rejected", False, "accepted")
    except SystemExit:
        check("float budget rejected", True)


def test_creative_flags() -> None:
    print("creative flags")
    spec = _spec_from(_base_spec(url_tags="utm_source=fb"))
    ad = spec["adsets"][0]["ads"][0]
    payload = launch.build_creative(spec, ad, None)
    check("contextual_multi_ads OPT_OUT by default",
          payload.get("contextual_multi_ads") == {"enroll_status": "OPT_OUT"}, str(payload.get("contextual_multi_ads")))
    check("spec-level url_tags inherited", payload.get("url_tags") == "utm_source=fb")
    feats = payload["degrees_of_freedom_spec"]["creative_features_spec"]
    check("adapt_to_placement opted out", feats.get("adapt_to_placement", {}).get("enroll_status") == "OPT_OUT")
    check("every default feature OPT_OUT", all(v["enroll_status"] == "OPT_OUT" for v in feats.values()))

    ad2 = {"name": "x", "creative": {"kind": "link_image", "image_hash": "h", "link": "https://x.tld/",
                                     "multi_advertiser": True, "url_tags": "own=1"}}
    p2 = launch.build_creative(spec, ad2, None)
    check("multi_advertiser: true leaves the field off", "contextual_multi_ads" not in p2)
    check("per-creative url_tags wins", p2.get("url_tags") == "own=1")

    car = {"name": "car", "creative": {"kind": "link_carousel", "link": "https://x.tld/", "message": "m",
           "cards": [{"image_hash": "a"}, {"image_hash": "b"}]}}
    p3 = launch.build_creative(spec, car, "178")
    ch = p3["object_story_spec"]["link_data"]["child_attachments"]
    check("carousel emits child_attachments", len(ch) == 2 and ch[0]["image_hash"] == "a")
    check("carousel cards inherit link", all(c["link"] == "https://x.tld/" for c in ch))
    bad = {"name": "car", "creative": {"kind": "link_carousel", "link": "https://x.tld/", "cards": [{"image_hash": "a"}]}}
    try:
        launch.build_creative(spec, bad, None)
        check("1-card carousel rejected", False, "accepted")
    except SystemExit:
        check("1-card carousel rejected", True)


def test_dlo() -> None:
    print("dlo")
    spec = launch.load_spec(str(HERE / "specs" / "example-dlo.json"))
    c = spec["adsets"][0]["ads"][0]["creative"]
    feed = launch.build_dlo_feed(c)
    rules = feed["asset_customization_rules"]
    check("at least two rules", len(rules) >= 2)
    check("exactly one default", sum(1 for r in rules if r.get("is_default")) == 1)
    label_key = "image_label" if feed["ad_formats"] == ["SINGLE_IMAGE"] else "video_label"
    check("every rule carries its media label", all(label_key in r for r in rules))
    check("descriptions present for every locale",
          len(feed["descriptions"]) == len(rules) and all(x["text"] for x in feed["descriptions"]))
    check("one link_url per locale", len(feed["link_urls"]) == len(rules))
    check("locale ids are ints",
          all(isinstance(x, int) for r in rules for x in r["customization_spec"]["locales"]))

    try:
        launch.build_dlo_feed({**c, "ad_format": "CAROUSEL"})
        check("CAROUSEL rejected", False, "accepted")
    except SystemExit:
        check("CAROUSEL rejected", True)


def test_catalog_template_url() -> None:
    print("catalog")
    spec = launch.load_spec(str(HERE / "specs" / "example-catalog-collection-tr.json"))
    ad = spec["adsets"][0]["ads"][0]
    payload = launch.build_creative(spec, ad, None)
    want = ad["creative"].get("template_url")
    check("spec ships a template_url", bool(want))
    check("template_url_spec is emitted",
          ((payload.get("template_url_spec") or {}).get("web") or {}).get("url") == want,
          str(payload.get("template_url_spec")))


# --- verify ---------------------------------------------------------------------

def test_destination() -> None:
    print("verify.destination")

    d = verify.Diff()
    verify.check_destination(
        d,
        {"kind": "link_video", "link": "https://a.tld/"},
        {"object_story_spec": {"video_data": {"link": "https://a.tld/"}}},
    )
    check("link_video match passes", d.bad == 0, f"bad={d.bad}")

    d = verify.Diff()
    verify.check_destination(
        d,
        {"kind": "link_video", "link": "https://a.tld/"},
        {"object_story_spec": {"video_data": {"link": "https://WRONG.tld/"}}},
    )
    check("wrong destination fails", d.bad == 1, f"bad={d.bad}")

    d = verify.Diff()
    locales = [{"link": "https://white.tld/"}, {"link": "https://money.tld/"}]
    verify.check_destination(
        d,
        {"kind": "dlo", "locales": locales},
        {"object_story_spec": {},
         "asset_feed_spec": {"link_urls": [{"website_url": "https://white.tld/"},
                                           {"website_url": "https://money.tld/"}]}},
    )
    check("dlo with matching link_urls passes", d.bad == 0, f"bad={d.bad}")

    d = verify.Diff()
    verify.check_destination(
        d,
        {"kind": "dlo", "locales": locales},
        {"object_story_spec": {}, "asset_feed_spec": {"link_urls": [
            {"website_url": "https://white.tld/"}, {"website_url": "https://TYPO.tld/"}]}},
    )
    check("dlo with a wrong locale link fails", d.bad == 1, f"bad={d.bad}")

    d = verify.Diff()
    verify.check_destination(d, {"kind": "dlo", "locales": locales},
                             {"object_story_spec": {}, "asset_feed_spec": {}})
    check("dlo with no link_urls fails exactly once", d.bad == 1, f"bad={d.bad}")

    d = verify.Diff()
    verify.check_destination(d, {"kind": "dlo"},
                             {"object_story_spec": {}, "asset_feed_spec": {}})
    check("dlo with neither spec locales nor link_urls fails once", d.bad == 1, f"bad={d.bad}")

    # Spec-less run: the kind is recovered from the built creative, so a DLO ad is not
    # mistaken for a link ad with a missing destination.
    d = verify.Diff()
    verify.check_destination(
        d, None,
        {"object_story_spec": {},
         "asset_feed_spec": {"link_urls": [{"website_url": "https://white.tld/"}]}},
    )
    check("no --spec: dlo is recognised and not failed", d.bad == 0, f"bad={d.bad}")

    d = verify.Diff()
    verify.check_destination(d, None, {"object_story_spec": {}, "asset_feed_spec": {}})
    check("no --spec: nothing is ever failed", d.bad == 0, f"bad={d.bad}")

    d = verify.Diff()
    verify.check_destination(
        d, {"kind": "link_video", "link": "https://a.tld/"},
        {"object_story_spec": {"video_data": {}}},
    )
    check("spec'd link with no destination fails exactly once", d.bad == 1, f"bad={d.bad}")

    d = verify.Diff()
    verify.check_destination(
        d,
        {"kind": "catalog_collection", "link": "https://shop.tld/",
         "template_url": "https://go.tld/?sub={{product.retailer_id}}"},
        {"object_story_spec": {"template_data": {"link": "https://shop.tld/"}},
         "template_url_spec": {"web": {"url": "https://go.tld/?sub={{product.retailer_id}}"}}},
    )
    check("catalog match passes", d.bad == 0, f"bad={d.bad}")

    d = verify.Diff()
    verify.check_destination(
        d,
        {"kind": "catalog_collection", "link": "https://shop.tld/",
         "template_url": "https://go.tld/?sub=X"},
        {"object_story_spec": {"template_data": {"link": "https://shop.tld/"}}},
    )
    check("dropped template_url_spec fails", d.bad == 1, f"bad={d.bad}")


def test_probe_is_retryable() -> None:
    """probe.py is diagnostic: none of its writes create anything a repeat could
    duplicate, so every one of them must survive a dropped connection. A one-shot POST
    here reports 'no write access' on an account that has it — the single most expensive
    false negative in the runbook, because it stops a launch at step 1."""
    print("probe")
    import ast

    src = (HERE / "probe.py").read_text(encoding="utf-8")
    bad = []
    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if not (isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name)
                and fn.value.id == "graph" and fn.attr in ("post", "call")):
            continue
        args = {kw.arg for kw in node.keywords}
        method = next((a.value for a in node.args if isinstance(a, ast.Constant)), None)
        if fn.attr == "call" and method == "GET":
            continue
        if "idempotent" not in args:
            bad.append(node.lineno)
    check("every probe.py write is marked idempotent", not bad, f"lines {bad}")


def test_equivalence() -> None:
    print("verify.equivalence")
    d = verify.Diff()
    d.check("tz", "2026-09-02T07:00:00+03:00", "2026-09-02T04:00:00+0000")
    check("same instant, different offset → match", d.bad == 0, f"bad={d.bad}")

    d = verify.Diff()
    d.check("subset", {"countries": ["TR"]}, {"countries": ["TR"], "location_types": ["home"]})
    check("Graph-enriched dict → match", d.bad == 0, f"bad={d.bad}")

    d = verify.Diff()
    d.check("loc", verify.normalize_location_types({"countries": ["TR"], "location_types": ["home", "recent"]}),
            {"countries": ["TR"], "location_types": ["frequently_in", "home", "recent"]})
    check("home+recent read back with frequently_in → match", d.bad == 0, f"bad={d.bad}")
    d = verify.Diff()
    d.check("loc", verify.normalize_location_types({"countries": ["TR"], "location_types": ["home"]}),
            {"countries": ["TR"], "location_types": ["frequently_in", "home"]})
    check("home alone not widened → mismatch", d.bad == 1, f"bad={d.bad}")

    d = verify.Diff()
    d.check("order", ["a", "b"], ["b", "a"])
    check("list order ignored", d.bad == 0, f"bad={d.bad}")

    d = verify.Diff()
    d.check("real diff", {"countries": ["TR"]}, {"countries": ["DE"]})
    check("a real difference still fails", d.bad == 1, f"bad={d.bad}")


def test_bulk() -> None:
    print("bulk")
    import bulk
    tpl = _base_spec()
    tpl["campaign"]["name"] = "{tag}|c"
    tpl["adsets"][0]["name"] = "{tag}|a"
    tpl["account_id"] = "act_REPLACE_ME"
    row = {"account_id": "act_77", "page_id": "88", "pixel_id": "99", "tag": "J41-16",
           "overrides": {"campaign": {"daily_budget_minor": 4200}},
           "media": {"ad": {"image_hash": "acct77hash"}}}
    previous_bulk_dir = bulk.BULK_DIR
    with tempfile.TemporaryDirectory(prefix="metaops-selftest-") as td:
        bulk.BULK_DIR = str(pathlib.Path(td) / "bulk")
        try:
            spec, _path = bulk.resolve(tpl, row, "selftest-run")
            check("account substituted", spec["account_id"] == "act_77")
            check("{tag} expanded in names", spec["campaign"]["name"] == "J41-16|c" and spec["adsets"][0]["name"] == "J41-16|a")
            check("overrides deep-merged", spec["campaign"]["daily_budget_minor"] == 4200)
            check("per-account media applied", spec["adsets"][0]["ads"][0]["creative"]["image_hash"] == "acct77hash")
            check("run_id per account", spec["run_id"] == "selftest-run-J41-16")
            check("no REPLACE_ME left", bulk.unresolved(spec) == [])
        finally:
            bulk.BULK_DIR = previous_bulk_dir


def test_rules_ladder() -> None:
    print("rules ladder")
    import rules
    # Reference multipliers from senior-buyer-ops/04 (95%): exact Poisson bounds.
    ref = {0: 3.00, 1: 4.74, 2: 6.30, 3: 7.75, 5: 10.51, 10: 16.96, 20: 29.06}
    for k, want in ref.items():
        got = rules.multiplier(k, 0.95)
        check(f"k={k} multiplier {want}", abs(got - want) < 0.02, f"got {got:.3f}")
    check("90% kills sooner than 95%", rules.multiplier(0, 0.90) < rules.multiplier(0, 0.95))
    lad = rules.ladder(1200, [0, 1], 0.95)
    check("spend threshold in minor units (exact bound × target)",
          abs(lad[0]["spend_minor"] - 3595) <= 3 and abs(lad[1]["spend_minor"] - 5693) <= 3, str(lad))
    r = rules.build_rule("n", "ADSET", 2, 7560, "offsite_conversion.fb_pixel_lead", "pause", "LIFETIME",
                         ["1", "2"], 500, "SEMI_HOURLY")
    f = {x["field"]: x for x in r["evaluation_spec"]["filters"]}
    check("count-form rung: spent > and count < k+1",
          f["spent"]["operator"] == "GREATER_THAN" and f["offsite_conversion.fb_pixel_lead"]["value"] == 3)
    check("no cost/ratio fields (scope ban)", not any(k.startswith("cost") or k == "cpa" for k in f))
    check("no deprecated attribution_window", "attribution_window" not in f)
    check("entity_type + id + time_preset present", {"entity_type", "id", "time_preset"} <= set(f))
    check("pause mode → PAUSE", r["execution_spec"]["execution_type"] == "PAUSE")
    check("notify mode → NOTIFICATION",
          rules.build_rule("n", "AD", 0, 1, "results", "notify", "LAST_7D", None, None, "DAILY")
          ["execution_spec"]["execution_type"] == "NOTIFICATION")


def test_bearer_header() -> None:
    print("bearer header")
    os.environ["META_TOKEN"] = "TESTTOKEN/with+chars"
    s = with_session([FakeResponse(200, {"id": "1"})])
    graph.get("me")
    kw = s.last_kw
    check("token in Authorization header", kw.get("headers", {}).get("Authorization") == "Bearer TESTTOKEN/with+chars")
    check("token NOT in query params", "access_token" not in (kw.get("params") or {}))


def test_gates() -> None:
    print("gates (dry-run marker, receipt, rules CLI)")
    import tempfile

    import activate
    import bulk
    import rules
    import verify
    tpl = {"campaign": {"name": "c", "daily_budget_minor": 100}}
    rows = [{"account_id": "act_1"}]
    h1 = bulk.inputs_hash(tpl, rows, None)
    h2 = bulk.inputs_hash({"campaign": {"name": "c", "daily_budget_minor": 999}}, rows, None)
    check("marker hash changes with template", h1 != h2)
    with tempfile.TemporaryDirectory() as td:
        m = bulk.pathlib.Path(td) / ".dry-run-ok"
        check("missing marker is stale", bulk.marker_stale(m, h1) is not None)
        m.write_text(json.dumps({"inputs_sha": h1}))
        check("matching marker is valid", bulk.marker_stale(m, h1) is None)
        check("edited inputs void the marker", bulk.marker_stale(m, h2) is not None)
        m.write_text(json.dumps(["act_1"]))  # old-format marker
        check("legacy list marker is stale", bulk.marker_stale(m, h1) is not None)

        st = os.path.join(td, "run.json")
        with open(st, "w") as fh:
            json.dump({"objects": {"campaign": "1"}}, fh)
        check("no receipt → refuse", activate.check_receipt(st) is not None)
        verify.write_receipt(st, None, None)
        check("spec-less receipt → refuse", activate.check_receipt(st) is not None)
        spec_min = {"adsets": [{"ads": [{}]}]}
        with open(st, "w") as fh:
            json.dump({"objects": {"campaign": "1", "adset[0]": "2", "ad[0.0]": "3"},
                       "spec_sha": launch.spec_hash(spec_min)}, fh)
        verify.write_receipt(st, "x.json", spec_min)
        check("spec'd receipt matching state → allowed", activate.check_receipt(st) is None)
        with open(st, "w") as fh:
            json.dump({"objects": {"campaign": "1", "adset[0]": "2", "ad[0.0]": "3"}}, fh)
        verify.write_receipt(st, "x.json", spec_min)
        check("state without spec_sha → refuse", "no spec_sha" in (activate.check_receipt(st) or ""))
        with open(st, "w") as fh:
            json.dump({"objects": {"campaign": "1", "adset[0]": "2", "ad[0.0]": "3"},
                       "spec_sha": launch.spec_hash(spec_min)}, fh)
        verify.write_receipt(st, "x.json", {"adsets": [{"ads": [{}, {}]}]})
        check("receipt from another spec → refuse", "different spec" in (activate.check_receipt(st) or ""))
        with open(st, "a") as fh:
            fh.write("\n")
        check("state changed after verify → refuse", "changed" in (activate.check_receipt(st) or ""))

    # verify must refuse an incomplete tree even when every present object is fine
    import contextlib
    import io
    with tempfile.TemporaryDirectory() as td:
        st = os.path.join(td, "run.json")
        with open(st, "w") as fh:
            json.dump({"objects": {"campaign": "1", "adset[0]": "2"}, "in_flight": {"creative[0.0]": "x"}}, fh)
        spec_min = {"adsets": [{"ads": [{}]}]}
        dd = verify.Diff()
        err = io.StringIO()
        with open(st, encoding="utf-8") as fh:
            st_data = json.load(fh)
        with contextlib.redirect_stderr(err):
            verify.completeness(dd, st_data, spec_min)
        check("in-flight + missing ad → 2 problems", dd.bad == 2)
        check("incomplete message names the ad", "ad[0.0]" in err.getvalue())

    class A:  # argparse stand-in
        ladder_only = False
        list = False
        execute = None
        delete_prefix = None

    a = A()
    check("create run needs ladder", rules.needs_ladder(a))
    a = A()
    a.delete_prefix = "LADDER|"
    check("--delete-prefix --dry-run needs no ladder", not rules.needs_ladder(a))
    a = A()
    a.list = True
    check("--list needs no ladder", not rules.needs_ladder(a))


def test_scripts_import() -> None:
    """Every new script must at least import and parse --help without a token or network."""
    print("scripts import")
    import importlib
    for name in (
        "monitor", "clone", "comments", "edit", "rules", "uniquify", "page", "bulk",
        "asset_graph", "meta_workspace", "metaops", "swapgate", "mutate_set",
    ):
        try:
            importlib.import_module(name)
            check(f"{name}.py imports", True)
        except Exception as e:  # noqa: BLE001
            check(f"{name}.py imports", False, repr(e))
    # The installed `metaops` only ships modules listed in pyproject py-modules; a new module that is
    # missing there imports fine here and dies with ModuleNotFoundError in the installed tool
    # (field 2026-09-26, swapgate).
    import pathlib
    import re as _re
    here = pathlib.Path(__file__).resolve().parent
    listed = set(_re.findall(r'"(\w+)"', (here.parent / "pyproject.toml").read_text().split("py-modules", 1)[1].split("]", 1)[0]))
    missing = sorted(p.stem for p in here.glob("*.py")
                     if not p.stem.startswith("test_") and p.stem != "selftest" and p.stem not in listed)
    check("every script module is packaged (pyproject py-modules)", not missing, f"missing: {missing}")


def main() -> int:
    for fn in (test_transport, test_bearer_header, test_gates, test_encoding, test_redact_vectors,
               test_version_window, test_specs, test_attribution, test_spec_rules,
               test_creative_flags, test_dlo, test_catalog_template_url, test_destination,
               test_probe_is_retryable, test_equivalence, test_bulk, test_rules_ladder,
               test_scripts_import):
        fn()
    print()
    if FAILED:
        print(f"{len(FAILED)} failure(s): {FAILED}", file=sys.stderr)
        return 1
    print("all green")
    return 0


if __name__ == "__main__":
    sys.exit(main())

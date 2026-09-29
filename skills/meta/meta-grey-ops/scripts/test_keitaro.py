#!/usr/bin/env python3
"""Offline contract tests for cmd_keitaro.py. No network, no real credentials: Graph and the
Keitaro HTTP layer are mocked."""

from __future__ import annotations

import os as _os
import tempfile as _tempfile

_os.environ["METAOPS_PACE_DIR"] = _tempfile.mkdtemp(prefix="metaops-pace-test-")
_os.environ.setdefault("METAOPS_CREATE_GAP_HOURS", "0")

import contextlib
import datetime as dt
import http.client
import io
import json
import os
import pathlib
import sys
import tempfile
import types
import unittest
import urllib.error
import urllib.request
from decimal import Decimal
from unittest import mock

os.environ.setdefault("META_TOKEN", "TEST_TOKEN")

import cmd_keitaro
import jsonschema
import meta_workspace
import metaops

API_KEY = "kt-secret-key-0123456789"
NOW = dt.datetime(2026, 9, 29, 15, 0, tzinfo=dt.timezone.utc)   # 11:00 in New York
DAYS3 = ["2026-09-27", "2026-09-28", "2026-09-29"]


class FakeWorkspace:
    def __init__(self, state_root: pathlib.Path, profile: dict | None = None):
        self.state_root = state_root
        self._profile = profile or {
            "ad_account_id": "act_1", "page_id": "2", "dataset_id": "3", "currency": "USD",
            "timezone": "America/New_York", "keitaro_campaign_id": "1234",
        }
        self.data = {"profiles": {"test": dict(self._profile)}}

    def profile(self, requested=None):
        return "test", dict(self._profile)


def mkargs(ws, **kw):
    base = dict(workspace_obj=ws, profile=None, keitaro_campaign=None, days=None, since=None,
                until=None, confirm=None, keitaro_currency=None, readback_wait=None, by="ad",
                keitaro_mode="push")
    base.update(kw)
    return types.SimpleNamespace(**base)


def ad_row(ad, day, spend, campaign="C1", adset="S1", name=None):
    return {"ad_id": ad, "ad_name": name or f"EN{ad}", "campaign_id": campaign, "adset_id": adset,
            "adset_name": f"adset {adset}", "spend": spend, "impressions": "1000",
            "inline_link_clicks": "50", "date_start": day, "date_stop": day}


ADS = [
    ad_row("111", "2026-09-27", "10.00"), ad_row("111", "2026-09-28", "20.50"),
    ad_row("111", "2026-09-29", "5.25"),
    ad_row("222", "2026-09-27", "4.00"), ad_row("222", "2026-09-28", "0.00"),
    ad_row("222", "2026-09-29", "8.00"),
    ad_row("333", "2026-09-28", "3.10", campaign="C2", adset="S2"),
    ad_row("333", "2026-09-29", "3.10", campaign="C2", adset="S2"),
]
DAY_SUMS = {"2026-09-27": "14.00", "2026-09-28": "23.60", "2026-09-29": "16.35"}


def fb_get_factory(ads=ADS, account_days=None, campaign_days=None, tz="America/New_York",
                   currency="USD", calls=None, campaign_error=None):
    """side_effect for graph.get: account read, ad / account / campaign level insights."""
    if account_days is None:
        sums: dict[str, Decimal] = {}
        for r in ads:
            sums[r["date_start"]] = sums.get(r["date_start"], Decimal(0)) + Decimal(r["spend"])
        account_days = {d: str(v) for d, v in sums.items()}

    def fake_get(path, params=None, context=""):
        if calls is not None:
            calls.append((path, dict(params or {})))
        if path == "act_1":
            return {"timezone_name": tz, "currency": currency, "id": "act_1"}
        assert path == "act_1/insights", path
        level = params["level"]
        if level == "ad":
            return {"data": list(ads)}
        if level == "account":
            return {"data": [{"spend": v, "date_start": d, "date_stop": d} for d, v in account_days.items()]}
        if level == "campaign":
            if campaign_error:
                raise campaign_error
            return {"data": [{"spend": v, "campaign_id": c, "date_start": d, "date_stop": d}
                             for (d, c), v in (campaign_days or {}).items()]}
        raise AssertionError(level)

    return fake_get


class FakeKeitaro:
    """Stands in for KeitaroClient. Tracks clicks/costs per (day, ad); applies update_costs."""

    def __init__(self, ads=ADS, clicks=None, campaign=None, fx=1.0, lag_reads=0, fail_post=None,
                 report_rows=None, report_error=None, update_response=None, apply_cost=True):
        self.calls: list[tuple[str, str, object]] = []
        self.campaign = campaign if campaign is not None else {
            "id": 1234, "name": "Longread", "cost_type": "CPC", "cost_value": 0, "cost_auto": False}
        keys = {(r["date_start"], r["ad_id"]) for r in ads if Decimal(r["spend"]) > 0}
        self.clicks = clicks if clicks is not None else {k: 10 for k in keys}
        self.costs: dict[tuple[str, str], float] = {}
        self.fx = fx
        self.lag_reads = lag_reads
        self.reads = 0
        self.fail_post = fail_post or {}
        self.report_rows = report_rows
        self.report_error = report_error
        self.update_response = update_response if update_response is not None else {"success": True}
        self.apply_cost = apply_cost
        self.posts = 0
        self.staged: list[tuple[str, str, float]] = []

    def get(self, path):
        self.calls.append(("GET", path, None))
        if path.startswith("/campaigns/"):
            if isinstance(self.campaign, cmd_keitaro.KeitaroError):
                raise self.campaign
            return dict(self.campaign)
        raise AssertionError(path)

    def post(self, path, body, *, write=False):
        self.calls.append(("POST", path, body))
        if path == "/clicks/update_costs":
            idx = self.posts
            self.posts += 1
            assert write is True
            if idx in self.fail_post:
                raise self.fail_post[idx]
            for e in body["costs"]:
                self.staged.append((e["start_date"][:10], e["filters"]["sub_id_6"], e["cost"] * self.fx))
            return self.update_response
        assert path == "/report/build", path
        if self.report_error:
            raise self.report_error
        self.reads += 1
        if self.report_rows is not None:
            rows = self.report_rows(body) if callable(self.report_rows) else self.report_rows
        else:
            if self.apply_cost and self.reads > self.lag_reads:
                for day, ad, cost in self.staged:
                    if self.clicks.get((day, ad), 0) > 0:
                        self.costs[(day, ad)] = cost
                self.staged = []
            rows = [{"day": d, "sub_id_6": a, "clicks": c, "cost": self.costs.get((d, a), 0)}
                    for (d, a), c in sorted(self.clicks.items())]
        off, lim = body.get("offset", 0), body.get("limit", 1000)
        return {"rows": rows[off:off + lim], "total": len(rows)}

    def update_posts(self):
        return [c for c in self.calls if c[1] == "/clicks/update_costs"]

    def report_bodies(self):
        return [c[2] for c in self.calls if c[1] == "/report/build"]


class Harness(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.ws = FakeWorkspace(pathlib.Path(self.td.name))
        self.sleeps: list[float] = []

    def run_cmd(self, fn, args, kt=None, get=None, fb_calls=None, env=None):
        kt = kt or FakeKeitaro()
        get = get or fb_get_factory(calls=fb_calls)
        err = io.StringIO()
        patches = [
            mock.patch.object(metaops.graph, "get", side_effect=get),
            mock.patch.object(cmd_keitaro, "_make_client", return_value=kt),
            mock.patch.object(cmd_keitaro, "_sleep", side_effect=self.sleeps.append),
            mock.patch.object(cmd_keitaro, "_utcnow", return_value=NOW),
            contextlib.redirect_stderr(err),
        ]
        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            code, payload = fn(args, metaops)
        json.dumps(payload)  # no Decimal or other non-JSON value may leak into the envelope
        self.stderr = err.getvalue()
        return code, payload

    def push(self, kt=None, get=None, fb_calls=None, **kw):
        return self.run_cmd(cmd_keitaro.command_push, mkargs(self.ws, **kw), kt, get, fb_calls)

    def report(self, kt=None, get=None, fb_calls=None, **kw):
        kw.setdefault("keitaro_mode", "report")
        return self.run_cmd(cmd_keitaro.command_report, mkargs(self.ws, **kw), kt, get, fb_calls)


# --------------------------------------------------------------------------- transport


class FakeResponse:
    def __init__(self, body=b"{}", status=200, read_error=None):
        self._body, self.status, self._read_error = body, status, read_error

    def read(self, *a):
        if self._read_error:
            raise self._read_error
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeOpener:
    def __init__(self, *script):
        self.script = list(script)
        self.requests: list[tuple[urllib.request.Request, float]] = []

    def open(self, req, timeout=None):
        self.requests.append((req, timeout))
        item = self.script.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


def http_error(code, body=b'{"message":"nope"}'):
    return urllib.error.HTTPError("https://k/x", code, "err", {}, io.BytesIO(body))


class FakeSock:
    def __init__(self, data: bytes):
        self._data = data

    def makefile(self, *a, **k):
        return io.BytesIO(self._data)


class CannedHTTPS(urllib.request.BaseHandler):
    """Replaces the socket layer of the REAL opener chain (error processor, redirect handler)."""

    handler_order = 100

    def __init__(self, *raw_responses: bytes):
        self.raw = list(raw_responses)
        self.seen: list[urllib.request.Request] = []

    def https_open(self, req):
        self.seen.append(req)
        resp = http.client.HTTPResponse(FakeSock(self.raw.pop(0)))
        resp.begin()
        resp.url = req.get_full_url()      # what AbstractHTTPHandler.do_open does
        resp.msg = resp.reason
        return resp


def canned(status_line: str, body: bytes = b"", headers: str = "") -> bytes:
    return (f"HTTP/1.1 {status_line}\r\nContent-Length: {len(body)}\r\n{headers}\r\n").encode() + body


class RealOpenerChainTests(unittest.TestCase):
    """The production opener (no proxy, no redirects) over a canned socket layer: no network."""

    def client(self, *raw):
        handler = CannedHTTPS(*raw)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), cmd_keitaro._NoRedirect(), handler)
        return cmd_keitaro.KeitaroClient("https://k.example", API_KEY, opener=opener), handler

    def test_success_through_the_real_chain(self):
        c, h = self.client(canned("200 OK", b'{"success":true}'))
        self.assertEqual(c.post("/clicks/update_costs", {"x": 1}, write=True), {"success": True})
        self.assertEqual(h.seen[0].get_header("Api-key"), API_KEY)

    def test_redirect_is_not_followed_and_the_key_is_not_replayed(self):
        c, h = self.client(canned("302 Found", b"", "Location: https://evil.example/steal\r\n"))
        with self.assertRaises(cmd_keitaro.KeitaroError) as cm:
            c.post("/clicks/update_costs", {"x": 1}, write=True)
        self.assertEqual(cm.exception.status, 302)
        self.assertIn("redirect refused", cm.exception.message)
        self.assertEqual(len(h.seen), 1)
        self.assertEqual(h.seen[0].full_url, "https://k.example/admin_api/v1/clicks/update_costs")

    def test_error_statuses_become_keitaro_errors_without_retry(self):
        for status in ("401 Unauthorized", "404 Not Found", "422 Unprocessable Entity", "500 Internal Server Error"):
            c, h = self.client(canned(status, json.dumps({"message": f"boom {API_KEY}"}).encode()))
            with self.assertRaises(cmd_keitaro.KeitaroError) as cm:
                c.get("/campaigns/1")
            self.assertEqual(cm.exception.status, int(status[:3]))
            self.assertEqual(len(h.seen), 1)
            self.assertNotIn(API_KEY, cm.exception.message)


class TransportTests(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(cmd_keitaro, "_sleep")
        self.sleep = p.start()
        self.addCleanup(p.stop)

    def client(self, *script, url="https://k.example"):
        opener = FakeOpener(*script)
        return cmd_keitaro.KeitaroClient(url, API_KEY, opener=opener), opener

    def test_api_base_variants(self):
        base = cmd_keitaro._api_base
        self.assertEqual(base("https://k.example"), "https://k.example/admin_api/v1")
        self.assertEqual(base("https://k.example/"), "https://k.example/admin_api/v1")
        self.assertEqual(base("https://k.example/admin_api/v1/"), "https://k.example/admin_api/v1")
        self.assertEqual(base("https://k.example/keitaro"), "https://k.example/keitaro/admin_api/v1")
        self.assertEqual(base("http://localhost:8080"), "http://localhost:8080/admin_api/v1")

    def test_api_base_refuses_unsafe_urls(self):
        for bad in ("http://k.example", "ftp://k.example", "file:///etc/passwd", "k.example",
                    "https://user:pw@k.example", "https://k.example/?api_key=x", "https://"):
            with self.assertRaises(cmd_keitaro.KeitaroError, msg=bad):
                cmd_keitaro._api_base(bad)

    def test_request_shape_headers_and_timeout(self):
        c, opener = self.client(FakeResponse(b'{"success":true}'))
        self.assertEqual(c.post("/clicks/update_costs", {"a": 1}, write=True), {"success": True})
        req, timeout = opener.requests[0]
        self.assertEqual(timeout, 20)
        self.assertEqual(req.full_url, "https://k.example/admin_api/v1/clicks/update_costs")
        self.assertEqual(req.get_method(), "POST")
        self.assertEqual(req.get_header("Api-key"), API_KEY)
        self.assertEqual(req.get_header("Content-type"), "application/json")
        self.assertEqual(json.loads(req.data), {"a": 1})
        self.assertNotIn("Python-urllib", req.get_header("User-agent"))
        self.assertNotIn(API_KEY, req.full_url)

    def test_default_opener_ignores_env_proxy_and_refuses_redirects(self):
        with mock.patch.dict(os.environ, {"HTTPS_PROXY": "http://proxy.invalid:3128",
                                          "ALL_PROXY": "http://proxy.invalid:3128"}):
            c = cmd_keitaro.KeitaroClient("https://k.example", API_KEY)
        kinds = [type(h) for h in c._opener.handlers]
        self.assertIn(cmd_keitaro._NoRedirect, kinds)
        self.assertFalse(any(isinstance(h, urllib.request.ProxyHandler) for h in c._opener.handlers))
        self.assertIsNone(cmd_keitaro._NoRedirect().redirect_request(None, None, 302, "x", {}, "https://evil"))

    def test_4xx_is_not_retried_and_never_echoes_the_key(self):
        body = json.dumps({"message": f"bad key {API_KEY}"}).encode()
        c, opener = self.client(http_error(403, body))
        with self.assertRaises(cmd_keitaro.KeitaroError) as cm:
            c.get("/campaigns/1")
        self.assertEqual(len(opener.requests), 1)
        self.assertEqual(cm.exception.status, 403)
        self.assertNotIn(API_KEY, cm.exception.message)
        self.assertNotIn(API_KEY, json.dumps(cm.exception.as_dict()))
        self.sleep.assert_not_called()

    def test_5xx_not_retried_and_write_outcome_unknown(self):
        c, opener = self.client(http_error(502, b"<html>bad gateway</html>"))
        with self.assertRaises(cmd_keitaro.KeitaroError) as cm:
            c.post("/clicks/update_costs", {}, write=True)
        self.assertEqual(len(opener.requests), 1)
        self.assertTrue(cm.exception.outcome_unknown)
        c, _ = self.client(http_error(500))
        with self.assertRaises(cmd_keitaro.KeitaroError) as cm:
            c.get("/campaigns/1")
        self.assertFalse(cm.exception.outcome_unknown)

    def test_4xx_write_outcome_is_known(self):
        c, _ = self.client(http_error(422))
        with self.assertRaises(cmd_keitaro.KeitaroError) as cm:
            c.post("/clicks/update_costs", {}, write=True)
        self.assertFalse(cm.exception.outcome_unknown)

    def test_redirect_is_reported_with_a_hint(self):
        c, _ = self.client(http_error(301, b""))
        with self.assertRaises(cmd_keitaro.KeitaroError) as cm:
            c.get("/x")
        self.assertIn("redirect refused", cm.exception.message)

    def test_one_retry_after_reset_before_any_response(self):
        for reset in (ConnectionResetError("reset"), http.client.RemoteDisconnected("closed"),
                      urllib.error.URLError(ConnectionResetError("reset")), BrokenPipeError("pipe")):
            self.sleep.reset_mock()
            c, opener = self.client(reset, FakeResponse(b'{"success":true}'))
            self.assertEqual(c.post("/clicks/update_costs", {}, write=True), {"success": True})
            self.assertEqual(len(opener.requests), 2, type(reset))
            self.sleep.assert_called_once_with(1.0)

    def test_second_reset_surfaces_and_is_not_retried_again(self):
        c, opener = self.client(ConnectionResetError("a"), ConnectionResetError("b"))
        with self.assertRaises(cmd_keitaro.KeitaroError) as cm:
            c.post("/clicks/update_costs", {}, write=True)
        self.assertEqual(len(opener.requests), 2)
        self.assertTrue(cm.exception.outcome_unknown)
        self.assertIn("retried once", cm.exception.message)

    def test_timeout_is_never_retried(self):
        for exc in (TimeoutError("timed out"), urllib.error.URLError(TimeoutError("timed out"))):
            c, opener = self.client(exc)
            with self.assertRaises(cmd_keitaro.KeitaroError) as cm:
                c.post("/clicks/update_costs", {}, write=True)
            self.assertEqual(len(opener.requests), 1)
            self.assertEqual(cm.exception.kind, "timeout")
            self.assertTrue(cm.exception.outcome_unknown)
            self.assertIn("20 s", cm.exception.message)

    def test_connection_refused_is_not_a_reset(self):
        c, opener = self.client(urllib.error.URLError(ConnectionRefusedError("refused")))
        with self.assertRaises(cmd_keitaro.KeitaroError):
            c.get("/x")
        self.assertEqual(len(opener.requests), 1)

    def test_body_lost_after_headers_is_not_retried(self):
        c, opener = self.client(FakeResponse(read_error=ConnectionResetError("mid-body")))
        with self.assertRaises(cmd_keitaro.KeitaroError) as cm:
            c.post("/clicks/update_costs", {}, write=True)
        self.assertEqual(len(opener.requests), 1)
        self.assertTrue(cm.exception.outcome_unknown)

    def test_kt_day_accepts_iso_and_rejects_other_formats(self):
        self.assertEqual(cmd_keitaro._kt_day({"day": "2026-09-27"}), "2026-09-27")
        self.assertEqual(cmd_keitaro._kt_day({"day": "2026-09-27 00:00:00"}), "2026-09-27")
        for bad in ({"day": "27.09.2026"}, {"day": ""}, {}):
            with self.assertRaises(cmd_keitaro.KeitaroError):
                cmd_keitaro._kt_day(bad)

    def test_non_json_answer_and_empty_answer(self):
        c, _ = self.client(FakeResponse(b"<html>login</html>"))
        with self.assertRaises(cmd_keitaro.KeitaroError) as cm:
            c.get("/x")
        self.assertEqual(cm.exception.kind, "non_json")
        c, _ = self.client(FakeResponse(b""))
        self.assertEqual(c.get("/x"), {})


# --------------------------------------------------------------------------- credentials


class CredentialTests(Harness):
    def test_make_client_names_the_missing_variables(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("KEITARO_URL", None)
            os.environ.pop("KEITARO_API_KEY", None)
            with self.assertRaises(cmd_keitaro.KeitaroError) as cm:
                cmd_keitaro._make_client(metaops)
        self.assertIn("KEITARO_URL", cm.exception.message)
        self.assertIn("KEITARO_API_KEY", cm.exception.message)
        with mock.patch.dict(os.environ, {"KEITARO_URL": "https://k.example"}):
            os.environ.pop("KEITARO_API_KEY", None)
            with self.assertRaises(cmd_keitaro.KeitaroError) as cm:
                cmd_keitaro._make_client(metaops)
        self.assertIn("KEITARO_API_KEY", cm.exception.message)
        self.assertNotIn("KEITARO_URL", cm.exception.message.replace("KEITARO_URL (base", ""))

    def test_make_client_registers_the_key_for_redaction(self):
        with mock.patch.dict(os.environ, {"KEITARO_URL": "https://k.example", "KEITARO_API_KEY": API_KEY}):
            client = cmd_keitaro._make_client(metaops)
        self.assertNotIn(API_KEY, metaops.graph.redact(f"boom {API_KEY} boom"))
        self.assertNotIn(API_KEY, client.redact(f"x {API_KEY}"))

    def test_commands_return_a_credentials_envelope_before_any_call(self):
        err = cmd_keitaro.KeitaroError("KEITARO_API_KEY is not set", kind="credentials")
        for fn, mode in ((cmd_keitaro.command_push, "push"), (cmd_keitaro.command_report, "report")):
            with mock.patch.object(metaops.graph, "get") as get, \
                    mock.patch.object(cmd_keitaro, "_make_client", side_effect=err), \
                    contextlib.redirect_stderr(io.StringIO()):
                code, payload = fn(mkargs(self.ws, keitaro_mode=mode), metaops)
            self.assertEqual(code, 2)
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["error"]["kind"], "keitaro")
            self.assertEqual(payload["error"]["reason"], "credentials")
            self.assertIn("KEITARO_API_KEY", payload["error"]["message"])
            get.assert_not_called()


# --------------------------------------------------------------------------- range


class RangeTests(unittest.TestCase):
    def test_trailing_days_end_today_in_the_account_timezone(self):
        parsed = cmd_keitaro._range_args(types.SimpleNamespace(days=3, since=None, until=None), metaops)
        with mock.patch.object(cmd_keitaro, "_utcnow", return_value=NOW):
            self.assertEqual(cmd_keitaro._resolve_range(parsed, "America/New_York", metaops),
                             (dt.date(2026, 9, 27), dt.date(2026, 9, 29)))
        late = dt.datetime(2026, 9, 30, 2, 0, tzinfo=dt.timezone.utc)   # still 29/09 in New York
        with mock.patch.object(cmd_keitaro, "_utcnow", return_value=late):
            self.assertEqual(cmd_keitaro._resolve_range(parsed, "America/New_York", metaops)[1], dt.date(2026, 9, 29))
            self.assertEqual(cmd_keitaro._resolve_range(parsed, "Europe/Istanbul", metaops)[1], dt.date(2026, 9, 30))

    def test_default_is_three_days_and_one_day_is_today_only(self):
        parsed = cmd_keitaro._range_args(types.SimpleNamespace(days=None, since=None, until=None), metaops)
        self.assertEqual(parsed[0], 3)
        parsed = cmd_keitaro._range_args(types.SimpleNamespace(days=1, since=None, until=None), metaops)
        with mock.patch.object(cmd_keitaro, "_utcnow", return_value=NOW):
            self.assertEqual(cmd_keitaro._resolve_range(parsed, "America/New_York", metaops),
                             (dt.date(2026, 9, 29), dt.date(2026, 9, 29)))

    def test_explicit_range_checks(self):
        ns = lambda **k: types.SimpleNamespace(**{"days": None, "since": None, "until": None, **k})  # noqa: E731
        with self.assertRaisesRegex(metaops.MetaOpsError, "together"):
            cmd_keitaro._range_args(ns(since="2026-09-01"), metaops)
        with self.assertRaisesRegex(metaops.MetaOpsError, "exclusive"):
            cmd_keitaro._range_args(ns(days=2, since="2026-09-01", until="2026-09-02"), metaops)
        with self.assertRaisesRegex(metaops.MetaOpsError, "YYYY-MM-DD"):
            cmd_keitaro._range_args(ns(since="09/01", until="2026-09-02"), metaops)
        with self.assertRaisesRegex(metaops.MetaOpsError, "after --until"):
            cmd_keitaro._range_args(ns(since="2026-09-05", until="2026-09-02"), metaops)
        with self.assertRaisesRegex(metaops.MetaOpsError, "longer than"):
            cmd_keitaro._range_args(ns(since="2026-01-01", until="2026-09-02"), metaops)
        for bad in (0, -1, 32):
            with self.assertRaisesRegex(metaops.MetaOpsError, "--days"):
                cmd_keitaro._range_args(ns(days=bad), metaops)
        parsed = cmd_keitaro._range_args(ns(since="2026-09-20", until="2026-09-30"), metaops)
        with mock.patch.object(cmd_keitaro, "_utcnow", return_value=NOW), \
                self.assertRaisesRegex(metaops.MetaOpsError, "after today"):
            cmd_keitaro._resolve_range(parsed, "America/New_York", metaops)


# --------------------------------------------------------------------------- pure builders


class BuilderTests(unittest.TestCase):
    def test_build_entries_are_keyed_on_ad_id_in_account_tz_and_currency(self):
        parsed = {}
        for r in ADS:
            parsed[(r["date_start"], r["ad_id"])] = {"spend": Decimal(r["spend"]), "ad_name": r["ad_name"]}
        entries, zero = cmd_keitaro.build_entries(parsed, "America/New_York", "USD")
        self.assertEqual(zero, 1)
        self.assertEqual(len(entries), 7)
        self.assertEqual(entries[0], {
            "start_date": "2026-09-27 00:00", "end_date": "2026-09-27 23:59",
            "timezone": "America/New_York", "currency": "USD", "cost": 10.0,
            "filters": {"sub_id_6": "111"}})
        self.assertEqual([(e["start_date"][:10], e["filters"]["sub_id_6"]) for e in entries][:3],
                         [("2026-09-27", "111"), ("2026-09-27", "222"), ("2026-09-28", "111")])
        for e in entries:
            self.assertEqual(set(e), {"start_date", "end_date", "timezone", "currency", "cost", "filters"})
            self.assertEqual(list(e["filters"]), ["sub_id_6"])

    def test_payloads_one_request_per_day_and_chunked(self):
        entries = [{"start_date": "2026-09-27 00:00", "filters": {"sub_id_6": str(i)}} for i in range(230)]
        entries += [{"start_date": "2026-09-28 00:00", "filters": {"sub_id_6": "1"}}]
        payloads = cmd_keitaro.build_payloads(1234, entries)
        self.assertEqual([(p["day"], len(p["body"]["costs"])) for p in payloads],
                         [("2026-09-27", 100), ("2026-09-27", 100), ("2026-09-27", 30), ("2026-09-28", 1)])
        for p in payloads:
            self.assertEqual(p["body"]["campaign_ids"], [1234])
            self.assertIs(p["body"]["only_campaign_uniques"], False)
            self.assertEqual(set(p["body"]), {"campaign_ids", "only_campaign_uniques", "costs"})


# --------------------------------------------------------------------------- push: dry run


class PushDryRunTests(Harness):
    def test_dry_run_prints_exact_entries_and_writes_nothing_to_keitaro(self):
        kt, calls = FakeKeitaro(), []
        code, payload = self.push(kt=kt, fb_calls=calls)
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual((payload["command"], payload["phase"]), ("keitaro", "dry_run"))
        self.assertEqual(kt.update_posts(), [])
        self.assertEqual([c[0] for c in kt.calls], ["GET", "POST"])       # campaign read + one readback
        data = payload["data"]
        self.assertEqual(data["mode"], "dry_run")
        self.assertEqual((data["since"], data["until"]), ("2026-09-27", "2026-09-29"))
        self.assertEqual(data["entries_count"], 7)
        self.assertEqual(data["entries_total"], 53.95)
        self.assertEqual(data["zero_spend_rows_skipped"], 1)
        self.assertEqual(len(data["entries"]), 7)
        self.assertEqual(data["entries"][0]["filters"], {"sub_id_6": "111"})
        self.assertIn("EN111", self.stderr)          # the entry table is readable in human mode
        self.assertIn("NOT sent", self.stderr)
        self.assertIn("--confirm PUSH", payload["next_action"])

    def test_facebook_calls_are_minimal_and_exact(self):
        calls = []
        self.push(fb_calls=calls)
        self.assertEqual(len(calls), 3)               # account, ad insights, account insights
        self.assertEqual(calls[0], ("act_1", {"fields": "timezone_name,currency"}))
        ad_path, ad = calls[1]
        self.assertEqual(ad_path, "act_1/insights")
        self.assertEqual(ad["level"], "ad")
        self.assertEqual(ad["time_increment"], 1)
        self.assertEqual(ad["time_range"], {"since": "2026-09-27", "until": "2026-09-29"})
        self.assertEqual(ad["fields"], "ad_id,ad_name,campaign_id,adset_id,spend,impressions,"
                                       "inline_link_clicks,date_start,date_stop")
        flt = ad["filtering"]
        self.assertEqual(len(flt), 1)
        self.assertEqual((flt[0]["field"], flt[0]["operator"]), ("ad.effective_status", "IN"))
        for status in ("ACTIVE", "PAUSED", "DELETED", "ARCHIVED", "DISAPPROVED", "WITH_ISSUES",
                       "CAMPAIGN_PAUSED", "ADSET_PAUSED", "IN_PROCESS", "PENDING_REVIEW"):
            self.assertIn(status, flt[0]["value"])
        acc = calls[2][1]
        self.assertEqual((acc["level"], acc["time_increment"]), ("account", 1))
        self.assertEqual(acc["time_range"], ad["time_range"])
        self.assertNotIn("filtering", acc)            # the account total is the billed truth

    def test_insights_pagination_follows_cursors(self):
        pages = [
            {"data": ADS[:3], "paging": {"cursors": {"after": "A"}, "next": "https://x"}},
            {"data": ADS[3:]},
        ]
        seen = []

        def get(path, params=None, context=""):
            if path == "act_1":
                return {"timezone_name": "America/New_York", "currency": "USD"}
            if params["level"] == "ad":
                seen.append(params.get("after"))
                return pages[len(seen) - 1]
            return fb_get_factory()(path, params, context)

        code, payload = self.push(get=get)
        self.assertEqual(seen, [None, "A"])
        self.assertEqual(payload["data"]["entries_count"], 7)

    def test_account_timezone_and_currency_come_from_graph_not_the_profile(self):
        code, payload = self.push(get=fb_get_factory(tz="Europe/Istanbul", currency="EUR"))
        data = payload["data"]
        self.assertEqual((data["timezone"], data["currency"]), ("Europe/Istanbul", "EUR"))
        e = data["entries"][0]
        self.assertEqual((e["timezone"], e["currency"]), ("Europe/Istanbul", "EUR"))
        codes = [w["code"] for w in data["warnings"]]
        self.assertIn("profile_timezone", codes)
        self.assertIn("profile_currency", codes)

    def test_campaign_from_profile_flag_or_error(self):
        kt = FakeKeitaro()
        self.push(kt=kt)
        self.assertEqual(kt.calls[0][1], "/campaigns/1234")
        kt = FakeKeitaro()
        code, payload = self.push(kt=kt, keitaro_campaign="777")
        self.assertEqual(kt.calls[0][1], "/campaigns/777")
        self.assertEqual(payload["data"]["keitaro_campaign"]["source"], "flag")
        ws = FakeWorkspace(pathlib.Path(self.td.name), {"ad_account_id": "act_1", "currency": "USD",
                                                        "timezone": "America/New_York"})
        with self.assertRaisesRegex(metaops.MetaOpsError, "keitaro_campaign_id"):
            self.run_cmd(cmd_keitaro.command_push, mkargs(ws))
        with self.assertRaisesRegex(metaops.MetaOpsError, "numeric"):
            self.push(keitaro_campaign="abc")

    def test_every_keitaro_call_carries_the_campaign(self):
        kt = FakeKeitaro()
        self.push(kt=kt, keitaro_campaign="1234")
        self.assertEqual(kt.calls[0], ("GET", "/campaigns/1234", None))
        for body in kt.report_bodies():
            self.assertEqual(body["filters"], [{"name": "campaign_id", "operator": "EQUALS", "expression": "1234"}])
        kt = FakeKeitaro()
        self.push(kt=kt, confirm="PUSH", readback_wait=0)
        for _, _, body in kt.update_posts():
            self.assertEqual(body["campaign_ids"], [1234])

    def test_wrong_confirm_literal_is_refused_before_any_call(self):
        kt = FakeKeitaro()
        for wrong in ("push", "YES", ""):
            with self.assertRaisesRegex(metaops.MetaOpsError, "--confirm PUSH"):
                self.push(kt=kt, confirm=wrong)
        self.assertEqual(kt.calls, [])

    def test_bad_arguments_fail_before_any_call(self):
        kt, calls = FakeKeitaro(), []
        with self.assertRaises(metaops.MetaOpsError):
            self.push(kt=kt, fb_calls=calls, days=99)
        with self.assertRaises(metaops.MetaOpsError):
            self.push(kt=kt, fb_calls=calls, readback_wait=-1)
        with self.assertRaises(metaops.MetaOpsError):
            self.push(kt=kt, fb_calls=calls, keitaro_currency="DOLLARS")
        self.assertEqual((kt.calls, calls), ([], []))

    def test_payload_file_holds_the_exact_request_bodies(self):
        code, payload = self.push()
        path = pathlib.Path(payload["artifacts"]["payload"])
        self.assertEqual(path.parent, (pathlib.Path(self.td.name) / "keitaro").resolve())
        doc = json.loads(path.read_text())
        self.assertEqual(doc["schema"], "metaops.keitaro-push/v1")
        self.assertFalse(doc["live"])
        self.assertEqual([r["day"] for r in doc["requests"]], DAYS3)
        flat = [e for r in doc["requests"] for e in r["body"]["costs"]]
        self.assertEqual(flat, payload["data"]["entries"])

    def test_no_secret_in_output(self):
        kt = FakeKeitaro()
        code, payload = self.push(kt=kt, confirm="PUSH")
        self.assertNotIn(API_KEY, json.dumps(payload) + self.stderr)

    def test_dry_run_reports_ad_days_that_have_spend_but_no_clicks(self):
        clicks = {(r["date_start"], r["ad_id"]): 10 for r in ADS if Decimal(r["spend"]) > 0}
        clicks[("2026-09-28", "333")] = 0
        code, payload = self.push(kt=FakeKeitaro(clicks=clicks))
        rec = payload["data"]["reconcile"]
        self.assertEqual(rec["no_clicks"], [{"day": "2026-09-28", "ad_id": "333", "spend": 3.1}])
        day = {d["day"]: d for d in rec["days"]}["2026-09-28"]
        self.assertIn("no_clicks", day["flags"])
        self.assertEqual(day["lost_no_clicks"], 3.1)
        self.assertIn("no_clicks", [w["code"] for w in payload["data"]["warnings"]])
        self.assertIn("3.1", self.stderr)

    def test_nothing_to_push_when_no_ad_has_spend(self):
        ads = [ad_row("111", "2026-09-29", "0.00")]
        kt = FakeKeitaro(ads=ads)
        code, payload = self.push(kt=kt, get=fb_get_factory(ads=ads), confirm="PUSH")
        self.assertEqual((code, payload["phase"]), (0, "nothing_to_push"))
        self.assertEqual(kt.update_posts(), [])
        self.assertEqual(payload["data"]["entries_count"], 0)

    def test_duplicate_or_malformed_insight_rows_abort_before_any_write(self):
        kt = FakeKeitaro()
        dup = [ADS[0], dict(ADS[0])]
        with self.assertRaisesRegex(metaops.MetaOpsError, "duplicate"):
            self.push(kt=kt, get=fb_get_factory(ads=dup), confirm="PUSH")
        bad = [dict(ADS[0], spend="abc")]
        with self.assertRaisesRegex(metaops.MetaOpsError, "spend"):
            self.push(kt=kt, get=fb_get_factory(ads=bad, account_days={"2026-09-27": "10.00"}), confirm="PUSH")
        multi = [dict(ADS[0], date_stop="2026-09-28")]
        with self.assertRaisesRegex(metaops.MetaOpsError, "daily rows"):
            self.push(kt=kt, get=fb_get_factory(ads=multi), confirm="PUSH")
        self.assertEqual(kt.update_posts(), [])


# --------------------------------------------------------------------------- push: live


class PushLiveTests(Harness):
    def test_live_push_sends_one_request_per_day_then_reads_back(self):
        kt = FakeKeitaro()
        code, payload = self.push(kt=kt, confirm="PUSH")
        self.assertEqual((code, payload["ok"], payload["phase"]), (0, True, "pushed"))
        posts = kt.update_posts()
        self.assertEqual(len(posts), 3)
        self.assertEqual([len(p[2]["costs"]) for p in posts], [2, 2, 3])
        first = posts[0][2]["costs"][0]
        self.assertEqual(first, {"start_date": "2026-09-27 00:00", "end_date": "2026-09-27 23:59",
                                 "timezone": "America/New_York", "currency": "USD", "cost": 10.0,
                                 "filters": {"sub_id_6": "111"}})
        data = payload["data"]
        self.assertNotIn("entries", data)             # only the dry run inlines them
        self.assertEqual(data["pushed"], {"requests": 3, "days": DAYS3, "pending_days": []})
        self.assertTrue(data["readback"]["settled"])
        self.assertEqual([(d["day"], d["fb_spend"], d["keitaro_cost"], d["delta"], d["flags"]) for d in data["reconcile"]["days"]],
                         [("2026-09-27", 14.0, 14.0, 0.0, []), ("2026-09-28", 23.6, 23.6, 0.0, []),
                          ("2026-09-29", 16.35, 16.35, 0.0, [])])
        self.assertIn("Costs stored", payload["next_action"])
        self.assertEqual(self.sleeps, [])
        readback = kt.report_bodies()[-1]
        self.assertEqual(readback["dimensions"], ["day", "sub_id_6"])
        self.assertEqual(readback["measures"], ["clicks", "cost"])
        self.assertEqual(readback["range"], {"from": "2026-09-27 00:00", "to": "2026-09-29 23:59",
                                             "timezone": "America/New_York"})

    def test_large_day_is_split_into_chunks_of_100(self):
        ads = [ad_row(str(1000 + i), "2026-09-29", "1.00") for i in range(230)]
        kt = FakeKeitaro(ads=ads)
        code, payload = self.push(kt=kt, get=fb_get_factory(ads=ads), confirm="PUSH", days=1)
        self.assertEqual([len(p[2]["costs"]) for p in kt.update_posts()], [100, 100, 30])
        self.assertEqual(payload["data"]["pushed"]["requests"], 3)

    def test_readback_lag_polls_without_repushing(self):
        kt = FakeKeitaro(lag_reads=2)
        code, payload = self.push(kt=kt, confirm="PUSH", readback_wait=45)
        self.assertEqual(code, 0)
        self.assertEqual(len(kt.update_posts()), 3)               # never re-pushed
        self.assertEqual(self.sleeps, [15, 15])
        self.assertTrue(payload["data"]["readback"]["settled"])
        self.assertEqual(payload["data"]["readback"]["attempts"], 3)

    def test_readback_that_never_settles_is_a_warning_not_a_failure(self):
        kt = FakeKeitaro(apply_cost=False)
        code, payload = self.push(kt=kt, confirm="PUSH", readback_wait=30)
        self.assertEqual((code, payload["ok"], payload["phase"]), (0, True, "pushed"))
        self.assertEqual(len(kt.update_posts()), 3)
        self.assertEqual(self.sleeps, [15, 15])
        self.assertFalse(payload["data"]["readback"]["settled"])
        codes = [w["code"] for w in payload["data"]["warnings"]]
        self.assertIn("readback_pending", codes)
        for d in payload["data"]["reconcile"]["days"]:
            self.assertIn("not_stored", d["flags"])
            self.assertIn("delta", d["flags"])
        self.assertIn("do not re-push", payload["next_action"])
        self.assertIn("lags", self.stderr)

    def test_readback_wait_zero_reads_once_and_never_sleeps(self):
        kt = FakeKeitaro(apply_cost=False)
        self.push(kt=kt, confirm="PUSH", readback_wait=0)
        self.assertEqual(len(kt.report_bodies()), 1)
        self.assertEqual(self.sleeps, [])

    def test_wait_shorter_than_one_poll_does_not_overshoot(self):
        kt = FakeKeitaro(apply_cost=False)
        self.push(kt=kt, confirm="PUSH", readback_wait=10)
        self.assertEqual(self.sleeps, [10])

    def test_delta_over_three_percent_is_flagged(self):
        kt = FakeKeitaro(fx=1.0)
        original = kt.post

        def post(path, body, *, write=False):
            if path == "/clicks/update_costs":
                for e in body["costs"]:
                    if e["start_date"].startswith("2026-09-28") and e["filters"]["sub_id_6"] == "111":
                        e = dict(e, cost=e["cost"] * 0.9)     # Keitaro stored 10% less for this ad
                    kt.staged.append((e["start_date"][:10], e["filters"]["sub_id_6"], e["cost"]))
                kt.posts += 1
                kt.calls.append(("POST", path, body))
                return {"success": True}
            return original(path, body, write=write)

        kt.post = post
        code, payload = self.push(kt=kt, confirm="PUSH", readback_wait=0)
        days = {d["day"]: d for d in payload["data"]["reconcile"]["days"]}
        self.assertEqual(days["2026-09-28"]["flags"], ["delta"])
        self.assertAlmostEqual(days["2026-09-28"]["delta"], -2.05, places=2)
        self.assertEqual(days["2026-09-27"]["flags"], [])
        self.assertFalse(payload["data"]["readback"]["settled"])

    def test_small_delta_within_three_percent_is_not_flagged(self):
        kt = FakeKeitaro(fx=1.02)
        code, payload = self.push(kt=kt, confirm="PUSH", readback_wait=0)
        for d in payload["data"]["reconcile"]["days"]:
            self.assertEqual(d["flags"], [])
        self.assertTrue(payload["data"]["readback"]["settled"])

    def test_spend_without_clicks_is_reported_as_lost(self):
        clicks = {(r["date_start"], r["ad_id"]): 10 for r in ADS if Decimal(r["spend"]) > 0}
        clicks[("2026-09-29", "222")] = 0
        kt = FakeKeitaro(clicks=clicks)
        code, payload = self.push(kt=kt, confirm="PUSH", readback_wait=0)
        d = {x["day"]: x for x in payload["data"]["reconcile"]["days"]}["2026-09-29"]
        self.assertEqual(d["lost_no_clicks"], 8.0)
        self.assertIn("no_clicks", d["flags"])
        self.assertIn("delta", d["flags"])            # raw delta is -8.00 of 16.35
        self.assertTrue(d["settled"])                 # what could land did land: not a lag
        self.assertTrue(payload["data"]["readback"]["settled"])
        self.assertIn("Not fully accounted for", payload["next_action"])
        self.assertIn("1 ad-day(s) had no Keitaro clicks", payload["next_action"])
        self.assertIn("no_clicks", [w["code"] for w in payload["data"]["warnings"]])

    def test_day_where_keitaro_stored_nothing_is_flagged_not_stored(self):
        clicks = {(r["date_start"], r["ad_id"]): 10 for r in ADS if Decimal(r["spend"]) > 0}
        for k in list(clicks):
            if k[0] == "2026-09-27":
                clicks[k] = 0
        kt = FakeKeitaro(clicks=clicks)
        code, payload = self.push(kt=kt, confirm="PUSH", readback_wait=0)
        d = {x["day"]: x for x in payload["data"]["reconcile"]["days"]}["2026-09-27"]
        self.assertEqual(d["flags"], ["no_clicks", "not_stored", "delta"])
        self.assertEqual(d["keitaro_cost"], 0.0)

    def test_4xx_stops_the_push_without_retry_and_reports_pending_days(self):
        kt = FakeKeitaro(fail_post={1: cmd_keitaro.KeitaroError("HTTP 422 on /clicks/update_costs: bad", status=422,
                                                               path="/clicks/update_costs")})
        code, payload = self.push(kt=kt, confirm="PUSH")
        self.assertEqual(code, 1)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["phase"], "push_failed")
        self.assertEqual(kt.posts, 2)                              # day 1 ok, day 2 failed, day 3 never sent
        self.assertEqual(payload["error"]["kind"], "keitaro")
        self.assertEqual(payload["error"]["status"], 422)
        pushed = payload["data"]["pushed"]
        self.assertEqual((pushed["days"], pushed["failed_day"], pushed["pending_days"]),
                         (["2026-09-27"], "2026-09-28", ["2026-09-28", "2026-09-29"]))
        self.assertEqual(kt.report_bodies(), [])                   # no readback of a half push
        self.assertIn("idempotent", payload["next_action"])
        self.assertNotIn("dry run first", payload["next_action"])
        self.assertIn("payload", payload["artifacts"])

    def test_unknown_outcome_tells_to_read_before_repeating(self):
        kt = FakeKeitaro(fail_post={0: cmd_keitaro.KeitaroError("timed out", kind="timeout", outcome_unknown=True)})
        code, payload = self.push(kt=kt, confirm="PUSH")
        self.assertEqual(code, 1)
        self.assertTrue(payload["error"]["outcome_unknown"])
        self.assertIn("dry run first", payload["next_action"])

    def test_success_false_answer_is_a_failure(self):
        kt = FakeKeitaro(update_response={"success": False, "message": "nope"})
        code, payload = self.push(kt=kt, confirm="PUSH")
        self.assertEqual((code, payload["phase"]), (1, "push_failed"))
        self.assertEqual(kt.posts, 1)

    def test_readback_failure_does_not_undo_a_successful_push(self):
        err = cmd_keitaro.KeitaroError("HTTP 500 on /report/build", status=500, path="/report/build")
        kt = FakeKeitaro(report_error=err)
        code, payload = self.push(kt=kt, confirm="PUSH")
        self.assertEqual((code, payload["ok"], payload["phase"]), (0, True, "pushed"))
        self.assertEqual(payload["data"]["pushed"]["requests"], 3)
        self.assertFalse(payload["data"]["readback"]["checked"])
        self.assertIn("readback_failed", [w["code"] for w in payload["data"]["warnings"]])

    def test_graph_failure_aborts_before_any_write(self):
        kt = FakeKeitaro()

        def get(path, params=None, context=""):
            if path == "act_1":
                return {"timezone_name": "America/New_York", "currency": "USD"}
            raise metaops.graph.GraphError(400, {"error": {"code": 100, "message": "bad"}}, "ad insights")

        with self.assertRaises(metaops.graph.GraphError):
            self.push(kt=kt, get=get, confirm="PUSH")
        self.assertEqual(kt.update_posts(), [])

    def test_campaign_read_failure_aborts_before_facebook(self):
        err = cmd_keitaro.KeitaroError("HTTP 404 on /campaigns/1234: not found", status=404, path="/campaigns/1234")
        kt, calls = FakeKeitaro(campaign=err), []
        code, payload = self.push(kt=kt, fb_calls=calls, confirm="PUSH")
        self.assertEqual((code, payload["phase"]), (1, "campaign_read"))
        self.assertEqual(calls, [])
        self.assertEqual(kt.posts, 0)


# --------------------------------------------------------------------------- unattributed spend


class UnattributedTests(Harness):
    def test_no_gap_means_no_campaign_level_call_and_no_warning(self):
        calls = []
        code, payload = self.push(fb_calls=calls)
        self.assertNotIn("campaign", [c[1].get("level") for c in calls])
        self.assertEqual(payload["data"]["unattributed"]["total"], 0.0)
        self.assertNotIn("unattributed", [w["code"] for w in payload["data"]["warnings"]])

    def test_rounding_noise_is_not_a_gap(self):
        account = {"2026-09-27": "14.01", "2026-09-28": "23.59", "2026-09-29": "16.36"}
        calls = []
        code, payload = self.push(get=fb_get_factory(account_days=account, calls=calls))
        self.assertEqual([c for c in calls if c[1].get("level") == "campaign"], [])
        self.assertEqual(payload["data"]["unattributed"]["total"], 0.0)

    def test_gap_is_reported_loudly_and_never_pushed(self):
        account = dict(DAY_SUMS, **{"2026-09-28": "33.60"})       # 10.00 nobody explains
        campaign_days = {("2026-09-28", "C1"): Decimal("20.50"), ("2026-09-28", "C2"): Decimal("3.10"),
                         ("2026-09-28", "C9"): Decimal("10.00")}
        calls = []
        kt = FakeKeitaro()
        code, payload = self.push(kt=kt, confirm="PUSH", get=fb_get_factory(
            account_days=account, campaign_days={k: str(v) for k, v in campaign_days.items()}, calls=calls))
        un = payload["data"]["unattributed"]
        self.assertEqual(un["total"], 10.0)
        self.assertTrue(un["days"]["2026-09-28"]["significant"])
        self.assertFalse(un["days"]["2026-09-27"]["significant"])
        self.assertIn("unattributed", [w["code"] for w in payload["data"]["warnings"]])
        self.assertIn("UNATTRIBUTED SPEND 10.0", self.stderr)
        self.assertIn("unattributed spend 10.0 USD was not pushed", payload["next_action"])
        # exactly the per-ad entries went out: nothing keyed on ad_campaign_id, nothing extra
        sent = [e for _, _, b in kt.update_posts() for e in b["costs"]]
        self.assertEqual(len(sent), 7)
        self.assertTrue(all(list(e["filters"]) == ["sub_id_6"] for e in sent))
        self.assertEqual(un["remainder_candidates"], [{
            "day": "2026-09-28", "campaign_id": "C9", "cost": 10.0,
            "entry": {"start_date": "2026-09-28 00:00", "end_date": "2026-09-28 23:59",
                      "timezone": "America/New_York", "currency": "USD", "cost": 10.0,
                      "filters": {"ad_campaign_id": "C9"}}}])
        self.assertEqual(un["partial_gaps"], [])
        camp_calls = [c for c in calls if c[1].get("level") == "campaign"]
        self.assertEqual(len(camp_calls), 1)
        self.assertEqual(camp_calls[0][1]["filtering"][0]["field"], "campaign.effective_status")

    def test_partly_explained_campaign_is_not_offered_as_pushable(self):
        account = dict(DAY_SUMS, **{"2026-09-28": "28.60"})       # 5.00 missing inside C1
        cdays = {("2026-09-28", "C1"): "25.50", ("2026-09-28", "C2"): "3.10"}
        code, payload = self.push(get=fb_get_factory(account_days=account, campaign_days=cdays))
        un = payload["data"]["unattributed"]
        self.assertEqual(un["remainder_candidates"], [])
        self.assertEqual(un["partial_gaps"], [{"day": "2026-09-28", "campaign_id": "C1", "gap": 5.0, "ad_rows": 2}])

    def test_ad_rows_above_account_total_warn_separately(self):
        account = dict(DAY_SUMS, **{"2026-09-29": "10.00"})
        code, payload = self.push(get=fb_get_factory(account_days=account))
        codes = [w["code"] for w in payload["data"]["warnings"]]
        self.assertIn("ad_rows_exceed_account", codes)
        self.assertNotIn("unattributed", codes)
        self.assertEqual(payload["data"]["unattributed"]["total"], 0.0)

    def test_campaign_breakdown_failure_does_not_block_the_push(self):
        account = dict(DAY_SUMS, **{"2026-09-28": "33.60"})
        err = metaops.graph.GraphError(400, {"error": {"code": 100, "message": "bad filter"}}, "campaign")
        kt = FakeKeitaro()
        code, payload = self.push(kt=kt, confirm="PUSH", get=fb_get_factory(account_days=account, campaign_error=err))
        self.assertEqual((code, payload["phase"]), (0, "pushed"))
        codes = [w["code"] for w in payload["data"]["warnings"]]
        self.assertIn("campaign_breakdown_failed", codes)
        self.assertIn("unattributed", codes)
        self.assertEqual(len(kt.update_posts()), 3)

    def test_deleted_and_archived_ads_are_in_the_push(self):
        # Facebook returns them because the filter names their statuses; the fixture returns them and
        # the entries must include them like any other ad.
        ads = ADS + [ad_row("999", "2026-09-29", "2.50", name="deleted ad")]
        kt = FakeKeitaro(ads=ads)
        code, payload = self.push(kt=kt, get=fb_get_factory(ads=ads))
        self.assertIn("999", [e["filters"]["sub_id_6"] for e in payload["data"]["entries"]])
        self.assertEqual(payload["data"]["unattributed"]["total"], 0.0)


# --------------------------------------------------------------------------- currency


class FxTests(Harness):
    def eur(self, **kw):
        return self.push(get=fb_get_factory(currency="EUR"), **kw)

    def test_currency_unknown_assumes_same_and_says_so(self):
        kt = FakeKeitaro(fx=1.139)
        code, payload = self.eur(kt=kt, confirm="PUSH", readback_wait=0)
        self.assertTrue(payload["data"]["keitaro_currency_assumed"])
        self.assertIn("assuming it equals", self.stderr)
        self.assertIn("delta", payload["data"]["reconcile"]["days"][0]["flags"])

    def test_different_currency_is_judged_by_consistency_not_by_one(self):
        kt = FakeKeitaro(fx=1.139)
        code, payload = self.eur(kt=kt, confirm="PUSH", readback_wait=0, keitaro_currency="USD")
        rec = payload["data"]["reconcile"]
        self.assertFalse(payload["data"]["keitaro_currency_assumed"])
        self.assertTrue(rec["converted"])
        self.assertAlmostEqual(rec["fx_rate"], 1.139, places=3)
        for d in rec["days"]:
            self.assertEqual(d["flags"], [])
            self.assertAlmostEqual(d["keitaro_cost"], d["fb_spend"], places=1)
        self.assertTrue(payload["data"]["readback"]["settled"])
        self.assertEqual(payload["data"]["keitaro_currency"], "USD")

    def test_an_inconsistent_day_stands_out_under_fx(self):
        kt = FakeKeitaro(fx=1.139)
        original = kt.post

        def post(path, body, *, write=False):
            if path == "/clicks/update_costs":
                for e in body["costs"]:
                    factor = 0.5 if e["start_date"].startswith("2026-09-29") else 1.139
                    kt.staged.append((e["start_date"][:10], e["filters"]["sub_id_6"], e["cost"] * factor))
                kt.posts += 1
                kt.calls.append(("POST", path, body))
                return {"success": True}
            return original(path, body, write=write)

        kt.post = post
        code, payload = self.eur(kt=kt, confirm="PUSH", readback_wait=0, keitaro_currency="usd")
        days = {d["day"]: d for d in payload["data"]["reconcile"]["days"]}
        self.assertEqual(days["2026-09-27"]["flags"], [])
        self.assertIn("delta", days["2026-09-29"]["flags"])

    def test_same_currency_given_explicitly_is_not_converted(self):
        code, payload = self.push(kt=FakeKeitaro(), keitaro_currency="USD", confirm="PUSH", readback_wait=0)
        self.assertFalse(payload["data"]["reconcile"]["converted"])
        self.assertIsNone(payload["data"]["reconcile"]["fx_rate"])

    def test_env_currency_is_used_when_no_flag(self):
        with mock.patch.dict(os.environ, {"KEITARO_CURRENCY": "usd"}):
            code, payload = self.eur(kt=FakeKeitaro(fx=1.139), confirm="PUSH", readback_wait=0)
        self.assertEqual(payload["data"]["keitaro_currency"], "USD")


# --------------------------------------------------------------------------- cost model


class CostModelTests(Harness):
    def codes(self, campaign):
        code, payload = self.push(kt=FakeKeitaro(campaign=campaign))
        self.assertEqual(code, 0)
        return [w["code"] for w in payload["data"]["warnings"]], payload

    def test_cpa_with_auto_on_warns_loudly(self):
        codes, payload = self.codes({"name": "c", "cost_type": "CPA", "cost_value": 60, "cost_auto": True})
        self.assertIn("cost_model_auto", codes)
        msg = [w["message"] for w in payload["data"]["warnings"] if w["code"] == "cost_model_auto"][0]
        self.assertIn("AUTO ON", msg)
        self.assertIn("fake cost", msg)
        self.assertEqual(payload["data"]["keitaro_campaign"]["cost_type"], "CPA")

    def test_cps_auto_and_string_flags(self):
        codes, _ = self.codes({"cost_type": "cps", "cost_value": "60", "cost_auto": "1"})
        self.assertIn("cost_model_auto", codes)

    def test_cpa_with_auto_off_and_cpc_zero_are_quiet(self):
        codes, _ = self.codes({"cost_type": "CPA", "cost_value": 60, "cost_auto": False})
        self.assertEqual(codes, [])
        codes, _ = self.codes({"cost_type": "CPC", "cost_value": 0, "cost_auto": False})
        self.assertEqual(codes, [])

    def test_cpc_with_a_value_warns(self):
        codes, _ = self.codes({"cost_type": "CPC", "cost_value": 0.05, "cost_auto": False})
        self.assertEqual(codes, ["cost_model_value"])

    def test_unreadable_cost_model_says_so(self):
        codes, _ = self.codes({"name": "c"})
        self.assertEqual(codes, ["cost_model_unreadable"])

    def test_campaign_is_only_read_never_written(self):
        kt = FakeKeitaro(campaign={"cost_type": "CPA", "cost_value": 60, "cost_auto": True})
        self.push(kt=kt, confirm="PUSH")
        self.assertEqual([c for c in kt.calls if c[0] == "PUT"], [])
        self.assertEqual([c[1] for c in kt.calls if c[0] == "GET"], ["/campaigns/1234"])


# --------------------------------------------------------------------------- report


def kt_row(ad, clicks=0, leads=0, sales=0, cost=0, sale_revenue=0, lead_revenue=0, day=None):
    row = {"sub_id_6": ad, "clicks": clicks, "leads": leads, "sales": sales, "cost": cost,
           "sale_revenue": sale_revenue, "lead_revenue": lead_revenue}
    if day:
        row["day"] = day
    return row


REPORT_ROWS = [
    kt_row("111", clicks=100, leads=5, sales=3, cost=40.0, sale_revenue=120.0),
    kt_row("222", clicks=50, leads=2, sales=0, cost=12.0, sale_revenue=0),
    kt_row("777", clicks=9, leads=0, sales=0, cost=0, sale_revenue=0),           # not in FB rows
    kt_row("{{ad.id}}", clicks=30, leads=1, sales=1, cost=0, sale_revenue=15.0),
    kt_row("{{ad.id}}x", clicks=5),
    kt_row("", clicks=7),
]


class ReportTests(Harness):
    def test_join_math_regs_deps_cost_per_and_roi_on_sale_revenue(self):
        kt = FakeKeitaro(report_rows=REPORT_ROWS)
        code, payload = self.report(kt=kt)
        self.assertEqual((code, payload["ok"], payload["phase"]), (0, True, "reported"))
        rows = {r["key"]: r for r in payload["data"]["rows"]}
        a = rows["111"]
        self.assertEqual((a["leads"], a["sales"], a["regs"], a["deps"]), (5, 3, 8, 3))
        self.assertEqual(a["fb_spend"], 35.75)                       # 10 + 20.50 + 5.25
        self.assertEqual(a["cost"], 40.0)
        self.assertEqual(a["cost_per_reg"], 5.0)                     # 40 / (5 + 3)
        self.assertEqual(a["cost_per_dep"], 13.33)
        self.assertEqual(a["roi_pct"], 200.0)                        # (120 - 40) / 40
        self.assertEqual(a["label"], "EN111")
        b = rows["222"]
        self.assertEqual((b["regs"], b["deps"], b["cost_per_dep"]), (2, 0, None))
        self.assertEqual(b["roi_pct"], -100.0)

    def test_conversions_is_never_requested(self):
        kt = FakeKeitaro(report_rows=REPORT_ROWS)
        self.report(kt=kt)
        body = kt.report_bodies()[0]
        self.assertEqual(body["measures"], ["clicks", "leads", "sales", "cost", "sale_revenue", "lead_revenue"])
        self.assertNotIn("conversions", json.dumps(body))
        self.assertNotIn("revenue\"", json.dumps(body).replace("sale_revenue", "").replace("lead_revenue", ""))
        self.assertEqual(body["dimensions"], ["sub_id_6"])
        self.assertEqual(body["filters"][0]["name"], "campaign_id")

    def test_macro_and_empty_rows_are_excluded_and_counted_apart(self):
        code, payload = self.report(kt=FakeKeitaro(report_rows=REPORT_ROWS))
        data = payload["data"]
        self.assertNotIn("{{ad.id}}", [r["key"] for r in data["rows"]])
        self.assertNotIn("", [r["key"] for r in data["rows"]])
        macro = data["excluded"]["unsubstituted_macros"]
        self.assertEqual((macro["clicks"], macro["regs"], macro["deps"], macro["sale_revenue"]), (35, 2, 1, 15.0))
        self.assertEqual(macro["distinct_values"], 2)
        self.assertEqual(data["excluded"]["empty_sub_id_6"]["clicks"], 7)
        self.assertEqual(data["totals"]["clicks"], 159)              # 100 + 50 + 9, excluded rows not in it
        self.assertIn("macros", [w["code"] for w in data["warnings"]])

    def test_ads_keitaro_has_but_facebook_does_not_are_flagged(self):
        code, payload = self.report(kt=FakeKeitaro(report_rows=REPORT_ROWS))
        rows = {r["key"]: r for r in payload["data"]["rows"]}
        self.assertEqual(rows["777"]["flags"], ["not_in_fb_rows"])
        self.assertEqual(rows["777"]["fb_spend"], 0.0)
        self.assertIsNone(rows["777"]["roi_pct"])

    def test_fb_ad_without_keitaro_clicks_and_clicks_without_cost(self):
        rows = [kt_row("111", clicks=10, leads=1, cost=0)]
        code, payload = self.report(kt=FakeKeitaro(report_rows=rows))
        by = {r["key"]: r for r in payload["data"]["rows"]}
        self.assertEqual(by["111"]["flags"], ["no_keitaro_cost"])
        self.assertEqual(by["222"]["flags"], ["no_keitaro_clicks"])
        self.assertEqual(by["333"]["flags"], ["no_keitaro_clicks"])

    def test_lead_revenue_sanity(self):
        rows = [kt_row("111", clicks=10, leads=1, lead_revenue=160.0, sale_revenue=0)]
        code, payload = self.report(kt=FakeKeitaro(report_rows=rows))
        self.assertEqual(payload["data"]["lead_revenue_total"], 160.0)
        self.assertIn("lead_revenue", [w["code"] for w in payload["data"]["warnings"]])
        self.assertIn("expected 0", self.stderr)
        code, payload = self.report(kt=FakeKeitaro(report_rows=REPORT_ROWS))
        self.assertEqual(payload["data"]["lead_revenue_total"], 0.0)
        self.assertNotIn("lead_revenue", [w["code"] for w in payload["data"]["warnings"]])

    def test_by_adset_uses_the_facebook_ad_to_adset_map(self):
        rows = [kt_row("111", clicks=100, leads=5, sales=3, cost=40.0, sale_revenue=120.0),
                kt_row("222", clicks=50, leads=2, cost=12.0),
                kt_row("333", clicks=20, leads=1, sales=1, cost=6.0, sale_revenue=30.0),
                kt_row("777", clicks=9, cost=1.0)]
        code, payload = self.report(kt=FakeKeitaro(report_rows=rows), by="adset")
        by = {r["key"]: r for r in payload["data"]["rows"]}
        self.assertEqual(set(by), {"S1", "S2", "(not in FB rows)"})
        self.assertEqual((by["S1"]["clicks"], by["S1"]["regs"], by["S1"]["deps"], by["S1"]["cost"]), (150, 10, 3, 52.0))
        self.assertEqual(by["S1"]["ads"], 2)
        self.assertEqual(by["S1"]["label"], "adset S1")
        self.assertEqual(by["S1"]["fb_spend"], 47.75)               # ads 111 + 222
        self.assertEqual((by["S2"]["regs"], by["S2"]["deps"]), (2, 1))
        self.assertEqual(payload["data"]["totals"]["clicks"], 179)
        self.assertEqual(payload["data"]["by"], "adset")

    def test_by_day_groups_on_day_and_sums_ads(self):
        rows = [kt_row("111", clicks=10, leads=1, cost=5.0, day="2026-09-27"),
                kt_row("222", clicks=5, sales=1, cost=2.0, sale_revenue=20.0, day="2026-09-27"),
                kt_row("111", clicks=8, leads=2, cost=4.0, day="2026-09-28"),
                kt_row("{{x}}", clicks=3, day="2026-09-28")]
        kt = FakeKeitaro(report_rows=rows)
        code, payload = self.report(kt=kt, by="day")
        self.assertEqual(kt.report_bodies()[0]["dimensions"], ["day", "sub_id_6"])
        by = {r["key"]: r for r in payload["data"]["rows"]}
        self.assertEqual([r["key"] for r in payload["data"]["rows"]], DAYS3[:3])
        self.assertEqual((by["2026-09-27"]["clicks"], by["2026-09-27"]["regs"], by["2026-09-27"]["deps"]), (15, 2, 1))
        self.assertEqual(by["2026-09-27"]["fb_spend"], 14.0)
        self.assertEqual(by["2026-09-28"]["clicks"], 8)
        self.assertEqual(payload["data"]["excluded"]["unsubstituted_macros"]["clicks"], 3)
        self.assertEqual(by["2026-09-29"]["clicks"], 0)

    def test_paging_through_a_long_report(self):
        rows = [kt_row(str(1000 + i), clicks=1) for i in range(7)]
        kt = FakeKeitaro(report_rows=rows)
        with mock.patch.object(cmd_keitaro, "KT_PAGE_LIMIT", 3):
            code, payload = self.report(kt=kt)
        self.assertEqual([b["offset"] for b in kt.report_bodies()], [0, 3, 6])
        self.assertEqual(payload["data"]["totals"]["clicks"], 7)

    def test_report_warns_about_the_cpa_auto_cost_model(self):
        kt = FakeKeitaro(report_rows=REPORT_ROWS, campaign={"cost_type": "CPA", "cost_value": 60, "cost_auto": True})
        code, payload = self.report(kt=kt)
        self.assertIn("cost_model_auto", [w["code"] for w in payload["data"]["warnings"]])

    def test_report_failure_is_an_envelope(self):
        err = cmd_keitaro.KeitaroError("HTTP 400 on /report/build: bad measure", status=400, path="/report/build")
        code, payload = self.report(kt=FakeKeitaro(report_error=err))
        self.assertEqual((code, payload["ok"], payload["phase"]), (1, False, "report_failed"))
        self.assertEqual(payload["error"]["status"], 400)

    def test_report_needs_a_campaign_and_a_valid_grouping(self):
        ws = FakeWorkspace(pathlib.Path(self.td.name), {"ad_account_id": "act_1", "currency": "USD", "timezone": "x"})
        with self.assertRaisesRegex(metaops.MetaOpsError, "campaign id required"):
            self.run_cmd(cmd_keitaro.command_report, mkargs(ws, keitaro_mode="report"))
        with self.assertRaisesRegex(metaops.MetaOpsError, "--by"):
            self.report(by="week")

    def test_report_facebook_side_uses_one_account_read_and_one_insights_call(self):
        calls = []
        self.report(kt=FakeKeitaro(report_rows=REPORT_ROWS), fb_calls=calls)
        self.assertEqual([c[0] for c in calls], ["act_1", "act_1/insights"])
        self.assertIn("adset_name", calls[1][1]["fields"])
        self.assertEqual(calls[1][1]["filtering"][0]["field"], "ad.effective_status")

    def test_report_prints_a_table_on_stderr(self):
        self.report(kt=FakeKeitaro(report_rows=REPORT_ROWS))
        self.assertIn("EN111", self.stderr)
        self.assertIn("TOTAL", self.stderr)
        self.assertIn("excluded, unsubstituted", self.stderr)


# --------------------------------------------------------------------------- workspace + CLI


class WorkspaceFieldTests(unittest.TestCase):
    def workspace(self, **profile_extra):
        profile = {"business_id": "10", "ad_account_id": "act_13", "page_id": "14", "dataset_id": "15",
                   "currency": "USD", "timezone": "America/New_York", **profile_extra}
        return {"schema": meta_workspace.WORKSPACE_SCHEMA, "name": "w", "api_version": "v26.0",
                "profiles": {"p": profile}, "defaults": {"profile": "p"}}

    def test_optional_numeric_string_is_accepted_and_absence_still_valid(self):
        meta_workspace.validate_workspace(self.workspace())
        meta_workspace.validate_workspace(self.workspace(keitaro_campaign_id="1234"))

    def test_rejects_non_numeric_or_non_string(self):
        for bad in ("abc", 1234, "25 52", ""):
            data = self.workspace(keitaro_campaign_id=bad)
            with self.assertRaises(meta_workspace.WorkspaceError, msg=repr(bad)):
                meta_workspace.validate_workspace(data)

    def test_published_schema_agrees(self):
        schema = json.loads((pathlib.Path(__file__).resolve().parent.parent / "schemas" / "workspace.v1.json").read_text())
        validator = jsonschema.Draft202012Validator(schema)
        validator.validate(self.workspace(keitaro_campaign_id="1234"))
        with self.assertRaises(jsonschema.ValidationError):
            validator.validate(self.workspace(keitaro_campaign_id="abc"))
        with self.assertRaises(jsonschema.ValidationError):
            validator.validate(self.workspace(unexpected="x"))


class CliTests(Harness):
    def parse(self, *argv):
        return metaops.parser().parse_args(list(argv))

    def test_registered_and_workspace_bound(self):
        self.assertIn("cmd_keitaro", metaops.COMMAND_MODULES)
        self.assertIn("keitaro", metaops.WORKSPACE_LIFECYCLE_COMMANDS)
        args = self.parse("keitaro", "push")
        self.assertEqual((args.days, args.confirm, args.keitaro_mode), (None, None, "push"))
        args = self.parse("keitaro", "report", "--by", "adset", "--days", "7", "--keitaro-campaign", "9")
        self.assertEqual((args.by, args.days, args.keitaro_campaign, args.keitaro_mode), ("adset", 7, "9", "report"))

    def test_profile_works_before_and_after_the_subcommand(self):
        self.assertEqual(self.parse("--profile", "ny957", "keitaro", "push").profile, "ny957")
        self.assertEqual(self.parse("keitaro", "push", "--profile", "eu312").profile, "eu312")
        self.assertEqual(self.parse("keitaro", "report", "--profile", "eu312").profile, "eu312")
        self.assertEqual(self.parse("--profile", "ny957", "keitaro", "report", "--by", "day").profile, "ny957")
        self.assertIsNone(self.parse("keitaro", "push").profile)

    def test_invalid_by_is_a_usage_error(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.parse("keitaro", "report", "--by", "week")

    def run_main(self, argv, kt=None, get=None, env=None):
        out, err = io.StringIO(), io.StringIO()
        kt = kt or FakeKeitaro()
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(sys, "argv", ["metaops", *argv]))
            stack.enter_context(mock.patch.object(metaops, "configure_workspace", return_value=self.ws))
            stack.enter_context(mock.patch.object(metaops.graph, "get", side_effect=get or fb_get_factory()))
            if env is None:
                stack.enter_context(mock.patch.object(cmd_keitaro, "_make_client", return_value=kt))
            else:
                stack.enter_context(mock.patch.dict(os.environ, env))
                for name in ("KEITARO_URL", "KEITARO_API_KEY"):
                    if name not in env:
                        os.environ.pop(name, None)
            stack.enter_context(mock.patch.object(cmd_keitaro, "_sleep"))
            stack.enter_context(mock.patch.object(cmd_keitaro, "_utcnow", return_value=NOW))
            stack.enter_context(contextlib.redirect_stdout(out))
            stack.enter_context(contextlib.redirect_stderr(err))
            try:
                code = metaops.main()
            except SystemExit as exc:      # argparse usage errors exit from inside parse_args
                code = exc.code
        return code, out.getvalue(), err.getvalue()

    def test_json_mode_is_one_envelope_line_on_stdout(self):
        code, out, err = self.run_main(["--json", "keitaro", "push", "--days", "2"])
        self.assertEqual(code, 0)
        self.assertEqual(len(out.splitlines()), 1)
        payload = json.loads(out)
        self.assertEqual((payload["schema"], payload["command"], payload["phase"], payload["ok"]),
                         ("metaops.result/v1", "keitaro", "dry_run", True))
        self.assertEqual(payload["data"]["since"], "2026-09-28")
        self.assertIn("update_costs entries", err)                  # the tables stay on stderr

    def test_json_mode_report(self):
        code, out, _ = self.run_main(["--json", "keitaro", "report", "--by", "day"],
                                     kt=FakeKeitaro(report_rows=[kt_row("111", clicks=3, day="2026-09-28")]))
        payload = json.loads(out)
        self.assertEqual((code, payload["phase"], payload["data"]["by"]), (0, "reported", "day"))

    def test_human_mode_prints_the_summary_line_on_stdout(self):
        code, out, err = self.run_main(["keitaro", "push"])
        self.assertEqual(code, 0)
        self.assertIn("OK: keitaro", out)
        self.assertIn("dry_run", out)
        self.assertIn("payload:", out)
        self.assertIn("EN111", err)

    def test_profile_flag_after_the_subcommand_reaches_the_handler(self):
        seen = []
        original = FakeWorkspace.profile

        def profile(self_, requested=None):
            seen.append(requested)
            return original(self_, requested)

        with mock.patch.object(FakeWorkspace, "profile", profile):
            self.run_main(["--json", "keitaro", "push", "--profile", "eu312"])
        self.assertIn("eu312", seen)

    def test_missing_credentials_give_a_json_envelope_naming_the_variable(self):
        code, out, err = self.run_main(["--json", "keitaro", "push"], env={})
        self.assertEqual(code, 2)
        payload = json.loads(out)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["kind"], "keitaro")
        self.assertIn("KEITARO_URL", payload["error"]["message"])
        self.assertIn("KEITARO_API_KEY", payload["error"]["message"])
        self.assertNotIn("Traceback", err)
        code, out, _ = self.run_main(["--json", "keitaro", "report"], env={"KEITARO_URL": "https://k.example"})
        payload = json.loads(out)
        self.assertIn("KEITARO_API_KEY", payload["error"]["message"])

    def test_usage_and_precondition_errors_are_envelopes_too(self):
        code, out, _ = self.run_main(["--json", "keitaro", "push", "--days", "x"])
        payload = json.loads(out)
        self.assertEqual((code, payload["ok"], payload["command"], payload["error"]["kind"]),
                         (2, False, "keitaro", "usage"))
        code, out, _ = self.run_main(["--json", "keitaro", "push", "--confirm", "nope"])
        payload = json.loads(out)
        self.assertEqual((code, payload["error"]["kind"]), (2, "precondition"))
        self.assertIn("--confirm PUSH", payload["error"]["message"])

    def test_graph_error_becomes_the_standard_graph_envelope(self):
        def get(path, params=None, context=""):
            if path == "act_1":
                raise metaops.graph.GraphError(400, {"error": {"code": 190, "message": "expired"}}, "keitaro account")
            raise AssertionError(path)

        code, out, _ = self.run_main(["--json", "keitaro", "push"], get=get)
        payload = json.loads(out)
        self.assertEqual((code, payload["error"]["kind"]), (1, "graph"))
        self.assertEqual(payload["error"]["graph"]["code"], 190)

    def test_live_run_end_to_end_never_leaks_the_key(self):
        kt = FakeKeitaro()
        code, out, err = self.run_main(["--json", "keitaro", "push", "--confirm", "PUSH", "--readback-wait", "0"], kt=kt)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["phase"], "pushed")
        self.assertEqual(len(kt.update_posts()), 3)
        self.assertNotIn(API_KEY, out + err)


if __name__ == "__main__":
    unittest.main()

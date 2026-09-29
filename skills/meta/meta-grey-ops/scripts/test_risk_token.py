#!/usr/bin/env python3
"""Offline tests: `doctor --risk`, token classes (tokens.py), capability routing (graph.py),
the multi-token doctor table and `metaops token import` (cmd_token.py).

No network, no real credentials: every token is `EAAx` + random hex, every Graph answer is mocked.
"""

from __future__ import annotations
import os as _os, tempfile as _tempfile
_PACE = _tempfile.mkdtemp(prefix="metaops-pace-test-")
_os.environ["METAOPS_PACE_DIR"] = _PACE
_os.environ.setdefault("METAOPS_CREATE_GAP_HOURS", "0")

import contextlib
import datetime as dt
import io
import json
import os
import pathlib
import secrets
import stat
import sys
import tempfile
import types
import unittest
from unittest import mock

import asset_graph
import cmd_token
import graph
import jsonschema
import meta_workspace
import metaops
import probe
import tokens

HERE = pathlib.Path(__file__).resolve().parent
SCHEMA_DIR = HERE.parent / "schemas"
NOW = dt.datetime(2026, 9, 29, 12, 0, tzinfo=dt.timezone.utc)
APP = {cls.key: cls.app_id for cls in tokens.FIRST_PARTY.values()}


def fake_token(prefix: str = "EAAB") -> str:
    return prefix + secrets.token_hex(40)


def env(**extra: str):
    """A clean process environment: pacing sandbox, nothing from the developer's shell."""
    base = {"METAOPS_PACE_DIR": _PACE, "PATH": os.environ.get("PATH", ""), "HOME": _PACE}
    base.update(extra)
    return mock.patch.dict(os.environ, base, clear=True)


def gerr(code: int, subcode: int | None = None, message: str = "boom", status: int = 400):
    return graph.GraphError(status, {"error": {"code": code, "error_subcode": subcode,
                                              "message": message, "type": "OAuthException"}}, "test")


def workspace_data(**over) -> dict:
    data = {
        "schema": meta_workspace.WORKSPACE_SCHEMA, "name": "risk-test",
        "api_version": graph.API_VERSION, "blocked_accounts": [],
        "profiles": {"test": {
            "business_id": "10", "app_id": "11", "system_user_id": "12", "ad_account_id": "act_13",
            "page_id": "14", "dataset_id": "15", "catalog_id": "16", "currency": "USD",
            "timezone": "Europe/Warsaw"}},
        "defaults": {"profile": "test", "state_dir": ".metaops"},
    }
    data.update(over)
    return data


def load_workspace(root: pathlib.Path, data: dict | None = None) -> meta_workspace.Workspace:
    (root / "workspace.json").write_text(json.dumps(data or workspace_data()), encoding="utf-8")
    return meta_workspace.load_workspace(str(root))


# ------------------------------------------------------------------------------------ tokens.py

class TokenClassTableTests(unittest.TestCase):
    def test_five_first_party_classes_carry_their_app_ids(self) -> None:
        self.assertEqual(APP, {
            "EAAB": "119211728144504", "EAAI": "624541620938530", "EAAG": "436761779744620",
            "EAAH": "515496645328243", "EAAd": "2094176354154603"})
        for key in ("system_user", "user", "unknown"):
            self.assertFalse(tokens.TOKEN_CLASSES[key].first_party)

    def test_every_capability_has_an_evidence_level_and_a_note(self) -> None:
        for cls in tokens.TOKEN_CLASSES.values():
            for cap, (evidence, note) in cls.capabilities.items():
                self.assertIn(cap, tokens.CAPABILITIES)
                self.assertIn(evidence, (tokens.VERIFIED, tokens.CLAIMED, tokens.UNVERIFIED))
                self.assertTrue(note, f"{cls.key}.{cap} has no note")

    def test_live_probes_of_2026_09_29_are_encoded(self) -> None:
        eaad = tokens.TOKEN_CLASSES["EAAd"]
        self.assertEqual(eaad.ads_write_policy, "refuse")
        self.assertNotIn("ads_write", eaad.capabilities)
        self.assertIn("ads_objects", eaad.known_failures)
        for key in ("EAAB", "EAAI", "EAAG", "EAAH"):   # a real ad-set rename + restore worked with each
            cls = tokens.TOKEN_CLASSES[key]
            self.assertEqual(cls.ads_write_policy, "allow", key)
            self.assertEqual(cls.capabilities["ads_write"][0], tokens.VERIFIED, key)
        # EAAH: an older report (other BM) says #10; the note keeps both, the class depends on the BM
        note = tokens.TOKEN_CLASSES["EAAH"].capabilities["ads_write"][1]
        self.assertIn("depends on the BM", note)
        self.assertIn("#10", note)
        self.assertIn("permissions", tokens.TOKEN_CLASSES["EAAH"].known_failures)

    def test_cookie_need_matches_the_second_round(self) -> None:
        for key in ("EAAB", "EAAI", "EAAG", "EAAH"):   # no cookies -> code 1 (verified for all four)
            cls = tokens.TOKEN_CLASSES[key]
            self.assertTrue(cls.needs_cookies, key)
            self.assertEqual(cls.session[0], "required", key)
            self.assertIn("verified", cls.session[1], key)
        eaad = tokens.TOKEN_CLASSES["EAAd"]
        self.assertFalse(eaad.needs_cookies)
        self.assertEqual(eaad.session[0], "not_needed")
        for cls in tokens.TOKEN_CLASSES.values():   # the User-Agent is required by no class
            self.assertNotIn("User-Agent required", cls.hint)
        self.assertIn("not required", tokens.TOKEN_CLASSES["EAAB"].hint)

    def test_events_write_evidence_per_scraped_class(self) -> None:
        # EAAd: a real test event (test_event_code) returned events_received=1 on 2026-09-29.
        self.assertEqual(tokens.TOKEN_CLASSES["EAAd"].capabilities["events_write"][0], tokens.VERIFIED)
        # EAAB: only the empty-batch probe passed (auth, no event posted).
        self.assertEqual(tokens.TOKEN_CLASSES["EAAB"].capabilities["events_write"][0], tokens.CLAIMED)

    def test_app_id_beats_prefix_and_prefix_alone_is_unconfirmed(self) -> None:
        guess = tokens.classify(fake_token("EAAH"))
        self.assertEqual((guess.cls.key, guess.confirmed, guess.source), ("EAAH", False, "prefix"))
        own_app = tokens.classify(fake_token("EAAH"), "999")  # own app that shares the prefix
        self.assertEqual((own_app.cls.key, own_app.confirmed), ("unknown", True))
        real = tokens.classify(fake_token("EAAB"), APP["EAAG"])
        self.assertEqual(real.cls.key, "EAAG")
        self.assertEqual(tokens.classify("EAAMzzzzzzzz").cls.key, "unknown")

    def test_carries_and_default_variables(self) -> None:
        self.assertTrue(tokens.carries(tokens.TOKEN_CLASSES["EAAB"], "catalog"))
        self.assertFalse(tokens.carries(tokens.TOKEN_CLASSES["EAAG"], "catalog"))
        self.assertFalse(tokens.carries(tokens.TOKEN_CLASSES["EAAd"], "ads_write"))
        self.assertEqual({k: c.default_var for k, c in tokens.FIRST_PARTY.items()}, {
            "EAAB": "META_TOKEN", "EAAG": "META_TOKEN_BUSINESS", "EAAH": "META_TOKEN_CATALOG",
            "EAAd": "META_TOKEN_EVENTS", "EAAI": "META_TOKEN_RULES"})
        self.assertEqual(tokens.cookie_var("META_TOKEN"), "META_COOKIES")
        self.assertEqual(tokens.cookie_var("META_TOKEN_CATALOG"), "META_COOKIES_CATALOG")
        self.assertEqual(tokens.cookie_var("CF1_CAT", "catalog"), "META_COOKIES_CATALOG")

    def test_mask_shows_only_prefix_and_last_four(self) -> None:
        token = fake_token()
        masked = tokens.mask(token)
        self.assertEqual(masked, f"{token[:4]}…{token[-4:]}")
        self.assertNotIn(token[4:-4], masked)


# ------------------------------------------------------------------------------ graph.py routing

class FakeResponse:
    ok = True
    status_code = 200
    headers: dict = {}

    def __init__(self, payload: dict | None = None):
        self._payload = payload or {"id": "1"}

    def json(self) -> dict:
        return self._payload


class RecordingSession:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def request(self, method, url, params=None, data=None, files=None, headers=None, timeout=None):
        self.calls.append({"method": method, "url": url, "headers": dict(headers or {})})
        return FakeResponse()


class RoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        graph._DEFAULT_CAPABILITY[0] = None
        graph._WARNED_WRITE_CLASSES.clear()
        self.addCleanup(lambda: graph._DEFAULT_CAPABILITY.__setitem__(0, None))

    def test_unrouted_call_is_exactly_meta_token(self) -> None:
        token = fake_token()
        with env(META_TOKEN=token):
            choice = graph.resolve_token()
            self.assertEqual((choice.token, choice.var, choice.cookies), (token, "META_TOKEN", None))
            self.assertEqual(graph.token_for("ads_write"), token)

    def test_own_variable_wins_and_missing_one_falls_back_when_the_class_carries_it(self) -> None:
        eaab, eaah = fake_token("EAAB"), fake_token("EAAH")
        with env(META_TOKEN=eaab, META_TOKEN_CATALOG=eaah):
            self.assertEqual(graph.resolve_token("catalog").token, eaah)
            self.assertEqual(graph.resolve_token("catalog").var, "META_TOKEN_CATALOG")
        with env(META_TOKEN=eaab):  # EAAB carries catalog (content) and rules (unverified)
            self.assertEqual(graph.resolve_token("catalog").var, "META_TOKEN")
            self.assertEqual(graph.resolve_token("rules").var, "META_TOKEN")

    def test_fallback_refuses_a_class_that_does_not_carry_the_capability(self) -> None:
        with env(META_TOKEN=fake_token("EAAG")):
            with self.assertRaises(SystemExit) as caught:
                graph.resolve_token("catalog")
        message = str(caught.exception.code)
        self.assertIn("META_TOKEN_CATALOG", message)
        self.assertIn("EAAH", message)      # the class that fits
        self.assertIn("EAAG", message)      # the class it found
        self.assertNotIn("EAAG" + "0", message)
        with env():
            with self.assertRaises(SystemExit) as caught:
                graph.resolve_token("events_write")
        self.assertIn("META_TOKEN_EVENTS", str(caught.exception.code))
        self.assertIn("EAAd", str(caught.exception.code))

    def test_recorded_app_id_decides_the_class_of_the_fallback_token(self) -> None:
        with env(META_TOKEN=fake_token("EAAG"), META_TOKEN_APP_ID="777"):  # confirmed own app
            self.assertEqual(graph.resolve_token("catalog").var, "META_TOKEN")

    def test_using_capability_scopes_the_default_and_restores_it(self) -> None:
        eaai = fake_token("EAAI")
        with env(META_TOKEN=fake_token("EAAB"), META_TOKEN_RULES=eaai):
            with graph.using_capability("rules"):
                self.assertEqual(graph.resolve_token().token, eaai)
            self.assertEqual(graph.resolve_token().var, "META_TOKEN")
        with self.assertRaises(ValueError):
            graph.set_default_capability("nonsense")

    def test_per_token_cookies_ride_the_request_and_fall_back_to_the_shared_ones(self) -> None:
        session = RecordingSession()
        with env(META_TOKEN=fake_token("EAAB"), META_TOKEN_RULES=fake_token("EAAI"),
                 META_COOKIES="c_user=1; xs=shared", META_COOKIES_RULES="c_user=1; xs=rules"), \
                mock.patch.object(graph, "session", return_value=session):
            graph.get("act_1", capability="rules")
            graph.get("act_1")
        self.assertEqual(session.calls[0]["headers"]["Cookie"], "c_user=1; xs=rules")
        self.assertNotIn("Cookie", session.calls[1]["headers"])  # the session-level header carries it
        with env(META_TOKEN=fake_token("EAAB"), META_TOKEN_RULES=fake_token("EAAI"),
                 META_COOKIES="c_user=1; xs=shared"), \
                mock.patch.object(graph, "session", return_value=session):
            graph.get("act_1", capability="rules")
        self.assertNotIn("Cookie", session.calls[2]["headers"])

    def test_redact_masks_every_token_and_cookie_variable(self) -> None:
        catalog, business = fake_token("EAAH"), fake_token("EAAG")
        with env(META_TOKEN=fake_token("EAAB"), META_TOKEN_CATALOG=catalog, META_TOKEN_BUSINESS=business,
                 META_COOKIES_RULES="c_user=99; xs=sekrit-value"):
            out = graph.redact(f"failed {catalog} and {business} with xs=sekrit-value")
        self.assertNotIn(catalog, out)
        self.assertNotIn(business, out)
        self.assertNotIn("sekrit-value", out)
        self.assertEqual(out.count("<TOKEN>"), 2)

    def test_workspace_token_envs_name_the_variable(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            data = workspace_data()
            data["defaults"]["token_envs"] = {"catalog": "CF1_CATALOG_TOKEN"}
            load_workspace(root, data)
            catalog = fake_token("EAAH")
            with env(META_TOKEN=fake_token("EAAB"), CF1_CATALOG_TOKEN=catalog, META_TOKEN_CATALOG="ignored",
                     METAOPS_WORKSPACE=str(root / "workspace.json")):
                self.assertEqual(graph.resolve_token("catalog").token, catalog)
                self.assertIn(catalog, [os.environ["CF1_CATALOG_TOKEN"]])
                self.assertNotIn(catalog, graph.redact(f"x {catalog} y"))

    def test_ads_write_guard_refuses_eaad_warns_others_and_can_be_overridden(self) -> None:
        session = RecordingSession()
        eaad = fake_token("EAAd")
        with env(META_TOKEN=eaad), mock.patch.object(graph, "session", return_value=session):
            graph.authorize_writes(["act_1"])
            try:
                with self.assertRaises(SystemExit) as caught:
                    graph.post("act_1/campaigns", {"name": "x"})
                text = str(caught.exception.code)
                self.assertIn("ads write refused", text)
                self.assertIn("EAAB", text)
                self.assertIn("METAOPS_ALLOW_TOKEN_CLASS=EAAd", text)
                self.assertEqual(session.calls, [], "nothing may be sent")
                with mock.patch.dict(os.environ, {"METAOPS_ALLOW_TOKEN_CLASS": "EAAd"}):
                    graph.post("act_1/campaigns", {"name": "x"})
                self.assertEqual(len(session.calls), 1)
                with mock.patch.dict(os.environ, {"META_TOKEN_APP_ID": "999"}):  # own app, same prefix
                    graph.post("act_1/campaigns", {"name": "y"})
                self.assertEqual(len(session.calls), 2)
            finally:
                graph._WRITE_ACCOUNTS = None
                graph._WRITE_CAPABILITY_LOADED = False

    def test_ads_write_with_the_other_scraped_ads_classes_goes_through_silently(self) -> None:
        session = RecordingSession()
        for prefix in ("EAAB", "EAAI", "EAAG", "EAAH"):
            err = io.StringIO()
            before = len(session.calls)
            with env(META_TOKEN=fake_token(prefix)), mock.patch.object(graph, "session", return_value=session), \
                    contextlib.redirect_stderr(err):
                graph.authorize_writes(["act_1"])
                try:
                    graph.post("act_1/adsets", {"name": "a"})
                finally:
                    graph._WRITE_ACCOUNTS = None
                    graph._WRITE_CAPABILITY_LOADED = False
            self.assertEqual(len(session.calls), before + 1, prefix)
            self.assertEqual(err.getvalue(), "", prefix)   # no warning for a class that is proven to write

    def test_a_class_with_the_warn_policy_still_warns_once(self) -> None:
        import dataclasses
        session = RecordingSession()
        warned = dataclasses.replace(tokens.FIRST_PARTY["EAAI"], ads_write_policy="warn")
        err = io.StringIO()
        with env(META_TOKEN=fake_token("EAAI")), mock.patch.object(graph, "session", return_value=session), \
                mock.patch.dict(tokens.FIRST_PARTY, {"EAAI": warned}), contextlib.redirect_stderr(err):
            graph.authorize_writes(["act_1"])
            try:
                graph.post("act_1/adsets", {"name": "a"})
                graph.post("act_1/adsets", {"name": "b"})
            finally:
                graph._WRITE_ACCOUNTS = None
                graph._WRITE_CAPABILITY_LOADED = False
        self.assertEqual(len(session.calls), 2)
        self.assertEqual(err.getvalue().count("ads write with a"), 1)

    def test_writes_on_other_capabilities_are_not_ads_writes(self) -> None:
        session = RecordingSession()
        with env(META_TOKEN=fake_token("EAAB"), META_TOKEN_CATALOG=fake_token("EAAH")), \
                mock.patch.object(graph, "session", return_value=session):
            graph.authorize_writes(["act_1"])
            try:
                graph.post("100/product_sets", {"name": "s"}, capability="catalog")
            finally:
                graph._WRITE_ACCOUNTS = None
                graph._WRITE_CAPABILITY_LOADED = False
        self.assertEqual(len(session.calls), 1)


# ----------------------------------------------------------------------------- resolve_token_kind

class ResolveTokenKindTests(unittest.TestCase):
    def test_scraped_prefix_is_recognised_with_one_app_call_and_no_debug_token(self) -> None:
        for prefix in ("EAAB", "EAAI", "EAAG", "EAAH", "EAAd"):
            calls: list[str] = []

            def fake_get(path, params=None, context="", **kw):
                calls.append(path)
                return {"id": APP[prefix]}

            with env(META_TOKEN=fake_token(prefix)), mock.patch.object(asset_graph.graph, "get", side_effect=fake_get):
                self.assertEqual(asset_graph.resolve_token_kind("10", {}), "user", prefix)
            self.assertEqual(calls, ["app"], prefix)

    def test_prefix_collision_with_an_own_app_falls_through_to_debug_token(self) -> None:
        calls: list[str] = []

        def fake_get(path, params=None, context="", **kw):
            calls.append(path)
            if path == "app":
                return {"id": "999"}  # own app that happens to share the EAAB prefix
            return {"data": {"type": "SYSTEM_USER"}}

        with env(META_TOKEN=fake_token("EAAB")), mock.patch.object(asset_graph.graph, "get", side_effect=fake_get):
            self.assertEqual(asset_graph.resolve_token_kind("10", {}), "system_user")
        self.assertEqual(calls, ["app", "debug_token"])

    def test_declared_kind_and_unknown_prefix_behave_as_before(self) -> None:
        with env(META_TOKEN=fake_token("EAAB")), mock.patch.object(asset_graph.graph, "get", side_effect=AssertionError("no call")):
            self.assertEqual(asset_graph.resolve_token_kind("10", {"token_kind": "system_user"}), "system_user")


# ------------------------------------------------------------------------------- workspace risk

class WorkspaceRiskTests(unittest.TestCase):
    def test_workspace_without_risk_block_is_unchanged(self) -> None:
        meta_workspace.validate_workspace(workspace_data())
        with tempfile.TemporaryDirectory() as td:
            workspace = load_workspace(pathlib.Path(td))
            self.assertEqual(workspace.risk_config(), meta_workspace.RISK_DEFAULTS)

    def test_defaults_are_the_documented_priors(self) -> None:
        d = meta_workspace.RISK_DEFAULTS
        self.assertEqual((d["min_account_age_days"], d["min_amount_spent"], d["min_pixel_age_days"],
                          d["min_page_followers"], d["max_disapproved_ratio"]), (14, 50, 3, 100, 0.20))

    def test_workspace_then_profile_override_the_defaults(self) -> None:
        data = workspace_data(risk={"min_account_age_days": 30, "min_page_followers": 500})
        data["profiles"]["test"]["risk"] = {"min_page_followers": 50}
        with tempfile.TemporaryDirectory() as td:
            cfg = load_workspace(pathlib.Path(td), data).risk_config()
        self.assertEqual(cfg["min_account_age_days"], 30)
        self.assertEqual(cfg["min_page_followers"], 50)
        self.assertEqual(cfg["min_amount_spent"], 50)

    def test_bad_risk_blocks_are_refused(self) -> None:
        for block, pattern in (
            ({"min_account_age_dayz": 3}, "unsupported keys"),
            ({"min_account_age_days": -1}, "must not be negative"),
            ({"min_account_age_days": True}, "must be a number"),
            ({"max_disapproved_ratio": 20}, "ratio between 0 and 1"),
            ({"ads_max_pages": 0}, "at least 1"),
            ("nope", "must be an object"),
        ):
            with self.assertRaisesRegex(meta_workspace.WorkspaceError, pattern, msg=str(block)):
                meta_workspace.validate_workspace(workspace_data(risk=block))
        data = workspace_data()
        data["profiles"]["test"]["risk"] = {"bogus": 1}
        with self.assertRaisesRegex(meta_workspace.WorkspaceError, "profiles.test.risk"):
            meta_workspace.validate_workspace(data)

    def test_schema_accepts_risk_and_token_envs_and_still_rejects_drift(self) -> None:
        schema = json.loads((SCHEMA_DIR / "workspace.v1.json").read_text(encoding="utf-8"))
        data = workspace_data(risk={"min_account_age_days": 7})
        data["profiles"]["test"]["risk"] = {"max_disapproved_ratio": 0.3}
        data["defaults"]["token_envs"] = {"catalog": "CF1_CAT_TOKEN", "rules": "CF1_RULES_TOKEN"}
        jsonschema.Draft202012Validator(schema).validate(data)
        meta_workspace.validate_workspace(data)
        bad = workspace_data(risk={"nonsense": 1})
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.Draft202012Validator(schema).validate(bad)

    def test_token_envs_are_validated_like_token_env(self) -> None:
        for value, pattern in (({"catalog": "lower"}, "uppercase"), ({"ads_write": "X"}, "unsupported"),
                               (["x"], "must be an object")):
            data = workspace_data()
            data["defaults"]["token_envs"] = value
            with self.assertRaisesRegex(meta_workspace.WorkspaceError, pattern):
                meta_workspace.validate_workspace(data)


# ------------------------------------------------------------------------------------ risk core

def account_raw(**over) -> dict:
    row = {"id": "act_13", "created_time": "2026-09-01T10:00:00+0000", "amount_spent": "12000",
           "balance": "0", "spend_cap": "0", "account_status": 1, "disable_reason": 0,
           "funding_source_details": {"type": 1, "display_string": "Visa *4242"}, "currency": "USD",
           "timezone_name": "America/Los_Angeles", "business": {"id": "10", "name": "BM"},
           "is_prepay_account": False}
    row.update(over)
    return row


def snapshot(account=None, extra=None, pixels=None, page="default", ads="default") -> dict:
    return {
        "account_raw": account_raw() if account is None else (None if account is False else account),
        "account_extra": {"age": "28.5", "min_daily_budget": "100"} if extra is None else extra,
        "pixels": [{"id": "15", "raw": {"id": "15", "name": "px", "creation_time": "2026-09-01T00:00:00+0000",
                                        "last_fired_time": "2026-09-28T00:00:00+0000"}}] if pixels is None else pixels,
        "page": ({"id": "14", "name": "Pg", "fan_count": 900, "followers_count": 1000,
                  "verification_status": "not_verified", "is_published": True} if page == "default" else page),
        "ads": ({"window_days": 30, "total": 20, "older_than_window": 3, "by_status": {"ACTIVE": 18, "DISAPPROVED": 1, "WITH_ISSUES": 1},
                 "pages_read": 1, "truncated": False} if ads == "default" else ads),
        "errors": {},
    }


def findings_for(snap: dict, cfg: dict | None = None, errors: dict | None = None) -> dict[str, dict]:
    config = meta_workspace.merge_risk(cfg)
    summary = probe.summarize_risk(snap, NOW)
    return {f["code"]: f for f in probe.evaluate_risk(summary, errors if errors is not None else snap["errors"], config)}


class RiskEvaluationTests(unittest.TestCase):
    def test_a_healthy_account_only_gets_the_ui_only_billing_note(self) -> None:
        found = findings_for(snapshot())
        self.assertEqual(set(found), {"billing_threshold_ui_only", "ads_with_issues"})
        self.assertEqual(found["billing_threshold_ui_only"]["level"], "info")
        self.assertIn("UI", found["billing_threshold_ui_only"]["message"])

    def test_every_finding_has_the_documented_shape(self) -> None:
        snap = snapshot(account_raw(created_time="2026-09-27T00:00:00+0000", amount_spent="500", account_status=2,
                                    disable_reason=1))
        for finding in probe.evaluate_risk(probe.summarize_risk(snap, NOW), {}, meta_workspace.merge_risk()):
            self.assertEqual(set(finding), {"level", "code", "message"})
            self.assertIn(finding["level"], ("info", "warn", "high"))

    def test_young_account_and_low_spend_warn_with_the_configured_thresholds(self) -> None:
        snap = snapshot(account_raw(created_time="2026-09-20T12:00:00+0000", amount_spent="4999"))
        found = findings_for(snap)
        self.assertEqual(found["account_young"]["level"], "warn")
        self.assertIn("9 days old", found["account_young"]["message"])
        self.assertEqual(found["spend_low"]["level"], "warn")
        self.assertIn("49.99", found["spend_low"]["message"])
        relaxed = findings_for(snap, {"min_account_age_days": 5, "min_amount_spent": 10})
        self.assertNotIn("account_young", relaxed)
        self.assertNotIn("spend_low", relaxed)

    def test_account_status_not_active_is_high_with_the_disable_reason_name(self) -> None:
        found = findings_for(snapshot(account_raw(account_status=2, disable_reason=1)))
        self.assertEqual(found["account_status_not_active"]["level"], "high")
        self.assertIn("DISABLED", found["account_status_not_active"]["message"])
        self.assertIn("ADS_INTEGRITY_POLICY", found["account_status_not_active"]["message"])
        self.assertEqual(findings_for(snapshot(account_raw(disable_reason=3)))["disable_reason_set"]["level"], "warn")

    def test_spend_cap_near_and_reached(self) -> None:
        near = findings_for(snapshot(account_raw(spend_cap="100000", amount_spent="95000")))
        self.assertEqual(near["spend_cap_near"]["level"], "warn")
        reached = findings_for(snapshot(account_raw(spend_cap="100000", amount_spent="100000")))
        self.assertEqual(reached["spend_cap_reached"]["level"], "high")
        none = findings_for(snapshot(account_raw(spend_cap="0", amount_spent="999999")))
        self.assertNotIn("spend_cap_near", none)
        self.assertNotIn("spend_cap_reached", none)
        self.assertIn("spend_cap_near", findings_for(snapshot(account_raw(spend_cap="100000", amount_spent="60000")),
                                                     {"spend_cap_near_ratio": 0.5}))

    def test_no_funding_source_is_high(self) -> None:
        self.assertEqual(findings_for(snapshot(account_raw(funding_source_details=None)))["no_funding_source"]["level"], "high")

    def test_amounts_use_the_currency_offset(self) -> None:
        summary = probe.summarize_risk(snapshot(account_raw(currency="JPY", amount_spent="5000")), NOW)
        self.assertEqual(summary["account"]["amount_spent"]["major"], 5000.0)
        summary = probe.summarize_risk(snapshot(account_raw(currency="EUR", amount_spent="5000")), NOW)
        self.assertEqual(summary["account"]["amount_spent"]["major"], 50.0)
        self.assertEqual(summary["account"]["amount_spent"]["minor"], "5000")

    def test_created_time_formats_and_age_fallback(self) -> None:
        for stamp in ("2026-09-19T12:00:00+0000", "2026-09-19T12:00:00+00:00", "2026-09-19T12:00:00Z", 1789819200):
            self.assertEqual(probe._parse_time(stamp).year, 2026, stamp)
        summary = probe.summarize_risk(snapshot(account_raw(created_time=None), extra={"age": "3.5"}), NOW)
        self.assertEqual(summary["account"]["age_days"], 3.5)
        self.assertIn("account_age_unknown", findings_for(snapshot(account_raw(created_time=None), extra={})))

    def test_pixel_findings(self) -> None:
        never = {"id": "15", "raw": {"id": "15", "name": "px", "creation_time": "2026-08-01T00:00:00+0000"}}
        found = findings_for(snapshot(pixels=[never]))
        self.assertEqual(found["pixel_never_fired"]["level"], "warn")
        self.assertIn("not readable", found["pixel_never_fired"]["message"])
        young = {"id": "15", "raw": {"id": "15", "creation_time": "2026-09-28T00:00:00+0000",
                                     "last_fired_time": "2026-09-29T00:00:00+0000", "is_unavailable": True}}
        found = findings_for(snapshot(pixels=[young]))
        self.assertEqual(found["pixel_young"]["level"], "warn")
        self.assertEqual(found["pixel_unavailable"]["level"], "high")
        found = findings_for(snapshot(pixels=[{"id": "15", "raw": None}]), errors={"pixel:15": "code 100"})
        self.assertEqual(found["pixel_read_failed"]["level"], "warn")
        self.assertIn("pixel_not_configured", findings_for(snapshot(pixels=[]), errors={}) if False else
                      {f["code"] for f in probe.evaluate_risk(
                          {"account": None, "pixels": [], "page": None, "ads": None}, {}, meta_workspace.merge_risk())})

    def test_page_findings_and_fan_count_fallback(self) -> None:
        low = {"id": "14", "fan_count": 40, "followers_count": 60, "is_published": False}
        found = findings_for(snapshot(page=low))
        self.assertEqual(found["page_followers_low"]["level"], "warn")
        self.assertIn("followers_count", found["page_followers_low"]["message"])
        self.assertEqual(found["page_unpublished"]["level"], "high")
        found = findings_for(snapshot(page={"id": "14", "fan_count": 40, "is_published": True}))
        self.assertIn("fan_count", found["page_followers_low"]["message"])
        self.assertIn("page_followers_unknown", findings_for(snapshot(page={"id": "14", "is_published": True})))

    def test_disapproved_ratio_thresholds(self) -> None:
        def ads(total, disapproved):
            return {"window_days": 30, "total": total, "older_than_window": 0,
                    "by_status": {"ACTIVE": total - disapproved, "DISAPPROVED": disapproved},
                    "pages_read": 1, "truncated": False}
        self.assertNotIn("ads_disapproved_ratio", findings_for(snapshot(ads=ads(20, 3))))     # 15%
        self.assertEqual(findings_for(snapshot(ads=ads(20, 4)))["ads_disapproved_ratio"]["level"], "warn")   # 20%
        self.assertEqual(findings_for(snapshot(ads=ads(20, 10)))["ads_disapproved_ratio"]["level"], "high")  # 50%
        small = findings_for(snapshot(ads=ads(4, 2)))
        self.assertNotIn("ads_disapproved_ratio", small)
        self.assertEqual(small["ads_disapproved_small_sample"]["level"], "info")
        self.assertIn("ads_disapproved_ratio", findings_for(snapshot(ads=ads(20, 3)), {"max_disapproved_ratio": 0.1}))
        self.assertIn("ads_sample_truncated", findings_for(snapshot(ads={**ads(20, 0), "truncated": True})))
        self.assertIn("ads_none_in_window", findings_for(snapshot(ads=ads(0, 0))))

    def test_failed_reads_become_warnings_not_crashes(self) -> None:
        found = findings_for(snapshot(account=False, page=None, ads=None),
                             errors={"account": "code 190", "page": "code 10", "ads": "code 17"})
        for code in ("account_read_failed", "page_read_failed", "ads_read_failed"):
            self.assertEqual(found[code]["level"], "warn", code)


class RiskGateTests(unittest.TestCase):
    def fake_graph(self, log: list, fail: set | None = None, page_fails_on_followers: bool = False):
        fail = fail or set()

        def fake_get(path, params=None, context="", **kw):
            fields = (params or {}).get("fields", "")
            log.append((path, fields))
            key = path if not path.endswith("/ads") else "ads"
            if key in fail or (path == "act_13" and fields == probe.RISK_ACCOUNT_UNVERIFIED_FIELDS and "unverified" in fail):
                raise gerr(100, message="Tried accessing nonexisting field")
            if path == "act_13" and fields == probe.RISK_ACCOUNT_FIELDS:
                return account_raw()
            if path == "act_13":
                return {"age": "28.0", "min_daily_budget": "100", "id": "act_13"}
            if path == "15":
                return {"id": "15", "name": "px", "creation_time": "2026-09-01T00:00:00+0000",
                        "last_fired_time": "2026-09-28T00:00:00+0000"}
            if path == "14":
                if page_fails_on_followers and "followers_count" in fields:
                    raise gerr(100, message="(#100) Tried accessing nonexisting field (followers_count)")
                return {"id": "14", "name": "Pg", "fan_count": 900, "followers_count": 1000,
                        "verification_status": "not_verified", "is_published": True}
            if key == "ads":
                return {"data": [{"effective_status": "ACTIVE", "created_time": "2026-09-20T00:00:00+0000"},
                                 {"effective_status": "DISAPPROVED", "created_time": "2026-09-21T00:00:00+0000"},
                                 {"effective_status": "DISAPPROVED", "created_time": "2026-05-01T00:00:00+0000"}]}
            raise AssertionError(f"unexpected read {path}")
        return fake_get

    def run_gate(self, fake_get, out_path=None, cfg=None, **kw):
        report = probe.Report()
        with mock.patch.object(probe.graph, "get", side_effect=fake_get), \
                contextlib.redirect_stdout(io.StringIO()):
            result = probe.gate_risk(report, "act_13", "14", ["15"], cfg, out_path, now=NOW)
        return report, result

    def test_reads_are_the_documented_ones_and_unverified_fields_go_in_a_separate_get(self) -> None:
        log: list = []
        report, result = self.run_gate(self.fake_graph(log))
        self.assertEqual([p for p, _ in log], ["act_13", "act_13", "15", "14", "act_13/ads"])
        self.assertEqual(log[0][1], probe.RISK_ACCOUNT_FIELDS)
        for name in ("created_time", "amount_spent", "balance", "spend_cap", "account_status", "disable_reason",
                     "funding_source_details{type,display_string}", "currency", "timezone_name",
                     "business{id,name}", "is_prepay_account"):
            self.assertIn(name, log[0][1])
        for name in ("age", "min_daily_budget"):
            self.assertNotIn(name, log[0][1].split(","))
            self.assertIn(name, log[1][1].split(","))
        self.assertEqual(log[2][1], "id,name,creation_time,last_fired_time,is_unavailable")
        self.assertEqual(log[3][1], "id,name,fan_count,followers_count,verification_status,is_published")
        self.assertEqual(log[4][1], "effective_status,created_time")
        self.assertFalse(report.failed, "the risk snapshot must never add a FAIL row")
        ads = result["snapshot"]["ads"]
        self.assertEqual((ads["total"], ads["older_than_window"]), (2, 1))   # the May ad is outside 30 days
        self.assertEqual(ads["by_status"], {"ACTIVE": 1, "DISAPPROVED": 1})

    def test_unverified_get_failing_does_not_fail_anything(self) -> None:
        log: list = []
        report, result = self.run_gate(self.fake_graph(log, fail={"unverified"}))
        self.assertFalse(report.failed)
        self.assertIn("account_unverified", result["errors"])
        self.assertIn("unverified_fields_unavailable", {f["code"] for f in result["risk_findings"]})
        self.assertIsNotNone(result["snapshot"]["account"])

    def test_page_retries_without_followers_count_on_code_100(self) -> None:
        log: list = []
        report, result = self.run_gate(self.fake_graph(log, page_fails_on_followers=True))
        page_reads = [fields for path, fields in log if path == "14"]
        self.assertEqual(len(page_reads), 2)
        self.assertNotIn("followers_count", page_reads[1])
        self.assertEqual(result["snapshot"]["page"]["fan_count"], 900)
        self.assertIn("page_followers_count", result["errors"])

    def test_a_throttle_stops_the_remaining_reads(self) -> None:
        log: list = []
        base = self.fake_graph(log)

        def throttled(path, params=None, context="", **kw):
            if path == "15":
                raise gerr(17, message="rate limit")
            return base(path, params, context)

        report, result = self.run_gate(throttled)
        self.assertNotIn("14", [p for p, _ in log])
        self.assertNotIn("act_13/ads", [p for p, _ in log])
        self.assertIn("skipped", result["errors"]["page"])
        self.assertFalse(report.failed)

    def test_ads_are_paged_but_capped(self) -> None:
        page = {"data": [{"effective_status": "ACTIVE", "created_time": "2026-09-25T00:00:00+0000"}] * 3,
                "paging": {"cursors": {"after": "c"}, "next": "https://x"}}
        calls = {"n": 0}
        base = self.fake_graph([])

        def fake_get(path, params=None, context="", **kw):
            if path == "act_13/ads":
                calls["n"] += 1
                return page
            return base(path, params, context)

        report, result = self.run_gate(fake_get, cfg={"ads_max_pages": 2})
        self.assertEqual(calls["n"], 2)
        self.assertTrue(result["snapshot"]["ads"]["truncated"])
        self.assertIn("ads_sample_truncated", {f["code"] for f in result["risk_findings"]})

    def test_out_file_is_private_and_carries_the_note_and_the_unverified_list(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out = pathlib.Path(td) / "risk.json"
            report, result = self.run_gate(self.fake_graph([]), str(out), cfg={"min_page_followers": 2000})
            self.assertEqual(stat.S_IMODE(out.stat().st_mode), 0o600)
            saved = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(saved["schema"], "metaops.risk/v1")
        self.assertIn("own priors", saved["note"])
        self.assertIn("No Meta source", saved["note"])
        self.assertIn("UI", saved["note"])
        self.assertEqual(saved["unverified_fields"]["AdAccount"]["separate_get"], ["age", "min_daily_budget"])
        self.assertEqual(saved["thresholds"]["min_page_followers"], 2000)
        self.assertIn("page_followers_low", {f["code"] for f in saved["risk_findings"]})
        self.assertTrue(any(row["gate"] == "risk note" for row in report.rows))


class ProbeMainRiskTests(unittest.TestCase):
    def run_main(self, argv: list[str]) -> tuple[int | None, str]:
        err = io.StringIO()
        with mock.patch.object(sys, "argv", ["probe.py", *argv]), contextlib.redirect_stderr(err), \
                contextlib.redirect_stdout(io.StringIO()):
            try:
                return probe.main(), err.getvalue()
            except SystemExit as exc:
                return exc.code, err.getvalue()

    def test_risk_needs_an_account_and_a_valid_config(self) -> None:
        code, err = self.run_main(["--whoami", "--risk"])
        self.assertEqual(code, 2)
        self.assertIn("--risk reads one ad account", err)
        code, err = self.run_main(["--account", "act_1", "--risk", "--risk-config", '{"nope": 1}'])
        self.assertEqual(code, 2)
        self.assertIn("--risk-config", err)

    def test_main_runs_the_risk_gate_last_and_keeps_the_exit_code(self) -> None:
        order: list[str] = []
        names = ("gate_identity", "gate_token_class", "gate_token_debug", "gate_token_table", "gate_scopes",
                 "gate_visible_accounts", "gate_account", "gate_pixel_attached", "gate_dataset",
                 "gate_page_and_pbia", "gate_write")
        patches = [mock.patch.object(probe, n, side_effect=lambda *a, _n=n, **k: order.append(_n)) for n in names]
        patches.append(mock.patch.object(probe, "gate_risk", side_effect=lambda *a, **k: order.append("risk")))
        with contextlib.ExitStack() as stack:
            for patch in patches:
                stack.enter_context(patch)
            code, _ = self.run_main(["--account", "act_1", "--page", "2", "--dataset", "3", "--risk"])
        self.assertEqual(code, 0)
        self.assertEqual(order[-2:], ["gate_write", "risk"])

    def test_without_risk_the_gate_is_never_called(self) -> None:
        with contextlib.ExitStack() as stack:
            for n in ("gate_identity", "gate_token_class", "gate_token_debug", "gate_token_table", "gate_scopes",
                      "gate_visible_accounts", "gate_account", "gate_write"):
                stack.enter_context(mock.patch.object(probe, n))
            risk = stack.enter_context(mock.patch.object(probe, "gate_risk"))
            code, _ = self.run_main(["--account", "act_1"])
        self.assertEqual(code, 0)
        risk.assert_not_called()


# ----------------------------------------------------------------------- doctor handler (metaops)

def doctor_args(workspace, **over):
    base = dict(workspace_obj=workspace, profile="test", account=None, page=None, dataset=None, business=None,
                whoami=False, create_pbia=False, attach_pixel=False, scope="core", timeout=10)
    base.update(over)
    return types.SimpleNamespace(**base)


class DoctorRiskHandlerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.workspace = load_workspace(self.root, workspace_data(risk={"min_account_age_days": 21}))
        plans = mock.patch.object(metaops, "PLAN_DIR", (self.root / ".metaops" / "plans").resolve())
        plans.start()
        self.addCleanup(plans.stop)

    def child(self, argv_log: list, report: dict | None, tokens_report: dict | None = None):
        def run_child(script, argv, timeout):
            argv_log.append(list(argv))
            if "--risk-out" in argv and report is not None:
                pathlib.Path(argv[argv.index("--risk-out") + 1]).write_text(json.dumps(report), encoding="utf-8")
            if tokens_report is not None:
                pathlib.Path(os.environ["METAOPS_TOKENS_OUT"]).write_text(json.dumps(tokens_report), encoding="utf-8")
            return metaops.ChildResult([script, *argv], 0, "", "")
        return run_child

    def test_without_risk_the_child_gets_the_arguments_it_always_got(self) -> None:
        log: list = []
        with mock.patch.object(metaops, "run_child", side_effect=self.child(log, None)):
            code, payload = metaops.command_doctor(doctor_args(self.workspace))
        self.assertEqual(code, 0)
        argv = log[0]
        self.assertEqual(argv, ["--account", "act_13", "--page", "14", "--dataset", "15", "--business", "10",
                                "--catalog", "16"])
        self.assertNotIn("risk_findings", payload["data"])
        self.assertEqual(payload["data"], {})

    def test_whoami_child_args_are_untouched(self) -> None:
        log: list = []
        with mock.patch.object(metaops, "run_child", side_effect=self.child(log, None)):
            metaops.command_doctor(doctor_args(self.workspace, whoami=True))
        self.assertEqual(log[0], ["--whoami"])

    def test_risk_passes_the_merged_thresholds_and_attaches_the_findings(self) -> None:
        report = {"schema": "metaops.risk/v1", "checked_at": "x", "account_id": "act_13", "snapshot": {"account": {}},
                  "risk_findings": [{"level": "warn", "code": "account_young", "message": "m"}],
                  "counts": {"high": 0, "warn": 1, "info": 0}, "errors": {}, "thresholds": {},
                  "unverified_fields": {}, "ui_only": [], "note": "own priors"}
        log: list = []
        with mock.patch.object(metaops, "run_child", side_effect=self.child(log, report)):
            code, payload = metaops.command_doctor(doctor_args(self.workspace, risk=True))
        argv = log[0]
        self.assertIn("--risk", argv)
        cfg = json.loads(argv[argv.index("--risk-config") + 1])
        self.assertEqual(cfg["min_account_age_days"], 21)
        self.assertEqual(cfg["min_amount_spent"], 50)
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["risk_findings"][0]["code"], "account_young")
        self.assertEqual(payload["data"]["risk"]["note"], "own priors")
        self.assertIn("1 warn", payload["next_action"])
        self.assertFalse(list(pathlib.Path(tempfile.gettempdir()).glob(f"metaops-risk.*{os.getpid()}*")))

    def test_missing_risk_report_is_reported_not_raised(self) -> None:
        with mock.patch.object(metaops, "run_child", side_effect=self.child([], None)):
            code, payload = metaops.command_doctor(doctor_args(self.workspace, risk=True))
        self.assertEqual(code, 0)
        self.assertEqual(payload["data"]["risk_findings"], [])
        self.assertFalse(payload["data"]["risk"]["available"])

    def test_risk_does_not_fail_or_change_the_receipt_verdict(self) -> None:
        with mock.patch.object(metaops, "run_child", side_effect=self.child([], None)):
            metaops.command_doctor(doctor_args(self.workspace, risk=True))
        self.assertTrue((metaops.PLAN_DIR / "doctor.act_13.json").exists())

    def test_risk_refuses_whoami_and_needs_a_workspace(self) -> None:
        with self.assertRaisesRegex(metaops.MetaOpsError, "doctor --risk"):
            metaops.command_doctor(doctor_args(self.workspace, whoami=True, risk=True))
        with self.assertRaisesRegex(metaops.MetaOpsError, "doctor --risk"):
            metaops.command_doctor(doctor_args(None, account="act_1", profile=None, risk=True))

    def test_token_table_from_the_child_reaches_the_envelope_only_when_written(self) -> None:
        table = {"tokens": [{"variable": "META_TOKEN", "class": "EAAB"}], "needed": ["ads_read"], "missing": []}
        with mock.patch.object(metaops, "run_child", side_effect=self.child([], None, table)):
            _, payload = metaops.command_doctor(doctor_args(self.workspace))
        self.assertEqual(payload["data"]["tokens"], table)
        self.assertNotIn("METAOPS_TOKENS_OUT", os.environ)

    def test_parser_exposes_the_flag(self) -> None:
        args = metaops.parser().parse_args(["doctor", "--risk"])
        self.assertTrue(args.risk)
        self.assertFalse(metaops.parser().parse_args(["doctor"]).risk)


# --------------------------------------------------------------------- doctor token gates (probe)

class ProbeTokenGateTests(unittest.TestCase):
    def report(self) -> probe.Report:
        return probe.Report()

    def quiet(self):
        return contextlib.redirect_stdout(io.StringIO())

    def row(self, r: probe.Report, gate: str) -> dict:
        return next(x for x in r.rows if x["gate"] == gate)

    def test_class_row_warns_for_missing_cookies_but_never_for_a_missing_user_agent(self) -> None:
        for prefix in ("EAAB", "EAAI", "EAAG", "EAAH"):   # code 1 without cookies, verified for all four
            r = self.report()
            with env(META_TOKEN=fake_token(prefix)), self.quiet():
                probe.gate_token_class(r)
            row = self.row(r, "token class")
            self.assertEqual(row["state"], probe.WARN, prefix)
            self.assertIn("META_COOKIES is not set", row["detail"], prefix)
            self.assertNotIn("USER_AGENT", row["detail"], prefix)
            self.assertIn("token import", row["detail"], prefix)
            r = self.report()   # cookies without a User-Agent: fine, the extension exports none
            with env(META_TOKEN=fake_token(prefix), META_COOKIES="c_user=1; xs=2"), self.quiet():
                probe.gate_token_class(r)
            self.assertEqual(self.row(r, "token class")["state"], probe.PASS, prefix)

    def test_class_row_for_an_eaad_needs_no_cookies_and_says_it_cannot_launch(self) -> None:
        r = self.report()
        with env(META_TOKEN=fake_token("EAAd")), self.quiet():
            probe.gate_token_class(r)
        row = self.row(r, "token class")
        self.assertEqual(row["state"], probe.WARN)
        self.assertNotIn("META_COOKIES", row["detail"])
        self.assertIn("cannot write ads", row["detail"])

    def test_class_row_never_prints_the_token_and_ignores_non_first_party(self) -> None:
        token = fake_token("EAAB")
        r = self.report()
        with env(META_TOKEN=token), self.quiet():
            probe.gate_token_class(r)
        self.assertNotIn(token, json.dumps(r.rows))
        r = self.report()
        with env(META_TOKEN="EAAMzzzzzzzzzzzzzzzzzzzzzzzzzzzz"), self.quiet():
            probe.gate_token_class(r)
        self.assertEqual(self.row(r, "token class")["state"], probe.PASS)
        r = self.report()
        with env(), self.quiet():
            probe.gate_token_class(r)
        self.assertEqual(r.rows, [])

    def test_c_user_must_match_the_me_id(self) -> None:
        r = self.report()
        with env(META_TOKEN=fake_token(), META_COOKIES="c_user=111; xs=2"), self.quiet():
            with mock.patch.object(probe.graph, "get", return_value={"id": "222", "name": "N"}):
                probe.gate_identity(r)
        row = self.row(r, "cookie / token binding")
        self.assertEqual(row["state"], probe.WARN)
        self.assertNotIn("111", row["detail"])
        r = self.report()
        with env(META_TOKEN=fake_token(), META_COOKIES="c_user=222; xs=2"), self.quiet():
            with mock.patch.object(probe.graph, "get", return_value={"id": "222", "name": "N"}):
                probe.gate_identity(r)
        self.assertEqual([x["gate"] for x in r.rows], ["token identity"])

    def test_first_party_token_asks_app_once_and_skips_debug_token(self) -> None:
        calls: list[str] = []

        def fake_get(path, params=None, context="", **kw):
            calls.append(path)
            return {"id": APP["EAAG"], "name": "Business Manager"}

        r = self.report()
        with env(META_TOKEN=fake_token("EAAG")), self.quiet(), mock.patch.object(probe.graph, "get", side_effect=fake_get):
            probe.gate_token_debug(r)
        self.assertEqual(calls, ["app"])
        self.assertTrue(self.row(r, "token app")["data"]["confirmed"])

    def test_prefix_collision_reads_debug_token_after_the_app_call(self) -> None:
        calls: list[str] = []

        def fake_get(path, params=None, context="", **kw):
            calls.append(path)
            if path == "app":
                return {"id": "999", "name": "My app"}
            return {"data": {"type": "SYSTEM_USER", "is_valid": True, "app_id": "999", "application": "My app",
                             "expires_at": 0}}

        r = self.report()
        with env(META_TOKEN=fake_token("EAAd")), self.quiet(), mock.patch.object(probe.graph, "get", side_effect=fake_get):
            probe.gate_token_debug(r)
        self.assertEqual(calls, ["app", "debug_token"])
        self.assertEqual(self.row(r, "token app")["state"], probe.WARN)
        self.assertEqual(self.row(r, "token debug")["state"], probe.PASS)

    def test_scope_gate_is_skipped_for_eaah_and_write_probe_refused_for_eaad(self) -> None:
        r = self.report()
        with env(META_TOKEN=fake_token("EAAH")), self.quiet(), mock.patch.object(
                probe.graph, "get", side_effect=AssertionError("/me/permissions must not be called")):
            probe.gate_scopes(r)
        self.assertEqual(self.row(r, "granted scopes")["state"], probe.WARN)
        self.assertIn("#10", self.row(r, "granted scopes")["detail"])
        r = self.report()
        with env(META_TOKEN=fake_token("EAAd")), self.quiet(), mock.patch.object(
                probe.graph, "post", side_effect=AssertionError("nothing may be sent")):
            probe.gate_write(r, "act_1")
        self.assertEqual(self.row(r, "write access (validate_only)")["state"], probe.FAIL)
        self.assertTrue(r.failed)

    def test_whoami_verdict_names_a_first_party_token_instead_of_unknown(self) -> None:
        r = self.report()
        with env(META_TOKEN=fake_token("EAAB")), self.quiet():
            probe.whoami_verdict(r)
        text = " ".join(x["detail"] for x in r.rows)
        self.assertIn("first-party", text)
        self.assertNotIn("unknown to this probe", text)
        self.assertNotIn("missing for launches", text)


class ProbeTokenTableTests(unittest.TestCase):
    def test_one_variable_prints_no_table(self) -> None:
        r = probe.Report()
        with env(META_TOKEN=fake_token()), mock.patch.object(probe.graph, "call", side_effect=AssertionError("no call")):
            probe.gate_token_table(r, ["ads_read"], None)
        self.assertEqual(r.rows, [])

    def test_several_variables_cost_two_calls_each_and_meta_token_none(self) -> None:
        eaab, eaah, eaad = fake_token("EAAB"), fake_token("EAAH"), fake_token("EAAd")
        r = probe.Report()
        r.rows.append({"gate": "token identity", "state": probe.PASS, "detail": "", "data": {"id": "1000", "name": "Alex"}})
        r.rows.append({"gate": "token app", "state": probe.PASS, "detail": "",
                       "data": {"app": {"id": APP["EAAB"], "name": "Power editor"}, "class": "EAAB", "confirmed": True}})
        seen: list[tuple] = []

        def fake_call(method, path, params=None, token_override=None, cookies=None, retries=None, context="", **kw):
            seen.append((path, token_override, cookies, retries))
            if path == "me":
                return {"id": "1000", "name": "Alex"}
            return {"id": APP["EAAH"] if token_override == eaah else APP["EAAd"], "name": "App"}

        with tempfile.TemporaryDirectory() as td:
            out = pathlib.Path(td) / "t.json"
            with env(META_TOKEN=eaab, META_TOKEN_CATALOG=eaah, META_TOKEN_EVENTS=eaad,
                     META_COOKIES="c_user=1000; xs=x", META_COOKIES_EVENTS="c_user=1000; xs=events"), \
                    contextlib.redirect_stdout(io.StringIO()), mock.patch.object(probe.graph, "call", side_effect=fake_call):
                probe.gate_token_table(r, ["ads_read", "ads_write", "business_read", "catalog", "events_write"], str(out))
            saved = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(stat.S_IMODE(out.stat().st_mode), 0o600)
        self.assertEqual(len(seen), 4)                       # 2 extra tokens x (/me + /app)
        self.assertTrue(all(retries == 0 for *_x, retries in seen))
        self.assertEqual({t for _p, t, _c, _r in seen}, {eaah, eaad})
        self.assertNotIn("debug_token", [p for p, *_ in seen])
        cookies = {t: c for _p, t, c, _r in seen}
        self.assertEqual(cookies[eaad], "c_user=1000; xs=events")   # own cookies
        self.assertEqual(cookies[eaah], "c_user=1000; xs=x")        # shared fallback
        rows = {x["variable"]: x for x in saved["tokens"]}
        self.assertEqual(rows["META_TOKEN"]["class"], "EAAB")
        self.assertEqual(rows["META_TOKEN_CATALOG"]["class"], "EAAH")
        self.assertTrue(rows["META_TOKEN_CATALOG"]["confirmed"])
        self.assertEqual(rows["META_TOKEN_EVENTS"]["app"]["id"], APP["EAAd"])
        self.assertEqual(saved["missing"], [])
        self.assertEqual(saved["unverified_only"], [])              # events_write: EAAd is "claimed", EAAB "unverified"
        for secret in (eaab, eaah, eaad):
            self.assertNotIn(secret, json.dumps(saved))
        detail = next(x for x in r.rows if x["gate"] == "token table")
        self.assertEqual(detail["state"], probe.PASS)
        self.assertIn("still missing: none", detail["detail"])

    def test_the_same_token_in_two_variables_is_probed_once(self) -> None:
        shared = fake_token("EAAG")
        calls: list[str] = []

        def fake_call(method, path, params=None, token_override=None, **kw):
            calls.append(path)
            return {"id": "1000", "name": "Alex"} if path == "me" else {"id": APP["EAAG"], "name": "BM"}

        r = probe.Report()
        with env(META_TOKEN_BUSINESS=shared, META_TOKEN_RULES=shared), contextlib.redirect_stdout(io.StringIO()), \
                mock.patch.object(probe.graph, "call", side_effect=fake_call):
            probe.gate_token_table(r, ["business_read"], None)
        self.assertEqual(calls, ["me", "app"])
        self.assertEqual(len(r.rows[-1]["data"]["tokens"]), 2)

    def test_a_capability_no_valid_token_carries_is_reported_missing(self) -> None:
        def fake_call(method, path, params=None, token_override=None, **kw):
            if path == "me":
                return {"id": "1000", "name": "Alex"}
            return {"id": APP["EAAH"] if token_override == os.environ["META_TOKEN_CATALOG"] else APP["EAAd"], "name": "App"}

        r = probe.Report()
        with env(META_TOKEN_CATALOG=fake_token("EAAH"), META_TOKEN_EVENTS=fake_token("EAAd")), \
                contextlib.redirect_stdout(io.StringIO()), mock.patch.object(probe.graph, "call", side_effect=fake_call):
            probe.gate_token_table(r, ["business_read", "rules", "ads_write"], None)
        data = r.rows[-1]["data"]
        self.assertEqual(data["missing"], ["rules"])
        self.assertEqual(data["unverified_only"], [])              # EAAH ads_write: a real rename worked 2026-09-29
        self.assertEqual(r.rows[-1]["state"], probe.WARN)

    def test_table_flags_a_cookie_class_without_cookies_and_not_an_eaad(self) -> None:
        def fake_call(method, path, params=None, token_override=None, **kw):
            if path == "me":
                return {"id": "1000", "name": "Alex"}
            return {"id": APP["EAAH"] if token_override == os.environ["META_TOKEN_CATALOG"] else APP["EAAd"], "name": "App"}

        for cookies, expect_flag, expect_state in ((None, True, probe.WARN), ("c_user=1000; xs=x", False, probe.PASS)):
            extra = {"META_COOKIES": cookies} if cookies else {}
            r = probe.Report()
            out = io.StringIO()
            with env(META_TOKEN_CATALOG=fake_token("EAAH"), META_TOKEN_EVENTS=fake_token("EAAd"), **extra), \
                    contextlib.redirect_stdout(out), mock.patch.object(probe.graph, "call", side_effect=fake_call):
                probe.gate_token_table(r, ["catalog", "events_write"], None)
            rows = {x["variable"]: x for x in r.rows[-1]["data"]["tokens"]}
            self.assertEqual(rows["META_TOKEN_CATALOG"]["needs_cookies"], True)
            self.assertEqual(rows["META_TOKEN_CATALOG"]["cookies_set"], bool(cookies))
            self.assertEqual(rows["META_TOKEN_EVENTS"]["needs_cookies"], False)
            self.assertEqual("NO-COOKIES" in out.getvalue(), expect_flag)
            self.assertEqual(out.getvalue().count("NO-COOKIES"), 1 if expect_flag else 0)   # never on the EAAd row
            self.assertEqual(r.rows[-1]["state"], expect_state)

    def test_dead_extra_token_is_marked_and_skips_the_app_call(self) -> None:
        calls: list[str] = []

        def fake_call(method, path, **kw):
            calls.append(path)
            raise gerr(190, 460)

        r = probe.Report()
        with env(META_TOKEN=fake_token("EAAB"), META_TOKEN_RULES=fake_token("EAAI")), \
                contextlib.redirect_stdout(io.StringIO()), mock.patch.object(probe.graph, "call", side_effect=fake_call):
            probe.gate_token_table(r, ["ads_read"], None)
        self.assertEqual(calls, ["me", "me"])  # META_TOKEN has no identity row here, so it is probed too
        rows = r.rows[-1]["data"]["tokens"]
        self.assertTrue(all(row["valid"] is False for row in rows))


# ------------------------------------------------------------------------------ token import

def make_import_args(**over):
    base = dict(env_file=None, name=None, dry_run=False, no_verify=False, allow_unknown=False, as_ads=False,
                cookies_suffix=None, force=False, workspace_obj=None, json=False)
    base.update(over)
    return types.SimpleNamespace(**base)


class ParsePasteTests(unittest.TestCase):
    def test_fb_helper_block_token_blank_line_cookie_header(self) -> None:
        token = fake_token()
        paste = cmd_token.parse_paste(f"{token}\n\nc_user=1000; xs=44%3Aabc; datr=zz\n")
        self.assertEqual((paste.token, paste.cookies, paste.user_agent),
                         (token, "c_user=1000; xs=44%3Aabc; datr=zz", None))

    def test_keyed_lines_with_export_and_quotes(self) -> None:
        token = fake_token()
        text = (f"export META_TOKEN=\"{token}\"\nMETA_COOKIES='c_user=1; xs=2'\n"
                "META_USER_AGENT=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36\n")
        paste = cmd_token.parse_paste(text)
        self.assertEqual((paste.token, paste.cookies), (token, "c_user=1; xs=2"))
        self.assertTrue(paste.user_agent.startswith("Mozilla/5.0 (Macintosh"))

    def test_all_three_keys_on_one_line(self) -> None:
        token = fake_token("EAAG")
        paste = cmd_token.parse_paste(
            f"META_TOKEN={token} META_COOKIES=\"c_user=1; xs=2\" META_USER_AGENT='Mozilla/5.0 (X11; Linux)'")
        self.assertEqual((paste.token, paste.cookies, paste.user_agent),
                         (token, "c_user=1; xs=2", "Mozilla/5.0 (X11; Linux)"))

    def test_cookie_prefix_user_agent_line_and_json_cookie_array(self) -> None:
        token = fake_token()
        rows = [{"name": "c_user", "value": "5", "domain": ".facebook.com"}, {"name": "xs", "value": "9%3Ax"}]
        text = f"{token}\nCookie: c_user=5; xs=9%3Ax\nUser-Agent: Mozilla/5.0 (Windows NT 10.0)\n"
        self.assertEqual(cmd_token.parse_paste(text).cookies, "c_user=5; xs=9%3Ax")
        self.assertEqual(cmd_token.parse_paste(text).user_agent, "Mozilla/5.0 (Windows NT 10.0)")
        self.assertEqual(cmd_token.parse_paste(f"{token}\n{json.dumps(rows, indent=2)}").cookies, "c_user=5; xs=9%3Ax")

    def test_token_only_and_repeated_same_token_are_fine(self) -> None:
        token = fake_token()
        paste = cmd_token.parse_paste(f"{token}\n{token}\n")
        self.assertEqual((paste.token, paste.cookies, paste.user_agent), (token, None, None))

    def test_ambiguous_or_missing_input_is_refused(self) -> None:
        a, b = fake_token("EAAB"), fake_token("EAAG")
        for text, pattern in (
            (f"{a}\n{b}", "different tokens"),
            (f"{a}\nc_user=1; xs=2\nc_user=9; xs=3", "cookie sets"),
            (f"{a}\nUser-Agent: Mozilla/5.0 (A)\nUser-Agent: Mozilla/5.0 (B)", "User-Agent"),
            ("hello world", "no token found"),
            ("META_TOKEN=not-a-token", "not a Graph token"),
            (f"{a}\nMETA_COOKIES=garbage", "cookie header"),
        ):
            with self.assertRaisesRegex(cmd_token.ImportRefused, pattern, msg=text):
                cmd_token.parse_paste(text)

    def test_single_quote_in_a_value_is_refused_because_it_cannot_be_stored_safely(self) -> None:
        with self.assertRaisesRegex(cmd_token.ImportRefused, "single quote"):
            cmd_token.parse_paste(f"{fake_token()}\nUser-Agent: Mozilla/5.0 (it's)")

    def test_unrelated_and_app_id_keys_are_ignored(self) -> None:
        token = fake_token()
        paste = cmd_token.parse_paste(f"PATH=/bin\nMETA_TOKEN_APP_ID=123\nMETA_TOKEN={token}\n")
        self.assertEqual(paste.token, token)


class EnvFileTests(unittest.TestCase):
    def test_only_managed_keys_change_and_everything_else_is_kept(self) -> None:
        old = "# header\nA=1\n\nexport META_TOKEN=old\nMETA_TOKEN=dup\nB='x y'\nMETA_COOKIES=stale\n"
        new = cmd_token.apply_updates(old, {"META_TOKEN": "EAABnew", "META_COOKIES": "c_user=1; xs=2",
                                            "META_TOKEN_APP_ID": None})
        self.assertEqual(new, "# header\nA=1\n\nexport META_TOKEN=EAABnew\nB='x y'\nMETA_COOKIES='c_user=1; xs=2'\n")

    def test_new_keys_are_appended_and_none_removes(self) -> None:
        new = cmd_token.apply_updates("A=1", {"META_TOKEN_CATALOG": "EAAHnew", "META_TOKEN_APP_ID": None})
        self.assertEqual(new, "A=1\nMETA_TOKEN_CATALOG=EAAHnew\n")
        self.assertEqual(cmd_token.apply_updates("META_TOKEN_APP_ID=5\nA=1\n", {"META_TOKEN_APP_ID": None}), "A=1\n")
        self.assertEqual(cmd_token.apply_updates("", {"X": "1"}), "X=1\n")

    def test_a_multiline_quoted_value_of_a_managed_key_is_not_touched(self) -> None:
        with self.assertRaisesRegex(cmd_token.ImportRefused, "spans several lines"):
            cmd_token.apply_updates("META_COOKIES='a\nb'\n", {"META_COOKIES": "c"})

    def test_values_round_trip_through_read_env_values(self) -> None:
        text = cmd_token.apply_updates("", {"META_COOKIES": "c_user=1; xs=44%3Aa", "META_USER_AGENT": "Mozilla/5.0 (X11; Linux)",
                                            "META_TOKEN": "EAABxyz"})
        values = cmd_token.read_env_values(text)
        self.assertEqual(values["META_COOKIES"], "c_user=1; xs=44%3Aa")
        self.assertEqual(values["META_USER_AGENT"], "Mozilla/5.0 (X11; Linux)")
        self.assertEqual(values["META_TOKEN"], "EAABxyz")

    def test_write_is_atomic_private_and_leaves_a_private_backup(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = pathlib.Path(td) / "meta.env"
            path.write_text("A=1\nMETA_TOKEN=old\n", encoding="utf-8")
            path.chmod(0o644)
            result = cmd_token.write_env(path, "A=1\nMETA_TOKEN=new\n", path.read_bytes())
            self.assertEqual(path.read_text(encoding="utf-8"), "A=1\nMETA_TOKEN=new\n")
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            backup = pathlib.Path(result["backup"])
            self.assertEqual(backup.read_text(encoding="utf-8"), "A=1\nMETA_TOKEN=old\n")
            self.assertEqual(stat.S_IMODE(backup.stat().st_mode), 0o600)
            self.assertEqual(sorted(p.name for p in pathlib.Path(td).iterdir()), ["meta.env", "meta.env.bak"])

    def test_a_failed_replace_leaves_the_old_file_and_no_temp_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = pathlib.Path(td) / "meta.env"
            path.write_text("META_TOKEN=old\n", encoding="utf-8")
            with mock.patch.object(cmd_token.os, "replace", side_effect=OSError("disk")):
                with self.assertRaises(OSError):
                    cmd_token.write_env(path, "META_TOKEN=new\n", path.read_bytes())
            self.assertEqual(path.read_text(encoding="utf-8"), "META_TOKEN=old\n")
            self.assertEqual(sorted(p.name for p in pathlib.Path(td).iterdir()), ["meta.env", "meta.env.bak"])

    def test_symlinked_env_file_is_written_through(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            real = pathlib.Path(td) / "real.env"
            real.write_text("A=1\n", encoding="utf-8")
            link = pathlib.Path(td) / "link.env"
            link.symlink_to(real)
            cmd_token.write_env(link, "A=2\n", real.read_bytes())
            self.assertTrue(link.is_symlink())
            self.assertEqual(real.read_text(encoding="utf-8"), "A=2\n")


class TokenImportTests(unittest.TestCase):
    """The handler end to end with Graph mocked. `ME` is the user every token belongs to."""

    ME = {"id": "1000", "name": "Alex"}

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.env_file = self.root / "meta.env"
        self.seen: list[dict] = []
        graph._WARNED_WRITE_CLASSES.clear()

    def graph_answers(self, prefix="EAAB", app_id=None, app_name="App", me=None, fail_me=None, fail_app=None):
        def fake_get(path, params=None, context="", **kw):
            self.seen.append({"path": path, "kw": kw, "cookies": os.environ.get("META_COOKIES"),
                              "ua": os.environ.get("META_USER_AGENT"), "secret": os.environ.get("META_APP_SECRET")})
            if path == "me":
                if fail_me:
                    raise fail_me
                return me or dict(self.ME)
            if path == "app":
                if fail_app:
                    raise fail_app
                return {"id": app_id or APP.get(prefix, "999"), "name": app_name}
            raise AssertionError(f"unexpected call {path}")
        return fake_get

    def run_import(self, text: str, fake_get=None, **over):
        args = make_import_args(env_file=str(self.env_file), **over)
        out, err = io.StringIO(), io.StringIO()
        fake_get = fake_get or self.graph_answers()
        with env(META_PROXY="socks5h://u:p@h:1", META_APP_SECRET="app-secret-value", META_COOKIES="c_user=7; xs=ambient"), \
                mock.patch.object(sys, "stdin", io.StringIO(text)), \
                mock.patch.object(metaops.graph, "get", side_effect=fake_get), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code, payload = cmd_token._token_import(metaops, args)
        self.printed = out.getvalue() + err.getvalue()
        return code, payload

    def block(self, prefix="EAAB", cookies="c_user=1000; xs=44%3Asecretxs; datr=dd", ua=None):
        token = fake_token(prefix)
        text = f"{token}\n\n{cookies}\n" + (f"User-Agent: {ua}\n" if ua else "")
        return token, text

    # -- verification ---------------------------------------------------------------------

    def test_verification_is_two_gets_with_the_pasted_session_and_a_scoped_env(self) -> None:
        token, text = self.block(ua="Mozilla/5.0 (Macintosh) Chrome/1")
        code, payload = self.run_import(text)
        self.assertEqual(code, 0)
        self.assertEqual([c["path"] for c in self.seen], ["me", "app"])
        for call in self.seen:
            self.assertEqual(call["kw"]["token_override"], token)
            self.assertEqual(call["kw"]["retries"], 0)
            self.assertEqual(call["cookies"], "c_user=1000; xs=44%3Asecretxs; datr=dd")  # the paste, not the ambient ones
            self.assertEqual(call["ua"], "Mozilla/5.0 (Macintosh) Chrome/1")
            self.assertIsNone(call["secret"], "appsecret_proof must not be computed for a first-party token")
        self.assertEqual(payload["data"]["graph_calls"], 2)

    def test_process_environment_is_restored_after_verification(self) -> None:
        token, text = self.block()
        with env(META_PROXY="socks5h://u:p@h:1", META_APP_SECRET="s", META_COOKIES="c_user=7; xs=ambient"):
            before = dict(os.environ)
            with mock.patch.object(sys, "stdin", io.StringIO(text)), \
                    mock.patch.object(metaops.graph, "get", side_effect=self.graph_answers()), \
                    contextlib.redirect_stdout(io.StringIO()):
                cmd_token._token_import(metaops, make_import_args(env_file=str(self.env_file)))
            self.assertEqual(dict(os.environ), before)

    def test_dead_token_codes_refuse_and_write_nothing(self) -> None:
        for error in (gerr(190), gerr(102), gerr(190, 459), gerr(190, 460), gerr(190, 463), gerr(190, 467),
                      gerr(459), gerr(1)):
            token, text = self.block()
            self.env_file.write_text("KEEP=1\n", encoding="utf-8")
            code, payload = self.run_import(text, self.graph_answers(fail_me=error))
            self.assertEqual(code, 1, (error.code, error.subcode))
            self.assertFalse(payload["ok"])
            self.assertEqual(self.env_file.read_text(encoding="utf-8"), "KEEP=1\n")
            self.assertFalse(self.env_file.with_name("meta.env.bak").exists())
            self.assertEqual(len(self.seen), 1)
            self.seen.clear()
            self.assertNotIn(token, json.dumps(payload) + self.printed)

    def test_code_1_message_says_to_bring_the_session(self) -> None:
        _, text = self.block()
        code, payload = self.run_import(text, self.graph_answers(fail_me=gerr(1, message="Invalid request")))
        self.assertIn("cookies of the SAME browser profile", payload["error"]["message"])

    def test_other_graph_errors_and_a_missing_proxy_refuse_too(self) -> None:
        _, text = self.block()
        code, payload = self.run_import(text, self.graph_answers(fail_me=gerr(4, message="throttled")))
        self.assertEqual(code, 1)

        def no_proxy(*a, **k):
            raise SystemExit("META_PROXY is not set.")
        code, payload = self.run_import(text, no_proxy)
        self.assertEqual(code, 1)
        self.assertIn("META_PROXY", payload["error"]["message"])
        self.assertFalse(self.env_file.exists())

    def test_c_user_that_is_not_the_me_id_refuses(self) -> None:
        token, text = self.block(cookies="c_user=555; xs=44%3Asecretxs")
        code, payload = self.run_import(text)
        self.assertEqual(code, 1)
        self.assertIn("c_user", payload["error"]["message"])
        self.assertNotIn("555", payload["error"]["message"])
        self.assertFalse(self.env_file.exists())

    def test_no_verify_makes_no_graph_call_and_warns(self) -> None:
        token, text = self.block()
        code, payload = self.run_import(text, self.graph_answers(fail_me=AssertionError("no call")), no_verify=True)
        self.assertEqual(code, 0)
        self.assertEqual(self.seen, [])
        self.assertFalse(payload["data"]["confirmed"])
        self.assertTrue(any("--no-verify" in w for w in payload["data"]["warnings"]))
        values = cmd_token.read_env_values(self.env_file.read_text(encoding="utf-8"))
        self.assertEqual(values["META_TOKEN"], token)
        self.assertNotIn("META_TOKEN_APP_ID", values)

    # -- class gate and routing -----------------------------------------------------------

    def test_each_class_goes_to_its_own_variable(self) -> None:
        expected = {"EAAB": "META_TOKEN", "EAAG": "META_TOKEN_BUSINESS", "EAAH": "META_TOKEN_CATALOG",
                    "EAAd": "META_TOKEN_EVENTS", "EAAI": "META_TOKEN_RULES"}
        for prefix, var in expected.items():
            self.env_file.unlink(missing_ok=True)
            token, text = self.block(prefix)
            code, payload = self.run_import(text, self.graph_answers(prefix))
            self.assertEqual(code, 0, prefix)
            values = cmd_token.read_env_values(self.env_file.read_text(encoding="utf-8"))
            self.assertEqual(values[var], token, prefix)
            self.assertEqual(values[f"{var}_APP_ID"], APP[prefix])
            self.assertEqual(values["META_COOKIES"], "c_user=1000; xs=44%3Asecretxs; datr=dd")
            self.assertEqual(payload["data"]["type"], prefix)
            self.assertEqual(payload["data"]["variable"], var)
            self.assertTrue(payload["data"]["confirmed"])
            self.seen.clear()

    def test_name_overrides_the_variable_and_a_workspace_token_env_is_used(self) -> None:
        token, text = self.block("EAAH")
        code, _ = self.run_import(text, self.graph_answers("EAAH"), name="CF1_CATALOG_TOKEN")
        self.assertEqual(cmd_token.read_env_values(self.env_file.read_text(encoding="utf-8"))["CF1_CATALOG_TOKEN"], token)
        self.env_file.unlink()
        data = workspace_data()
        data["defaults"]["token_envs"] = {"catalog": "CF1_CAT"}
        workspace = load_workspace(self.root, data)
        token, text = self.block("EAAH")
        code, _ = self.run_import(text, self.graph_answers("EAAH"), workspace_obj=workspace)
        self.assertEqual(cmd_token.read_env_values(self.env_file.read_text(encoding="utf-8"))["CF1_CAT"], token)

    def test_eaah_and_eaad_into_the_ads_variable_are_refused_without_force(self) -> None:
        for prefix in ("EAAH", "EAAd", "EAAI"):
            self.env_file.unlink(missing_ok=True)
            token, text = self.block(prefix)
            code, payload = self.run_import(text, self.graph_answers(prefix), name="META_TOKEN")
            self.assertEqual(code, 1, prefix)
            self.assertIn("--force", payload["error"]["message"])
            self.assertFalse(self.env_file.exists())
            code, payload = self.run_import(text, self.graph_answers(prefix), name="META_TOKEN", force=True)
            self.assertEqual(code, 0, prefix)
            self.assertEqual(cmd_token.read_env_values(self.env_file.read_text(encoding="utf-8"))["META_TOKEN"], token)

    def test_eaag_into_meta_token_needs_as_ads_and_no_eaab_already_there(self) -> None:
        token, text = self.block("EAAG")
        code, payload = self.run_import(text, self.graph_answers("EAAG"), name="META_TOKEN")
        self.assertEqual(code, 1)
        self.assertIn("--as-ads", payload["error"]["message"])
        code, _ = self.run_import(text, self.graph_answers("EAAG"), as_ads=True)
        self.assertEqual(code, 0)
        self.assertEqual(cmd_token.read_env_values(self.env_file.read_text(encoding="utf-8"))["META_TOKEN"], token)
        self.env_file.write_text(f"META_TOKEN={fake_token('EAAB')}\nMETA_COOKIES='c_user=1000; xs=old'\n", encoding="utf-8")
        code, payload = self.run_import(text, self.graph_answers("EAAG"), as_ads=True)
        self.assertEqual(code, 1)
        self.assertIn("EAAB", payload["error"]["message"])
        code, _ = self.run_import(text, self.graph_answers("EAAG"), as_ads=True, force=True)
        self.assertEqual(code, 0)

    def test_unknown_class_needs_allow_unknown_and_records_the_app_id(self) -> None:
        token = "EAAM" + secrets.token_hex(40)
        text = f"{token}\n\nc_user=1000; xs=44%3Asecretxs\n"
        code, payload = self.run_import(text, self.graph_answers(app_id="777", app_name="My app"))
        self.assertEqual(code, 1)
        self.assertIn("--allow-unknown", payload["error"]["message"])
        self.assertFalse(self.env_file.exists())
        code, payload = self.run_import(text, self.graph_answers(app_id="777", app_name="My app"), allow_unknown=True)
        self.assertEqual(code, 0)
        values = cmd_token.read_env_values(self.env_file.read_text(encoding="utf-8"))
        self.assertEqual((values["META_TOKEN"], values["META_TOKEN_APP_ID"]), (token, "777"))
        self.assertEqual(payload["data"]["type"], "unknown")

    def test_a_first_party_prefix_on_an_own_app_is_unknown_and_recorded_so_the_write_guard_stands_down(self) -> None:
        token = fake_token("EAAd")   # a System User token that happens to start with EAAd
        text = f"{token}\n"
        code, payload = self.run_import(text, self.graph_answers(app_id="888"))
        self.assertEqual(code, 1)
        self.assertIn("share a prefix", payload["error"]["message"])
        code, _ = self.run_import(text, self.graph_answers(app_id="888"), allow_unknown=True)
        self.assertEqual(code, 0)
        values = cmd_token.read_env_values(self.env_file.read_text(encoding="utf-8"))
        self.assertEqual(values["META_TOKEN"], token)
        self.assertEqual(values["META_TOKEN_APP_ID"], "888")
        with env(META_TOKEN=token, META_TOKEN_APP_ID="888"):
            self.assertEqual(tokens.classify(token, "888").cls.ads_write_policy, "allow")
            graph.authorize_writes(["act_1"])
            try:
                graph._guard_ads_write(graph.resolve_token())   # must not exit
            finally:
                graph._WRITE_ACCOUNTS = None
                graph._WRITE_CAPABILITY_LOADED = False

    def test_prefix_and_app_id_disagreeing_refuses_unless_forced(self) -> None:
        token, text = self.block("EAAB")
        code, payload = self.run_import(text, self.graph_answers(app_id=APP["EAAH"]))
        self.assertEqual(code, 1)
        self.assertIn("prefix EAAB", payload["error"]["message"])
        code, payload = self.run_import(text, self.graph_answers(app_id=APP["EAAH"]), force=True)
        self.assertEqual(code, 0)
        self.assertEqual(payload["data"]["type"], "EAAH")     # the app id decides
        self.assertEqual(payload["data"]["variable"], "META_TOKEN_CATALOG")

    def test_app_call_failing_softly_falls_back_to_the_prefix_with_a_warning(self) -> None:
        token, text = self.block("EAAH")
        code, payload = self.run_import(text, self.graph_answers("EAAH", fail_app=gerr(100, message="no")))
        self.assertEqual(code, 0)
        self.assertFalse(payload["data"]["confirmed"])
        self.assertTrue(any("not confirmed" in w for w in payload["data"]["warnings"]))
        self.assertEqual(payload["data"]["graph_calls"], 2)

    # -- cookies ----------------------------------------------------------------------------

    def test_shared_cookies_of_another_login_are_not_replaced_silently(self) -> None:
        self.env_file.write_text("META_COOKIES='c_user=555; xs=old'\n", encoding="utf-8")
        token, text = self.block("EAAH")
        code, payload = self.run_import(text, self.graph_answers("EAAH"))
        self.assertEqual(code, 1)
        self.assertIn("--cookies-suffix", payload["error"]["message"])
        self.assertEqual(self.env_file.read_text(encoding="utf-8"), "META_COOKIES='c_user=555; xs=old'\n")
        code, _ = self.run_import(text, self.graph_answers("EAAH"), cookies_suffix="auto")
        self.assertEqual(code, 0)
        values = cmd_token.read_env_values(self.env_file.read_text(encoding="utf-8"))
        self.assertEqual(values["META_COOKIES"], "c_user=555; xs=old")
        self.assertEqual(values["META_COOKIES_CATALOG"], "c_user=1000; xs=44%3Asecretxs; datr=dd")

    def test_cookies_suffix_must_be_one_graph_reads(self) -> None:
        token, text = self.block("EAAB")
        code, payload = self.run_import(text, cookies_suffix="auto")   # META_TOKEN has no suffix
        self.assertEqual(code, 1)
        code, payload = self.run_import(text, cookies_suffix="ODD")
        self.assertEqual(code, 1)

    def test_eaab_without_cookies_warns_without_asking_for_a_user_agent_and_old_cookies_are_kept(self) -> None:
        self.env_file.write_text("META_COOKIES='c_user=1000; xs=old'\n", encoding="utf-8")
        token = fake_token("EAAB")
        with env(META_PROXY="socks5h://u:p@h:1"), mock.patch.object(sys, "stdin", io.StringIO(token)), \
                mock.patch.object(metaops.graph, "get", side_effect=self.graph_answers()), \
                contextlib.redirect_stdout(io.StringIO()):
            code, payload = cmd_token._token_import(metaops, make_import_args(env_file=str(self.env_file)))
        warnings = " ".join(payload["data"]["warnings"])
        self.assertIn("without cookies", warnings)
        self.assertNotIn("User-Agent", warnings)
        self.assertIn("previous session", warnings)
        self.assertEqual(cmd_token.read_env_values(self.env_file.read_text(encoding="utf-8"))["META_COOKIES"],
                         "c_user=1000; xs=old")

    def test_every_cookie_class_warns_without_cookies_and_an_eaad_never_does(self) -> None:
        for prefix in ("EAAB", "EAAI", "EAAG", "EAAH"):
            self.env_file.unlink(missing_ok=True)
            code, payload = self.run_import(fake_token(prefix), self.graph_answers(prefix))
            self.assertEqual(code, 0, prefix)
            self.assertTrue(any(f"{prefix} without cookies" in w for w in payload["data"]["warnings"]), prefix)
        self.env_file.unlink(missing_ok=True)
        eaad = fake_token("EAAd")
        code, payload = self.run_import(eaad, self.graph_answers("EAAd"))
        self.assertEqual(code, 0)
        self.assertFalse(any("cookies" in w for w in payload["data"]["warnings"]), payload["data"]["warnings"])
        self.assertIsNone(payload["data"]["cookies_variable"])
        values = cmd_token.read_env_values(self.env_file.read_text(encoding="utf-8"))
        self.assertEqual(values["META_TOKEN_EVENTS"], eaad)
        self.assertNotIn("META_COOKIES", values)

    def test_an_eaad_paste_with_cookies_still_stores_them(self) -> None:
        token, text = self.block("EAAd")
        code, payload = self.run_import(text, self.graph_answers("EAAd"))
        self.assertEqual(code, 0)
        self.assertFalse(any("cookies" in w.lower() and "without" in w for w in payload["data"]["warnings"]))
        self.assertEqual(cmd_token.read_env_values(self.env_file.read_text(encoding="utf-8"))["META_COOKIES"],
                         "c_user=1000; xs=44%3Asecretxs; datr=dd")

    # -- writing ----------------------------------------------------------------------------

    def test_existing_file_keeps_unrelated_lines_and_gets_a_private_backup(self) -> None:
        old = "# mine\nMETA_PROXY=socks5h://u:p@h:1\nMETA_TOKEN=old\nMETA_TOKEN_APP_ID=1\nOTHER='a b'\n"
        self.env_file.write_text(old, encoding="utf-8")
        self.env_file.chmod(0o644)
        token, text = self.block("EAAB", ua="Mozilla/5.0 (X11; Linux)")
        code, payload = self.run_import(text)
        self.assertEqual(code, 0)
        new = self.env_file.read_text(encoding="utf-8")
        self.assertTrue(new.startswith("# mine\nMETA_PROXY=socks5h://u:p@h:1\nMETA_TOKEN="))
        self.assertIn("OTHER='a b'\n", new)
        values = cmd_token.read_env_values(new)
        self.assertEqual(values["META_TOKEN"], token)
        self.assertEqual(values["META_TOKEN_APP_ID"], APP["EAAB"])
        self.assertEqual(values["META_USER_AGENT"], "Mozilla/5.0 (X11; Linux)")
        backup = self.env_file.with_name("meta.env.bak")
        self.assertEqual(backup.read_text(encoding="utf-8"), old)
        self.assertEqual(stat.S_IMODE(backup.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.env_file.stat().st_mode), 0o600)
        self.assertEqual(payload["data"]["written"]["keys"][0], "META_TOKEN")

    def test_a_second_identical_import_changes_nothing(self) -> None:
        token, text = self.block()
        self.run_import(text)
        first = self.env_file.read_bytes()
        code, payload = self.run_import(text)
        self.assertEqual(code, 0)
        self.assertEqual(self.env_file.read_bytes(), first)
        self.assertTrue(payload["data"]["written"]["unchanged"])
        self.assertFalse(self.env_file.with_name("meta.env.bak").exists())

    def test_stale_app_id_is_dropped_when_the_token_is_replaced_without_verification(self) -> None:
        self.env_file.write_text(f"META_TOKEN={fake_token()}\nMETA_TOKEN_APP_ID={APP['EAAB']}\n", encoding="utf-8")
        token, text = self.block()
        self.run_import(text, no_verify=True)
        self.assertNotIn("META_TOKEN_APP_ID", cmd_token.read_env_values(self.env_file.read_text(encoding="utf-8")))

    def test_missing_env_file_directory_is_an_error(self) -> None:
        token, text = self.block()
        args = make_import_args(env_file=str(self.root / "nope" / "meta.env"))
        with env(), mock.patch.object(sys, "stdin", io.StringIO(text)):
            with self.assertRaisesRegex(metaops.MetaOpsError, "does not exist"):
                cmd_token._token_import(metaops, args)

    # -- dry run and output ----------------------------------------------------------------

    def test_without_env_file_it_is_a_dry_run_that_verifies_and_writes_nothing(self) -> None:
        token, text = self.block()
        args = make_import_args(env_file=None)
        out = io.StringIO()
        with env(META_PROXY="socks5h://u:p@h:1"), mock.patch.object(sys, "stdin", io.StringIO(text)), \
                mock.patch.object(metaops.graph, "get", side_effect=self.graph_answers()), contextlib.redirect_stdout(out):
            code, payload = cmd_token._token_import(metaops, args)
        self.assertEqual((code, payload["phase"]), (0, "dry_run"))
        self.assertEqual(len(self.seen), 2)
        self.assertEqual(list(self.root.iterdir()), [])
        self.assertIn("dry run", out.getvalue())

    def test_explicit_dry_run_with_env_file_writes_nothing(self) -> None:
        token, text = self.block()
        code, payload = self.run_import(text, dry_run=True)
        self.assertEqual(payload["phase"], "dry_run")
        self.assertFalse(self.env_file.exists())

    def test_nothing_secret_is_printed_or_returned(self) -> None:
        token, text = self.block("EAAB", cookies="c_user=1000; xs=44%3Asecretxs; datr=dddvalue", ua="Mozilla/5.0 (X11; Linux)")
        code, payload = self.run_import(text)
        blob = self.printed + json.dumps(payload)
        for secret in (token, token[4:-4], "44%3Asecretxs", "dddvalue", "app-secret-value"):
            self.assertNotIn(secret, blob, secret[:8])
        self.assertIn(token[:4], blob)
        self.assertIn(token[-4:], blob)
        self.assertEqual(payload["data"]["cookie_names"], ["c_user", "datr", "xs"])
        self.assertEqual(payload["data"]["user"], self.ME)
        self.assertIn(str(self.env_file.resolve()), blob)
        self.assertIn("Power editor" if False else "App", blob)
        # a refusal must be just as clean
        token2, text2 = self.block("EAAB", cookies="c_user=1000; xs=44%3Asecretxs2")
        code, payload = self.run_import(text2, self.graph_answers(fail_me=gerr(190, 460, message=f"bad {token2} xs=44%3Asecretxs2")))
        blob = self.printed + json.dumps(payload)
        self.assertNotIn(token2, blob)
        self.assertNotIn("secretxs2", blob)

    def test_role_hints_and_evidence_are_printed(self) -> None:
        token, text = self.block("EAAH")
        code, payload = self.run_import(text, self.graph_answers("EAAH"))
        self.assertIn("Commerce Manager", self.printed)
        self.assertIn("catalog", self.printed)
        self.assertEqual(payload["data"]["provides"]["catalog"]["evidence"], tokens.VERIFIED)
        self.assertEqual(payload["data"]["provides"]["ads_write"]["evidence"], tokens.VERIFIED)
        self.assertIn("depends on the BM", payload["data"]["provides"]["ads_write"]["note"])
        self.assertIn("needs the cookies", payload["data"]["role"])

    def test_profile_cross_check_warns_without_an_extra_graph_call(self) -> None:
        data = workspace_data()
        data["profiles"]["test"]["token_kind"] = "system_user"
        workspace = load_workspace(self.root, data)
        token, text = self.block()
        code, payload = self.run_import(text, workspace_obj=workspace, profile="test")
        warnings = " ".join(payload["data"]["warnings"])
        self.assertIn("token_kind system_user", warnings)
        self.assertIn("system_user_id 12", warnings)
        self.assertEqual(len(self.seen), 2)
        self.assertIn("--profile test", payload["next_action"])
        with self.assertRaisesRegex(metaops.MetaOpsError, "needs a workspace"):
            with env(), mock.patch.object(sys, "stdin", io.StringIO(text)):
                cmd_token._token_import(metaops, make_import_args(profile="test"))

    def test_tty_stdin_and_bad_name_are_usage_errors(self) -> None:
        tty = mock.Mock()
        tty.isatty.return_value = True
        with env(), mock.patch.object(sys, "stdin", tty):
            with self.assertRaisesRegex(metaops.MetaOpsError, "nothing on stdin"):
                cmd_token._token_import(metaops, make_import_args())
        with self.assertRaisesRegex(metaops.MetaOpsError, "--name"):
            cmd_token._token_import(metaops, make_import_args(name="lower"))

    def test_two_tokens_of_one_class_are_a_usage_error_before_any_graph_call(self) -> None:
        text = f"{fake_token('EAAB')}\n{fake_token('EAAB')}\n"
        with env(), mock.patch.object(sys, "stdin", io.StringIO(text)), \
                mock.patch.object(metaops.graph, "get", side_effect=AssertionError("no call")):
            with self.assertRaisesRegex(metaops.MetaOpsError, "ambiguous input: two tokens of the same class"):
                cmd_token._token_import(metaops, make_import_args(env_file=str(self.env_file)))
        self.assertFalse(self.env_file.exists())


# ------------------------------------------------------------------- several tokens in one paste

class ParseBatchTests(unittest.TestCase):
    COOKIES = "c_user=1000; xs=44%3Aone; datr=dd"

    def blocks(self, prefixes, cookies=None) -> tuple[list[str], str]:
        toks = [fake_token(p) for p in prefixes]
        cookies = cookies or [self.COOKIES] * len(toks)
        return toks, "\n\n".join(f"{t}\n\n{c}" for t, c in zip(toks, cookies)) + "\n"

    def test_five_fb_helper_blocks_with_the_same_cookies_each_time(self) -> None:
        toks, text = self.blocks(["EAAB", "EAAI", "EAAG", "EAAH", "EAAd"])
        batch = cmd_token.parse_batch(text)
        self.assertEqual(batch.tokens, toks)
        self.assertEqual(batch.cookies, self.COOKIES)
        self.assertEqual(batch.warnings, [])

    def test_one_token_paste_is_parsed_as_before(self) -> None:
        toks, text = self.blocks(["EAAB"])
        self.assertEqual(cmd_token.parse_batch(text).tokens, toks)
        with self.assertRaisesRegex(cmd_token.ImportRefused, "cookie sets"):   # single token stays strict
            cmd_token.parse_batch(f"{toks[0]}\nc_user=1; xs=2\nc_user=1; xs=3")

    def test_two_tokens_of_one_class_are_ambiguous(self) -> None:
        for prefixes, what in ((["EAAB", "EAAH", "EAAB"], "the same class \\(EAAB\\)"),
                               (["EAAM", "EAAH", "EAAN"], "unknown class")):
            _t, text = self.blocks(prefixes)
            with self.assertRaisesRegex(cmd_token.ImportRefused, f"ambiguous input: two tokens of {what}"):
                cmd_token.parse_batch(text)

    def test_the_same_token_twice_is_one_token(self) -> None:
        token = fake_token("EAAB")
        self.assertEqual(cmd_token.parse_batch(f"{token}\n{token}\n{self.COOKIES}").tokens, [token])

    def test_differing_cookie_sets_keep_the_last_complete_one_and_warn(self) -> None:
        one, two, partial = self.COOKIES, "c_user=1000; xs=44%3Atwo; datr=dd", "c_user=1000; datr=only"
        _t, text = self.blocks(["EAAB", "EAAI", "EAAG"], [one, two, partial])
        batch = cmd_token.parse_batch(text)
        self.assertEqual(batch.cookies, two)
        self.assertEqual(len(batch.warnings), 1)
        self.assertIn("last complete one", batch.warnings[0])
        _t, text = self.blocks(["EAAB", "EAAI"], [partial, "c_user=1000; datr=other"])   # none complete: the last
        self.assertEqual(cmd_token.parse_batch(text).cookies, "c_user=1000; datr=other")

    def test_a_different_c_user_between_blocks_is_refused(self) -> None:
        _t, text = self.blocks(["EAAB", "EAAI"], [self.COOKIES, "c_user=2000; xs=44%3Aone"])
        with self.assertRaisesRegex(cmd_token.ImportRefused, "different logins"):
            cmd_token.parse_batch(text)

    def test_differing_user_agents_are_still_ambiguous(self) -> None:
        toks, _ = self.blocks(["EAAB", "EAAI"])
        with self.assertRaisesRegex(cmd_token.ImportRefused, "User-Agent"):
            cmd_token.parse_batch(f"{toks[0]}\nUser-Agent: Mozilla/5.0 (A)\n{toks[1]}\nUser-Agent: Mozilla/5.0 (B)")


class TokenImportManyTests(unittest.TestCase):
    COOKIES = "c_user=1000; xs=44%3Asecretxs; datr=dddvalue"
    ORDER = ["EAAB", "EAAI", "EAAG", "EAAH", "EAAd"]
    VARS = {"EAAB": "META_TOKEN", "EAAI": "META_TOKEN_RULES", "EAAG": "META_TOKEN_BUSINESS",
            "EAAH": "META_TOKEN_CATALOG", "EAAd": "META_TOKEN_EVENTS"}

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.env_file = self.root / "meta.env"
        self.seen: list[tuple[str, str]] = []
        self.printed = ""

    def answers(self, dead_on=None, users=None, apps=None):
        def fake_get(path, params=None, context="", **kw):
            prefix = kw["token_override"][:4]
            self.seen.append((path, prefix))
            if dead_on == prefix and path == "me":
                raise gerr(190, 460)
            if path == "me":
                return {"id": (users or {}).get(prefix, "1000"), "name": "Alex"}
            return {"id": (apps or {}).get(prefix, APP.get(prefix, "999")), "name": f"app-{prefix}"}
        return fake_get

    def text(self, prefixes=None, cookies=None):
        self.toks = {p: fake_token(p) for p in (prefixes or self.ORDER)}
        return "\n\n".join(f"{t}\n\n{cookies or self.COOKIES}" for t in self.toks.values()) + "\n"

    def run_import(self, text, fake_get=None, **over):
        args = make_import_args(env_file=str(self.env_file), **over)
        out, err = io.StringIO(), io.StringIO()
        with env(META_PROXY="socks5h://u:p@h:1", META_APP_SECRET="app-secret-value"), \
                mock.patch.object(sys, "stdin", io.StringIO(text)), \
                mock.patch.object(metaops.graph, "get", side_effect=fake_get or self.answers()), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code, payload = cmd_token._token_import(metaops, args)
        self.printed = out.getvalue() + err.getvalue()
        return code, payload

    def test_five_classes_in_one_paste_are_routed_verified_and_written_once(self) -> None:
        self.env_file.write_text("KEEP=1\nMETA_TOKEN=old\n", encoding="utf-8")
        text = self.text()
        with mock.patch.object(cmd_token, "write_env", wraps=cmd_token.write_env) as write:
            code, payload = self.run_import(text)
        self.assertEqual(code, 0, payload.get("error"))
        write.assert_called_once()
        self.assertEqual(self.seen, [(path, p) for p in self.ORDER for path in ("me", "app")])   # 2 calls each, in order
        values = cmd_token.read_env_values(self.env_file.read_text(encoding="utf-8"))
        for prefix, var in self.VARS.items():
            self.assertEqual(values[var], self.toks[prefix], prefix)
            self.assertEqual(values[f"{var}_APP_ID"], APP[prefix], prefix)
        self.assertEqual(values["META_COOKIES"], self.COOKIES)
        self.assertEqual(values["KEEP"], "1")
        self.assertEqual(self.env_file.with_name("meta.env.bak").read_text(encoding="utf-8"), "KEEP=1\nMETA_TOKEN=old\n")
        self.assertEqual(stat.S_IMODE(self.env_file.stat().st_mode), 0o600)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["meta.env", "meta.env.bak"])
        data = payload["data"]
        self.assertEqual(data["types"], self.ORDER)
        self.assertEqual(data["graph_calls"], 10)
        self.assertEqual(payload["phase"], "written")

    def test_one_masked_row_per_token_and_nothing_secret(self) -> None:
        text = self.text()
        code, payload = self.run_import(text)
        rows = [line for line in self.printed.splitlines() if line.strip().startswith("[")]
        self.assertEqual(len(rows), 5)
        for line, prefix in zip(rows, self.ORDER):
            token = self.toks[prefix]
            self.assertIn(f"{token[:4]}…{token[-4:]}", line)
            self.assertIn(self.VARS[prefix], line)
            self.assertIn(f"app {APP[prefix]}", line)
            self.assertIn("user 1000 Alex", line)
        blob = self.printed + json.dumps(payload)
        for prefix, token in self.toks.items():
            self.assertNotIn(token, blob)
            self.assertNotIn(token[4:-4], blob)
        for secret in ("44%3Asecretxs", "dddvalue", "app-secret-value"):
            self.assertNotIn(secret, blob)
        self.assertEqual(payload["data"]["cookie_names"], ["c_user", "datr", "xs"])

    def test_the_first_dead_token_stops_the_whole_import(self) -> None:
        self.env_file.write_text("KEEP=1\n", encoding="utf-8")
        code, payload = self.run_import(self.text(), self.answers(dead_on="EAAG"))
        self.assertEqual(code, 1)
        self.assertFalse(payload["ok"])
        self.assertEqual(self.seen, [("me", "EAAB"), ("app", "EAAB"), ("me", "EAAI"), ("app", "EAAI"), ("me", "EAAG")])
        self.assertIn("token 3 of 5", payload["error"]["message"])
        self.assertIn("nothing was written", payload["error"]["message"])
        self.assertEqual(payload["data"]["graph_calls"], 5)
        self.assertEqual(self.env_file.read_text(encoding="utf-8"), "KEEP=1\n")
        self.assertFalse(self.env_file.with_name("meta.env.bak").exists())
        for token in self.toks.values():
            self.assertNotIn(token, self.printed + json.dumps(payload))

    def test_two_of_one_class_or_a_bad_flag_is_a_usage_error_without_graph_calls(self) -> None:
        text = "\n\n".join(f"{fake_token(p)}\n\n{self.COOKIES}" for p in ("EAAB", "EAAH", "EAAB"))
        with env(), mock.patch.object(sys, "stdin", io.StringIO(text)), \
                mock.patch.object(metaops.graph, "get", side_effect=AssertionError("no call")):
            with self.assertRaisesRegex(metaops.MetaOpsError, "same class"):
                cmd_token._token_import(metaops, make_import_args(env_file=str(self.env_file)))
        for over, pattern in (({"name": "META_TOKEN_X"}, "--name"), ({"cookies_suffix": "auto"}, "--cookies-suffix")):
            with env(), mock.patch.object(sys, "stdin", io.StringIO(self.text(["EAAB", "EAAH"]))), \
                    mock.patch.object(metaops.graph, "get", side_effect=AssertionError("no call")):
                with self.assertRaisesRegex(metaops.MetaOpsError, pattern):
                    cmd_token._token_import(metaops, make_import_args(env_file=str(self.env_file), **over))
        self.assertFalse(self.env_file.exists())

    def test_different_c_user_between_blocks_is_refused_before_any_graph_call(self) -> None:
        one = f"{fake_token('EAAB')}\n\nc_user=1000; xs=1"
        two = f"{fake_token('EAAH')}\n\nc_user=2000; xs=2"
        with env(), mock.patch.object(sys, "stdin", io.StringIO(one + "\n\n" + two)), \
                mock.patch.object(metaops.graph, "get", side_effect=AssertionError("no call")):
            with self.assertRaisesRegex(metaops.MetaOpsError, "different logins"):
                cmd_token._token_import(metaops, make_import_args(env_file=str(self.env_file)))

    def test_differing_cookie_blocks_keep_the_last_complete_one_and_warn(self) -> None:
        a, b, c = fake_token("EAAB"), fake_token("EAAH"), fake_token("EAAd")
        text = (f"{a}\n\nc_user=1000; xs=44%3Aold\n\n{b}\n\nc_user=1000; xs=44%3Anew\n\n"
                f"{c}\n\nc_user=1000; datr=partial\n")
        code, payload = self.run_import(text)
        self.assertEqual(code, 0)
        values = cmd_token.read_env_values(self.env_file.read_text(encoding="utf-8"))
        self.assertEqual(values["META_COOKIES"], "c_user=1000; xs=44%3Anew")
        self.assertTrue(any("different cookie sets" in w for w in payload["data"]["warnings"]))

    def test_unknown_class_needs_the_flag_and_cannot_share_the_ads_variable_with_an_eaab(self) -> None:
        unknown = "EAAM" + secrets.token_hex(40)
        eaah, eaad = fake_token("EAAH"), fake_token("EAAd")
        text = f"{unknown}\n\n{self.COOKIES}\n\n{eaah}\n\n{self.COOKIES}\n\n{eaad}\n\n{self.COOKIES}\n"

        def get(path, params=None, context="", **kw):
            prefix = kw["token_override"][:4]
            if path == "me":
                return {"id": "1000", "name": "Alex"}
            return {"id": "777" if prefix == "EAAM" else APP[prefix], "name": "n"}

        code, payload = self.run_import(text, get)
        self.assertEqual(code, 1)
        self.assertIn("--allow-unknown", payload["error"]["message"])
        self.assertFalse(self.env_file.exists())
        code, payload = self.run_import(text, get, allow_unknown=True)
        self.assertEqual(code, 0)
        values = cmd_token.read_env_values(self.env_file.read_text(encoding="utf-8"))
        self.assertEqual((values["META_TOKEN"], values["META_TOKEN_APP_ID"]), (unknown, "777"))
        self.assertEqual(values["META_TOKEN_CATALOG"], eaah)
        self.assertEqual(values["META_TOKEN_EVENTS"], eaad)
        # an EAAB and an unknown token both want META_TOKEN
        self.env_file.unlink()
        text = f"{unknown}\n\n{fake_token('EAAB')}\n\n{self.COOKIES}\n"
        code, payload = self.run_import(text, get, allow_unknown=True)
        self.assertEqual(code, 1)
        self.assertIn("same variable (META_TOKEN)", payload["error"]["message"])
        self.assertFalse(self.env_file.exists())

    def test_one_bad_token_refuses_the_whole_batch(self) -> None:
        # the EAAH-prefixed token answers with the EAAG app: prefix and app id disagree
        code, payload = self.run_import(self.text(["EAAB", "EAAH"]), self.answers(apps={"EAAH": APP["EAAG"]}))
        self.assertEqual(code, 1)
        self.assertIn("prefix EAAH", payload["error"]["message"])
        self.assertFalse(self.env_file.exists())
        self.assertEqual(len(payload["data"]["tokens"]), 2)

    def test_tokens_of_different_users_are_refused(self) -> None:
        code, payload = self.run_import(self.text(["EAAB", "EAAH"]), self.answers(users={"EAAH": "2000"}))
        self.assertEqual(code, 1)
        self.assertIn("different users", payload["error"]["message"])
        self.assertFalse(self.env_file.exists())

    def test_as_ads_eaag_and_an_eaab_collide_on_meta_token(self) -> None:
        code, payload = self.run_import(self.text(["EAAB", "EAAG"]), as_ads=True)
        self.assertEqual(code, 1)
        self.assertIn("same variable (META_TOKEN)", payload["error"]["message"])

    def test_another_logins_shared_cookies_are_refused_once(self) -> None:
        self.env_file.write_text("META_COOKIES='c_user=555; xs=old'\n", encoding="utf-8")
        code, payload = self.run_import(self.text(["EAAB", "EAAI", "EAAH"]))
        self.assertEqual(code, 1)
        self.assertEqual(payload["error"]["message"].count("another login"), 1)
        self.assertEqual(self.env_file.read_text(encoding="utf-8"), "META_COOKIES='c_user=555; xs=old'\n")

    def test_dry_run_verifies_everything_and_writes_nothing(self) -> None:
        args = make_import_args(env_file=None)
        with env(META_PROXY="socks5h://u:p@h:1"), mock.patch.object(sys, "stdin", io.StringIO(self.text())), \
                mock.patch.object(metaops.graph, "get", side_effect=self.answers()), \
                contextlib.redirect_stdout(io.StringIO()):
            code, payload = cmd_token._token_import(metaops, args)
        self.assertEqual((code, payload["phase"]), (0, "dry_run"))
        self.assertEqual(len(self.seen), 10)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_no_verify_batch_makes_no_call_and_drops_stale_app_ids(self) -> None:
        self.env_file.write_text(f"META_TOKEN_CATALOG_APP_ID={APP['EAAH']}\n", encoding="utf-8")
        code, payload = self.run_import(self.text(["EAAB", "EAAH"]), self.answers(dead_on="EAAB"), no_verify=True)
        self.assertEqual(code, 0)
        self.assertEqual(self.seen, [])
        values = cmd_token.read_env_values(self.env_file.read_text(encoding="utf-8"))
        self.assertNotIn("META_TOKEN_CATALOG_APP_ID", values)
        self.assertEqual(values["META_TOKEN_CATALOG"], self.toks["EAAH"])
        self.assertEqual(payload["data"]["graph_calls"], 0)

    def test_without_cookies_one_line_names_only_the_classes_that_need_them(self) -> None:
        text = "\n\n".join(fake_token(p) for p in ("EAAB", "EAAd", "EAAH")) + "\n"
        code, payload = self.run_import(text)
        self.assertEqual(code, 0)
        cookie_lines = [w for w in payload["data"]["warnings"] if "no cookies in the paste" in w]
        self.assertEqual(len(cookie_lines), 1)
        self.assertIn("EAAB, EAAH", cookie_lines[0])
        self.assertNotIn("EAAd answer", cookie_lines[0])
        self.assertFalse(any("EAAd without cookies" in w for w in payload["data"]["warnings"]))
        text = "\n\n".join(fake_token(p) for p in ("EAAd",)) + "\n"
        self.env_file.unlink()
        code, payload = self.run_import(text)
        self.assertFalse(any("cookies" in w for w in payload["data"]["warnings"]))

    def test_an_eaad_among_others_shares_the_cookies_like_the_rest(self) -> None:
        code, payload = self.run_import(self.text(["EAAd", "EAAB"]))
        self.assertEqual(code, 0)
        values = cmd_token.read_env_values(self.env_file.read_text(encoding="utf-8"))
        self.assertEqual(values["META_COOKIES"], self.COOKIES)
        self.assertEqual(payload["data"]["cookies_variable"], "META_COOKIES")
        self.assertFalse(any("cookies" in w.lower() and "no cookies" in w for w in payload["data"]["warnings"]))

    def test_a_second_identical_paste_changes_nothing(self) -> None:
        text = self.text()
        self.run_import(text)
        first = self.env_file.read_bytes()
        code, payload = self.run_import(text)
        self.assertEqual(code, 0)
        self.assertEqual(self.env_file.read_bytes(), first)
        self.assertTrue(payload["data"]["written"]["unchanged"])


# -------------------------------------------------------------------------- c_user is not a secret

class OpenCookieRedactionTests(unittest.TestCase):
    COOKIES = "c_user=10000000; xs=24%3Asecretxs; datr=datrvalue; sb=sbvalue; fr=frvalue"

    def test_c_user_stays_readable_and_every_other_cookie_is_masked(self) -> None:
        with env(META_TOKEN=fake_token(), META_COOKIES=self.COOKIES):
            out = graph.redact("Sam Park (10000000) c_user=10000000 xs=24%3Asecretxs datr=datrvalue "
                               "sb=sbvalue fr=frvalue raw 24%3Asecretxs datrvalue sbvalue frvalue")
        self.assertIn("Sam Park (10000000)", out)
        self.assertIn("c_user=10000000", out)
        for secret in ("secretxs", "datrvalue", "sbvalue", "frvalue"):
            self.assertNotIn(secret, out)

    def test_the_whole_header_is_still_masked_when_it_appears_verbatim(self) -> None:
        with env(META_COOKIES=self.COOKIES):
            out = graph.redact(f"Cookie: {self.COOKIES}")
        self.assertNotIn("secretxs", out)
        self.assertIn("<COOKIES>", out)

    def test_per_token_cookie_variables_follow_the_same_rule(self) -> None:
        with env(META_COOKIES_CATALOG="c_user=42; xs=catalogsecret"):
            out = graph.redact("user 42 xs=catalogsecret")
        self.assertIn("user 42", out)
        self.assertNotIn("catalogsecret", out)

    def test_a_call_registers_cookie_secrets_but_not_the_user_id(self) -> None:
        session = RecordingSession()
        with env(META_TOKEN=fake_token()), mock.patch.object(graph, "session", return_value=session):
            graph.get("me", cookies="c_user=987654321; xs=registeredsecretxs")
        try:
            self.assertIn("registeredsecretxs", graph._KNOWN_SECRETS)
            self.assertNotIn("987654321", graph._KNOWN_SECRETS)
            self.assertIn("987654321", graph.redact("user 987654321"))
        finally:
            graph._KNOWN_SECRETS.discard("registeredsecretxs")

    def test_token_import_verification_does_not_register_the_user_id_either(self) -> None:
        token = fake_token()
        paste = cmd_token.Paste(token, "c_user=13572468; xs=importsecretxs")
        with env(META_PROXY="socks5h://u:p@h:1"), \
                mock.patch.object(metaops.graph, "get", return_value={"id": "13572468", "name": "N"}):
            cmd_token.verify(metaops, paste)
        try:
            self.assertIn("importsecretxs", graph._KNOWN_SECRETS)
            self.assertNotIn("13572468", graph._KNOWN_SECRETS)
        finally:
            graph._KNOWN_SECRETS.discard("importsecretxs")
            graph._KNOWN_SECRETS.discard(token)

    def test_doctor_rows_show_the_user_id(self) -> None:
        r = probe.Report()
        out = io.StringIO()
        with env(META_TOKEN=fake_token(), META_COOKIES=self.COOKIES), contextlib.redirect_stdout(out), \
                mock.patch.object(probe.graph, "get", return_value={"id": "10000000", "name": "Sam Park"}):
            probe.gate_identity(r)
        self.assertIn("Sam Park (10000000)", out.getvalue())
        self.assertNotIn("<COOKIE_VAL>", out.getvalue())
        self.assertNotIn("<TOKEN>", out.getvalue())

    def test_the_token_table_shows_ids_and_still_hides_the_secrets(self) -> None:
        eaab, eaah = fake_token("EAAB"), fake_token("EAAH")

        def fake_call(method, path, params=None, token_override=None, **kw):
            return {"id": "10000000", "name": "Sam Park"} if path == "me" else {"id": APP["EAAH"], "name": "Products"}

        r = probe.Report()
        out = io.StringIO()
        with env(META_TOKEN=eaab, META_TOKEN_CATALOG=eaah, META_COOKIES=self.COOKIES), \
                contextlib.redirect_stdout(out), mock.patch.object(probe.graph, "call", side_effect=fake_call):
            r.rows.append({"gate": "token identity", "state": probe.PASS, "detail": "",
                           "data": {"id": "10000000", "name": "Sam Park"}})
            probe.gate_token_table(r, ["ads_read", "catalog"], None)
        printed = out.getvalue()
        self.assertIn("Sam Park (10000000)", printed)
        self.assertNotIn("<TOKEN>", printed)
        self.assertNotIn(eaab, printed)
        self.assertNotIn("secretxs", printed)


class TokenCommandRegistrationTests(unittest.TestCase):
    def test_parser_has_token_import_with_every_flag(self) -> None:
        args = metaops.parser().parse_args([
            "token", "import", "--env-file", "x.env", "--name", "META_TOKEN_CATALOG", "--profile", "p",
            "--no-verify", "--allow-unknown", "--force", "--dry-run", "--as-ads", "--cookies-suffix"])
        self.assertEqual((args.command, args.token_action), ("token", "import"))
        self.assertEqual((args.env_file, args.name, args.profile), ("x.env", "META_TOKEN_CATALOG", "p"))
        self.assertTrue(all((args.no_verify, args.allow_unknown, args.force, args.dry_run, args.as_ads)))
        self.assertEqual(args.cookies_suffix, "auto")
        self.assertTrue(callable(args.handler))

    def test_global_profile_is_not_clobbered_by_the_subcommand_default(self) -> None:
        args = metaops.parser().parse_args(["--profile", "outer", "token", "import"])
        self.assertEqual(args.profile, "outer")
        self.assertEqual(metaops.parser().parse_args(["token", "import"]).profile, None)

    def test_token_is_not_a_workspace_lifecycle_command(self) -> None:
        self.assertNotIn("token", metaops.WORKSPACE_LIFECYCLE_COMMANDS)

    def test_main_runs_the_command_end_to_end_and_exits_nonzero_on_a_refusal(self) -> None:
        token = fake_token("EAAB")
        with tempfile.TemporaryDirectory() as td:
            envfile = pathlib.Path(td) / "meta.env"
            out, err = io.StringIO(), io.StringIO()

            def dead(path, params=None, context="", **kw):
                raise gerr(190, 460)

            with env(METAOPS_STATE_DIR=td), mock.patch.object(sys, "argv", ["metaops", "--json", "token", "import",
                                                                             "--env-file", str(envfile)]), \
                    mock.patch.object(sys, "stdin", io.StringIO(token)), \
                    mock.patch.object(metaops.graph, "get", side_effect=dead), \
                    mock.patch.object(metaops.meta_workspace, "discover_workspace", return_value=None), \
                    contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = metaops.main()
            payload = json.loads(out.getvalue().strip().splitlines()[-1])
            self.assertEqual(code, 1)
            self.assertFalse(payload["ok"])
            self.assertFalse(envfile.exists())
            self.assertNotIn(token, out.getvalue() + err.getvalue())


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Regression tests for the core-fix pass: Graph transport (path guard, retry policy, API
version, proxy message), receipt policy, doctor/assets invalidation, error envelopes, the
`pace` CLI, the assets-swap interval floor and activate --refresh-start.

Offline: no network, no credentials. Every test here fails on the pre-fix code."""

from __future__ import annotations
import os as _os, tempfile as _tempfile
_os.environ["METAOPS_PACE_DIR"] = _tempfile.mkdtemp(prefix="metaops-pace-test-")
_os.environ.setdefault("METAOPS_CREATE_GAP_HOURS", "0")

import contextlib
import datetime as dt
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

os.environ.setdefault("META_TOKEN", "TEST_TOKEN")

import activate  # noqa: E402
import graph  # noqa: E402
import metaops  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent


class _Resp:
    def __init__(self, payload, status=200, headers=None):
        self._payload = payload
        self.status_code = status
        self.ok = status < 400
        self.headers = headers or {}
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


def valid_spec(run_id: str = "core-fix") -> dict:
    return {
        "run_id": run_id,
        "account_id": "act_1",
        "page_id": "2",
        "pixel_id": "3",
        "currency": "USD",
        "campaign": {
            "name": "Campaign",
            "objective": "OUTCOME_LEADS",
            "special_ad_categories": [],
            "daily_budget_minor": 1000,
        },
        "adsets": [{
            "name": "Ad set",
            "optimization_goal": "OFFSITE_CONVERSIONS",
            "start_time": "2030-01-01T08:00:00+00:00",
            "targeting": {"geo_locations": {"countries": ["TR"]}, "advantage_audience": False},
            "ads": [{"name": "Ad", "creative": {
                "kind": "link_image", "image_hash": "test_hash", "link": "https://example.com/"}}],
        }],
    }


def iso_ago(seconds: float) -> str:
    return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=seconds)).isoformat(timespec="seconds")


class Fixture(unittest.TestCase):
    """Temp dir + isolated pacing dir + PLAN_DIR, plus a one-profile workspace."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.plans = self.root / "plans"
        env = mock.patch.dict(os.environ, {"METAOPS_PACE_DIR": str(self.root / "pace"),
                                           "METAOPS_PACE_OVERRIDE": ""})
        env.start()
        self.addCleanup(env.stop)
        plan_dir = mock.patch.object(metaops, "PLAN_DIR", self.plans)
        plan_dir.start()
        self.addCleanup(plan_dir.stop)

    def write_json(self, name: str, value: object) -> pathlib.Path:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def workspace(self):
        path = self.write_json("workspace.json", {
            "schema": metaops.meta_workspace.WORKSPACE_SCHEMA,
            "name": "core-fix",
            "api_version": graph.API_VERSION,
            "blocked_accounts": ["act_99"],
            "profiles": {"test": {
                "business_id": "10", "app_id": "11", "system_user_id": "12",
                "ad_account_id": "act_1", "page_id": "2", "dataset_id": "3",
                "currency": "USD", "timezone": "Europe/Warsaw",
            }},
            "defaults": {"profile": "test", "state_dir": ".metaops"},
        })
        return metaops.meta_workspace.load_workspace(str(path))

    def doctor_receipt(self, path: pathlib.Path, age: float, account: str = "act_1") -> pathlib.Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "schema": metaops.DOCTOR_SCHEMA, "checked_at": iso_ago(age),
            "api_version": graph.API_VERSION, "account_id": account,
            "page_id": "2", "dataset_id": "3", "business_id": "10",
        }), encoding="utf-8")
        return path

    def asset_receipt(self, path: pathlib.Path, workspace, age: float, scope: str = "core") -> pathlib.Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "schema": metaops.ASSET_RECEIPT_SCHEMA, "checked_at": iso_ago(age),
            "api_version": graph.API_VERSION, "workspace_sha": metaops.file_sha(workspace.path),
            "profile": "test", "scope": scope,
        }), encoding="utf-8")
        return path

    def bound_plan(self, age: float):
        """(args, plan, workspace) for a saved single plan whose receipts are `age` seconds old."""
        workspace = self.workspace()
        source = self.write_json("source.json", valid_spec())
        plan = metaops.build_single_plan(source, str(self.root / "state.json"))
        snapshot = self.root / "snapshot.json"
        plan["spec_path"] = str(snapshot.resolve())
        metaops.atomic_json(snapshot, metaops.load_launch_spec(source))
        doctor = self.doctor_receipt(self.root / "doctor.json", age)
        assets = self.asset_receipt(self.root / "assets.json", workspace, age)
        plan.update({
            "workspace_path": str(workspace.path), "workspace_sha": metaops.file_sha(workspace.path),
            "profile": "test",
            "doctor_receipt": str(doctor.resolve()), "doctor_sha": metaops.file_sha(doctor),
            "asset_receipt": str(assets.resolve()), "asset_sha": metaops.file_sha(assets),
        })
        plan_path = self.root / "plan.json"
        metaops.atomic_json(plan_path, plan)
        args = types.SimpleNamespace(
            plan=str(plan_path), timeout=10, workspace_obj=workspace, profile="test",
            confirm="SPEND", confirm_ui="REVIEWED", refresh_start=None,
        )
        return args, plan, workspace


# --- 1. write-guard bypass ---------------------------------------------------------------


class PathGuardTests(unittest.TestCase):
    BAD_PATHS = [
        "act_1/../act_99/campaigns",
        "123/../act_99/campaigns",
        "act_1/./campaigns",
        "act_1//campaigns",
        "act_1/campaigns/",
        "act_1/%2e%2e/act_99/campaigns",
        "act_1/%2E%2E%2Fact_99/campaigns",
        "act_1/campaigns?fields=id",
        "act_1/campaigns#frag",
        "act_1\\..\\act_99\\campaigns",
        "act_1/campaigns\n",
        "act_1/cam paigns",
        "act_1/campaigns\x00",
        "v26.0/act_1/../act_99/campaigns",
        "https://graph.facebook.com/v26.0/act_1/../act_99/campaigns",
        "https://graph.facebook.com/v26.0/act_1/%2e%2e/act_99/campaigns",
    ]

    def setUp(self) -> None:
        patches = [
            mock.patch.object(graph, "_WRITE_ACCOUNTS", {"act_1"}),
            mock.patch.object(graph, "_WRITE_CAPABILITY_LOADED", True),
            mock.patch.dict(os.environ, {"META_TOKEN": "TEST_TOKEN",
                                         "METAOPS_PACE_DIR": _tempfile.mkdtemp(prefix="guard-")}),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        session = mock.patch.object(graph, "session")
        self.session = session.start()
        self.addCleanup(session.stop)
        self.session.return_value.request.return_value = _Resp({"id": "1"})

    def test_dot_segment_and_encoded_paths_never_reach_the_wire(self) -> None:
        for path in self.BAD_PATHS:
            with self.subTest(path=path, method="POST"):
                with self.assertRaises(SystemExit):
                    graph.post(path, {"name": "x"})
            with self.subTest(path=path, method="GET"):
                with self.assertRaises(SystemExit):
                    graph.get(path)
        self.session.return_value.request.assert_not_called()

    def test_bypass_would_have_reached_an_unauthorized_account(self) -> None:
        # requests normalises this to /act_99/campaigns; the guard must refuse it up front.
        with self.assertRaises(SystemExit) as caught:
            graph.post("act_1/../act_99/campaigns", {"name": "x"})
        self.assertIn("refusing Graph path", str(caught.exception))
        with self.assertRaises(SystemExit):
            graph.require_write_authority("POST", "act_1/../act_99/campaigns")

    def test_normal_paths_still_pass(self) -> None:
        for path in ("act_1/campaigns", "/act_1/campaigns", "v26.0/act_1/campaigns",
                     "https://graph.facebook.com/v26.0/act_1/campaigns"):
            with self.subTest(path=path):
                self.session.return_value.request.reset_mock()
                self.assertEqual(graph.post(path, {"name": "x"}), {"id": "1"})
                self.session.return_value.request.assert_called_once()
        self.session.return_value.request.reset_mock()
        graph.get("me")
        self.assertEqual(self.session.return_value.request.call_args.args[1], f"{graph.BASE}/me")

    def test_unauthorized_account_is_still_refused(self) -> None:
        with self.assertRaisesRegex(SystemExit, "does not authorize.*act_99"):
            graph.post("act_99/campaigns", {"name": "x"})


# --- 2. transient errors on creates ---------------------------------------------------------


class RetryPolicyTests(unittest.TestCase):
    TRANSIENT = {"error": {"code": 2, "message": "Service temporarily unavailable",
                           "is_transient": True}}

    def setUp(self) -> None:
        for patch in (
            mock.patch.object(graph, "require_write_authority", lambda *a, **k: None),
            mock.patch.dict(os.environ, {"META_TOKEN": "TEST_TOKEN", "METAOPS_PACE_OVERRIDE": "",
                                         "METAOPS_PACE_DIR": _tempfile.mkdtemp(prefix="retry-")}),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        graph._LAST_ACCOUNT = None

    def _session(self, *responses):
        sess = mock.Mock()
        sess.request.side_effect = list(responses)
        return mock.patch.object(graph, "session", return_value=sess), sess

    def test_transient_error_on_a_create_is_not_resent(self) -> None:
        patcher, sess = self._session(*[_Resp(self.TRANSIENT, 500)] * 3)
        with patcher, mock.patch.object(graph.time, "sleep") as sleep:
            with self.assertRaises(graph.GraphError) as caught:
                graph.post("act_1/campaigns", {"name": "x"})
        self.assertEqual(sess.request.call_count, 1)
        sleep.assert_not_called()
        err = caught.exception
        self.assertTrue(err.is_transient)
        self.assertTrue(err.outcome_unknown)
        self.assertTrue(err.as_dict()["outcome_unknown"])
        self.assertIn("outcome unknown", str(err))

    def test_transient_error_is_retried_for_idempotent_calls_and_gets(self) -> None:
        for label, call in (
            ("idempotent post", lambda: graph.post("1/status", {"status": "ACTIVE"}, idempotent=True)),
            ("get", lambda: graph.get("act_1/campaigns")),
        ):
            with self.subTest(label):
                patcher, sess = self._session(_Resp(self.TRANSIENT, 500), _Resp({"id": "ok"}))
                with patcher, mock.patch.object(graph.time, "sleep") as sleep:
                    self.assertEqual(call(), {"id": "ok"})
                self.assertEqual(sess.request.call_count, 2)
                sleep.assert_called_once()

    def test_idempotent_transient_error_surfaces_after_retries(self) -> None:
        patcher, sess = self._session(*[_Resp(self.TRANSIENT, 500)] * 5)
        with patcher, mock.patch.object(graph.time, "sleep"):
            with self.assertRaises(graph.GraphError):
                graph.post("1/status", {"status": "ACTIVE"}, idempotent=True, retries=2)
        self.assertEqual(sess.request.call_count, 3)

    def test_plain_rejection_stays_a_known_outcome(self) -> None:
        rejected = {"error": {"code": 100, "error_subcode": 33, "message": "bad param"}}
        patcher, sess = self._session(_Resp(rejected, 400))
        with patcher:
            with self.assertRaises(graph.GraphError) as caught:
                graph.post("act_1/campaigns", {"name": "x"})
        self.assertFalse(caught.exception.outcome_unknown)
        self.assertNotIn("outcome unknown", str(caught.exception))
        self.assertEqual(sess.request.call_count, 1)


# --- 5. META_API_VERSION ------------------------------------------------------------------


class ApiVersionTests(unittest.TestCase):
    def _import(self, version: str | None):
        env = {k: v for k, v in os.environ.items() if k != "META_API_VERSION"}
        env["PYTHONPATH"] = str(HERE)
        if version is not None:
            env["META_API_VERSION"] = version
        return subprocess.run(
            [sys.executable, "-c", "import graph; print(graph.BASE)"],
            env=env, cwd=HERE, text=True, capture_output=True, check=False, timeout=60,
        )

    def test_resolve_accepts_only_vNN_N(self) -> None:
        for good in ("v26.0", "v25.0", "v27.1", "v9.0", " v26.0 "):
            self.assertRegex(graph.resolve_api_version(good), r"^v\d+\.\d+$")
        self.assertEqual(graph.resolve_api_version(None), graph.DEFAULT_API_VERSION)
        self.assertEqual(graph.resolve_api_version(""), graph.DEFAULT_API_VERSION)
        for bad in ("26.0", "v26", "v26.0.1", "V26.0", "latest", "v26.0/../x", "v26.0?x=1", "v26.a"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    graph.resolve_api_version(bad)

    def test_window_warning(self) -> None:
        self.assertIsNone(graph.api_version_window_warning("v26.0"))
        self.assertIsNone(graph.api_version_window_warning("v25.0"))
        self.assertIn("outside the supported window", graph.api_version_window_warning("v24.0"))
        self.assertIn("outside the supported window", graph.api_version_window_warning("v27.0"))

    def test_import_time_behaviour(self) -> None:
        ok = self._import("v26.0")
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertEqual(ok.stdout.strip(), "https://graph.facebook.com/v26.0")
        self.assertNotIn("supported window", ok.stderr)
        self.assertEqual(self._import(None).stdout.strip(), "https://graph.facebook.com/v26.0")
        old = self._import("v24.0")
        self.assertEqual(old.returncode, 0, old.stderr)
        self.assertEqual(old.stdout.strip(), "https://graph.facebook.com/v24.0")
        self.assertIn("outside the supported window", old.stderr)
        bad = self._import("v26.0/../x")
        self.assertNotEqual(bad.returncode, 0)
        self.assertIn("META_API_VERSION", bad.stderr)
        self.assertNotIn("graph.facebook.com", bad.stdout)


# --- 12. proxy refusal message --------------------------------------------------------------


class ProxyMessageTests(unittest.TestCase):
    def test_missing_proxy_message_names_the_workspace_setting(self) -> None:
        with mock.patch.dict(os.environ, {"META_PROXY": "", "META_ALLOW_NO_PROXY": ""}):
            with self.assertRaises(SystemExit) as caught:
                graph._session()
        message = str(caught.exception.code)
        self.assertIn("defaults.allow_no_proxy", message)
        self.assertIn("metaops", message)
        self.assertIn("META_ALLOW_NO_PROXY=1", message)


# --- 6. receipt freshness policy --------------------------------------------------------------


class ReceiptAgePolicyTests(Fixture):
    STALE = 3 * 86400

    def test_read_side_commands_ignore_receipt_age(self) -> None:
        args, plan, workspace = self.bound_plan(self.STALE)
        self.assertEqual(metaops.validate_single_plan(plan, workspace, "test")[0].name, "snapshot.json")
        code, payload = metaops.command_status(args)
        self.assertEqual((code, payload["ok"]), (0, True))
        with self.assertRaisesRegex(metaops.MetaOpsError, "state does not exist"):
            metaops.command_verify(args)

    def test_media_ignores_receipt_age(self) -> None:
        workspace = self.workspace()
        self.doctor_receipt(self.plans / "doctor.act_1.json", self.STALE)
        self.asset_receipt(self.plans / "assets.test.core.json", workspace, self.STALE)
        image = self.root / "a.jpg"
        image.write_bytes(b"x")
        manifest = self.root / "out" / "media.json"

        def fake_child(script, argv, _timeout):
            metaops.atomic_json(manifest, {"account_id": "act_1"})
            return metaops.ChildResult([script, *argv], 0, "", "")

        args = types.SimpleNamespace(workspace_obj=workspace, profile="test", image=[str(image)],
                                     video=[], manifest=str(manifest), timeout=10)
        with mock.patch.object(metaops, "run_child", side_effect=fake_child):
            code, payload = metaops.command_media(args)
        self.assertEqual(code, 0, payload)

    def test_apply_and_activate_enforce_receipt_age(self) -> None:
        args, plan, workspace = self.bound_plan(self.STALE)
        with self.assertRaisesRegex(metaops.MetaOpsError, "stale"):
            metaops.validate_single_plan(plan, workspace, "test", check_age=True)
        with mock.patch.object(metaops, "run_child") as child:
            with self.assertRaisesRegex(metaops.MetaOpsError, "stale"):
                metaops.command_apply(args)
            with self.assertRaisesRegex(metaops.MetaOpsError, "stale"):
                metaops.command_activate(args)
        child.assert_not_called()

    def test_fresh_receipts_pass_the_enforcing_commands(self) -> None:
        _, plan, workspace = self.bound_plan(60)
        metaops.validate_single_plan(plan, workspace, "test", check_age=True)

    def test_env_override_still_extends_the_ttl(self) -> None:
        _, plan, workspace = self.bound_plan(self.STALE)
        with mock.patch.object(metaops, "DOCTOR_MAX_AGE", 10 * 86400):
            metaops.validate_single_plan(plan, workspace, "test", check_age=True)

    def test_bindings_are_enforced_even_when_age_is_ignored(self) -> None:
        workspace = self.workspace()
        wrong_account = self.doctor_receipt(self.root / "d2.json", self.STALE, account="act_2")
        spec = {"account_id": "act_1", "page_id": "2", "pixel_id": "3"}
        with self.assertRaisesRegex(metaops.MetaOpsError, "account_id mismatch"):
            metaops.require_doctor(spec, str(wrong_account), "10")
        assets = self.asset_receipt(self.root / "a2.json", workspace, self.STALE)
        with self.assertRaisesRegex(metaops.MetaOpsError, "workspace/profile changed"):
            metaops.validate_asset_receipt(assets, workspace, "other-profile", False)
        broken = self.root / "d3.json"
        broken.write_text(json.dumps({"schema": metaops.DOCTOR_SCHEMA, "checked_at": "not-a-date",
                                      "account_id": "act_1"}), encoding="utf-8")
        with self.assertRaisesRegex(metaops.MetaOpsError, "checked_at"):
            metaops.require_doctor(spec, str(broken), "10")

    def test_bulk_create_and_activate_enforce_age_status_does_not(self) -> None:
        args = types.SimpleNamespace(plan="p", timeout=10, workspace_obj=None, verify=False,
                                     dlo_tested=False, confirm="SPEND", confirm_ui="REVIEWED",
                                     account="act_1", refresh_start=None, profile=None)
        stop = metaops.MetaOpsError("stop here")
        bulk_plan = {"schema": metaops.BULK_PLAN_SCHEMA, "run_id": "r", "items": []}
        with (
            mock.patch.object(metaops, "load_plan", return_value=(self.root / "p.json", bulk_plan)),
            mock.patch.object(metaops, "validate_bulk_plan", side_effect=stop) as validate,
        ):
            for command in (metaops.command_bulk_apply, metaops.command_bulk_activate):
                validate.reset_mock()
                with self.assertRaises(metaops.MetaOpsError):
                    command(args)
                self.assertIs(validate.call_args.kwargs.get("check_age"), True, command.__name__)
            validate.reset_mock()
            with self.assertRaises(metaops.MetaOpsError):
                metaops.command_status(args)
            self.assertFalse(validate.call_args.kwargs.get("check_age", False))


# --- 7. failed doctor / assets verify invalidate the previous receipt ------------------------------


class ReceiptInvalidationTests(Fixture):
    def doctor_args(self, workspace, **over):
        base = dict(workspace_obj=workspace, profile="test", account=None, page=None, dataset=None,
                    business=None, whoami=False, create_pbia=False, attach_pixel=False,
                    scope="core", timeout=10)
        base.update(over)
        return types.SimpleNamespace(**base)

    def test_failed_doctor_deletes_the_previous_ok_receipt(self) -> None:
        workspace = self.workspace()
        receipt = self.doctor_receipt(self.plans / "doctor.act_1.json", 60)
        other = self.doctor_receipt(self.plans / "doctor.act_2.json", 60, account="act_2")
        failed = metaops.ChildResult(["probe.py"], 1, "", "code=190 subcode=None: expired (trace T1)")
        with mock.patch.object(metaops, "run_child", return_value=failed):
            code, payload = metaops.command_doctor(self.doctor_args(workspace))
        self.assertEqual(code, 1)
        self.assertFalse(payload["ok"])
        self.assertFalse(receipt.exists())
        self.assertTrue(other.exists())
        self.assertEqual(payload["data"]["receipt_invalidated"], str(receipt.resolve()))

    def test_doctor_that_raises_also_deletes_the_receipt(self) -> None:
        workspace = self.workspace()
        receipt = self.doctor_receipt(self.plans / "doctor.act_1.json", 60)
        with mock.patch.object(metaops, "run_child", side_effect=metaops.MetaOpsError("timed out")):
            with self.assertRaises(metaops.MetaOpsError):
                metaops.command_doctor(self.doctor_args(workspace))
        self.assertFalse(receipt.exists())

    def test_failed_provisioning_check_deletes_the_receipt(self) -> None:
        workspace = self.workspace()
        receipt = self.doctor_receipt(self.plans / "doctor.act_1.json", 60)
        ok_child = metaops.ChildResult(["probe.py"], 0, "", "")
        with (
            mock.patch.object(metaops, "run_child", return_value=ok_child),
            mock.patch.object(metaops, "require_provisioning_admin",
                              side_effect=metaops.MetaOpsError("not ADMIN")),
        ):
            with self.assertRaises(metaops.MetaOpsError):
                metaops.command_doctor(self.doctor_args(workspace, scope="provisioning"))
        self.assertFalse(receipt.exists())

    def test_passing_doctor_rewrites_the_receipt_and_whoami_touches_nothing(self) -> None:
        workspace = self.workspace()
        receipt = self.doctor_receipt(self.plans / "doctor.act_1.json", 5 * 86400)
        ok_child = metaops.ChildResult(["probe.py"], 0, "", "")
        with mock.patch.object(metaops, "run_child", return_value=ok_child):
            code, _ = metaops.command_doctor(self.doctor_args(workspace))
        self.assertEqual(code, 0)
        fresh = json.loads(receipt.read_text(encoding="utf-8"))
        self.assertLess(
            (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(fresh["checked_at"])).total_seconds(), 120)
        bad_child = metaops.ChildResult(["probe.py"], 1, "", "boom")
        with mock.patch.object(metaops, "run_child", return_value=bad_child):
            metaops.command_doctor(self.doctor_args(workspace, whoami=True))
        self.assertTrue(receipt.exists(), "--whoami has no account receipt to invalidate")

    def assets_args(self, workspace, scope="all"):
        return types.SimpleNamespace(workspace_obj=workspace, profile="test", scope=scope, timeout=10)

    def report(self, failed, scope="all"):
        return {"profile": "test", "scope": scope, "ready": not failed, "failed_checks": failed,
                "checks": [], "product_sets": [], "token_kind": "system_user"}

    def two_receipts(self, workspace):
        return (self.asset_receipt(self.plans / "assets.test.core.json", workspace, 60, "core"),
                self.asset_receipt(self.plans / "assets.test.all.json", workspace, 60, "all"))

    def test_failed_core_check_deletes_both_receipts(self) -> None:
        workspace = self.workspace()
        core, everything = self.two_receipts(workspace)
        with mock.patch.object(metaops.asset_graph, "verify_assets",
                               return_value=self.report(["account_active"])):
            code, payload = metaops.command_assets_verify(self.assets_args(workspace))
        self.assertEqual(code, 1)
        self.assertFalse(core.exists())
        self.assertFalse(everything.exists())
        self.assertEqual(len(payload["data"]["receipts_invalidated"]), 2)

    def test_catalog_only_failure_deletes_only_the_all_receipt(self) -> None:
        workspace = self.workspace()
        core, everything = self.two_receipts(workspace)
        with mock.patch.object(metaops.asset_graph, "verify_assets",
                               return_value=self.report(["product_set:main"])):
            code, _ = metaops.command_assets_verify(self.assets_args(workspace))
        self.assertEqual(code, 1)
        self.assertTrue(core.exists())
        self.assertFalse(everything.exists())

    def test_failed_core_scope_run_deletes_both_receipts(self) -> None:
        workspace = self.workspace()
        core, everything = self.two_receipts(workspace)
        with mock.patch.object(metaops.asset_graph, "verify_assets",
                               return_value=self.report(["page_instagram"], "core")):
            metaops.command_assets_verify(self.assets_args(workspace, "core"))
        self.assertFalse(core.exists())
        self.assertFalse(everything.exists())

    def test_assets_verify_that_raises_deletes_receipts(self) -> None:
        workspace = self.workspace()
        core, everything = self.two_receipts(workspace)
        boom = graph.GraphError(400, {"error": {"code": 190, "message": "expired"}}, "ctx")
        with mock.patch.object(metaops.asset_graph, "verify_assets", side_effect=boom):
            with self.assertRaises(metaops.MetaOpsError):
                metaops.command_assets_verify(self.assets_args(workspace))
        self.assertFalse(core.exists())
        self.assertFalse(everything.exists())

    def test_passing_assets_verify_writes_the_receipt(self) -> None:
        workspace = self.workspace()
        with mock.patch.object(metaops.asset_graph, "verify_assets", return_value=self.report([])):
            code, payload = metaops.command_assets_verify(self.assets_args(workspace, "core"))
        self.assertEqual(code, 0)
        self.assertTrue((self.plans / "assets.test.core.json").is_file())
        self.assertNotIn("receipts_invalidated", payload["data"])


# --- 8. graph_error / envelopes ------------------------------------------------------------------


class GraphErrorParsingTests(unittest.TestCase):
    def test_last_error_in_the_log_wins(self) -> None:
        log = (
            "  ! transient (2) — retrying in 2.1s\n"
            "[read a] code=17 subcode=2446079: too many calls (trace AAA)\n"
            "  x campaign: CREATE FAILED\n"
            "      [create campaign] code=-1 subcode=None: proxy died (trace BBB) [outcome unknown]\n"
        )
        got = metaops.graph_error(log)
        self.assertEqual(got["code"], -1)
        self.assertIsInstance(got["code"], int)
        self.assertIsNone(got["subcode"])
        self.assertEqual(got["fbtrace_id"], "BBB")
        self.assertTrue(got["outcome_unknown"])

    def test_known_rejection_is_not_outcome_unknown(self) -> None:
        got = metaops.graph_error("[x] code=100 subcode=33: bad (trace T9)\nnothing else")
        self.assertEqual((got["code"], got["subcode"], got["fbtrace_id"]), (100, 33, "T9"))
        self.assertFalse(got["outcome_unknown"])

    def test_unknown_outcome_line_printed_by_launch_counts(self) -> None:
        log = ("  x campaign: CREATE FAILED\n      [c] code=1 subcode=None: oops (trace Z)\n"
               "      Outcome UNKNOWN — campaign may exist in the account.\n")
        self.assertTrue(metaops.graph_error(log)["outcome_unknown"])

    def test_text_without_a_graph_error(self) -> None:
        self.assertIsNone(metaops.graph_error("plain failure"))

    def test_graph_error_text_round_trips_through_the_parser(self) -> None:
        err = graph.GraphError(0, {"error": {"message": "proxy died", "code": -1, "is_transient": True,
                                             "fbtrace_id": "TR"}}, "create campaign")
        got = metaops.graph_error(f"noise\n{err}\n")
        self.assertEqual((got["code"], got["outcome_unknown"]), (-1, True))


class MainEnvelopeTests(unittest.TestCase):
    def run_main(self, argv, handler, json_mode=True):
        out, err = io.StringIO(), io.StringIO()
        argv = ["metaops.py", *(["--json"] if json_mode else []), *argv]
        with (
            mock.patch.object(sys, "argv", argv),
            mock.patch.object(metaops, "configure_workspace", return_value=None),
            mock.patch.object(metaops, "command_pace", side_effect=handler),
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(err),
        ):
            code = metaops.main()
        return code, out.getvalue(), err.getvalue()

    def test_in_process_graph_error_is_kind_graph_with_as_dict(self) -> None:
        exc = graph.GraphError(400, {"error": {"code": 100, "error_subcode": 33, "message": "bad",
                                               "fbtrace_id": "TR1"}}, "ctx")
        code, out, _ = self.run_main(["pace"], exc)
        payload = json.loads(out)
        self.assertEqual(len(out.splitlines()), 1)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["kind"], "graph")
        detail = payload["error"]["graph"]
        self.assertEqual((detail["code"], detail["subcode"], detail["fbtrace_id"]), (100, 33, "TR1"))
        self.assertFalse(detail["outcome_unknown"])
        self.assertFalse(payload["error"]["outcome_unknown"])
        self.assertEqual(code, 1)

    def test_unknown_outcome_is_carried_and_hints_reconcile(self) -> None:
        exc = graph.GraphError(0, {"error": {"message": "proxy died", "code": -1, "is_transient": True}}, "c")
        _, out, _ = self.run_main(["pace"], exc)
        payload = json.loads(out)
        self.assertTrue(payload["error"]["outcome_unknown"])
        self.assertEqual(payload["error"]["graph"]["code"], -1)
        self.assertIn("reconcile", payload["next_action"].lower())

    def test_system_exit_message_becomes_a_json_envelope(self) -> None:
        code, out, _ = self.run_main(["pace"], SystemExit("META_PROXY is not set. Use the workspace."))
        payload = json.loads(out)
        self.assertEqual(code, 2)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["kind"], "precondition")
        self.assertIn("META_PROXY is not set", payload["error"]["message"])

    def test_missing_token_inside_a_handler_becomes_a_json_envelope(self) -> None:
        def handler(_args):
            graph.token()

        with mock.patch.dict(os.environ):
            os.environ.pop("META_TOKEN", None)
            code, out, _ = self.run_main(["pace"], handler)
        self.assertEqual(code, 2)
        self.assertIn("META_TOKEN is not set", json.loads(out)["error"]["message"])

    def test_pacing_refusal_gets_its_own_kind_and_integer_exit_is_kept(self) -> None:
        _, out, _ = self.run_main(["pace"], graph.PacingError("act_1: wait 120 min"))
        self.assertEqual(json.loads(out)["error"]["kind"], "pacing")
        code, out, _ = self.run_main(["pace"], SystemExit(3))
        self.assertEqual(code, 3)
        self.assertFalse(json.loads(out)["ok"])

    def test_clean_system_exit_still_exits(self) -> None:
        for clean in (0, None):
            with self.assertRaises(SystemExit):
                self.run_main(["pace"], SystemExit(clean))

    def test_human_mode_prints_the_failure_instead_of_a_bare_exit(self) -> None:
        code, out, err = self.run_main(["pace"], SystemExit("META_TOKEN is not set."), json_mode=False)
        self.assertEqual(code, 2)
        self.assertIn("FAILED", out)
        self.assertIn("META_TOKEN is not set", err)


# --- 9. pace CLI and the assets-swap interval floor -----------------------------------------------


class PaceCliTests(Fixture):
    def pace(self, clear=None):
        return metaops.command_pace(types.SimpleNamespace(clear_cooldown=clear))

    def test_clear_cooldown_normalises_the_id_and_prints_state_after(self) -> None:
        graph._set_cooldown("act_123", 1800, "test")
        _, before = self.pace()
        self.assertIn("act_123", before["data"]["cooldowns"])
        _, after = self.pace(clear="123")
        self.assertNotIn("act_123", after["data"]["cooldowns"])
        self.assertEqual(after["data"]["cleared"], {"key": "act_123", "existed": True})
        self.assertNotIn("act_123", graph._pace_load().get("cooldown", {}))

    def test_clear_cooldown_accepts_act_prefix_star_and_reports_a_miss(self) -> None:
        graph._set_cooldown("act_5", 1800, "a")
        graph._set_cooldown("*", 1800, "global")
        _, out = self.pace(clear="act_5")
        self.assertEqual(out["data"]["cleared"]["existed"], True)
        self.assertNotIn("act_5", out["data"]["cooldowns"])
        _, out = self.pace(clear="*")
        self.assertEqual(out["data"]["cooldowns"], {})
        _, out = self.pace(clear="777")
        self.assertEqual(out["data"]["cleared"], {"key": "act_777", "existed": False})

    def test_clear_cooldown_rejects_garbage(self) -> None:
        with self.assertRaises(metaops.MetaOpsError):
            self.pace(clear="not-an-account")


class SwapIntervalFloorTests(Fixture):
    def args(self, interval, **over):
        base = dict(workspace_obj=self.workspace(), profile="test", map="a1=T01", confirm="SWAP",
                    dry_run=False, timeout=10, watch=True, interval=interval, max_wait=0,
                    paused_ok=False, allow_message=False, revert=False)
        base.update(over)
        return types.SimpleNamespace(**base)

    def test_interval_under_300_is_refused(self) -> None:
        for interval in (0, 1, 60, 299):
            with self.subTest(interval=interval):
                with self.assertRaisesRegex(metaops.MetaOpsError, "300"):
                    metaops.command_assets_swap(self.args(interval))

    def test_interval_at_or_above_300_passes_the_floor(self) -> None:
        for interval in (300, 600):
            with self.subTest(interval=interval):
                # the run then stops on the unknown product-set alias: the floor did not fire
                with self.assertRaisesRegex(metaops.MetaOpsError, "unknown product-set alias"):
                    metaops.command_assets_swap(self.args(interval))

    def test_pace_override_lifts_the_floor(self) -> None:
        with mock.patch.dict(os.environ, {"METAOPS_PACE_OVERRIDE": "1"}):
            with self.assertRaisesRegex(metaops.MetaOpsError, "unknown product-set alias"):
                metaops.command_assets_swap(self.args(10))

    def test_cli_default_is_the_floor(self) -> None:
        parsed = metaops.parser().parse_args(
            ["assets", "swap", "--map", "a1=T01", "--confirm", "SWAP"])
        self.assertEqual(parsed.interval, metaops.MIN_SWAP_INTERVAL_S)
        self.assertEqual(metaops.MIN_SWAP_INTERVAL_S, 300)


# --- 11. activate --refresh-start records start_overrides ---------------------------------------------


class RefreshStartTests(Fixture):
    REFRESH = "2099-01-01T08:00:00+00:00"

    def run_activate(self, post):
        state_path = self.root / "state.json"
        state_path.write_text(json.dumps({
            "objects": {"campaign": "100", "adset[0]": "200", "adset[1]": "201", "ad[0.0]": "300"},
            "in_flight": {}, "errors": [], "spec_sha": "abc", "spec_account": "act_1",
        }), encoding="utf-8")
        argv = ["activate.py", "--state", str(state_path), "--confirm", "SPEND",
                "--refresh-start", self.REFRESH]
        with (
            mock.patch.object(sys, "argv", argv),
            mock.patch.object(activate.graph, "require_write_authority"),
            mock.patch.object(activate, "check_receipt", return_value=None),
            mock.patch.object(activate.graph, "get",
                              return_value={"name": "C", "status": "PAUSED", "effective_status": "PAUSED"}),
            mock.patch.object(activate.graph, "post", side_effect=post),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            code = activate.main()
        return code, state_path

    def test_every_redated_adset_is_recorded_for_verify(self) -> None:
        code, state_path = self.run_activate(lambda *a, **k: {"success": True})
        self.assertEqual(code, 0)
        state = json.loads(state_path.read_text(encoding="utf-8"))
        # verify.py reads state["start_overrides"]["adset[i]"] (falling back to the spec)
        self.assertEqual(state["start_overrides"], {"adset[0]": self.REFRESH, "adset[1]": self.REFRESH})
        self.assertEqual(state["objects"]["campaign"], "100")
        self.assertEqual(state["spec_sha"], "abc")
        self.assertEqual(state_path.stat().st_mode & 0o777, 0o600)

    def test_an_adset_that_kept_its_old_start_is_not_recorded(self) -> None:
        def post(obj_id, data, **kwargs):
            if "start_time" in data and obj_id == "201":
                raise graph.GraphError(400, {"error": {"code": 100, "error_subcode": 1487057,
                                                       "message": "start time already active"}}, "x")
            return {"success": True}

        code, state_path = self.run_activate(post)
        self.assertEqual(code, 0)
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["start_overrides"], {"adset[0]": self.REFRESH})


class ReceiptSurvivesThrottleTests(unittest.TestCase):
    """A throttle / local cooldown proves nothing about the account: it must not void a passing receipt."""

    def test_cooldown_and_throttle_errors_prove_nothing(self) -> None:
        cooldown = graph.CooldownError("act_1", 12.0, "doctor")
        throttle = graph.GraphError(400, {"error": {"code": 17, "message": "User request limit reached"}}, "x")
        bucket = graph.GraphError(400, {"error": {"code": 80004, "message": "too many calls"}}, "x")
        for exc in (cooldown, throttle, bucket):
            self.assertTrue(metaops._proves_nothing(exc), repr(exc))

    def test_a_definite_error_still_voids_the_receipt(self) -> None:
        rejected = graph.GraphError(400, {"error": {"code": 100, "error_subcode": 1487390, "message": "bad"}}, "x")
        self.assertFalse(metaops._proves_nothing(rejected))
        self.assertFalse(metaops._proves_nothing(RuntimeError("boom")))


if __name__ == "__main__":
    unittest.main()

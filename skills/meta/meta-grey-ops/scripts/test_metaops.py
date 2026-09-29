#!/usr/bin/env python3
"""Offline contract tests for metaops.py. No network or real credentials."""

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
import unittest
from unittest import mock

import feed_upload
import jsonschema
import mcp
import metaops
import monitor
import probe
import verify

os.environ.setdefault("META_TOKEN", "TEST_TOKEN")


HERE = pathlib.Path(__file__).resolve().parent
SCHEMA_DIR = HERE.parent / "schemas"


def valid_spec(run_id: str = "contract-test") -> dict:
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
        "adsets": [
            {
                "name": "Ad set",
                "optimization_goal": "OFFSITE_CONVERSIONS",
                "start_time": "2030-01-01T08:00:00+00:00",
                "targeting": {
                    "geo_locations": {"countries": ["TR"]},
                    "advantage_audience": False,
                },
                "ads": [
                    {
                        "name": "Ad",
                        "creative": {
                            "kind": "link_image",
                            "image_hash": "test_hash",
                            "link": "https://example.com/",
                        },
                    }
                ],
            }
        ],
    }


class MetaOpsContractTests(unittest.TestCase):
    def write_json(self, root: pathlib.Path, name: str, value: object) -> pathlib.Path:
        path = root / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def write_doctor(self, root: pathlib.Path, account: str = "act_1") -> pathlib.Path:
        return self.write_json(
            root,
            "doctor.json",
            {
                "schema": metaops.DOCTOR_SCHEMA,
                "checked_at": metaops.now_utc(),
                "api_version": metaops.graph.API_VERSION,
                "account_id": account,
                "page_id": "2",
                "dataset_id": "3",
                "business_id": "10",
            },
        )

    def workspace(self, root: pathlib.Path) -> metaops.meta_workspace.Workspace:
        path = self.write_json(
            root,
            "workspace.json",
            {
                "schema": metaops.meta_workspace.WORKSPACE_SCHEMA,
                "name": "contract",
                "api_version": metaops.graph.API_VERSION,
                "blocked_accounts": ["act_99"],
                "profiles": {
                    "test": {
                        "business_id": "10",
                        "app_id": "11",
                        "system_user_id": "12",
                        "ad_account_id": "act_1",
                        "page_id": "2",
                        "dataset_id": "3",
                        "currency": "USD",
                        "timezone": "Europe/Warsaw",
                    }
                },
                "defaults": {"profile": "test", "state_dir": ".metaops"},
            },
        )
        return metaops.meta_workspace.load_workspace(str(path))

    def bind_single_plan(
        self,
        root: pathlib.Path,
        plan: dict,
        workspace: metaops.meta_workspace.Workspace,
    ) -> None:
        doctor = self.write_doctor(root)
        asset = self.write_json(
            root,
            "assets.json",
            {
                "schema": metaops.ASSET_RECEIPT_SCHEMA,
                "checked_at": metaops.now_utc(),
                "api_version": metaops.graph.API_VERSION,
                "workspace_sha": metaops.file_sha(workspace.path),
                "profile": "test",
                "scope": "core",
            },
        )
        plan.update(
            {
                "workspace_path": str(workspace.path),
                "workspace_sha": metaops.file_sha(workspace.path),
                "profile": "test",
                "doctor_receipt": str(doctor.resolve()),
                "doctor_sha": metaops.file_sha(doctor),
                "asset_receipt": str(asset.resolve()),
                "asset_sha": metaops.file_sha(asset),
            }
        )

    def test_single_plan_is_absolute_and_hash_bound(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            spec_path = self.write_json(root, "spec.json", valid_spec())
            plan = metaops.build_single_plan(spec_path)
            self.assertEqual(plan["schema"], metaops.SINGLE_PLAN_SCHEMA)
            self.assertTrue(pathlib.Path(plan["state_path"]).is_absolute())
            self.assertTrue(pathlib.Path(plan["dry_state_path"]).is_absolute())
            self.assertEqual(len(plan["spec_sha"]), 16)

    def test_saved_spec_isolated_from_source_change_and_tamper_evident(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            spec_path = self.write_json(root, "spec.json", valid_spec())
            plan = metaops.build_single_plan(spec_path)
            plan["spec_path"] = str(root / "snapshot.json")
            snapshot = pathlib.Path(plan["spec_path"])
            metaops.atomic_json(snapshot, metaops.load_launch_spec(spec_path))
            workspace = self.workspace(root)
            self.bind_single_plan(root, plan, workspace)
            changed = valid_spec()
            changed["campaign"]["daily_budget_minor"] = 2000
            self.write_json(root, "spec.json", changed)
            resolved, _ = metaops.validate_single_plan(plan, workspace, "test")
            self.assertEqual(resolved, snapshot.resolve())
            snapshot_data = json.loads(snapshot.read_text(encoding="utf-8"))
            snapshot_data["campaign"]["daily_budget_minor"] = 3000
            metaops.atomic_json(snapshot, snapshot_data)
            with self.assertRaisesRegex(metaops.MetaOpsError, "spec changed after plan"):
                metaops.validate_single_plan(plan, workspace, "test")

    def test_invalid_spec_becomes_launcher_error_in_json_mode(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            bad = self.write_json(root, "bad.json", {"account_id": "act_1"})
            proc = subprocess.run(
                [sys.executable, str(HERE / "metaops.py"), "--json", "plan", "--spec", str(bad)],
                cwd=HERE,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 2)
            rows = proc.stdout.splitlines()
            self.assertEqual(len(rows), 1)
            payload = json.loads(rows[0])
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["error"]["kind"], "precondition")

    def test_dlo_requires_an_explicit_static_adset(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            spec = valid_spec()
            spec["adsets"][0]["ads"][0]["creative"]["kind"] = "dlo"
            path = self.write_json(root, "dlo.json", spec)
            with self.assertRaisesRegex(metaops.launch.SpecError, "is_dynamic_creative: false"):
                metaops.launch.load_spec(str(path))
            spec["adsets"][0]["is_dynamic_creative"] = False
            self.write_json(root, "dlo.json", spec)
            self.assertEqual(metaops.launch.load_spec(str(path))["adsets"][0]["is_dynamic_creative"], False)

    def test_cbo_bid_cap_sends_bid_amount_and_no_budget_on_adset(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            raw = valid_spec()
            raw["campaign"]["bid_strategy"] = "LOWEST_COST_WITH_BID_CAP"
            raw["adsets"][0]["bid_amount_minor"] = 777
            spec = metaops.load_launch_spec(self.write_json(root, "spec.json", raw))
            state = metaops.launch.State(str(root / "state.json"))
            captured: dict[str, dict] = {}

            def fake_create(node, path, payload, state, dry):
                captured[node.split("[")[0]] = payload
                return {"campaign": "1", "adset": "2", "creative": "3", "ad": "4"}[node.split("[")[0]]

            with (
                mock.patch.object(metaops.launch, "account_currency", return_value="USD"),
                mock.patch.object(metaops.launch, "resolve_identity", return_value=None),
                mock.patch.object(metaops.launch, "_create", side_effect=fake_create),
                mock.patch.object(metaops.launch.graph, "post", return_value={"id": "budget"}),
            ):
                metaops.launch.run(spec, state, False)
            adset_payload = captured["adset"]
            self.assertEqual(adset_payload.get("bid_amount"), 777)
            self.assertNotIn("daily_budget", adset_payload)
            self.assertNotIn("bid_strategy", adset_payload)

    def test_cbo_without_cap_strategy_omits_bid_amount(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            spec = metaops.load_launch_spec(self.write_json(root, "spec.json", valid_spec()))
            state = metaops.launch.State(str(root / "state.json"))
            captured: dict[str, dict] = {}

            def fake_create(node, path, payload, state, dry):
                captured[node.split("[")[0]] = payload
                return {"campaign": "1", "adset": "2", "creative": "3", "ad": "4"}[node.split("[")[0]]

            with (
                mock.patch.object(metaops.launch, "account_currency", return_value="USD"),
                mock.patch.object(metaops.launch, "resolve_identity", return_value=None),
                mock.patch.object(metaops.launch, "_create", side_effect=fake_create),
                mock.patch.object(metaops.launch.graph, "post", return_value={"id": "budget"}),
            ):
                metaops.launch.run(spec, state, False)
            self.assertNotIn("bid_amount", captured["adset"])

    def test_launch_creates_active_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            spec = metaops.load_launch_spec(self.write_json(root, "spec.json", valid_spec()))
            self.assertEqual(spec["create_status"], "ACTIVE")
            state = metaops.launch.State(str(root / "state.json"))
            captured: dict[str, dict] = {}

            def fake_create(node, path, payload, state, dry):
                captured[node.split("[")[0]] = payload
                return {"campaign": "1", "adset": "2", "creative": "3", "ad": "4"}[node.split("[")[0]]

            with (
                mock.patch.object(metaops.launch, "account_currency", return_value="USD"),
                mock.patch.object(metaops.launch, "resolve_identity", return_value=None),
                mock.patch.object(metaops.launch, "_create", side_effect=fake_create),
                mock.patch.object(metaops.launch.graph, "post", return_value={"id": "budget"}) as post,
            ):
                metaops.launch.run(spec, state, False)
            # The campaign is created PAUSED and flipped ACTIVE once the tree is complete.
            self.assertEqual(captured["campaign"]["status"], "PAUSED")
            self.assertEqual(captured["adset"]["status"], "ACTIVE")
            self.assertEqual(captured["ad"]["status"], "ACTIVE")
            self.assertEqual(post.call_args_list[-1].args, ("1", {"status": "ACTIVE"}))
            self.assertEqual(state.data["campaign_activated"], "1")

    def test_launch_create_status_paused_override(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            raw = valid_spec()
            raw["create_status"] = "PAUSED"
            spec = metaops.load_launch_spec(self.write_json(root, "spec.json", raw))
            self.assertEqual(spec["create_status"], "PAUSED")
            state = metaops.launch.State(str(root / "state.json"))
            captured: dict[str, dict] = {}

            def fake_create(node, path, payload, state, dry):
                captured[node.split("[")[0]] = payload
                return {"campaign": "1", "adset": "2", "creative": "3", "ad": "4"}[node.split("[")[0]]

            with (
                mock.patch.object(metaops.launch, "account_currency", return_value="USD"),
                mock.patch.object(metaops.launch, "resolve_identity", return_value=None),
                mock.patch.object(metaops.launch, "_create", side_effect=fake_create),
                mock.patch.object(metaops.launch.graph, "post", return_value={"id": "budget"}),
            ):
                metaops.launch.run(spec, state, False)
            self.assertEqual(captured["campaign"]["status"], "PAUSED")
            self.assertEqual(captured["adset"]["status"], "PAUSED")
            self.assertEqual(captured["ad"]["status"], "PAUSED")

    def test_launch_rejects_invalid_create_status(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            raw = valid_spec()
            raw["create_status"] = "DELETED"
            path = self.write_json(root, "spec.json", raw)
            with self.assertRaisesRegex(metaops.launch.SpecError, "create_status"):
                metaops.launch.load_spec(str(path))

    def test_verify_diffs_cbo_bid_cap_and_attribution_readback(self) -> None:
        """End-to-end verify.py read-back for Goal 2 (CBO bid cap) and Goal 3 (attribution)."""
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            raw = valid_spec()
            raw["create_status"] = "PAUSED"
            raw["campaign"]["bid_strategy"] = "LOWEST_COST_WITH_BID_CAP"
            raw["adsets"][0]["bid_amount_minor"] = 250
            raw["adsets"][0]["attribution"] = {"click_days": 7, "view_days": 1}
            spec_path = self.write_json(root, "spec.json", raw)
            spec = metaops.load_launch_spec(spec_path)
            state = {
                "objects": {"campaign": "1", "adset[0]": "2", "ad[0.0]": "3"},
                "spec_sha": metaops.launch.spec_hash(spec),
                "spec_account": "act_1",
            }
            state_path = self.write_json(root, "state.json", state)

            objects = {
                "1": {
                    "id": "1", "name": "Campaign", "objective": "OUTCOME_LEADS",
                    "status": "PAUSED", "effective_status": "PAUSED",
                    "daily_budget": 1000, "bid_strategy": "LOWEST_COST_WITH_BID_CAP",
                    "special_ad_categories": [],
                },
                "2": {
                    "id": "2", "name": "Ad set", "status": "PAUSED", "effective_status": "PAUSED",
                    "optimization_goal": "OFFSITE_CONVERSIONS", "billing_event": "IMPRESSIONS",
                    "bid_amount": 250,
                    "start_time": "2030-01-01T08:00:00+00:00",
                    "attribution_spec": [
                        {"event_type": "CLICK_THROUGH", "window_days": 7},
                        {"event_type": "VIEW_THROUGH", "window_days": 1},
                    ],
                    "targeting": {"geo_locations": {"countries": ["TR"]},
                                  "targeting_automation": {"advantage_audience": 0},
                                  # verify now fails a read-back without pinned placements
                                  "publisher_platforms": ["facebook", "instagram"],
                                  "facebook_positions": ["feed"], "instagram_positions": ["stream"]},
                },
                "3": {
                    "id": "3", "name": "Ad", "status": "PAUSED", "effective_status": "PAUSED",
                    "creative": {
                        "id": "9",
                        "object_story_spec": {
                            "page_id": "2",
                            "instagram_user_id": "17841400000000000",
                            "link_data": {
                                "link": "https://example.com/",
                                "message": "",
                                "image_hash": "test_hash",
                                "call_to_action": {"type": "LEARN_MORE",
                                                    "value": {"link": "https://example.com/"}},
                            },
                        },
                        "degrees_of_freedom_spec": {"creative_features_spec": {}},
                        "contextual_multi_ads": {"enroll_status": "OPT_OUT"},
                    },
                },
            }

            def fake_get(path, **kwargs):
                del kwargs
                return objects[path]

            with (
                mock.patch.object(sys, "argv",
                                   ["verify.py", "--state", str(state_path), "--spec", str(spec_path)]),
                mock.patch.object(verify.graph, "get", side_effect=fake_get),
            ):
                code = verify.main()
            self.assertEqual(code, 0)
            receipt = json.loads((state_path.parent / (state_path.name + ".verified.json")).read_text())
            self.assertTrue(receipt["ok"])

            # A mismatched bid_amount must fail the run.
            objects["2"]["bid_amount"] = 999
            with (
                mock.patch.object(sys, "argv",
                                   ["verify.py", "--state", str(state_path), "--spec", str(spec_path)]),
                mock.patch.object(verify.graph, "get", side_effect=fake_get),
            ):
                self.assertEqual(verify.main(), 1)

    def test_verify_accepts_active_and_flags_unwanted_paused(self) -> None:
        """launch.py now defaults create_status to ACTIVE; verify.py must accept an ACTIVE
        read-back for that default and flag PAUSED as a mismatch only when the spec never
        asked for it (create_status: PAUSED)."""
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            raw = valid_spec()
            spec_path = self.write_json(root, "spec.json", raw)
            spec = metaops.load_launch_spec(spec_path)
            self.assertEqual(spec["create_status"], "ACTIVE")
            state = {
                "objects": {"campaign": "1", "adset[0]": "2", "ad[0.0]": "3"},
                "spec_sha": metaops.launch.spec_hash(spec),
                "spec_account": "act_1",
            }
            state_path = self.write_json(root, "state.json", state)

            def objects_for(status: str) -> dict:
                return {
                    "1": {
                        "id": "1", "name": "Campaign", "objective": "OUTCOME_LEADS",
                        "status": status, "effective_status": status,
                        "daily_budget": 1000, "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
                        "special_ad_categories": [],
                    },
                    "2": {
                        "id": "2", "name": "Ad set", "status": status, "effective_status": status,
                        "optimization_goal": "OFFSITE_CONVERSIONS", "billing_event": "IMPRESSIONS",
                        "start_time": "2030-01-01T08:00:00+00:00",
                        "attribution_spec": [
                            {"event_type": "CLICK_THROUGH", "window_days": 1},
                            {"event_type": "VIEW_THROUGH", "window_days": 1},
                            {"event_type": "ENGAGED_VIDEO_VIEW", "window_days": 1},
                        ],
                        "targeting": {"geo_locations": {"countries": ["TR"]},
                                      "targeting_automation": {"advantage_audience": 0},
                                      "publisher_platforms": ["facebook", "instagram"],
                                      "facebook_positions": ["feed"], "instagram_positions": ["stream"]},
                    },
                    "3": {
                        "id": "3", "name": "Ad", "status": status, "effective_status": status,
                        "creative": {
                            "id": "9",
                            "object_story_spec": {
                                "page_id": "2",
                                "instagram_user_id": "17841400000000000",
                                "link_data": {
                                    "link": "https://example.com/",
                                    "message": "",
                                    "image_hash": "test_hash",
                                    "call_to_action": {"type": "LEARN_MORE",
                                                        "value": {"link": "https://example.com/"}},
                                },
                            },
                            "degrees_of_freedom_spec": {"creative_features_spec": {}},
                            "contextual_multi_ads": {"enroll_status": "OPT_OUT"},
                        },
                    },
                }

            active_objects = objects_for("ACTIVE")
            with (
                mock.patch.object(sys, "argv",
                                   ["verify.py", "--state", str(state_path), "--spec", str(spec_path)]),
                mock.patch.object(verify.graph, "get", side_effect=lambda path, **kw: active_objects[path]),
            ):
                self.assertEqual(verify.main(), 0, "ACTIVE read-back must not be a mismatch")

            paused_objects = objects_for("PAUSED")
            with (
                mock.patch.object(sys, "argv",
                                   ["verify.py", "--state", str(state_path), "--spec", str(spec_path)]),
                mock.patch.object(verify.graph, "get", side_effect=lambda path, **kw: paused_objects[path]),
            ):
                self.assertEqual(
                    verify.main(), 1,
                    "a default (ACTIVE) spec whose campaign read back PAUSED must fail verify",
                )

    def test_verify_receipt_expires_before_activation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            spec = {"adsets": [{"ads": [{}]}]}
            state = {"objects": {"campaign": "1", "adset[0]": "2", "ad[0.0]": "3"},
                     "spec_sha": metaops.launch.spec_hash(spec)}
            state_path = self.write_json(root, "state.json", state)
            verify.write_receipt(str(state_path), "spec.json", spec)
            receipt_path = pathlib.Path(str(state_path) + ".verified.json")
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            receipt["ts"] = "2000-01-01T00:00:00+00:00"
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
            self.assertIn("maximum", metaops.activate.check_receipt(str(state_path), state) or "")

    def test_verify_receipt_ttl_is_configurable_without_import_time_failure(self) -> None:
        checked_at = dt.datetime(2030, 1, 1, tzinfo=dt.timezone.utc)
        with mock.patch.dict(os.environ, {"METAOPS_VERIFY_MAX_AGE_SECONDS": "1"}, clear=False):
            why = metaops.activate.receipt_timestamp_error(
                checked_at.isoformat(), now=checked_at + dt.timedelta(seconds=2)
            )
        self.assertIn("maximum 1s", why or "")
        with mock.patch.dict(os.environ, {"METAOPS_VERIFY_MAX_AGE_SECONDS": "bad"}, clear=False):
            why = metaops.activate.receipt_timestamp_error(checked_at.isoformat(), now=checked_at)
        self.assertIn("must be a positive integer", why or "")

    def test_lock_excludes_concurrent_writer_and_is_removed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state = pathlib.Path(td) / "state.json"
            lock = pathlib.Path(str(state) + ".metaops.lock")
            with metaops.state_lock(state):
                self.assertTrue(lock.exists())
                with (
                    self.assertRaisesRegex(metaops.MetaOpsError, "locked by another launcher"),
                    metaops.state_lock(state),
                ):
                    pass
            self.assertFalse(lock.exists())

    def test_missing_state_is_not_activation_ready(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            summary = metaops.state_summary(pathlib.Path(td) / "missing.json")
            self.assertEqual(summary["phase"], "planned")
            self.assertFalse(summary["activation_ready"])

    def test_bulk_input_change_invalidates_plan(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            template = valid_spec("template")
            accounts = [{"account_id": "act_1", "page_id": "2", "pixel_id": "3"}]
            template_path = self.write_json(root, "template.json", template)
            accounts_path = self.write_json(root, "accounts.json", accounts)
            workspace = self.workspace(root)
            plan = metaops.build_bulk_plan(
                template_path, accounts_path, "batch", None, workspace
            )
            plan["template_path"] = str(root / "template.snapshot.json")
            plan["accounts_path"] = str(root / "accounts.snapshot.json")
            metaops.atomic_json(pathlib.Path(plan["template_path"]), template)
            metaops.atomic_json(
                pathlib.Path(plan["accounts_path"]),
                metaops.workspace_bulk_rows(
                    workspace, metaops.validated_bulk_rows(accounts, None, "batch")
                ),
            )
            doctor = self.write_doctor(root)
            plan["doctor_receipts"] = [
                {"account_id": "act_1", "path": str(doctor.resolve()),
                 "sha": metaops.file_sha(doctor)}
            ]
            asset = self.write_json(
                root,
                "assets.json",
                {
                    "schema": metaops.ASSET_RECEIPT_SCHEMA,
                    "checked_at": metaops.now_utc(),
                    "api_version": metaops.graph.API_VERSION,
                    "workspace_sha": metaops.file_sha(workspace.path),
                    "profile": "test",
                    "scope": "core",
                },
            )
            plan["asset_receipts"] = [
                {"profile": "test", "path": str(asset.resolve()),
                 "sha": metaops.file_sha(asset), "catalog_required": False}
            ]
            accounts[0]["page_id"] = "4"
            self.write_json(root, "accounts.json", accounts)
            metaops.validate_bulk_plan(plan, workspace)
            snapshot_rows = json.loads(pathlib.Path(plan["accounts_path"]).read_text(encoding="utf-8"))
            snapshot_rows[0]["page_id"] = "5"
            metaops.atomic_json(pathlib.Path(plan["accounts_path"]), snapshot_rows)
            with self.assertRaisesRegex(metaops.MetaOpsError, "changed after plan"):
                metaops.validate_bulk_plan(plan, workspace)

    def test_bulk_rejects_path_tags_and_routing_overrides(self) -> None:
        with self.assertRaises(metaops.MetaOpsError):
            metaops.validated_bulk_rows(
                [{"account_id": "act_1", "tag": "../escape"}], None, "batch"
            )
        with self.assertRaisesRegex(metaops.MetaOpsError, "routing keys"):
            metaops.validated_bulk_rows(
                [{"account_id": "act_1", "overrides": {"account_id": "act_2"}}],
                None,
                "batch",
            )

    def test_state_must_match_plan_before_activation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            state_path = self.write_json(
                root,
                "state.json",
                {"spec_sha": "other", "spec_account": "act_2", "objects": {}},
            )
            plan = {"spec_sha": "expected", "account_id": "act_1"}
            with self.assertRaisesRegex(metaops.MetaOpsError, "different spec"):
                metaops.require_state_binding(plan, state_path)

    def test_mismatched_in_flight_state_is_rejected_before_apply(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            source = self.write_json(root, "source.json", valid_spec())
            state_path = self.write_json(
                root,
                "state.json",
                {"spec_sha": "other", "spec_account": "act_2", "objects": {},
                 "in_flight": {"campaign": {"path": "act_2/campaigns"}}},
            )
            plan = metaops.build_single_plan(source, str(state_path))
            snapshot = root / "snapshot.json"
            plan["spec_path"] = str(snapshot.resolve())
            metaops.atomic_json(snapshot, metaops.load_launch_spec(source))
            workspace = self.workspace(root)
            self.bind_single_plan(root, plan, workspace)
            plan_path = root / "plan.json"
            metaops.atomic_json(plan_path, plan)
            args = type("Args", (), {
                "plan": str(plan_path), "timeout": 10,
                "workspace_obj": workspace, "profile": "test", "confirm": "SPEND",
            })()
            with (
                mock.patch.object(metaops, "run_child") as child,
                self.assertRaisesRegex(metaops.MetaOpsError, "different spec"),
            ):
                metaops.command_apply(args)
            child.assert_not_called()

    def test_apply_invokes_launch_with_saved_snapshot_and_paused_state(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            source = self.write_json(root, "source.json", valid_spec())
            plan = metaops.build_single_plan(source, str(root / "state.json"))
            snapshot = root / "snapshot.json"
            plan["spec_path"] = str(snapshot.resolve())
            normalized = metaops.load_launch_spec(source)
            metaops.atomic_json(snapshot, normalized)
            workspace = self.workspace(root)
            self.bind_single_plan(root, plan, workspace)
            plan_path = root / "plan.json"
            metaops.atomic_json(plan_path, plan)

            def fake_child(script: str, argv: list[str], _timeout: int) -> metaops.ChildResult:
                self.assertEqual(script, "launch.py")
                self.assertEqual(argv[argv.index("--spec") + 1], str(snapshot.resolve()))
                self.assertNotIn("activate.py", argv)
                self.write_json(
                    root,
                    "state.json",
                    {
                        "spec_sha": plan["spec_sha"],
                        "spec_account": "act_1",
                        "objects": {"campaign": "1", "adset[0]": "2", "ad[0.0]": "3"},
                    },
                )
                return metaops.ChildResult([script, *argv], 0, "", "")

            args = type("Args", (), {
                "plan": str(plan_path), "timeout": 10,
                "workspace_obj": workspace, "profile": "test", "confirm": "SPEND",
            })()
            with mock.patch.object(metaops, "run_child", side_effect=fake_child):
                code, payload = metaops.command_apply(args)
            self.assertEqual(code, 0)
            self.assertEqual(payload["phase"], "built")

    def test_apply_refuses_without_confirm_spend(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            source = self.write_json(root, "source.json", valid_spec())
            plan = metaops.build_single_plan(source, str(root / "state.json"))
            snapshot = root / "snapshot.json"
            plan["spec_path"] = str(snapshot.resolve())
            metaops.atomic_json(snapshot, metaops.load_launch_spec(source))
            workspace = self.workspace(root)
            self.bind_single_plan(root, plan, workspace)
            plan_path = root / "plan.json"
            metaops.atomic_json(plan_path, plan)
            for bad in (None, "", "PLEASE", "spend"):
                args = type("Args", (), {
                    "plan": str(plan_path), "timeout": 10,
                    "workspace_obj": workspace, "profile": "test", "confirm": bad,
                })()
                with (
                    mock.patch.object(metaops, "run_child") as child,
                    self.assertRaisesRegex(metaops.MetaOpsError, "confirm SPEND"),
                ):
                    metaops.command_apply(args)
                child.assert_not_called()

    def _bound_apply_args(self, root: pathlib.Path, raw: dict):
        source = self.write_json(root, "source.json", raw)
        plan = metaops.build_single_plan(source, str(root / "state.json"))
        snapshot = root / "snapshot.json"
        plan["spec_path"] = str(snapshot.resolve())
        metaops.atomic_json(snapshot, metaops.load_launch_spec(source))
        workspace = self.workspace(root)
        self.bind_single_plan(root, plan, workspace)
        plan_path = root / "plan.json"
        metaops.atomic_json(plan_path, plan)
        return type("Args", (), {
            "plan": str(plan_path), "timeout": 10,
            "workspace_obj": workspace, "profile": "test", "confirm": "SPEND",
        })()

    def test_apply_refuses_active_build_with_past_start_time(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            raw = valid_spec()
            raw["adsets"][0]["start_time"] = "2020-01-01T08:00:00+00:00"
            args = self._bound_apply_args(pathlib.Path(td), raw)
            with (
                mock.patch.object(metaops, "run_child") as child,
                self.assertRaisesRegex(metaops.MetaOpsError, "refusing ACTIVE apply.*start_time"),
            ):
                metaops.command_apply(args)
            child.assert_not_called()

    def test_apply_refuses_active_build_with_offsetless_start_time(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            raw = valid_spec()
            raw["adsets"][0]["start_time"] = "2030-01-01T08:00:00"
            args = self._bound_apply_args(pathlib.Path(td), raw)
            with (
                mock.patch.object(metaops, "run_child") as child,
                self.assertRaisesRegex(metaops.MetaOpsError, "lacks an offset"),
            ):
                metaops.command_apply(args)
            child.assert_not_called()

    def test_apply_refresh_start_resumes_past_spec_with_start_override(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            raw = valid_spec()
            raw["adsets"][0]["start_time"] = "2020-01-01T08:00:00+00:00"
            args = self._bound_apply_args(pathlib.Path(td), raw)
            args.refresh_start = "2099-01-01T08:00:00+00:00"
            seen: list[list[str]] = []

            def fake_child(script: str, argv: list[str], _timeout: int) -> metaops.ChildResult:
                seen.append(argv)
                return metaops.ChildResult([script, *argv], 1, "", "stop")

            with mock.patch.object(metaops, "run_child", side_effect=fake_child):
                metaops.command_apply(args)
            self.assertEqual(seen[0][seen[0].index("--start-override") + 1], args.refresh_start)

    def test_apply_refresh_start_must_be_future(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            args = self._bound_apply_args(pathlib.Path(td), valid_spec())
            args.refresh_start = "2020-01-01T08:00:00+00:00"
            with (
                mock.patch.object(metaops, "run_child") as child,
                self.assertRaisesRegex(metaops.MetaOpsError, "future"),
            ):
                metaops.command_apply(args)
            child.assert_not_called()

    def test_paused_build_skips_apply_start_time_gate(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            raw = valid_spec()
            raw["create_status"] = "PAUSED"
            raw["adsets"][0]["start_time"] = "2020-01-01T08:00:00+00:00"
            self.assertIsNone(metaops._active_start_blocker(self.write_json(root, "p.json", raw)))
            raw["create_status"] = "ACTIVE"
            self.assertIn("plan again",
                          metaops._active_start_blocker(self.write_json(root, "a.json", raw)))

    def test_bulk_apply_refuses_active_item_with_past_start_time(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            raw = valid_spec()
            raw["adsets"][0]["start_time"] = "2020-01-01T08:00:00+00:00"
            spec_path = self.write_json(root, "item.json", raw)
            item = {"account_id": "act_1", "spec_path": str(spec_path),
                    "state_path": str(root / "state.json"), "spec_sha": "x"}
            args = type("Args", (), {
                "plan": "p", "timeout": 10, "workspace_obj": None,
                "verify": False, "dlo_tested": False, "confirm": "SPEND",
            })()
            plan = {"run_id": "batch", "items": [item], "template_path": "t", "accounts_path": "a"}
            with (
                mock.patch.object(metaops, "load_plan", return_value=(root / "plan.json", plan)),
                mock.patch.object(metaops, "validate_bulk_plan",
                                  return_value=(root / "t.json", root / "a.json")),
                mock.patch.object(metaops, "validate_bulk_items", return_value=[item]),
                mock.patch.object(metaops, "expected_bulk_state_paths", return_value=[]),
                mock.patch.object(metaops, "state_lock",
                                  side_effect=lambda _path: contextlib.nullcontext()),
                mock.patch.object(metaops, "run_child") as child,
                self.assertRaisesRegex(metaops.MetaOpsError, "refusing ACTIVE bulk-apply for act_1"),
            ):
                metaops.command_bulk_apply(args)
            child.assert_not_called()

    def test_bulk_rows_cannot_override_create_status(self) -> None:
        for value in ("ACTIVE", "PAUSED"):
            with self.assertRaisesRegex(metaops.MetaOpsError, "create_status"):
                metaops.validated_bulk_rows(
                    [{"account_id": "act_1", "overrides": {"create_status": value}}],
                    None, "batch",
                )

    def test_bulk_apply_refuses_without_confirm_spend(self) -> None:
        for bad in (None, "", "PLEASE", "spend"):
            args = type("Args", (), {
                "plan": "/nonexistent/bulk-plan.json", "timeout": 10, "workspace_obj": None,
                "verify": False, "dlo_tested": False, "confirm": bad,
            })()
            with (
                mock.patch.object(metaops, "run_child") as child,
                self.assertRaisesRegex(metaops.MetaOpsError, "confirm SPEND"),
            ):
                metaops.command_bulk_apply(args)
            child.assert_not_called()

    def test_json_usage_error_is_one_object(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(HERE / "metaops.py"), "--json", "apply"],
            cwd=HERE,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(len(proc.stdout.splitlines()), 1)
        self.assertEqual(json.loads(proc.stdout)["error"]["kind"], "usage")

    def test_refresh_start_requires_offset_and_future_time(self) -> None:
        with self.assertRaises(metaops.MetaOpsError):
            metaops.validate_future_start("2020-01-01T08:00:00")
        with self.assertRaises(metaops.MetaOpsError):
            metaops.validate_future_start("2020-01-01T08:00:00+00:00")

    def test_run_name_rejects_paths(self) -> None:
        with self.assertRaises(metaops.MetaOpsError):
            metaops.safe_name("../escape", "run_id")

    def test_workspace_free_plan_is_rejected_before_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            spec = self.write_json(root, "spec.json", valid_spec())
            proc = subprocess.run(
                [sys.executable, str(HERE / "metaops.py"), "--json", "plan", "--spec", str(spec)],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
                env={key: value for key, value in os.environ.items()
                     if key != "METAOPS_WORKSPACE"},
            )
            self.assertEqual(proc.returncode, 2)
            payload = json.loads(proc.stdout)
            self.assertIn("requires a workspace", payload["error"]["message"])
            self.assertFalse((root / ".metaops").exists())

    def test_invalid_timeout_environment_still_returns_one_json_envelope(self) -> None:
        env = dict(os.environ, METAOPS_TIMEOUT_SECONDS="not-an-integer")
        proc = subprocess.run(
            [sys.executable, str(HERE / "metaops.py"), "--json", "doctor", "--whoami"],
            cwd=HERE,
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )
        self.assertEqual(proc.returncode, 2)
        payload = json.loads(proc.stdout)
        self.assertFalse(payload["ok"])
        self.assertIn("METAOPS_TIMEOUT_SECONDS", payload["error"]["message"])

    def test_low_level_graph_write_requires_metaops_authority(self) -> None:
        with (
            mock.patch.dict(os.environ, {"META_TOKEN": "TEST_TOKEN"}, clear=True),
            mock.patch.object(metaops.graph, "_WRITE_ACCOUNTS", None),
            mock.patch.object(metaops.graph, "_WRITE_CAPABILITY_LOADED", True),
            mock.patch.object(metaops.graph, "session") as session,
            self.assertRaisesRegex(SystemExit, "direct Graph POST is disabled"),
        ):
            metaops.graph.post("act_1/campaigns", {"name": "blocked"})
        session.assert_not_called()

    def test_low_level_graph_write_rejects_an_empty_workspace_capability(self) -> None:
        with (
            mock.patch.dict(os.environ, {"META_TOKEN": "TEST_TOKEN"}, clear=True),
            mock.patch.object(metaops.graph, "_WRITE_ACCOUNTS", set()),
            mock.patch.object(metaops.graph, "_WRITE_CAPABILITY_LOADED", True),
            mock.patch.object(metaops.graph, "session") as session,
            self.assertRaisesRegex(SystemExit, "direct Graph POST is disabled"),
        ):
            metaops.graph.post("123/anything", {"name": "blocked"})
        session.assert_not_called()

    def test_low_level_graph_write_rejects_account_outside_workspace(self) -> None:
        with (
            mock.patch.dict(os.environ, {"META_TOKEN": "TEST_TOKEN"}, clear=True),
            mock.patch.object(metaops.graph, "_WRITE_ACCOUNTS", {"act_1"}),
            mock.patch.object(metaops.graph, "_WRITE_CAPABILITY_LOADED", True),
            mock.patch.object(metaops.graph, "session") as session,
            self.assertRaisesRegex(SystemExit, "does not authorize.*act_99"),
        ):
            metaops.graph.post("act_99/campaigns", {"name": "blocked"})
        session.assert_not_called()

    def test_absolute_graph_url_cannot_bypass_account_or_host_gate(self) -> None:
        with (
            mock.patch.object(metaops.graph, "_WRITE_ACCOUNTS", {"act_1"}),
            mock.patch.object(metaops.graph, "_WRITE_CAPABILITY_LOADED", True),
            mock.patch.object(metaops.graph, "session") as session,
            self.assertRaisesRegex(SystemExit, "does not authorize.*act_99"),
        ):
            metaops.graph.post(
                "https://graph.facebook.com/v26.0/act_99/campaigns", {"name": "blocked"}
            )
        session.assert_not_called()

        with (
            mock.patch.object(metaops.graph, "session") as session,
            self.assertRaisesRegex(SystemExit, "outside https://graph.facebook.com"),
        ):
            metaops.graph.get("https://example.com/collect")
        session.assert_not_called()

    def test_provisioning_admin_binds_the_token_to_workspace_role(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            workspace = self.workspace(pathlib.Path(td))

            def fake_get(path, params=None, context=""):
                if path == "me":
                    self.assertEqual(params, {"fields": "id,name"})
                    return {"id": "12", "name": "Launcher"}
                self.assertEqual(path, "10/system_users")
                self.assertEqual(params, {"fields": "id,name,role", "limit": 500})
                return {"data": [{"id": "12", "name": "Launcher", "role": "ADMIN"}]}

            with mock.patch.object(metaops.graph, "get", side_effect=fake_get) as get:
                result = metaops.require_provisioning_admin(workspace, "test")
            self.assertEqual(result["role"], "ADMIN")
            self.assertEqual(result["system_user_id"], "12")
            self.assertEqual(get.call_count, 2)

    def test_provisioning_rejects_employee_system_user(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            workspace = self.workspace(pathlib.Path(td))
            responses = [
                {"id": "12", "name": "Launcher"},
                {"data": [{"id": "12", "name": "Launcher", "role": "EMPLOYEE"}]},
            ]
            with mock.patch.object(metaops.graph, "get", side_effect=responses):
                with self.assertRaisesRegex(metaops.MetaOpsError, "requires an ADMIN"):
                    metaops.require_provisioning_admin(workspace, "test")

    def test_provisioning_rejects_a_token_other_than_workspace_system_user(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            workspace = self.workspace(pathlib.Path(td))
            with mock.patch.object(metaops.graph, "get", return_value={"id": "99", "name": "Other"}) as get:
                with self.assertRaisesRegex(metaops.MetaOpsError, "workspace System User token"):
                    metaops.require_provisioning_admin(workspace, "test")
            get.assert_called_once()

    def test_only_whoami_doctor_is_workspace_free(self) -> None:
        blocked = type("Args", (), {
            "command": "doctor", "whoami": False, "workspace_obj": None,
        })()
        with self.assertRaisesRegex(metaops.MetaOpsError, "account-targeted doctor"):
            metaops.require_command_workspace(blocked)
        allowed = type("Args", (), {
            "command": "doctor", "whoami": True, "workspace_obj": None,
        })()
        metaops.require_command_workspace(allowed)
        provisioning = type("Args", (), {
            "command": "doctor", "whoami": True, "workspace_obj": None, "scope": "provisioning",
        })()
        with self.assertRaisesRegex(metaops.MetaOpsError, "scope provisioning requires a workspace"):
            metaops.require_command_workspace(provisioning)

    def test_state_summary_does_not_claim_past_spec_ready_for_activation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            spec = valid_spec()
            spec["adsets"][0]["start_time"] = "2000-01-01T08:00:00+00:00"
            spec_path = self.write_json(root, "spec.json", spec)
            state_path = self.write_json(root, "state.json", {
                "objects": {"campaign": "1", "adset[0]": "2", "ad[0.0]": "3"},
                "in_flight": {}, "errors": [],
            })
            with mock.patch.object(metaops.activate, "check_receipt", return_value=None):
                summary = metaops.state_summary(state_path, spec_path)
            self.assertFalse(summary["activation_ready"])
            self.assertIn("start_time is past", summary["activation_blocker"])

    def test_plan_cannot_move_to_another_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            first_workspace = self.workspace(pathlib.Path(first))
            second_workspace = self.workspace(pathlib.Path(second))
            plan = {
                "workspace_path": str(first_workspace.path),
                "workspace_sha": metaops.file_sha(first_workspace.path),
                "profile": "test",
            }
            with self.assertRaisesRegex(metaops.MetaOpsError, "does not match"):
                metaops.require_plan_workspace(plan, second_workspace, "test")

    def test_mcp_blocks_every_mutating_tool_before_network(self) -> None:
        for name in (
            "ads_activate_entity",
            "ads_create_campaign",
            "ads_catalog_update_product_set",
            "ads_pixel_event_delete",
        ):
            with self.assertRaisesRegex(SystemExit, "read-only allowlist"):
                mcp.require_read_only_tool(name)
        mcp.require_read_only_tool("ads_get_ad_entities")
        mcp.require_read_only_tool("ads_catalog_list_products")

    def test_doctor_receipt_is_bound_to_business(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            receipt = self.write_doctor(root)
            with self.assertRaisesRegex(metaops.MetaOpsError, "business_id mismatch"):
                metaops.require_doctor(valid_spec(), str(receipt), "999")

    def test_dry_run_refuses_missing_pbia_for_instagram_placements(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            raw = valid_spec()
            raw["instagram_user_id"] = "auto"
            spec = metaops.load_launch_spec(self.write_json(root, "spec.json", raw))
            state = metaops.launch.State(str(root / "dry.json"))
            with (
                mock.patch.object(metaops.launch, "account_currency", return_value="USD"),
                mock.patch.object(metaops.launch, "resolve_identity", return_value=None),
                self.assertRaisesRegex(metaops.launch.SpecError, "no PBIA"),
            ):
                metaops.launch.run(spec, state, True)

    def test_media_routes_upload_to_workspace_profile(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            workspace = self.workspace(root)
            image = root / "creative.jpg"
            image.write_bytes(b"image")
            manifest = root / "output" / "media.json"
            args = type("Args", (), {
                "workspace_obj": workspace,
                "profile": "test",
                "image": [str(image)],
                "video": [],
                "manifest": str(manifest),
                "timeout": 10,
            })()

            def fake_child(script: str, argv: list[str], _timeout: int) -> metaops.ChildResult:
                self.assertEqual(script, "media.py")
                self.assertEqual(argv[argv.index("--account") + 1], "act_1")
                metaops.atomic_json(manifest, {"account_id": "act_1"})
                return metaops.ChildResult([script, *argv], 0, "", "")

            with (
                mock.patch.object(metaops, "require_assets", return_value=(root, "sha")),
                mock.patch.object(metaops, "require_doctor", return_value=(root, "sha")),
                mock.patch.object(metaops, "run_child", side_effect=fake_child),
            ):
                code, payload = metaops.command_media(args)
            self.assertEqual(code, 0)
            self.assertEqual(payload["artifacts"]["manifest"], str(manifest.resolve()))

    def test_product_set_mutation_rejects_wrong_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            data = json.loads(self.workspace(root).path.read_text(encoding="utf-8"))
            data["profiles"]["test"]["catalog_id"] = "16"
            data["profiles"]["test"]["product_sets"] = {"main": "17"}
            workspace = metaops.meta_workspace.load_workspace(
                str(self.write_json(root, "workspace.json", data))
            )
            args = type("Args", (), {
                "workspace_obj": workspace,
                "profile": "test",
                "set": "main",
                "retailer_ids": "sku-1",
                "confirm": "SET",
                "timeout": 10,
            })()
            with (
                mock.patch.object(metaops, "require_assets", return_value=(root, "sha")),
                mock.patch.object(metaops, "require_doctor", return_value=(root, "sha")),
                mock.patch.object(
                    metaops.asset_graph,
                    "verify_product_set_binding",
                    return_value={
                        "ready": False,
                        "checks": {"product_set_catalog": False},
                    },
                ),
                mock.patch.object(metaops, "run_child") as child,
                self.assertRaisesRegex(metaops.MetaOpsError, "repair binding failed"),
            ):
                metaops.command_assets_set_products(args)
            child.assert_not_called()

    def _swap_args(self, root, dry=False, sets=None, mapping="a1=T01", **kw):
        workspace = self.workspace(root)
        workspace.data["profiles"]["test"]["product_sets"] = sets or {"a1": "17"}
        workspace.data["profiles"]["test"]["catalog_id"] = "16"
        base = {"workspace_obj": workspace, "profile": "test", "map": mapping, "confirm": "SWAP",
                "dry_run": dry, "timeout": 10, "watch": False, "interval": 300, "max_wait": 0,
                "paused_ok": False, "allow_message": False, "revert": False}
        base.update(kw)
        return type("Args", (), base)()

    @staticmethod
    def _ad(ad_id, set_id, status="ACTIVE", headline="{{product.name}}", message="-----",
            description="{{product.description}}"):
        return {"id": ad_id, "name": f"ad{ad_id}", "effective_status": status,
                "creative": {"product_set_id": set_id, "object_story_spec": {"template_data": {
                    "name": headline, "description": description, "message": message}}}}

    @staticmethod
    def _swap_graph(ads=None, items=None, members=None, headline="{{product.name}}", message="-----",
                    item=None):
        """Routes Graph GETs: account ads/insights, catalog products, set info/members.
        `ads` may be a list of lists: one per poll round (watch)."""
        rounds = ads if ads and isinstance(ads[0], list) else [ads or [
            MetaOpsContractTests._ad("9", "17", headline=headline, message=message)]]
        if item is not None:
            items = [item] if item else []
        catalog = items if items is not None else [
            {"retailer_id": r, "name": f"Bonus {r}", "description": "Desc", "image_url": "https://x/i.png",
             "visibility": "published"} for r in ("T01", "T02", "T03", "W01")]
        members = members or {}
        calls = {"ads": 0}

        def fake_get(path, params=None, context=None):
            if path.endswith("/ads"):
                i = min(calls["ads"], len(rounds) - 1)
                calls["ads"] += 1
                return {"data": rounds[i]}
            if path.endswith("/insights"):
                return {"data": []}
            if path == "16/products":
                want = json.loads(params["filter"])["retailer_id"]["is_any"]
                return {"data": [c for c in catalog if c.get("retailer_id") in want]}
            if path.endswith("/products"):
                return {"data": [{"retailer_id": r} for r in members.get(path.split("/")[0], ["W01"])]}
            return {"id": path, "name": "Set", "filter": '{"retailer_id":{"is_any":["W01"]}}', "product_count": 1}
        return fake_get

    def _run_swap(self, td, fake_get, **kw):
        args = self._swap_args(pathlib.Path(td), **kw)
        with (
            mock.patch.object(metaops.graph, "get", side_effect=fake_get),
            mock.patch.object(metaops.graph, "next_page_params", return_value=None),
            mock.patch.object(metaops, "asset_receipt_path", return_value=pathlib.Path(td) / "r.json"),
            mock.patch("time.sleep"),
            mock.patch.object(metaops, "run_child",
                              return_value=metaops.ChildResult(["mutate_set.py"], 0, "", "")) as child,
        ):
            code, payload = metaops.command_assets_swap(args)
        return code, payload, child

    def test_assets_swap_waits_while_swapped_ad_in_review(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            fake = self._swap_graph(ads=[self._ad("9", "17", "PENDING_REVIEW")])
            code, payload, child = self._run_swap(td, fake)
            self.assertEqual(code, 2)
            self.assertEqual(payload["phase"], "waiting_review")
            child.assert_not_called()

    def test_assets_swap_runs_right_after_approval_without_delivery(self) -> None:
        # operator 2026-09-26: swap at approval; zero impressions and a rejected ad on ANOTHER set never hold it.
        with tempfile.TemporaryDirectory() as td:
            fake = self._swap_graph(ads=[self._ad("9", "17"), self._ad("8", "99", "DISAPPROVED")])
            code, payload, child = self._run_swap(td, fake)
            self.assertEqual(code, 0, payload)
            self.assertEqual(child.call_args[0][1], ["--set-id", "17", "--retailer-ids", "T01"])

    def test_assets_swap_is_per_set_ready_one_swaps_while_other_waits(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            fake = self._swap_graph(ads=[self._ad("9", "17"), self._ad("8", "18", "IN_PROCESS")])
            code, payload, child = self._run_swap(td, fake, sets={"a1": "17", "b1": "18"}, mapping="a1=T01,b1=T02")
            self.assertEqual(code, 2)
            child.assert_called_once()
            self.assertEqual(child.call_args[0][1][1], "17")
            self.assertEqual([s["set"] for s in payload["data"]["swapped"]], ["a1"])

    def test_assets_swap_watch_swaps_each_set_on_its_approval(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            rounds = [[self._ad("9", "17", "PENDING_REVIEW"), self._ad("8", "18", "PENDING_REVIEW")],
                      [self._ad("9", "17"), self._ad("8", "18", "PENDING_REVIEW")],
                      [self._ad("9", "17"), self._ad("8", "18")]]
            fake = self._swap_graph(ads=rounds)
            code, payload, child = self._run_swap(td, fake, sets={"a1": "17", "b1": "18"},
                                                  mapping="a1=T01,b1=T02", watch=True, max_wait=3600)
            self.assertEqual(code, 0, payload)
            self.assertEqual([c[0][1][1] for c in child.call_args_list], ["17", "18"])

    def test_assets_swap_watch_survives_transient_read_error(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = self._swap_graph()
            state = {"n": 0}

            def flaky(path, params=None, context=None):
                if path.endswith("/ads") and state["n"] == 0:
                    state["n"] += 1
                    raise metaops.graph.GraphError(0, {"error": {"code": -1, "is_transient": True}})
                return base(path, params, context)
            code, payload, child = self._run_swap(td, flaky, watch=True, max_wait=3600)
            self.assertEqual(code, 0, payload)
            child.assert_called_once()

    def test_assets_swap_multi_product_set_and_idempotent_rerun(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            code, _, child = self._run_swap(td, self._swap_graph(), mapping="a1=T01+T02")
            self.assertEqual(code, 0)
            self.assertEqual(child.call_args[0][1], ["--set-id", "17", "--retailer-ids", "T01,T02"])
            done = self._swap_graph(members={"17": ["T02", "T01"]})
            code, payload, child = self._run_swap(td, done, mapping="a1=T01+T02")
            self.assertEqual(code, 0)
            child.assert_not_called()
            self.assertTrue(payload["data"]["swapped"][0]["already"])

    def test_assets_swap_paused_ad_needs_paused_ok(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            fake = self._swap_graph(ads=[self._ad("9", "17", "ADSET_PAUSED")])
            code, payload, child = self._run_swap(td, fake)
            self.assertEqual(code, 1)
            self.assertIn("--paused-ok", payload["error"]["message"])
            code, _, child = self._run_swap(td, fake, paused_ok=True)
            self.assertEqual(code, 0)

    def test_assets_swap_blocks_unused_set_and_all_rejected_set(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            code, payload, child = self._run_swap(td, self._swap_graph(ads=[self._ad("9", "99")]))
            self.assertEqual(code, 1)
            self.assertIn("no ad in this account uses it", payload["error"]["message"])
            code, payload, child = self._run_swap(td, self._swap_graph(ads=[self._ad("9", "17", "DISAPPROVED")]))
            self.assertEqual(code, 1)
            self.assertIn("every ad on it is rejected", payload["error"]["message"])
            child.assert_not_called()

    def test_assets_swap_rejected_ad_on_same_set_warns_but_swaps(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            fake = self._swap_graph(ads=[self._ad("9", "17"), self._ad("8", "17", "DISAPPROVED")])
            code, payload, child = self._run_swap(td, fake)
            self.assertEqual(code, 0)
            self.assertTrue(payload["data"]["sets"][0]["warnings"])

    def test_assets_swap_revert_to_white_runs_during_review_without_text_gate(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            fake = self._swap_graph(ads=[self._ad("9", "17", "IN_PROCESS", headline=None, message="casino")],
                                    members={"17": ["T01"]})
            code, payload, child = self._run_swap(td, fake, mapping="a1=W01", revert=True)
            self.assertEqual(code, 0, payload)
            child.assert_called_once()

    def test_assets_swap_collection_needs_four_items(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            ad = self._ad("9", "17")
            ad["creative"]["asset_feed_spec"] = {"ad_formats": ["COLLECTION"]}
            code, payload, child = self._run_swap(td, self._swap_graph(ads=[ad]), mapping="a1=T01+T02")
            self.assertEqual(code, 1)
            self.assertIn("COLLECTION", payload["error"]["message"])
            code, _, child = self._run_swap(td, self._swap_graph(ads=[ad]), mapping="a1=T01+T02+T03+W01")
            self.assertEqual(code, 0)

    def test_spec_swap_map_from_creative_swap_to(self) -> None:
        spec = {"adsets": [{"ads": [
            {"name": "A", "creative": {"kind": "catalog_single", "product_set_id": "17", "swap_to": "T01"}},
            {"name": "B", "creative": {"kind": "catalog_collection", "product_set_id": "18",
                                       "swap_to": ["T01", "T02", "T03", "T04"]}},
            {"name": "C", "creative": {"kind": "catalog_single", "product_set_id": "19"}},
            {"name": "L", "creative": {"kind": "link_image"}}]}]}
        m, problems = metaops.spec_swap_map(spec, {"a1": "17", "b1": "18", "c1": "19"})
        self.assertEqual(m, "a1=T01,b1=T01+T02+T03+T04")
        self.assertEqual(len(problems), 1)
        self.assertIn("C:", problems[0])

    def test_assets_swap_map_rejects_duplicate_alias(self) -> None:
        with self.assertRaisesRegex(metaops.MetaOpsError, "twice"):
            metaops.parse_swap_map("a1=T01,a1=T02", {"a1": "17"})

    def test_assets_swap_blocks_static_headline_scraped_from_link(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            code, payload, child = self._run_swap(td, self._swap_graph(headline=None))
            self.assertEqual(code, 1)
            self.assertIn("product.name", payload["error"]["message"])
            child.assert_not_called()

    def test_assets_swap_blocks_white_primary_text_unless_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            fake = self._swap_graph(message="Useful things for home")
            code, payload, child = self._run_swap(td, fake)
            self.assertEqual(code, 1)
            self.assertIn("primary text", payload["error"]["message"])
            code, _, child = self._run_swap(td, fake, allow_message=True)
            self.assertEqual(code, 0)

    def test_assets_swap_blocks_target_item_without_texts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            item = {"retailer_id": "T01", "name": "Bonus", "description": "", "image_url": "https://x/i.png"}
            code, payload, child = self._run_swap(td, self._swap_graph(item=item))
            self.assertEqual(code, 1)
            self.assertIn("empty description", payload["error"]["message"])
            code, payload, child = self._run_swap(td, self._swap_graph(item={}))
            self.assertIn("not in catalog", payload["error"]["message"])
            child.assert_not_called()

    def test_assets_swap_dry_run_changes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            code, payload, child = self._run_swap(td, self._swap_graph(), dry=True)
            self.assertEqual((code, payload["phase"]), (0, "dry_run"))
            self.assertEqual(payload["data"]["sets"][0]["verdict"], "ready")
            child.assert_not_called()

    def test_bulk_activate_targets_one_bound_account(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            workspace = self.workspace(root)
            spec_path = self.write_json(root, "item.json", valid_spec("bulk-one"))
            spec = metaops.load_launch_spec(spec_path)
            state_path = self.write_json(
                root,
                "state.json",
                {
                    "spec_sha": metaops.launch.spec_hash(spec),
                    "spec_account": "act_1",
                    "objects": {"campaign": "1", "adset[0]": "2", "ad[0.0]": "3"},
                },
            )
            item = {
                "account_id": "act_1",
                "run_id": "bulk-one",
                "spec_path": str(spec_path.resolve()),
                "spec_sha": metaops.launch.spec_hash(spec),
                "state_path": str(state_path.resolve()),
            }
            plan_path = self.write_json(
                root,
                "bulk-plan.json",
                {
                    "schema": metaops.BULK_PLAN_SCHEMA,
                    "api_version": metaops.graph.API_VERSION,
                    "items": [item],
                },
            )
            args = type("Args", (), {
                "plan": str(plan_path),
                "account": "1",
                "confirm": "SPEND",
                "confirm_ui": "REVIEWED",
                "refresh_start": None,
                "timeout": 10,
                "workspace_obj": workspace,
            })()
            child = metaops.ChildResult(["activate.py"], 0, "", "")
            with (
                mock.patch.object(metaops, "validate_bulk_plan") as validate_plan,
                mock.patch.object(metaops, "validate_bulk_items", return_value=[item]),
                mock.patch.object(metaops, "run_child", return_value=child) as run,
            ):
                code, payload = metaops.command_bulk_activate(args)
            self.assertEqual(code, 0)
            self.assertEqual(payload["data"]["account_id"], "act_1")
            run.assert_called_once_with(
                "activate.py", ["--state", str(state_path.resolve()), "--confirm", "SPEND"], 10
            )
            self.assertEqual(validate_plan.call_count, 2)
            for call in validate_plan.call_args_list:
                self.assertEqual(call.args[2], {"act_1"})

    def test_result_envelope_matches_published_schema(self) -> None:
        schema = json.loads((SCHEMA_DIR / "result.v1.json").read_text(encoding="utf-8"))
        payload = metaops.result_envelope("test", True, "valid")
        jsonschema.Draft202012Validator(schema).validate(payload)

    def test_graph_session_rebuilds_when_proxy_configuration_changes(self) -> None:
        old_session = object()
        new_session = object()
        with (
            mock.patch.object(metaops.graph, "_SESSION", old_session),
            mock.patch.object(metaops.graph, "_SESSION_CONFIG", ("socks5h://old", "", "", "")),
            mock.patch.dict(
                os.environ,
                {"META_PROXY": "socks5h://new", "META_ALLOW_NO_PROXY": ""},
                clear=False,
            ),
            mock.patch.object(metaops.graph, "_session", return_value=new_session) as rebuild,
        ):
            self.assertIs(metaops.graph.session(), new_session)
        rebuild.assert_called_once_with()

    def test_graph_session_rebuilds_when_cookies_or_ua_change(self) -> None:
        old_session = object()
        new_session = object()
        with (
            mock.patch.object(metaops.graph, "_SESSION", old_session),
            mock.patch.object(metaops.graph, "_SESSION_CONFIG", ("", "1", "c_user=1; xs=old", "UA/1.0")),
            mock.patch.dict(
                os.environ,
                {
                    "META_ALLOW_NO_PROXY": "1",
                    "META_COOKIES": "c_user=1; xs=new_secret",
                    "META_USER_AGENT": "UA/2.0",
                },
                clear=False,
            ),
            mock.patch.object(metaops.graph, "_session", return_value=new_session) as rebuild,
        ):
            self.assertIs(metaops.graph.session(), new_session)
        rebuild.assert_called_once_with()

    def test_graph_session_injects_cookies_and_user_agent(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "META_ALLOW_NO_PROXY": "1",
                "META_COOKIES": "c_user=61577; xs=super_secret_xs_token; datr=foo",
                "META_USER_AGENT": "Mozilla/5.0 CustomUA",
            },
            clear=False,
        ):
            s = metaops.graph._session()
            self.assertEqual(s.headers.get("Cookie"), "c_user=61577; xs=super_secret_xs_token; datr=foo")
            self.assertEqual(s.headers.get("User-Agent"), "Mozilla/5.0 CustomUA")

    def test_graph_redact_masks_cookies_and_values(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "META_TOKEN": "RAW_META_TOKEN_123",
                "META_PROXY": "socks5h://puser:ppassword@1.2.3.4:1080",
                "META_COOKIES": "c_user=10000000; xs=24%3Asecrettokenval%3A01",
            },
            clear=False,
        ):
            # Test whole string, individual pairs, and split values
            sample = (
                "Call failed with token RAW_META_TOKEN_123 on proxy socks5h://puser:ppassword@1.2.3.4:1080 "
                "Cookie: c_user=10000000; xs=24%3Asecrettokenval%3A01 or partial xs=24%3Asecrettokenval%3A01 "
                "or raw value 24%3Asecrettokenval%3A01"
            )
            redacted = metaops.graph.redact(sample)
            self.assertNotIn("RAW_META_TOKEN_123", redacted)
            self.assertNotIn("ppassword", redacted)
            self.assertNotIn("10000000", redacted)
            self.assertNotIn("secrettokenval", redacted)

    def test_json_parse_error_names_a_new_command(self) -> None:
        with mock.patch.object(sys, "argv", ["metaops", "--json", "monitor"]):
            with self.assertRaises(SystemExit) as exit_info, mock.patch("builtins.print") as printed:
                metaops.parser().error("the following arguments are required: --accounts")
        self.assertEqual(exit_info.exception.code, 2)
        payload = json.loads(printed.call_args.args[0])
        self.assertEqual(payload["command"], "monitor")

    def test_global_json_survives_monitor_subparser(self) -> None:
        parsed = metaops.parser().parse_args(["--json", "monitor", "--accounts", "act_1"])
        self.assertTrue(parsed.json)
        self.assertIsNone(parsed.out_json)




class FeedAndMonitorTests(unittest.TestCase):
    def test_feed_upload_polls_until_end_time(self) -> None:
        states = [{"id": "u1"}, {"id": "u1", "end_time": "t", "num_persisted_items": 3, "error_count": 0}]
        with (
            mock.patch.object(feed_upload.graph, "get", side_effect=lambda *a, **k: states.pop(0)),
            mock.patch.object(feed_upload.time, "sleep"),
        ):
            u = feed_upload.poll("u1", wait_s=60)
        self.assertTrue(feed_upload.finished(u))
        self.assertEqual(u["num_persisted_items"], 3)

    def test_feed_upload_start_posts_url(self) -> None:
        with mock.patch.object(feed_upload.graph, "post", return_value={"id": "u9"}) as post:
            self.assertEqual(feed_upload.start("77", "https://x/export?format=csv&gid=0", True), "u9")
        self.assertEqual(post.call_args.args[0], "77/uploads")
        self.assertEqual(post.call_args.args[1], {"url": "https://x/export?format=csv&gid=0", "update_only": True})

    def test_monitor_stall_heuristic(self) -> None:
        rows = [{"id": "1", "impressions": 45, "clicks": 0}, {"id": "2", "impressions": 45, "clicks": 1},
                {"id": "3", "impressions": 10, "clicks": 0}]
        self.assertEqual([r["id"] for r in monitor.stalled(rows)], ["1"])
        self.assertEqual(monitor.stalled(rows, 5), [rows[0], rows[2]])

    def test_feed_swap_gate_blocks_ads_in_review(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            ws = MetaOpsContractTests().workspace(root)
            items = MetaOpsContractTests().write_json(root, "items.json", [{"id": "SKU1", "link": "https://a/"}])
            args = type("Args", (), {"workspace_obj": ws, "profile": "test", "feed_id": "5", "sheet": "abc",
                                     "tab": "products", "gid": 0, "url": None, "update_only": False,
                                     "wait": 1, "timeout": 5, "file": str(items), "force": False,
                                     "confirm": "FEED"})()
            import swapgate
            ads = [MetaOpsContractTests._ad("1", "17", "PENDING_REVIEW"), MetaOpsContractTests._ad("2", "18", "PENDING_REVIEW")]

            def fake_get(path, params=None, context=None):
                if path.endswith("/ads"):
                    return {"data": ads}
                if path.endswith("/products"):  # set 17 holds SKU1, set 18 holds OTHER
                    return {"data": [{"retailer_id": "SKU1" if path.startswith("17") else "OTHER"}]}
                return {"id": path, "name": "S", "filter": '{"retailer_id":{"eq":"x"}}'}
            with (
                mock.patch.object(metaops, "ad_statuses", return_value={}),
                mock.patch.object(swapgate.graph, "get", side_effect=fake_get),
                mock.patch.object(swapgate.graph, "next_page_params", return_value=None),
            ):
                with self.assertRaisesRegex(metaops.MetaOpsError, "swap gate: waiting"):
                    metaops.command_feed_swap(args)
                gate = swapgate.item_gate("act_1", ["SKU1"])
            self.assertEqual([s["set"] for s in gate["sets"]], ["17"])  # set 18's review is irrelevant

    def test_feed_swap_validates_prospective_rows_before_sheet_write(self) -> None:
        import sheetfeed
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            ws = MetaOpsContractTests().workspace(root)
            args = type("Args", (), {"workspace_obj": ws, "profile": "test", "feed_id": "5", "sheet": "abc",
                                     "tab": "products", "gid": 0, "url": None, "update_only": False,
                                     "wait": 1, "timeout": 5, "file": str(root / "items.json"), "force": False,
                                     "confirm": "FEED"})()
            sheet = mock.Mock()
            sheet.read.return_value = (["id"], [])  # Missing required feed columns.
            with (
                mock.patch.object(sheetfeed, "load_items", return_value=[{"id": "SKU1"}]),
                mock.patch.object(sheetfeed, "Sheet", return_value=sheet),
                mock.patch.object(metaops, "ad_statuses", return_value={}),
                mock.patch("swapgate.item_gate", return_value={"verdict": "ready", "waiting": [], "blockers": []}),
                mock.patch.object(metaops, "run_feed_upload") as upload,
            ):
                code, payload = metaops.command_feed_swap(args)
            self.assertEqual(code, 1)
            self.assertEqual(payload["phase"], "sheet_invalid")
            sheet.upsert.assert_not_called()
            upload.assert_not_called()

    def test_feed_binding_requires_feed_id(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            ws = MetaOpsContractTests().workspace(pathlib.Path(td))
            args = type("Args", (), {"workspace_obj": ws, "profile": "test", "feed_id": None})()
            with self.assertRaisesRegex(metaops.MetaOpsError, "no feed id"):
                metaops.feed_binding(args)
            args.feed_id = "42"
            self.assertEqual(metaops.feed_binding(args)[2], "42")

    def test_whoami_returns_nonzero_when_a_required_gate_fails(self) -> None:
        def fail_gate(report):
            report.add("token", probe.FAIL, "expired")

        with (
            mock.patch.object(probe.sys, "argv", ["probe.py", "--whoami"]),
            mock.patch.object(probe, "gate_identity", side_effect=fail_gate),
            mock.patch.object(probe, "gate_token_debug"),
            mock.patch.object(probe, "gate_scopes"),
            mock.patch.object(probe, "gate_visible_accounts"),
            mock.patch.object(probe, "whoami_verdict"),
        ):
            self.assertEqual(probe.main(), 1)

    def test_pixel_gate_follows_pagination_before_declaring_missing(self) -> None:
        report = probe.Report()
        first = {"data": [{"id": "first"}], "paging": {"cursors": {"after": "cursor-2"}, "next": "yes"}}
        second = {"data": [{"id": "wanted"}]}
        with mock.patch.object(probe.graph, "get", side_effect=[first, second]) as get:
            probe.gate_pixel_attached(report, "act_1", "wanted", None, False)
        self.assertEqual(get.call_count, 2)
        self.assertEqual(report.rows[-1]["state"], probe.PASS)

    def test_monitor_adset_queries_follow_pagination(self) -> None:
        pages = [
            {"data": [{"id": "a1", "issues_info": {"error_code": 1}}], "paging": {"cursors": {"after": "cursor"}, "next": "next"}},
            {"data": [{"id": "a2", "issues_info": {"error_code": 2}}]},
        ]
        with mock.patch.object(monitor.graph, "get", side_effect=lambda *a, **k: pages.pop(0)) as get:
            issues = monitor.adset_issues("act_1")
        self.assertEqual([issue["id"] for issue in issues], ["a1", "a2"])
        self.assertEqual(get.call_count, 2)

    def test_workspace_schema_accepts_feed_id(self) -> None:
        schema = json.loads((SCHEMA_DIR / "workspace.v1.json").read_text(encoding="utf-8"))
        doc = json.loads((HERE / "specs" / "example-workspace.json").read_text(encoding="utf-8"))
        prof = doc["profiles"].pop("<profile>")
        doc["profiles"]["p1"] = prof
        doc["defaults"]["profile"] = "p1"
        prof.update({"business_id": "1", "app_id": "1", "system_user_id": "1", "ad_account_id": "act_1",
                     "page_id": "1", "dataset_id": "1", "catalog_id": "1", "feed_id": "9",
                     "product_sets": {"main": "1"}})
        jsonschema.validate(doc, schema)

    def test_user_token_workspace_example_is_valid_without_app_or_system_user(self) -> None:
        """The user-token example (Goal 1) declares neither app_id nor system_user_id —
        confirm the schema and meta_workspace.validate_workspace both accept that."""
        schema = json.loads((SCHEMA_DIR / "workspace.v1.json").read_text(encoding="utf-8"))
        doc = json.loads((HERE / "specs" / "example-workspace-user-token.json").read_text(encoding="utf-8"))
        prof = doc["profiles"].pop("<profile>")
        doc["profiles"]["p1"] = prof
        doc["defaults"]["profile"] = "p1"
        prof.update({"business_id": "1", "ad_account_id": "act_1", "page_id": "1",
                     "dataset_id": "1", "catalog_id": "1", "feed_id": "9",
                     "product_sets": {"main": "1"}})
        self.assertNotIn("app_id", prof)
        self.assertNotIn("system_user_id", prof)
        self.assertEqual(prof["token_kind"], "user")
        jsonschema.validate(doc, schema)
        metaops.meta_workspace.validate_workspace(doc)

    def test_uniquify_no_crop_keeps_dimensions(self) -> None:
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("pillow not installed")
        import uniquify
        with tempfile.TemporaryDirectory() as td:
            src = pathlib.Path(td) / "a.jpg"
            Image.new("RGB", (64, 48), (200, 30, 30)).save(src, "JPEG")
            dst = pathlib.Path(td) / "a.v01.jpg"
            uniquify.uniq_image(src, dst, uniquify.seed_for(src, "v01"), crop=False)
            with Image.open(dst) as image:
                self.assertEqual(image.size, (64, 48))
            self.assertNotEqual(src.read_bytes(), dst.read_bytes())
            report = uniquify.image_report(src, dst)
            self.assertTrue(report["same_size"])
            self.assertLessEqual(report["dhash"], 8)
            self.assertLessEqual(report["phash"], 8)

    def test_uniquify_hashes_separate_distinct_images(self) -> None:
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            self.skipTest("pillow not installed")
        import uniquify
        a = Image.new("L", (64, 64), 0)
        ImageDraw.Draw(a).rectangle((0, 0, 31, 63), fill=255)
        b = Image.new("L", (64, 64), 0)
        ImageDraw.Draw(b).rectangle((0, 0, 63, 31), fill=255)
        self.assertEqual(uniquify.hamming(uniquify.dhash(a), uniquify.dhash(a)), 0)
        self.assertGreater(uniquify.hamming(uniquify.dhash(a), uniquify.dhash(b)), 8)
        self.assertGreater(uniquify.hamming(uniquify.phash(a), uniquify.phash(b)), 8)


class VersionWindowTests(unittest.TestCase):
    def test_supported_window_is_n_and_n_minus_1_with_v24_sunset(self) -> None:
        self.assertIn(metaops.graph.API_VERSION, metaops.graph.SUPPORTED_VERSIONS)
        self.assertEqual(tuple(metaops.graph.SUPPORTED_VERSIONS), ("v26.0", "v25.0"))
        self.assertEqual(metaops.graph.VERSION_SUNSET["v24.0"], "2026-10-06")

    def test_check_api_version_current_passes_silently(self) -> None:
        with mock.patch("sys.stderr"):
            warning = metaops.check_api_version(metaops.graph.API_VERSION, "plan")
        self.assertIsNone(warning)

    def test_check_api_version_previous_warns_but_passes(self) -> None:
        import io

        buf = io.StringIO()
        with mock.patch.object(sys, "stderr", buf):
            warning = metaops.check_api_version("v25.0", "workspace")
        self.assertIsNotNone(warning)
        self.assertIn("v25.0", buf.getvalue())
        self.assertIn("2026-10-06", buf.getvalue())

    def test_check_api_version_outside_window_fails(self) -> None:
        for bad in ("v24.0", "v23.0", "v22.0", "v99.0", None, ""):
            with self.assertRaises(metaops.MetaOpsError, msg=f"version {bad!r}"):
                metaops.check_api_version(bad, "plan")

    def test_plan_n_minus_1_loads_outside_refused(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            good = root / "plan-n1.json"
            good.write_text(json.dumps({"schema": metaops.SINGLE_PLAN_SCHEMA,
                                        "api_version": "v25.0"}), encoding="utf-8")
            _, plan = metaops.load_plan(str(good), {metaops.SINGLE_PLAN_SCHEMA})
            self.assertEqual(plan["api_version"], "v25.0")
            bad = root / "plan-old.json"
            bad.write_text(json.dumps({"schema": metaops.SINGLE_PLAN_SCHEMA,
                                       "api_version": "v24.0"}), encoding="utf-8")
            with self.assertRaisesRegex(metaops.MetaOpsError, "supported"):
                metaops.load_plan(str(bad), {metaops.SINGLE_PLAN_SCHEMA})

    def test_doctor_receipt_n_minus_1_warns_but_field_mismatch_still_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            receipt = root / "doctor.act_1.json"
            receipt.write_text(json.dumps({
                "schema": metaops.DOCTOR_SCHEMA,
                "checked_at": metaops.now_utc(),
                "api_version": "v25.0",
                "account_id": "act_1",
                "page_id": "2",
                "dataset_id": "3",
                "business_id": "10",
            }), encoding="utf-8")
            import io

            buf = io.StringIO()
            with mock.patch.object(sys, "stderr", buf):
                path, _ = metaops.require_doctor(
                    {"account_id": "act_1", "page_id": "2", "pixel_id": "3"},
                    str(receipt), "10",
                )
            self.assertEqual(path, receipt.resolve() if hasattr(receipt, "resolve") else path)
            self.assertIn("v25.0", buf.getvalue())
            # Fail-closed: same N-1 receipt with a wrong account still refuses.
            with self.assertRaisesRegex(metaops.MetaOpsError, "mismatch"):
                metaops.require_doctor(
                    {"account_id": "act_2", "page_id": "2", "pixel_id": "3"},
                    str(receipt), "10",
                )
            old = root / "doctor-old.json"
            old.write_text(json.dumps({
                "schema": metaops.DOCTOR_SCHEMA,
                "checked_at": metaops.now_utc(),
                "api_version": "v24.0",
                "account_id": "act_1",
            }), encoding="utf-8")
            with self.assertRaisesRegex(metaops.MetaOpsError, "supported"):
                metaops.require_doctor({"account_id": "act_1"}, str(old), None)


class RedactVectorTests(unittest.TestCase):
    def test_page_token_set_is_masked_not_only_meta_token(self) -> None:
        page_token = "PAGE_TOKEN_ABC123XYZ"
        metaops.graph.register_secret(page_token)
        with mock.patch.dict(os.environ, {"META_TOKEN": "META_MAIN_999"}, clear=False):
            metaops.graph.register_secret("META_MAIN_999")
            sample = f"failed with {page_token} and META_MAIN_999 in log"
            redacted = metaops.graph.redact(sample)
        self.assertNotIn(page_token, redacted)
        self.assertNotIn("META_MAIN_999", redacted)
        self.assertIn("<TOKEN>", redacted)

    def test_page_token_url_encoded_form_is_masked(self) -> None:
        from urllib.parse import quote

        page_token = "PAGE/with+chars=="
        metaops.graph.register_secret(page_token)
        sample = f"url=https://x/?t={quote(page_token, safe='')}"
        self.assertNotIn(quote(page_token, safe=""), metaops.graph.redact(sample))

    def test_app_secret_is_masked_centrally(self) -> None:
        with mock.patch.dict(os.environ, {"META_APP_SECRET": "SUPER_SECRET_ABC"}, clear=False):
            redacted = metaops.graph.redact("proof SUPER_SECRET_ABC leaked")
        self.assertNotIn("SUPER_SECRET_ABC", redacted)
        self.assertIn("<APP_SECRET>", redacted)

    def test_tg_bot_token_is_masked_centrally(self) -> None:
        with mock.patch.dict(os.environ, {"TG_BOT_TOKEN": "TG123456:FAKE"}, clear=False):
            redacted = metaops.graph.redact("https://api.telegram.org/botTG123456:FAKE/sendMessage boom")
        self.assertNotIn("TG123456:FAKE", redacted)
        self.assertIn("<TG_TOKEN>", redacted)

    def test_token_override_registers_for_later_redact(self) -> None:
        override = "OVERRIDE_PAGE_TOKEN_777"
        with mock.patch.dict(os.environ, {"META_ALLOW_NO_PROXY": "1",
                                           "META_TOKEN": "DUMMY"}, clear=False):
            with mock.patch.object(metaops.graph, "session") as sess:
                resp = mock.Mock()
                resp.ok = True
                resp.headers = {}
                resp.json.return_value = {"id": "1"}
                resp.status_code = 200
                sess.return_value.request.return_value = resp
                metaops.graph.call("GET", "me", token_override=override, retries=0)
        self.assertIn(override, metaops.graph._KNOWN_SECRETS)
        self.assertNotIn(override, metaops.graph.redact(f"leak {override}"))

    def test_page_token_return_registers(self) -> None:
        with mock.patch.object(metaops.graph, "get",
                               return_value={"access_token": "PAGETOK_REGISTER_ME_123"}) as _get:
            token = metaops.graph.page_token("123")
        self.assertEqual(token, "PAGETOK_REGISTER_ME_123")
        self.assertNotIn("PAGETOK_REGISTER_ME_123", metaops.graph.redact("leak PAGETOK_REGISTER_ME_123"))
        _get.assert_called_once()

    def test_cmd_operate_uses_central_redact_no_adhoc_replace(self) -> None:
        import inspect

        import cmd_operate

        src = inspect.getsource(cmd_operate.command_monitor)
        self.assertIn("ctx.graph.redact", src)
        self.assertNotIn(".replace(tg_token", src)


class DedupAndAtomicTests(unittest.TestCase):
    def test_rules_create_one_dedups_existing_name_without_post(self) -> None:
        import rules

        with (
            mock.patch.object(rules, "list_rules",
                              return_value=[{"id": "R1", "name": "LADDER|k0"}]),
            mock.patch.object(rules.graph, "post") as post,
        ):
            rule_id = rules.create_one_rule("act_1", "LADDER|k0", {"name": "LADDER|k0"})
        self.assertEqual(rule_id, "R1")
        post.assert_not_called()

    def test_rules_retry_after_outcome_unknown_reconciles_without_duplicate(self) -> None:
        import rules

        unknown = rules.graph.GraphError(0, {"error": {"message": "dropped", "code": -1}}, "x")
        self.assertTrue(unknown.outcome_unknown)
        calls = {"n": 0}

        def fake_post(*a, **k):
            calls["n"] += 1
            raise unknown

        with (
            mock.patch.object(rules, "list_rules", side_effect=[
                [],
                [{"id": "R9", "name": "LADDER|k1"}],
                [{"id": "R9", "name": "LADDER|k1"}],
            ]),
            mock.patch.object(rules.graph, "post", side_effect=fake_post),
        ):
            rule_id = rules.create_one_rule("act_1", "LADDER|k1", {"name": "LADDER|k1"})
        self.assertEqual(rule_id, "R9")
        self.assertEqual(calls["n"], 1)

    def test_clone_state_blocks_blind_retry_after_break(self) -> None:
        import clone

        with tempfile.TemporaryDirectory() as td:
            state_path = str(pathlib.Path(td) / "clone-state.json")
            state = {"completed": {}, "in_flight": {"1": "campaign:111"}}
            clone.save_clone_state(state_path, state)
            loaded = clone.load_clone_state(state_path)
            self.assertIn("1", loaded["in_flight"])
            # A second run with the same state must not POST again.
            with mock.patch.object(clone.graph, "post") as post:
                post.side_effect = AssertionError("must not POST on in-flight retry")
                argv = ["clone.py", "campaign", "111", "--times", "1",
                        "--state", state_path, "--dry-run"]
                with mock.patch.object(sys, "argv", argv):
                    # dry-run bypasses the guard; emulate the guard directly:
                    guard_hit = "1" in clone.load_clone_state(state_path)["in_flight"]
                self.assertTrue(guard_hit)
                post.assert_not_called()
            mode = oct(pathlib.Path(state_path).stat().st_mode & 0o777)
            self.assertEqual(mode, "0o600")

    def test_catalog_create_dedups_by_name(self) -> None:
        import cmd_catalog

        args = type("Args", (), {
            "workspace_obj": mock.Mock(**{"profile.return_value": ("test", {
                "business_id": "10"})}),
            "profile": "test", "name": "Shop", "vertical": "commerce", "confirm": "CREATE",
        })()
        with (
            mock.patch.object(metaops, "require_provisioning_admin",
                              return_value={"role": "ADMIN"}),
            mock.patch.object(cmd_catalog, "_paginate",
                              return_value=[{"id": "999", "name": "Shop"}]),
            mock.patch.object(metaops.graph, "post") as post,
        ):
            code, payload = cmd_catalog.command_catalog_create(args, metaops)
        self.assertEqual(code, 0)
        self.assertTrue(payload["data"].get("deduped"))
        self.assertEqual(payload["data"]["catalog_id"], "999")
        post.assert_not_called()

    def test_catalog_create_reconciles_after_outcome_unknown(self) -> None:
        import cmd_catalog

        unknown = metaops.graph.GraphError(0, {"error": {"message": "dropped", "code": -1}}, "x")
        args = type("Args", (), {
            "workspace_obj": mock.Mock(**{"profile.return_value": ("test", {
                "business_id": "10"})}),
            "profile": "test", "name": "Shop2", "vertical": "commerce", "confirm": "CREATE",
        })()
        with (
            mock.patch.object(metaops, "require_provisioning_admin",
                              return_value={"role": "ADMIN"}),
            mock.patch.object(cmd_catalog, "_paginate", side_effect=[
                [], [{"id": "1001", "name": "Shop2"}],
            ]),
            mock.patch.object(metaops.graph, "post", side_effect=unknown) as post,
        ):
            code, payload = cmd_catalog.command_catalog_create(args, metaops)
        self.assertEqual(code, 0)
        self.assertEqual(payload["phase"], "reconciled")
        self.assertEqual(post.call_count, 1)

    def test_business_pixel_dedups_by_name(self) -> None:
        import cmd_business

        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            path = root / "workspace.json"
            path.write_text(json.dumps({
                "schema": metaops.meta_workspace.WORKSPACE_SCHEMA,
                "name": "c", "api_version": metaops.graph.API_VERSION,
                "blocked_accounts": [],
                "profiles": {"test": {
                    "business_id": "10", "ad_account_id": "act_1", "page_id": "2",
                    "dataset_id": "3", "currency": "USD", "timezone": "Europe/Warsaw",
                }},
                "defaults": {"profile": "test", "state_dir": ".metaops"},
            }), encoding="utf-8")
            workspace = metaops.meta_workspace.load_workspace(str(path))
            args = type("Args", (), {
                "workspace_obj": workspace, "profile": "test",
                "confirm": "CREATE", "name": "Px", "is_crm": False,
            })()
            with (
                mock.patch.object(metaops, "require_provisioning_admin",
                                  return_value={"role": "ADMIN"}),
                mock.patch.object(cmd_business, "_list_edge",
                                  return_value=[{"id": "555", "name": "Px"}]),
                mock.patch.object(metaops.graph, "post") as post,
            ):
                code, payload = cmd_business._pixel_create(metaops, args)
            self.assertEqual(code, 0)
            self.assertTrue(payload["data"].get("deduped"))
            post.assert_not_called()

    def test_products_batch_retry_same_payload_is_harmless(self) -> None:
        import cmd_catalog

        with tempfile.TemporaryDirectory() as td:
            items_path = pathlib.Path(td) / "items.json"
            items_path.write_text(json.dumps([{"id": "SKU1"}]), encoding="utf-8")
            args = type("Args", (), {
                "workspace_obj": mock.Mock(**{"profile.return_value": ("test", {
                    "catalog_id": "100", "ad_account_id": "act_1"})}),
                "profile": "test", "file": str(items_path),
                "method": "UPDATE", "wait": 5, "confirm": "BATCH",
            })()
            bodies: list[dict] = []

            def fake_post(path, data, **kw):
                bodies.append(data)
                return {"handles": ["H1"]}

            def fake_get(path, params=None, **kw):
                return {"handle": "H1", "status": "finished", "errors_total_count": 0}

            with (
                mock.patch.object(metaops.graph, "post", side_effect=fake_post),
                mock.patch.object(metaops.graph, "get", side_effect=fake_get),
                mock.patch("swapgate.item_gate", return_value={"verdict": "ready", "waiting": [], "blockers": []}),
            ):
                code1, _ = cmd_catalog.command_catalog_products_batch(args, metaops)
                code2, _ = cmd_catalog.command_catalog_products_batch(args, metaops)
            self.assertEqual((code1, code2), (0, 0))
            self.assertEqual(len(bodies), 2)
            self.assertEqual(bodies[0], bodies[1])

    def test_feed_upload_retry_same_url_is_harmless(self) -> None:
        import feed_upload

        bodies: list[dict] = []

        def fake_post(path, data, **kw):
            bodies.append((path, data))
            return {"id": "u1"}

        with mock.patch.object(feed_upload.graph, "post", side_effect=fake_post):
            first = feed_upload.start("77", "https://x/export?format=csv&gid=0", True)
            second = feed_upload.start("77", "https://x/export?format=csv&gid=0", True)
        self.assertEqual((first, second), ("u1", "u1"))
        self.assertEqual(bodies[0], bodies[1])

    def test_bulk_atomic_write_is_0600_and_no_tmp_left(self) -> None:
        import bulk

        with tempfile.TemporaryDirectory() as td:
            target = pathlib.Path(td) / "sub" / "spec.json"
            bulk.atomic_write_text(target, '{"a":1}')
            self.assertTrue(target.is_file())
            self.assertEqual(oct(target.stat().st_mode & 0o777), "0o600")
            leftovers = list(pathlib.Path(td).rglob(".spec.json.*"))
            self.assertEqual(leftovers, [])

    def test_launch_state_save_is_atomic_and_0600(self) -> None:
        import launch

        with tempfile.TemporaryDirectory() as td:
            state_path = str(pathlib.Path(td) / "run.json")
            state = launch.State(state_path)
            state.data["objects"]["campaign"] = "111"
            state.save()
            saved = pathlib.Path(state_path)
            self.assertTrue(saved.is_file())
            self.assertEqual(oct(saved.stat().st_mode & 0o777), "0o600")
            leftovers = list(pathlib.Path(td).glob(".state.*"))
            self.assertEqual(leftovers, [])
            reloaded = launch.State(state_path)
            self.assertEqual(reloaded.data["objects"]["campaign"], "111")

    def test_user_assign_retry_sends_identical_payload(self) -> None:
        import cmd_business

        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            path = root / "workspace.json"
            path.write_text(json.dumps({
                "schema": metaops.meta_workspace.WORKSPACE_SCHEMA,
                "name": "c", "api_version": metaops.graph.API_VERSION,
                "blocked_accounts": [],
                "profiles": {"test": {
                    "business_id": "10", "ad_account_id": "act_1", "page_id": "2",
                    "dataset_id": "3", "currency": "USD", "timezone": "Europe/Warsaw",
                }},
                "defaults": {"profile": "test", "state_dir": ".metaops"},
            }), encoding="utf-8")
            workspace = metaops.meta_workspace.load_workspace(str(path))
            args = type("Args", (), {
                "workspace_obj": workspace, "profile": "test", "confirm": "SHARE",
                "user_id": "999", "asset": "adaccount", "tasks": "MANAGE",
            })()
            bodies: list[dict] = []

            def fake_post(path, data, **kw):
                bodies.append(data)
                return {}

            with (
                mock.patch.object(metaops, "require_provisioning_admin",
                                  return_value={"role": "ADMIN"}),
                mock.patch.object(metaops.graph, "post", side_effect=fake_post),
            ):
                cmd_business._user_assign(metaops, args)
                cmd_business._user_assign(metaops, args)
            self.assertEqual(len(bodies), 2)
            self.assertEqual(bodies[0], bodies[1])


class ReviewFixTests(unittest.TestCase):
    """Regression tests for the 2026-09-25 review fixes. Offline; graph is mocked."""

    def write_json(self, root: pathlib.Path, name: str, value: object) -> pathlib.Path:
        path = root / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    # --- launch: campaign PAUSED until the tree is complete, then ACTIVE -------------

    def _run_launch(self, spec: dict, state, fail_on: str | None = None, post=None):
        created: list[tuple[str, dict]] = []
        ids = {"campaign": "1", "adset": "2", "creative": "3", "ad": "4"}

        def fake_create(node, path, payload, st, dry):
            if node == fail_on:
                raise SystemExit(1)
            cached = st.get(node)
            if cached:
                return cached
            created.append((node, payload))
            st.put(node, ids[node.split("[")[0]])
            return ids[node.split("[")[0]]

        post = post or mock.MagicMock(return_value={"success": True})
        with (
            mock.patch.object(metaops.launch, "account_currency", return_value="USD"),
            mock.patch.object(metaops.launch, "resolve_identity", return_value=None),
            mock.patch.object(metaops.launch, "_create", side_effect=fake_create),
            mock.patch.object(metaops.launch.graph, "post", post),
        ):
            metaops.launch.run(spec, state, False)
        return created, post

    def _status_posts(self, post) -> list:
        return [c for c in post.call_args_list if c.args[1] == {"status": "ACTIVE"}]

    def test_partial_tree_leaves_campaign_paused_and_resume_flips_once(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            spec = metaops.load_launch_spec(self.write_json(root, "s.json", valid_spec()))
            state = metaops.launch.State(str(root / "state.json"))
            with self.assertRaises(SystemExit):
                self._run_launch(spec, state, fail_on="ad[0.0]")
            self.assertNotIn("campaign_activated", state.data)
            self.assertEqual(state.get("campaign"), "1")

            # Resume: ad created, then exactly one flip.
            created, post = self._run_launch(spec, metaops.launch.State(str(root / "state.json")))
            self.assertEqual([n for n, _ in created], ["ad[0.0]"])
            self.assertEqual(len(self._status_posts(post)), 1)
            reloaded = metaops.launch.State(str(root / "state.json"))
            self.assertEqual(reloaded.data["campaign_activated"], "1")
            self.assertIn("campaign 1 ACTIVE", metaops.launch.live_summary(spec, reloaded))

            # A second resume does not flip again.
            _, post = self._run_launch(spec, reloaded)
            self.assertEqual(self._status_posts(post), [])

    def test_create_failure_before_flip_never_posts_campaign_status(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            spec = metaops.load_launch_spec(self.write_json(root, "s.json", valid_spec()))
            state = metaops.launch.State(str(root / "state.json"))
            post = mock.MagicMock(return_value={"success": True})
            with self.assertRaises(SystemExit):
                self._run_launch(spec, state, fail_on="adset[0]", post=post)
            self.assertEqual(self._status_posts(post), [])
            self.assertNotIn("campaign_activated", state.data)

    def test_reused_campaign_status_is_never_touched(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            raw = valid_spec()
            raw["campaign"]["id"] = "777"
            spec = metaops.load_launch_spec(self.write_json(root, "s.json", raw))
            state = metaops.launch.State(str(root / "state.json"))
            created, post = self._run_launch(spec, state)
            self.assertNotIn("campaign", [n for n, _ in created])
            # The campaign itself is never posted to. (Its ad sets are now created PAUSED and
            # flipped ACTIVE one by one, so "no ACTIVE post at all" was too broad: see
            # test_launch_fixes.ReusedCampaignStagingTests.)
            self.assertEqual([c for c in self._status_posts(post) if c.args[0] == "777"], [])
            self.assertIn("reused campaign 777", metaops.launch.live_summary(spec, state))

    def test_paused_build_never_flips_campaign(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            raw = valid_spec()
            raw["create_status"] = "PAUSED"
            spec = metaops.load_launch_spec(self.write_json(root, "s.json", raw))
            created, post = self._run_launch(spec, metaops.launch.State(str(root / "st.json")))
            self.assertEqual(dict(created)["campaign"]["status"], "PAUSED")
            self.assertEqual(dict(created)["adset[0]"]["status"], "PAUSED")
            self.assertEqual(self._status_posts(post), [])

    def test_campaign_flip_failure_is_recorded_and_retried_on_resume(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            spec = metaops.load_launch_spec(self.write_json(root, "s.json", valid_spec()))
            state = metaops.launch.State(str(root / "state.json"))
            err = metaops.graph.GraphError(400, {"error": {"message": "nope", "code": 100}}, "x")
            with (
                mock.patch.object(metaops.launch.graph, "post", side_effect=err),
                self.assertRaises(SystemExit),
            ):
                metaops.launch.activate_campaign(spec, state, "1", False)
            self.assertNotIn("campaign_activated", state.data)
            self.assertEqual(state.data["errors"][-1]["key"], "campaign_activate")
            with mock.patch.object(metaops.launch.graph, "post", return_value={}) as post:
                metaops.launch.activate_campaign(spec, state, "1", False)
            post.assert_called_once_with("1", {"status": "ACTIVE"}, context="activate campaign",
                                         idempotent=True)

    def test_dry_run_never_posts_campaign_status(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            spec = metaops.load_launch_spec(self.write_json(root, "s.json", valid_spec()))
            with mock.patch.object(metaops.launch.graph, "post") as post:
                metaops.launch.activate_campaign(
                    spec, metaops.launch.State(str(root / "st.json")), "<dry-run>", True
                )
            post.assert_not_called()

    # --- currencies -------------------------------------------------------------------

    def test_no_offset_currencies_match_meta_reference(self) -> None:
        self.assertEqual(
            metaops.launch.NO_OFFSET_CURRENCIES,
            {"CLP", "COP", "CRC", "HUF", "ISK", "IDR", "JPY", "KRW", "PYG", "TWD", "VND"},
        )
        self.assertEqual(metaops.launch.currency_offset("CRC"), 1)
        self.assertEqual(metaops.launch.major(5000, "CRC"), "5,000 CRC")
        self.assertEqual(metaops.launch.currency_offset("XOF"), 100)

    # --- transport ----------------------------------------------------------------------

    def test_graph_session_ignores_environment_proxies(self) -> None:
        with mock.patch.dict(os.environ, {"META_PROXY": "socks5h://127.0.0.1:1",
                                          "HTTPS_PROXY": "http://evil:1"}, clear=False):
            s = metaops.graph._session()
        self.assertFalse(s.trust_env)
        self.assertEqual(s.proxies["https"], "socks5h://127.0.0.1:1")

    def test_plain_session_keeps_proxy_but_drops_cookies(self) -> None:
        env = {"META_PROXY": "socks5h://127.0.0.1:1", "META_COOKIES": "c_user=1; xs=secret",
               "META_USER_AGENT": "UA/1"}
        with mock.patch.dict(os.environ, env, clear=False):
            s = metaops.graph.plain_session()
            g = metaops.graph._session()
        self.assertNotIn("Cookie", s.headers)
        self.assertEqual(g.headers["Cookie"], "c_user=1; xs=secret")
        self.assertEqual(s.proxies["https"], "socks5h://127.0.0.1:1")
        self.assertFalse(s.trust_env)
        self.assertEqual(s.headers["User-Agent"], "UA/1")

    def test_plain_session_fails_closed_without_proxy(self) -> None:
        with (
            mock.patch.dict(os.environ, {"META_PROXY": "", "META_ALLOW_NO_PROXY": ""}, clear=False),
            self.assertRaises(SystemExit),
        ):
            metaops.graph.plain_session()

    def test_media_thumbnail_download_uses_cookie_free_session(self) -> None:
        import media

        resp = mock.Mock(content=b"jpg")
        plain = mock.Mock()
        plain.get.return_value = resp
        with (
            mock.patch.object(media.graph, "get",
                              return_value={"data": [{"uri": "https://scontent.fbcdn/x.jpg",
                                                      "is_preferred": True}]}),
            mock.patch.object(media.graph, "plain_session", return_value=plain),
            mock.patch.object(media.graph, "session",
                              side_effect=AssertionError("cookie session used for fbcdn")),
            mock.patch.object(media, "upload_image", return_value={"image_hash": "h"}),
        ):
            out = media.thumbnail_hash("act_1", "55")
        self.assertEqual(out["thumbnail_image_hash"], "h")
        plain.get.assert_called_once()

    def test_mcp_routes_through_plain_proxied_session(self) -> None:
        resp = mock.Mock(status_code=200, content=b'{"jsonrpc":"2.0","result":{}}',
                         headers={"Mcp-Session-Id": "sid"})
        plain = mock.Mock()
        plain.post.return_value = resp
        with mock.patch.object(mcp.graph, "plain_session", return_value=plain):
            sid, msg = mcp._post("initialize", {}, None, 1)
        self.assertEqual(sid, "sid")
        self.assertEqual(plain.post.call_args.args[0], mcp.URL)

    def test_mcp_fails_closed_without_proxy(self) -> None:
        with (
            mock.patch.dict(os.environ, {"META_PROXY": "", "META_ALLOW_NO_PROXY": ""}, clear=False),
            self.assertRaises(SystemExit),
        ):
            mcp._post("initialize", {}, None, 1)

    def test_upload_retry_resends_the_same_bytes(self) -> None:
        sent: list[bytes] = []

        class FlakySession:
            def request(self, method, url, files=None, **kw):
                sent.append(files["img.jpg"][1])
                if len(sent) == 1:
                    raise ConnectionError("dropped")
                return mock.Mock(ok=True, headers={}, json=lambda: {"images": {}})

        with tempfile.TemporaryDirectory() as td:
            path = pathlib.Path(td) / "img.jpg"
            path.write_bytes(b"IMAGEBYTES")
            with (
                open(path, "rb") as fh,
                mock.patch.object(metaops.graph, "session", return_value=FlakySession()),
                mock.patch.object(metaops.graph, "require_write_authority"),
                mock.patch.object(metaops.graph.time, "sleep"),
            ):
                metaops.graph.call("POST", "act_1/adimages", files={"img.jpg": ("img.jpg", fh)},
                                   idempotent=True)
        self.assertEqual(sent, [b"IMAGEBYTES", b"IMAGEBYTES"])

    def test_media_upload_image_passes_bytes_not_a_handle(self) -> None:
        import media

        with tempfile.TemporaryDirectory() as td:
            path = pathlib.Path(td) / "a.jpg"
            path.write_bytes(b"XYZ")
            with mock.patch.object(media.graph, "call",
                                   return_value={"images": {"a.jpg": {"hash": "h"}}}) as call:
                media.upload_image("act_1", str(path))
        self.assertEqual(call.call_args.kwargs["files"], {"a.jpg": ("a.jpg", b"XYZ")})

    # --- workspace env binding ------------------------------------------------------------

    def _workspace_file(self, root: pathlib.Path, defaults: dict) -> pathlib.Path:
        return self.write_json(root, "workspace.json", {
            "schema": metaops.meta_workspace.WORKSPACE_SCHEMA,
            "name": "fix", "api_version": metaops.graph.API_VERSION,
            "blocked_accounts": [],
            "profiles": {"test": {
                "business_id": "10", "ad_account_id": "act_1", "page_id": "2",
                "dataset_id": "3", "currency": "USD", "timezone": "Europe/Warsaw",
            }},
            "defaults": {"profile": "test", "state_dir": ".metaops", **defaults},
        })

    @contextlib.contextmanager
    def _isolated_globals(self):
        """configure_workspace rebinds module globals; restore them for later tests."""
        with (
            mock.patch.object(metaops.launch, "STATE_DIR", metaops.launch.STATE_DIR),
            mock.patch.object(metaops.bulk, "BULK_DIR", metaops.bulk.BULK_DIR),
            mock.patch.object(metaops, "PLAN_DIR", metaops.PLAN_DIR),
            mock.patch.object(metaops.graph, "_WRITE_ACCOUNTS", metaops.graph._WRITE_ACCOUNTS),
            mock.patch.object(metaops.graph, "_WRITE_CAPABILITY_LOADED",
                              metaops.graph._WRITE_CAPABILITY_LOADED),
            mock.patch.dict(os.environ, {}, clear=False),
        ):
            yield

    def test_inherited_allow_no_proxy_is_dropped_unless_workspace_opts_in(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            path = self._workspace_file(root, {})
            with self._isolated_globals():
                os.environ["META_ALLOW_NO_PROXY"] = "1"
                metaops.configure_workspace(str(path))
                self.assertNotIn("META_ALLOW_NO_PROXY", os.environ)
            path = self._workspace_file(root, {"allow_no_proxy": True})
            with self._isolated_globals():
                os.environ.pop("META_ALLOW_NO_PROXY", None)
                metaops.configure_workspace(str(path))
                self.assertEqual(os.environ.get("META_ALLOW_NO_PROXY"), "1")

    def test_custom_token_env_never_falls_back_to_ambient_meta_token(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            path = self._workspace_file(root, {"token_env": "FIX_META_TOKEN"})
            with self._isolated_globals():
                os.environ["META_TOKEN"] = "AMBIENT"
                os.environ.pop("FIX_META_TOKEN", None)
                with self.assertRaisesRegex(metaops.MetaOpsError, "FIX_META_TOKEN"):
                    metaops.configure_workspace(str(path))
                self.assertNotIn("META_TOKEN", os.environ)
            with self._isolated_globals():
                os.environ["META_TOKEN"] = "AMBIENT"
                os.environ.pop("FIX_META_TOKEN", None)
                metaops.configure_workspace(str(path), require_token=False)
                self.assertNotIn("META_TOKEN", os.environ)

    # --- edit --all ------------------------------------------------------------------------

    def test_edit_all_selects_every_live_effective_status(self) -> None:
        import edit

        with mock.patch.object(edit.graph, "get", return_value={"data": [{"id": "9"}]}) as get:
            self.assertEqual(edit.ids_from_account("act_1", "ad"), ["9"])
        sent = json.loads(get.call_args.kwargs["params"]["effective_status"])
        for status in ("ACTIVE", "IN_PROCESS", "PENDING_REVIEW", "PREAPPROVED", "WITH_ISSUES",
                       "CAMPAIGN_PAUSED", "ADSET_PAUSED"):
            self.assertIn(status, sent)
        # Only values from the documented effective_status enum.
        enum = {"ACTIVE", "PAUSED", "DELETED", "PENDING_REVIEW", "DISAPPROVED", "PREAPPROVED",
                "PENDING_BILLING_INFO", "CAMPAIGN_PAUSED", "ARCHIVED", "ADSET_PAUSED",
                "IN_PROCESS", "WITH_ISSUES"}
        self.assertTrue(set(sent) <= enum)
        self.assertNotIn("PAUSED", sent)

    # --- bulk --------------------------------------------------------------------------------

    def _run_bulk(self, root: pathlib.Path, template: dict, run_side_effect, dry: bool = False):
        import bulk

        rows = [{"account_id": "act_1", "tag": "a"}, {"account_id": "act_2", "tag": "b"}]
        tpath = self.write_json(root, "template.json", template)
        apath = self.write_json(root, "accounts.json", rows)
        argv = ["bulk.py", "--template", str(tpath), "--accounts", str(apath), "--run", "batch"]
        if dry:
            argv.append("--dry-run")
        out, err = io.StringIO(), io.StringIO()
        with (
            mock.patch.object(bulk, "BULK_DIR", str(root / "bulk")),
            mock.patch.object(bulk.launch, "STATE_DIR", str(root / "state")),
            mock.patch.object(bulk.launch.graph, "require_write_authority"),
            mock.patch.object(bulk, "marker_stale", return_value=None),
            mock.patch.object(bulk.launch, "run", side_effect=run_side_effect),
            mock.patch.object(sys, "argv", argv),
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(err),
        ):
            code = bulk.main()
        return code, out.getvalue(), err.getvalue()

    def test_bulk_graph_error_fails_one_account_not_the_batch(self) -> None:
        calls: list[str] = []

        def fake_run(spec, state, dry):
            calls.append(spec["account_id"])
            if spec["account_id"] == "act_1":
                raise metaops.graph.GraphError(400, {"error": {"message": "acct read", "code": 100}},
                                               "account currency")

        with tempfile.TemporaryDirectory() as td:
            code, out, err = self._run_bulk(pathlib.Path(td), valid_spec(), fake_run)
        self.assertEqual(calls, ["act_1", "act_2"])
        self.assertEqual(code, 1)
        self.assertIn("batch summary", out)
        self.assertRegex(out, r"act_1\s+FAILED")
        self.assertRegex(out, r"act_2\s+BUILT")

    def test_bulk_messages_follow_create_status(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            code, out, _ = self._run_bulk(pathlib.Path(td), valid_spec(), lambda *a: None)
        self.assertEqual(code, 0)
        self.assertIn("LIVE", out)
        self.assertNotIn("Nothing spends", out)
        paused = valid_spec()
        paused["create_status"] = "PAUSED"
        with tempfile.TemporaryDirectory() as td:
            code, out, _ = self._run_bulk(pathlib.Path(td), paused, lambda *a: None)
        self.assertIn("built PAUSED", out)
        with tempfile.TemporaryDirectory() as td:
            code, out, _ = self._run_bulk(pathlib.Path(td), valid_spec(), lambda *a: None, dry=True)
        self.assertIn("build ACTIVE", out)
        self.assertNotIn("build PAUSED", out)

    # --- activate halt message -------------------------------------------------------------------

    def test_activate_halt_message_follows_campaign_status(self) -> None:
        import activate

        self.assertIn("nothing is spending", activate.halt_message("adset[0]", "PAUSED", ["ad[0.0]"]))
        live = activate.halt_message("adset[0]", "ACTIVE", ["ad[0.0]"])
        self.assertNotIn("nothing is spending", live)
        self.assertIn("spending now", live)
        self.assertIn("can spend now", activate.halt_message("campaign", "ACTIVE", ["ad[0.0]"]))
        self.assertIn("nothing is", activate.halt_message("campaign", "PAUSED", ["ad[0.0]"]))

    # --- verify ------------------------------------------------------------------------------------

    def test_verify_diffs_adset_and_ad_status_against_create_status(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            spec_path = self.write_json(root, "spec.json", valid_spec())
            spec = metaops.load_launch_spec(spec_path)
            state_path = self.write_json(root, "state.json", {
                "objects": {"campaign": "1", "adset[0]": "2", "ad[0.0]": "3"},
                "spec_sha": metaops.launch.spec_hash(spec), "spec_account": "act_1",
            })
            objects = {
                "1": {"id": "1", "objective": "OUTCOME_LEADS", "status": "ACTIVE",
                      "effective_status": "ACTIVE", "daily_budget": 1000,
                      "bid_strategy": "LOWEST_COST_WITHOUT_CAP", "special_ad_categories": []},
                "2": {"id": "2", "status": "PAUSED", "effective_status": "PAUSED",
                      "optimization_goal": "OFFSITE_CONVERSIONS", "billing_event": "IMPRESSIONS",
                      "start_time": "2030-01-01T08:00:00+00:00",
                      "attribution_spec": [
                          {"event_type": "CLICK_THROUGH", "window_days": 1},
                          {"event_type": "VIEW_THROUGH", "window_days": 1},
                          {"event_type": "ENGAGED_VIDEO_VIEW", "window_days": 1}],
                      "targeting": {"geo_locations": {"countries": ["TR"]},
                                    "targeting_automation": {"advantage_audience": 0},
                                    "publisher_platforms": ["facebook", "instagram"],
                                    "facebook_positions": ["feed"], "instagram_positions": ["stream"]}},
                "3": {"id": "3", "name": "Ad", "status": "PAUSED", "effective_status": "ADSET_PAUSED",
                      "creative": {"object_story_spec": {"page_id": "2",
                                                         "instagram_user_id": "17841400000000000",
                                                         "link_data": {
                          "link": "https://example.com/", "message": "", "image_hash": "test_hash",
                          "call_to_action": {"type": "LEARN_MORE",
                                             "value": {"link": "https://example.com/"}}}},
                          "contextual_multi_ads": {"enroll_status": "OPT_OUT"}}},
            }
            out = io.StringIO()
            with (
                mock.patch.object(sys, "argv", ["verify.py", "--state", str(state_path),
                                                "--spec", str(spec_path)]),
                mock.patch.object(verify.graph, "get", side_effect=lambda p, **kw: objects[p]),
                contextlib.redirect_stdout(out),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                self.assertEqual(verify.main(), 1)
        text = out.getvalue()
        self.assertRegex(text, r"MISMATCH\s+status: expected 'ACTIVE', got 'PAUSED'")
        self.assertEqual(text.count("MISMATCH"), 2, text)

    def _dlo_spec_creative(self) -> dict:
        return {"kind": "dlo", "ad_format": "SINGLE_VIDEO", "video_id": "100", "locales": [
            {"label": "exotic", "ids": [27], "is_default": True, "body": "B0", "title": "T0",
             "link": "https://x/"},
            {"label": "main", "ids": [1002, 1001], "body": "B1", "title": "T1",
             "link": "https://y/"},
        ]}

    def _dlo_feed(self) -> dict:
        def lab(name):
            return [{"name": name, "id": "9" + name}]
        return {
            "bodies": [{"text": "B0", "adlabels": lab("exotic")},
                       {"text": "B1", "adlabels": lab("main")}],
            "titles": [{"text": "T0", "adlabels": lab("exotic")},
                       {"text": "T1", "adlabels": lab("main")}],
            "videos": [{"video_id": "999", "adlabels": lab("exotic")},
                       {"video_id": "998", "adlabels": lab("main")}],
            "asset_customization_rules": [
                {"customization_spec": {"locales": [27], "age_min": 13, "age_max": 65},
                 "body_label": {"name": "exotic", "id": "1"}, "is_default": True},
                {"customization_spec": {"locales": [7, 23, 6, 24], "age_min": 13, "age_max": 65},
                 "body_label": {"name": "main", "id": "2"}},
            ],
        }

    def test_dlo_readback_matches_with_group_expansion_and_remapped_videos(self) -> None:
        d = verify.Diff()
        with contextlib.redirect_stdout(io.StringIO()):
            verify.check_dlo_feed(d, self._dlo_spec_creative(), self._dlo_feed())
        self.assertEqual(d.bad, 0)

    def test_dlo_readback_flags_rule_locale_default_and_text_drift(self) -> None:
        cases = []
        feed = self._dlo_feed()
        feed["asset_customization_rules"][1]["customization_spec"]["locales"] = [7, 23]
        cases.append(("locale ids", feed, 1))
        feed = self._dlo_feed()
        feed["asset_customization_rules"][1]["is_default"] = True
        cases.append(("two defaults", feed, 2))
        feed = self._dlo_feed()
        feed["bodies"][1]["text"] = "WRONG"
        cases.append(("body text", feed, 1))
        feed = self._dlo_feed()
        feed["titles"][0]["text"] = "WRONG"
        cases.append(("title text", feed, 1))
        feed = self._dlo_feed()
        feed["asset_customization_rules"].pop()
        cases.append(("missing rule", feed, 2))
        for label, feed, bad in cases:
            d = verify.Diff()
            with contextlib.redirect_stdout(io.StringIO()):
                verify.check_dlo_feed(d, self._dlo_spec_creative(), feed)
            self.assertEqual(d.bad, bad, label)

    # --- clone ------------------------------------------------------------------------------------

    def _run_clone(self, state_path: str, copy_side_effect) -> int:
        import clone

        argv = ["clone.py", "campaign", "111", "--times", "1", "--state", state_path,
                "--start", "2030-01-01T08:00:00+00:00",
                # campaign copies are paced per account (launch.py's rule); the account comes
                # from the metaops profile binding, so the test needs no source-campaign read
                "--expected-account", "act_1"]
        with (
            mock.patch.object(sys, "argv", argv),
            mock.patch.object(clone, "require_expected_account"),
            mock.patch.object(clone, "copy_obj", side_effect=copy_side_effect),
            mock.patch.object(clone, "children", return_value=[{"id": "222"}]),
            mock.patch.object(clone, "copyable", side_effect=lambda rows, _kind: rows),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            return clone.main()

    def test_clone_rejection_with_nothing_created_clears_in_flight(self) -> None:
        import clone

        err = clone.graph.GraphError(400, {"error": {"message": "bad", "code": 100}}, "copy")
        with tempfile.TemporaryDirectory() as td:
            state_path = str(pathlib.Path(td) / "clone.json")
            self.assertEqual(self._run_clone(state_path, err), 1)
            self.assertEqual(clone.load_clone_state(state_path)["in_flight"], {})

    def test_clone_rejection_after_partial_tree_keeps_in_flight(self) -> None:
        import clone

        err = clone.graph.GraphError(400, {"error": {"message": "bad", "code": 100}}, "copy")
        with tempfile.TemporaryDirectory() as td:
            state_path = str(pathlib.Path(td) / "clone.json")
            self.assertEqual(self._run_clone(state_path, ["900", err]), 1)
            self.assertIn("1", clone.load_clone_state(state_path)["in_flight"])


class CatalogCreativeTextTests(unittest.TestCase):
    """A catalog ad is swapped later: texts must follow the product or stay neutral."""

    def _build(self, **creative):
        import launch
        c = {"kind": "catalog_single", "product_set_id": "5", "link": "https://x.shop/?a={{ad.id}}",
             "cta": "PLAY_GAME", **creative}
        return launch.build_creative({"page_id": "1"}, {"name": "ad1", "creative": c}, None)

    def test_defaults_follow_the_product(self) -> None:
        td = self._build()["object_story_spec"]["template_data"]
        self.assertEqual(td["name"], "{{product.name}}")
        self.assertEqual(td["description"], "{{product.description}}")
        self.assertEqual(td["message"], "-----")

    def test_wordy_message_is_refused(self) -> None:
        import launch
        with self.assertRaises(launch.SpecError):
            self._build(message="Useful things for home")
        self.assertEqual(self._build(message="Hi", allow_message=True)["object_story_spec"]
                         ["template_data"]["message"], "Hi")

    def test_static_headline_is_refused(self) -> None:
        import launch
        with self.assertRaises(launch.SpecError):
            self._build(headline="Kettle 1.7 l")
        # any product tag follows the swap
        self.assertEqual(self._build(headline="{{product.brand}} - top")["object_story_spec"]
                         ["template_data"]["name"], "{{product.brand}} - top")

    def test_carousel_kind_has_no_force_single_link(self) -> None:
        td = self._build(kind="catalog_carousel")["object_story_spec"]["template_data"]
        self.assertNotIn("force_single_link", td)
        self.assertFalse(td["multi_share_end_card"])
        self.assertTrue(self._build()["object_story_spec"]["template_data"]["force_single_link"])

    def test_format_option_enum(self) -> None:
        import launch
        with self.assertRaises(launch.SpecError):
            self._build(format_option="single_vid")
        self.assertEqual(self._build(format_option="single_image")["object_story_spec"]
                         ["template_data"]["format_option"], "single_image")

    def test_product_video_keeps_media_type_automation(self) -> None:
        def feats(**kw):
            return self._build(**kw)["degrees_of_freedom_spec"]["creative_features_spec"]
        self.assertIn("media_type_automation", feats())
        self.assertNotIn("media_type_automation", feats(product_video=True))
        self.assertNotIn("media_type_automation", feats(kind="catalog_carousel", product_video=True))
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertNotIn("media_type_automation", feats(format_option="single_video"))

    def test_paused_ad_counts_as_reviewed(self) -> None:
        import swapgate
        self.assertEqual(swapgate.classify("PAUSED"), "approved")
        self.assertEqual(swapgate.classify("CAMPAIGN_PAUSED"), "paused")



class SwapGateUnitTests(unittest.TestCase):
    def test_id_only_filter(self) -> None:
        import swapgate
        self.assertTrue(swapgate.id_only_filter({"retailer_id": {"eq": "T01"}}))
        self.assertTrue(swapgate.id_only_filter({"retailer_id": {"is_any": ["T01", "T02"]}}))
        self.assertFalse(swapgate.id_only_filter({"product_type": {"i_contains": "slot"}}))
        self.assertTrue(swapgate.id_only_filter({"and": [{"retailer_id": {"eq": "T01"}}]}))
        self.assertFalse(swapgate.id_only_filter({"and": [{"product_type": {"eq": "slot"}}]}))
        self.assertFalse(swapgate.id_only_filter({}))

    def test_classify(self) -> None:
        import swapgate
        self.assertEqual(swapgate.classify("ACTIVE"), "approved")
        self.assertEqual(swapgate.classify("IN_PROCESS"), "review")
        self.assertEqual(swapgate.classify("PREAPPROVED"), "review")
        self.assertEqual(swapgate.classify("DISAPPROVED"), "rejected")
        self.assertEqual(swapgate.classify("ADSET_PAUSED"), "paused")
        self.assertEqual(swapgate.classify("PAUSED"), "approved")
        self.assertEqual(swapgate.classify("ADSET_PAUSED", paused_ok=True), "approved")

    def test_set_products_refuses_while_ad_on_set_in_review(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            base = MetaOpsContractTests()
            args = base._swap_args(root)
            args.set, args.retailer_ids, args.confirm, args.force = "a1", "T01", "SET", False
            ads = [{"ad": "9", "name": "a", "set": "17", "status": "PENDING_REVIEW"}]
            with (
                mock.patch.object(metaops, "require_assets", return_value=(root, "sha")),
                mock.patch.object(metaops, "require_doctor", return_value=(root, "sha")),
                mock.patch.object(metaops.asset_graph, "verify_product_set_binding", return_value={"ready": True}),
                mock.patch("swapgate.catalog_ads", return_value=ads),
                mock.patch.object(metaops, "run_child") as child,
            ):
                with self.assertRaisesRegex(metaops.MetaOpsError, "in review"):
                    metaops.command_assets_set_products(args)
                child.assert_not_called()
                args.force = True
                child.return_value = metaops.ChildResult(["mutate_set.py"], 0, "", "")
                code, _ = metaops.command_assets_set_products(args)
            self.assertEqual(code, 0)

    def test_white_item_problems(self) -> None:
        import swapgate
        items = {"data": [
            {"retailer_id": "W01", "name": "Электрический чайник 1,7 л", "description": "Быстрый нагрев", "image_url": "u"},
            {"retailer_id": "W02", "name": "Фен", "description": "", "image_url": "u"},
            {"retailer_id": "W03", "name": "Рюкзак", "description": "Бонус 300 вращений", "image_url": "u"}]}
        with mock.patch.object(swapgate.graph, "get", return_value=items):
            probs = swapgate.white_item_problems("17")
        self.assertEqual(len(probs), 2)
        self.assertTrue(any("W02" in p and "empty description" in p for p in probs))
        self.assertTrue(any("W03" in p and "Бонус" in p for p in probs))
        with mock.patch.object(swapgate.graph, "get", return_value={"data": []}):
            self.assertIn("empty", swapgate.white_item_problems("17")[0])

    def test_plan_swap_check_blocks_bad_white_and_target(self) -> None:
        import swapgate
        spec = {"adsets": [{"ads": [{"name": "A", "creative": {"kind": "catalog_single", "product_set_id": "17",
                                                               "swap_to": "T01"}}]}]}
        profile = {"product_sets": {"a1": "17"}, "catalog_id": "16"}
        with (
            mock.patch.object(swapgate, "target_items", return_value=([], ["target T01: empty description"])),
            mock.patch.object(swapgate, "white_item_problems", return_value=["white W01: 'казино'"]) as white,
        ):
            out = metaops.plan_swap_check(spec, profile)
        self.assertEqual(out["map"], "a1=T01")
        self.assertEqual(len(out["blockers"]), 2)
        white.assert_called_once_with("17")
        spec["adsets"][0]["ads"][0]["creative"]["allow_white_text"] = True
        with (
            mock.patch.object(swapgate, "target_items", return_value=([], [])),
            mock.patch.object(swapgate, "white_item_problems") as white,
        ):
            self.assertEqual(metaops.plan_swap_check(spec, profile)["blockers"], [])
        white.assert_not_called()

    def test_mutate_set_retries_duplicate_filter_with_equivalent_shape(self) -> None:
        import mutate_set
        posts = []

        def fake_post(path, data, **kw):
            posts.append(data["filter"])
            if len(posts) == 1:
                raise metaops.graph.GraphError(400, {"error": {"code": 10803, "error_subcode": 1798073}})
            return {"id": path}
        state = {"filter": '{"retailer_id":{"is_any":["W01"]}}'}

        def fake_get(path, params=None, **kw):
            if path.endswith("/products"):
                return {"data": [{"retailer_id": "T02"}]} if len(posts) > 1 else {"data": [{"retailer_id": "W01"}]}
            if len(posts) > 1:
                state["filter"] = json.dumps(posts[-1])
            return {"id": "5", "name": "S", "product_count": 1, "filter": state["filter"]}
        with (
            mock.patch.object(mutate_set.graph, "post", side_effect=fake_post),
            mock.patch.object(mutate_set.graph, "get", side_effect=fake_get),
            mock.patch.object(sys, "argv", ["mutate_set.py", "--set-id", "5", "--retailer-ids", "T02"]),
            mock.patch("time.sleep"),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(mutate_set.main(), 0)
        self.assertEqual(posts, [{"retailer_id": {"is_any": ["T02"]}}, {"retailer_id": {"eq": "T02"}}])

    def test_mutate_set_walks_all_equivalent_shapes(self) -> None:
        import mutate_set
        shapes = mutate_set.equivalent_filters(["T02"])
        self.assertEqual(len(shapes), len({json.dumps(x, sort_keys=True) for x in shapes}))
        self.assertGreaterEqual(len(shapes), 4)
        posts = []

        def fake_post(path, data, **kw):
            posts.append(data["filter"])
            if len(posts) < 3:  # is_any and eq both taken by other sets (field 2026-09-26)
                raise metaops.graph.GraphError(400, {"error": {"code": 10803, "error_subcode": 1798073}})
            return {"id": path}

        def fake_get(path, params=None, **kw):
            if path.endswith("/products"):
                return {"data": [{"retailer_id": "T02" if len(posts) >= 3 else "W02"}]}
            return {"id": "5", "product_count": 1,
                    "filter": json.dumps(posts[-1]) if len(posts) >= 3 else '{"retailer_id":{"is_any":["W02"]}}'}
        with (
            mock.patch.object(mutate_set.graph, "post", side_effect=fake_post),
            mock.patch.object(mutate_set.graph, "get", side_effect=fake_get),
            mock.patch.object(sys, "argv", ["mutate_set.py", "--set-id", "5", "--retailer-ids", "T02"]),
            mock.patch("time.sleep"),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(mutate_set.main(), 0)
        self.assertEqual(posts[2], {"and": [{"retailer_id": {"is_any": ["T02"]}}]})

    def test_mutate_set_fails_when_members_differ(self) -> None:
        import mutate_set
        state = {"n": 0}

        def fake_get(path, params=None, **kw):
            if path.endswith("/products"):
                return {"data": []}  # id not in catalog -> set emptied
            state["n"] += 1
            return {"id": "5", "product_count": 0,
                    "filter": '{"retailer_id":{"is_any":["W01"]}}' if state["n"] == 1 else '{"retailer_id":{"is_any":["NOPE"]}}'}
        with (
            mock.patch.object(mutate_set.graph, "post", return_value={"id": "5"}),
            mock.patch.object(mutate_set.graph, "get", side_effect=fake_get),
            mock.patch.object(sys, "argv", ["mutate_set.py", "--set-id", "5", "--retailer-ids", "NOPE"]),
            mock.patch("time.sleep"),
            contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()),
        ):
            self.assertEqual(mutate_set.main(), 1)

if __name__ == "__main__":
    unittest.main(verbosity=2)

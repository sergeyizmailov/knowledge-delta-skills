#!/usr/bin/env python3
"""Offline contract tests for cmd_edit.py. No network or real credentials."""

from __future__ import annotations
import os as _os, tempfile as _tempfile
_os.environ["METAOPS_PACE_DIR"] = _tempfile.mkdtemp(prefix="metaops-pace-test-")
_os.environ.setdefault("METAOPS_CREATE_GAP_HOURS", "0")

import argparse
import contextlib
import io
import json
import os
import pathlib
import tempfile
import unittest
from unittest import mock

import clone
import cmd_edit
import edit
import edit_tags
import edit_targeting
import metaops
import rules

os.environ.setdefault("META_TOKEN", "TEST_TOKEN")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)
    cmd_edit.register(sub, metaops)
    return ap


def make_workspace(root: pathlib.Path) -> metaops.meta_workspace.Workspace:
    path = root / "workspace.json"
    path.write_text(json.dumps({
        "schema": metaops.meta_workspace.WORKSPACE_SCHEMA,
        "name": "contract",
        "api_version": metaops.graph.API_VERSION,
        "blocked_accounts": [],
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
    }), encoding="utf-8")
    return metaops.meta_workspace.load_workspace(str(path))


def fake_child(stdout: str, returncode: int = 0, argv: list[str] | None = None) -> metaops.ChildResult:
    return metaops.ChildResult(argv=argv or [], returncode=returncode, stdout=stdout, stderr="")


class CmdEditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.workspace = make_workspace(self.root)
        self.ap = build_parser()

    def parse(self, argv: list[str], timeout: int = 30) -> argparse.Namespace:
        args = self.ap.parse_args(argv)
        args.workspace_obj = self.workspace
        args.profile = "test"
        args.timeout = timeout
        return args

    # --- JSON line parsing -------------------------------------------------

    def test_parse_last_json_line_picks_final_line(self) -> None:
        stdout = "human line one\n{\"not\": \"this one\"}\nhuman line two\n{\"schema\": \"edit.result/v1\", \"ok\": true}\n"
        self.assertEqual(
            cmd_edit._parse_last_json_line(stdout),
            {"schema": "edit.result/v1", "ok": True},
        )

    def test_parse_last_json_line_empty_when_absent(self) -> None:
        self.assertEqual(cmd_edit._parse_last_json_line("no json here\n"), {})

    def test_edit_help_expands_percent_literals(self) -> None:
        with self.assertRaises(SystemExit) as exit_info:
            self.ap.parse_args(["edit", "--help"])
        self.assertEqual(exit_info.exception.code, 0)

    # --- edit status ---------------------------------------------------------

    def test_edit_status_active_requires_confirm_spend(self) -> None:
        args = self.parse(["edit", "status", "--ids", "1,2", "--status", "ACTIVE"])
        with self.assertRaises(metaops.MetaOpsError):
            args.handler(args)

    def test_edit_status_active_with_confirm_translates_to_activate(self) -> None:
        args = self.parse([
            "edit", "status", "--ids", "1,2", "--status", "ACTIVE", "--confirm", "SPEND",
        ])
        with mock.patch.object(
            metaops, "run_child",
            return_value=fake_child('{"schema": "edit.result/v1", "ok": true, "count": 2}\n'),
        ) as run_child:
            code, payload = args.handler(args)
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["count"], 2)
        script, child_args, _timeout = run_child.call_args[0]
        self.assertEqual(script, "edit.py")
        self.assertEqual(child_args, [
            "--ids", "1,2", "--status", "ACTIVE", "--confirm", "ACTIVATE",
            "--expected-account", "act_1",
        ])

    def test_edit_status_paused_requires_delivery_confirm(self) -> None:
        args = self.parse(["edit", "status", "--ids", "1,2", "--status", "PAUSED"])
        with self.assertRaises(metaops.MetaOpsError):
            args.handler(args)
        args = self.parse([
            "edit", "status", "--ids", "1,2", "--status", "PAUSED", "--confirm", "PAUSE",
        ])
        with mock.patch.object(
            metaops, "run_child",
            return_value=fake_child('{"schema": "edit.result/v1", "ok": true}\n'),
        ) as run_child:
            code, payload = args.handler(args)
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        _script, child_args, _timeout = run_child.call_args[0]
        self.assertIn("--confirm", child_args)
        self.assertEqual(child_args[child_args.index("--confirm") + 1], "PAUSE")
        self.assertEqual(child_args[-2:], ["--expected-account", "act_1"])

    def test_edit_status_state_account_mismatch_refused(self) -> None:
        state_path = self.root / "state.json"
        state_path.write_text(json.dumps({"spec_account": "act_2", "objects": {}}), encoding="utf-8")
        args = self.parse([
            "edit", "status", "--state", str(state_path), "--level", "campaign", "--status", "PAUSED", "--confirm", "PAUSE",
        ])
        with self.assertRaises(metaops.MetaOpsError):
            args.handler(args)

    def test_edit_status_state_matching_account_passes(self) -> None:
        state_path = self.root / "state.json"
        state_path.write_text(json.dumps({"spec_account": "act_1", "objects": {}}), encoding="utf-8")
        args = self.parse([
            "edit", "status", "--state", str(state_path), "--level", "campaign", "--status", "PAUSED", "--confirm", "PAUSE",
        ])
        with mock.patch.object(
            metaops, "run_child",
            return_value=fake_child('{"schema": "edit.result/v1", "ok": true}\n'),
        ) as run_child:
            code, _payload = args.handler(args)
        self.assertEqual(code, 0)
        _script, child_args, _timeout = run_child.call_args[0]
        self.assertEqual(child_args, [
            "--state", str(state_path), "--level", "campaign", "--status", "PAUSED",
            "--confirm", "PAUSE", "--expected-account", "act_1",
        ])

    def test_edit_status_all_routes_through_profile_account(self) -> None:
        args = self.parse(["edit", "status", "--all", "--level", "adset", "--status", "PAUSED", "--confirm", "PAUSE"])
        with mock.patch.object(
            metaops, "run_child",
            return_value=fake_child('{"schema": "edit.result/v1", "ok": true}\n'),
        ) as run_child:
            args.handler(args)
        _script, child_args, _timeout = run_child.call_args[0]
        self.assertEqual(
            child_args, ["--account", "act_1", "--level", "adset", "--all", "--status", "PAUSED",
                         "--confirm", "PAUSE", "--expected-account", "act_1"]
        )

    def test_edit_status_child_failure_is_reported(self) -> None:
        args = self.parse(["edit", "status", "--ids", "1", "--status", "PAUSED", "--confirm", "PAUSE"])
        with mock.patch.object(
            metaops, "run_child",
            return_value=fake_child("boom\n", returncode=1),
        ):
            code, payload = args.handler(args)
        self.assertEqual(code, 1)
        self.assertFalse(payload["ok"])

    # --- edit budget -----------------------------------------------------

    def test_edit_budget_positive_pct_requires_confirm(self) -> None:
        args = self.parse(["edit", "budget", "--ids", "1", "--budget-pct", "+20"])
        with self.assertRaises(metaops.MetaOpsError):
            args.handler(args)

    def test_edit_budget_negative_pct_needs_no_confirm(self) -> None:
        args = self.parse(["edit", "budget", "--ids", "1", "--budget-pct", "-15"])
        with mock.patch.object(
            metaops, "run_child",
            return_value=fake_child('{"schema": "edit.result/v1", "ok": true}\n'),
        ) as run_child:
            code, _payload = args.handler(args)
        self.assertEqual(code, 0)
        _script, child_args, _timeout = run_child.call_args[0]
        self.assertEqual(child_args, ["--ids", "1", "--expected-account", "act_1", "--budget-pct", "-15"])

    def test_edit_budget_minor_always_requires_confirm(self) -> None:
        args = self.parse(["edit", "budget", "--ids", "1", "--budget-minor", "500"])
        with self.assertRaises(metaops.MetaOpsError):
            args.handler(args)
        args = self.parse([
            "edit", "budget", "--ids", "1", "--budget-minor", "500", "--confirm", "SPEND",
            "--force-step",
        ])
        with mock.patch.object(
            metaops, "run_child",
            return_value=fake_child('{"schema": "edit.result/v1", "ok": true}\n'),
        ) as run_child:
            code, _payload = args.handler(args)
        self.assertEqual(code, 0)
        _script, child_args, _timeout = run_child.call_args[0]
        self.assertEqual(child_args, ["--ids", "1", "--expected-account", "act_1", "--budget-minor", "500", "--force-step"])

    def test_edit_budget_rejects_both_forms(self) -> None:
        # argparse's mutually-exclusive group refuses --budget-minor with --budget-pct at parse time.
        with self.assertRaises(SystemExit):
            self.ap.parse_args([
                "edit", "budget", "--ids", "1", "--budget-minor", "500", "--budget-pct", "+10",
            ])

    # --- edit rename -----------------------------------------------------

    def test_edit_rename_builds_args(self) -> None:
        args = self.parse(["edit", "rename", "--ids", "1,2", "--prefix", "J41|", "--suffix", "|v2"])
        with mock.patch.object(
            metaops, "run_child",
            return_value=fake_child('{"schema": "edit.result/v1", "ok": true}\n'),
        ) as run_child:
            code, _payload = args.handler(args)
        self.assertEqual(code, 0)
        _script, child_args, _timeout = run_child.call_args[0]
        self.assertEqual(
            child_args, ["--ids", "1,2", "--expected-account", "act_1", "--rename-prefix", "J41|", "--rename-suffix", "|v2"]
        )

    # --- edit ramp ---------------------------------------------------------

    def test_edit_ramp_requires_confirm_ramp(self) -> None:
        args = self.parse(["edit", "ramp", "--ids", "1", "--step", "20"])
        with self.assertRaises(metaops.MetaOpsError):
            args.handler(args)

    def test_edit_ramp_wrong_confirm_literal_refused(self) -> None:
        args = self.parse(["edit", "ramp", "--ids", "1", "--step", "20", "--confirm", "YES"])
        with self.assertRaises(metaops.MetaOpsError):
            args.handler(args)

    def test_edit_ramp_step_over_guard_refused(self) -> None:
        args = self.parse(["edit", "ramp", "--ids", "1", "--step", "25", "--confirm", "RAMP"])
        with self.assertRaises(metaops.MetaOpsError):
            args.handler(args)

    def test_edit_ramp_makes_exactly_one_guarded_call(self) -> None:
        args = self.parse(["edit", "ramp", "--ids", "1", "--step", "20", "--confirm", "RAMP"])
        with mock.patch.object(
            metaops, "run_child",
            return_value=fake_child('{"schema": "edit.result/v1", "ok": true}\n'),
        ) as run_child:
            code, payload = args.handler(args)
        self.assertEqual(code, 0)
        run_child.assert_called_once()
        _script, child_args, _timeout = run_child.call_args[0]
        self.assertEqual(child_args, ["--ids", "1", "--expected-account", "act_1", "--budget-pct", "+20"])
        self.assertEqual(payload["data"]["step_pct"], 20)

    def test_edit_ramp_propagates_child_failure(self) -> None:
        args = self.parse(["edit", "ramp", "--ids", "1", "--step", "20", "--confirm", "RAMP"])
        with mock.patch.object(
            metaops, "run_child",
            return_value=fake_child("boom\n", returncode=1),
        ) as run_child:
            code, payload = args.handler(args)
        self.assertEqual(code, 1)
        self.assertFalse(payload["ok"])
        self.assertEqual(run_child.call_count, 1)

    # --- edit targeting ---------------------------------------------------

    def test_edit_targeting_requires_scalar_flag(self) -> None:
        args = self.parse(["edit", "targeting", "--ids", "1", "--confirm", "TARGETING"])
        with self.assertRaises(metaops.MetaOpsError):
            args.handler(args)

    def test_edit_targeting_requires_confirm_literal(self) -> None:
        args = self.parse(["edit", "targeting", "--ids", "1", "--user-os", "iOS"])
        with self.assertRaises(metaops.MetaOpsError):
            args.handler(args)

    def test_edit_targeting_confirm_required_even_under_dry_run(self) -> None:
        args = self.parse(["edit", "targeting", "--ids", "1", "--user-os", "iOS", "--dry-run"])
        with self.assertRaises(metaops.MetaOpsError):
            args.handler(args)

    def test_edit_targeting_ids_builds_args(self) -> None:
        args = self.parse([
            "edit", "targeting", "--ids", "1,2", "--user-os", "iOS,Android", "--confirm", "TARGETING",
        ])
        with mock.patch.object(
            metaops, "run_child",
            return_value=fake_child('{"schema": "edit_targeting.result/v1", "ok": true}\n'),
        ) as run_child:
            code, payload = args.handler(args)
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        script, child_args, _timeout = run_child.call_args[0]
        self.assertEqual(script, "edit_targeting.py")
        self.assertEqual(child_args, [
            "--ids", "1,2", "--user-os", "iOS,Android", "--confirm", "TARGETING",
            "--expected-account", "act_1",
        ])

    def test_edit_targeting_dry_run_passes_dry_run_flag(self) -> None:
        args = self.parse([
            "edit", "targeting", "--ids", "1", "--user-os", "iOS", "--confirm", "TARGETING", "--dry-run",
        ])
        with mock.patch.object(
            metaops, "run_child",
            return_value=fake_child('{"schema": "edit_targeting.result/v1", "ok": true}\n'),
        ) as run_child:
            args.handler(args)
        _script, child_args, _timeout = run_child.call_args[0]
        self.assertIn("--dry-run", child_args)

    def test_edit_targeting_state_account_mismatch_refused(self) -> None:
        state_path = self.root / "state.json"
        state_path.write_text(json.dumps({"spec_account": "act_2", "objects": {}}), encoding="utf-8")
        args = self.parse([
            "edit", "targeting", "--state", str(state_path), "--user-os", "iOS", "--confirm", "TARGETING",
        ])
        with self.assertRaises(metaops.MetaOpsError):
            args.handler(args)

    def test_edit_targeting_all_routes_through_profile_account(self) -> None:
        args = self.parse(["edit", "targeting", "--all", "--user-os", "iOS", "--confirm", "TARGETING"])
        with mock.patch.object(
            metaops, "run_child",
            return_value=fake_child('{"schema": "edit_targeting.result/v1", "ok": true}\n'),
        ) as run_child:
            args.handler(args)
        _script, child_args, _timeout = run_child.call_args[0]
        self.assertEqual(child_args, [
            "--account", "act_1", "--all", "--user-os", "iOS", "--confirm", "TARGETING",
            "--expected-account", "act_1",
        ])

    def test_edit_targeting_child_failure_nonzero_exit(self) -> None:
        args = self.parse(["edit", "targeting", "--ids", "1", "--user-os", "iOS", "--confirm", "TARGETING"])
        with mock.patch.object(
            metaops, "run_child",
            return_value=fake_child("boom\n", returncode=1),
        ):
            code, payload = args.handler(args)
        self.assertEqual(code, 1)
        self.assertFalse(payload["ok"])

    # --- edit_targeting.py (child script; read-modify-write contract) -----

    def test_edit_targeting_child_preserves_untouched_keys_no_delta_post(self) -> None:
        argv = [
            "edit_targeting.py", "--ids", "42", "--user-os", "iOS,Android", "--confirm", "TARGETING",
            "--expected-account", "act_1",
        ]
        current_targeting = {
            "geo_locations": {"countries": ["US"]},
            "custom_audiences": [{"id": "555"}],
            "user_os": ["Android"],
        }
        read_back = dict(current_targeting, user_os=["iOS", "Android"])
        with (
            mock.patch.object(edit_targeting.sys, "argv", argv),
            mock.patch.object(edit_targeting.graph, "require_write_authority"),
            mock.patch.object(
                edit_targeting.graph, "get",
                side_effect=[
                    {"id": "42", "name": "AS1", "targeting": current_targeting, "account_id": "1"},
                    {"id": "42", "name": "AS1", "targeting": read_back},
                ],
            ),
            mock.patch.object(edit_targeting.graph, "post", return_value={}) as post,
        ):
            self.assertEqual(edit_targeting.main(), 0)
        post.assert_called_once()
        posted_id, posted_payload = post.call_args.args[0], post.call_args.args[1]
        self.assertEqual(posted_id, "42")
        # The whole targeting object travels every time — never a bare {"user_os": [...]}.
        self.assertEqual(posted_payload["targeting"]["geo_locations"], {"countries": ["US"]})
        self.assertEqual(posted_payload["targeting"]["custom_audiences"], [{"id": "555"}])
        self.assertEqual(posted_payload["targeting"]["user_os"], ["iOS", "Android"])
        self.assertEqual(set(posted_payload["targeting"]), set(current_targeting))

    def test_edit_targeting_child_dry_run_writes_nothing(self) -> None:
        argv = [
            "edit_targeting.py", "--ids", "42", "--user-os", "iOS", "--confirm", "TARGETING", "--dry-run",
        ]
        current_targeting = {"geo_locations": {"countries": ["US"]}, "user_os": ["Android"]}
        with (
            mock.patch.object(edit_targeting.sys, "argv", argv),
            mock.patch.object(edit_targeting.graph, "require_write_authority"),
            mock.patch.object(
                edit_targeting.graph, "get",
                return_value={"id": "42", "name": "AS1", "targeting": current_targeting, "account_id": "1"},
            ),
            mock.patch.object(edit_targeting.graph, "post") as post,
        ):
            self.assertEqual(edit_targeting.main(), 0)
        post.assert_not_called()

    def test_edit_targeting_child_refuses_write_when_get_fails(self) -> None:
        argv = [
            "edit_targeting.py", "--ids", "42", "--user-os", "iOS", "--confirm", "TARGETING",
        ]
        with (
            mock.patch.object(edit_targeting.sys, "argv", argv),
            mock.patch.object(edit_targeting.graph, "require_write_authority"),
            mock.patch.object(
                edit_targeting.graph, "get",
                side_effect=edit_targeting.graph.GraphError(
                    500, {"error": {"message": "boom", "code": 1}}, "read 42",
                ),
            ),
            mock.patch.object(edit_targeting.graph, "post") as post,
        ):
            self.assertEqual(edit_targeting.main(), 1)
        post.assert_not_called()

    def test_edit_targeting_child_rejects_id_outside_expected_account(self) -> None:
        argv = [
            "edit_targeting.py", "--ids", "42", "--user-os", "iOS", "--confirm", "TARGETING",
            "--expected-account", "act_1",
        ]
        foreign = {"id": "42", "name": "foreign", "targeting": {"geo_locations": {}}, "account_id": "2"}
        with (
            mock.patch.object(edit_targeting.sys, "argv", argv),
            mock.patch.object(edit_targeting.graph, "require_write_authority"),
            mock.patch.object(edit_targeting.graph, "get", return_value=foreign),
            mock.patch.object(edit_targeting.graph, "post") as post,
        ):
            self.assertEqual(edit_targeting.main(), 1)
        post.assert_not_called()

    def test_edit_targeting_child_partial_failure_nonzero_exit(self) -> None:
        argv = [
            "edit_targeting.py", "--ids", "42,43", "--user-os", "iOS", "--confirm", "TARGETING",
        ]
        good = {"id": "42", "name": "AS1", "targeting": {"geo_locations": {}}, "account_id": "1"}

        def get_side_effect(oid, **_kw):
            if oid == "42":
                return good
            raise edit_targeting.graph.GraphError(500, {"error": {"message": "boom", "code": 1}}, "read 43")

        with (
            mock.patch.object(edit_targeting.sys, "argv", argv),
            mock.patch.object(edit_targeting.graph, "require_write_authority"),
            mock.patch.object(edit_targeting.graph, "get", side_effect=get_side_effect),
            mock.patch.object(edit_targeting.graph, "post", return_value={}),
        ):
            self.assertEqual(edit_targeting.main(), 1)

    # --- edit tags ---------------------------------------------------------

    def test_edit_tags_requires_one_of_url_tags_or_template_url(self) -> None:
        args = self.parse(["edit", "tags", "--ids", "1", "--confirm", "TAGS"])
        with self.assertRaises(metaops.MetaOpsError):
            args.handler(args)

    def test_edit_tags_requires_confirm_literal(self) -> None:
        args = self.parse(["edit", "tags", "--ids", "1", "--url-tags", "sub1={{ad.id}}"])
        with self.assertRaises(metaops.MetaOpsError):
            args.handler(args)

    def test_edit_tags_builds_args_with_both_flags(self) -> None:
        args = self.parse([
            "edit", "tags", "--ids", "1,2", "--url-tags", "sub1={{ad.id}}",
            "--template-url", "https://x.example/?id={{product.id}}", "--confirm", "TAGS",
        ])
        with mock.patch.object(
            metaops, "run_child",
            return_value=fake_child('{"schema": "edit_tags.result/v1", "ok": true}\n'),
        ) as run_child:
            code, payload = args.handler(args)
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        self.assertIn("first-publish snapshot", payload["next_action"])
        script, child_args, _timeout = run_child.call_args[0]
        self.assertEqual(script, "edit_tags.py")
        self.assertEqual(child_args, [
            "--ids", "1,2", "--url-tags", "sub1={{ad.id}}",
            "--template-url", "https://x.example/?id={{product.id}}",
            "--confirm", "TAGS", "--expected-account", "act_1",
        ])

    def test_edit_tags_child_failure_nonzero_exit(self) -> None:
        args = self.parse(["edit", "tags", "--ids", "1", "--url-tags", "sub1={{ad.id}}", "--confirm", "TAGS"])
        with mock.patch.object(
            metaops, "run_child",
            return_value=fake_child("boom\n", returncode=1),
        ):
            code, payload = args.handler(args)
        self.assertEqual(code, 1)
        self.assertFalse(payload["ok"])

    # --- edit_tags.py (child script; clone-and-swap, catalog handling) -----

    def test_edit_tags_child_catalog_creative_skipped_without_template_url(self) -> None:
        argv = [
            "edit_tags.py", "--ids", "77", "--url-tags", "sub1={{ad.id}}", "--confirm", "TAGS",
        ]
        catalog_ad = {
            "id": "77", "name": "Catalog Ad", "account_id": "1",
            "creative": {"id": "500", "product_set_id": "999", "name": "Catalog Creative"},
        }
        with (
            mock.patch.object(edit_tags.sys, "argv", argv),
            mock.patch.object(edit_tags.graph, "require_write_authority"),
            mock.patch.object(edit_tags.graph, "get", return_value=catalog_ad),
            mock.patch.object(edit_tags.graph, "post") as post,
        ):
            self.assertEqual(edit_tags.main(), 0)
        post.assert_not_called()

    def test_edit_tags_child_catalog_creative_uses_template_url_spec(self) -> None:
        argv = [
            "edit_tags.py", "--ids", "77", "--template-url", "https://x.example/?id={{product.id}}",
            "--confirm", "TAGS",
        ]
        catalog_ad = {
            "id": "77", "name": "Catalog Ad", "account_id": "1",
            "creative": {"id": "500", "product_set_id": "999", "name": "Catalog Creative"},
        }
        readback = {
            "name": "Catalog Ad",
            "creative": {"id": "600", "template_url_spec": {"web": {"url": "https://x.example/?id={{product.id}}"}}},
        }
        with (
            mock.patch.object(edit_tags.sys, "argv", argv),
            mock.patch.object(edit_tags.graph, "require_write_authority"),
            mock.patch.object(edit_tags.graph, "get", side_effect=[catalog_ad, readback]),
            mock.patch.object(edit_tags.graph, "post", side_effect=[{"id": "600"}, {}]) as post,
        ):
            self.assertEqual(edit_tags.main(), 0)
        self.assertEqual(post.call_count, 2)
        create_path, create_payload = post.call_args_list[0].args[0], post.call_args_list[0].args[1]
        self.assertEqual(create_path, "act_1/adcreatives")
        self.assertEqual(create_payload["template_url_spec"], {"web": {"url": "https://x.example/?id={{product.id}}"}})
        self.assertNotIn("url_tags", create_payload)
        swap_id, swap_payload = post.call_args_list[1].args[0], post.call_args_list[1].args[1]
        self.assertEqual(swap_id, "77")
        self.assertEqual(swap_payload, {"creative": {"creative_id": "600"}})

    def test_edit_tags_child_non_catalog_writes_url_tags_via_clone_and_swap(self) -> None:
        argv = [
            "edit_tags.py", "--ids", "77", "--url-tags", "sub1={{ad.id}}", "--confirm", "TAGS",
        ]
        plain_ad = {
            "id": "77", "name": "Plain Ad", "account_id": "1",
            "creative": {
                "id": "500", "name": "Plain Creative",
                "object_story_spec": {"page_id": "2", "link_data": {"link": "https://x.example"}},
                "url_tags": "sub1=OLD",
            },
        }
        readback = {"name": "Plain Ad", "creative": {"id": "600", "url_tags": "sub1={{ad.id}}"}}
        with (
            mock.patch.object(edit_tags.sys, "argv", argv),
            mock.patch.object(edit_tags.graph, "require_write_authority"),
            mock.patch.object(edit_tags.graph, "get", side_effect=[plain_ad, readback]),
            mock.patch.object(edit_tags.graph, "post", side_effect=[{"id": "600"}, {}]) as post,
        ):
            self.assertEqual(edit_tags.main(), 0)
        create_path, create_payload = post.call_args_list[0].args[0], post.call_args_list[0].args[1]
        self.assertEqual(create_path, "act_1/adcreatives")
        self.assertEqual(create_payload["url_tags"], "sub1={{ad.id}}")
        self.assertEqual(create_payload["object_story_spec"], plain_ad["creative"]["object_story_spec"])
        swap_id, swap_payload = post.call_args_list[1].args[0], post.call_args_list[1].args[1]
        self.assertEqual(swap_id, "77")
        self.assertEqual(swap_payload, {"creative": {"creative_id": "600"}})

    def test_edit_tags_child_skips_creative_with_authorization_category(self) -> None:
        argv = [
            "edit_tags.py", "--ids", "77", "--url-tags", "sub1={{ad.id}}", "--confirm", "TAGS",
        ]
        political_ad = {
            "id": "77", "name": "Political Ad", "account_id": "1",
            "creative": {
                "id": "500", "name": "Political Creative",
                "object_story_spec": {"page_id": "2", "link_data": {"link": "https://x.example"}},
                "authorization_category": "POLITICAL",
            },
        }
        buf = io.StringIO()
        with (
            mock.patch.object(edit_tags.sys, "argv", argv),
            mock.patch.object(edit_tags.graph, "require_write_authority"),
            mock.patch.object(edit_tags.graph, "get", return_value=political_ad),
            mock.patch.object(edit_tags.graph, "post") as post,
            contextlib.redirect_stdout(buf),
        ):
            self.assertEqual(edit_tags.main(), 0)
        post.assert_not_called()
        row = cmd_edit._parse_last_json_line(buf.getvalue())["results"][0]
        self.assertEqual(row["fields"], ["authorization_category"])
        self.assertIn("authorization_category", row["reason"])
        self.assertTrue(row["skipped"])

    def test_edit_tags_child_skips_creative_with_object_story_id(self) -> None:
        argv = [
            "edit_tags.py", "--ids", "77", "--url-tags", "sub1={{ad.id}}", "--confirm", "TAGS",
        ]
        boosted_post_ad = {
            "id": "77", "name": "Boosted Ad", "account_id": "1",
            "creative": {"id": "500", "name": "Boosted Creative", "object_story_id": "2_12345"},
        }
        buf = io.StringIO()
        with (
            mock.patch.object(edit_tags.sys, "argv", argv),
            mock.patch.object(edit_tags.graph, "require_write_authority"),
            mock.patch.object(edit_tags.graph, "get", return_value=boosted_post_ad),
            mock.patch.object(edit_tags.graph, "post") as post,
            contextlib.redirect_stdout(buf),
        ):
            self.assertEqual(edit_tags.main(), 0)
        post.assert_not_called()
        row = cmd_edit._parse_last_json_line(buf.getvalue())["results"][0]
        self.assertEqual(row["fields"], ["object_story_id"])
        self.assertIn("object_story_id", row["reason"])

    def test_edit_tags_child_skips_creative_with_platform_customizations(self) -> None:
        argv = [
            "edit_tags.py", "--ids", "77", "--url-tags", "sub1={{ad.id}}", "--confirm", "TAGS",
        ]
        stories_ad = {
            "id": "77", "name": "Stories Ad", "account_id": "1",
            "creative": {
                "id": "500", "name": "Stories Creative",
                "object_story_spec": {"page_id": "2", "link_data": {"link": "https://x.example"}},
                "platform_customizations": {"instagram": {"image_hash": "abc"}},
            },
        }
        buf = io.StringIO()
        with (
            mock.patch.object(edit_tags.sys, "argv", argv),
            mock.patch.object(edit_tags.graph, "require_write_authority"),
            mock.patch.object(edit_tags.graph, "get", return_value=stories_ad),
            mock.patch.object(edit_tags.graph, "post") as post,
            contextlib.redirect_stdout(buf),
        ):
            self.assertEqual(edit_tags.main(), 0)
        post.assert_not_called()
        row = cmd_edit._parse_last_json_line(buf.getvalue())["results"][0]
        self.assertEqual(row["fields"], ["platform_customizations"])

    def test_edit_tags_child_swap_failure_reports_orphaned_creative_id(self) -> None:
        argv = [
            "edit_tags.py", "--ids", "77", "--url-tags", "sub1={{ad.id}}", "--confirm", "TAGS",
        ]
        plain_ad = {
            "id": "77", "name": "Plain Ad", "account_id": "1",
            "creative": {
                "id": "500", "name": "Plain Creative",
                "object_story_spec": {"page_id": "2", "link_data": {"link": "https://x.example"}},
                "url_tags": "sub1=OLD",
            },
        }
        buf = io.StringIO()
        with (
            mock.patch.object(edit_tags.sys, "argv", argv),
            mock.patch.object(edit_tags.graph, "require_write_authority"),
            mock.patch.object(edit_tags.graph, "get", return_value=plain_ad),
            mock.patch.object(
                edit_tags.graph, "post",
                side_effect=[
                    {"id": "600"},
                    edit_tags.graph.GraphError(500, {"error": {"message": "swap boom", "code": 1}}, "swap"),
                ],
            ) as post,
            contextlib.redirect_stdout(buf),
        ):
            self.assertEqual(edit_tags.main(), 1)
        self.assertEqual(post.call_count, 2)
        row = cmd_edit._parse_last_json_line(buf.getvalue())["results"][0]
        self.assertFalse(row["ok"])
        self.assertEqual(row["orphaned_creative_id"], "600")

    def test_edit_tags_child_dry_run_writes_nothing(self) -> None:
        argv = [
            "edit_tags.py", "--ids", "77", "--url-tags", "sub1={{ad.id}}", "--confirm", "TAGS", "--dry-run",
        ]
        plain_ad = {
            "id": "77", "name": "Plain Ad", "account_id": "1",
            "creative": {"id": "500", "object_story_spec": {"page_id": "2"}, "url_tags": "sub1=OLD"},
        }
        with (
            mock.patch.object(edit_tags.sys, "argv", argv),
            mock.patch.object(edit_tags.graph, "require_write_authority"),
            mock.patch.object(edit_tags.graph, "get", return_value=plain_ad),
            mock.patch.object(edit_tags.graph, "post") as post,
        ):
            self.assertEqual(edit_tags.main(), 0)
        post.assert_not_called()

    def test_edit_tags_child_rejects_id_outside_expected_account(self) -> None:
        argv = [
            "edit_tags.py", "--ids", "77", "--url-tags", "sub1={{ad.id}}", "--confirm", "TAGS",
            "--expected-account", "act_1",
        ]
        foreign = {
            "id": "77", "name": "foreign", "account_id": "2",
            "creative": {"id": "500", "object_story_spec": {"page_id": "2"}},
        }
        with (
            mock.patch.object(edit_tags.sys, "argv", argv),
            mock.patch.object(edit_tags.graph, "require_write_authority"),
            mock.patch.object(edit_tags.graph, "get", return_value=foreign),
            mock.patch.object(edit_tags.graph, "post") as post,
        ):
            self.assertEqual(edit_tags.main(), 1)
        post.assert_not_called()

    def test_edit_tags_child_partial_failure_nonzero_exit(self) -> None:
        argv = [
            "edit_tags.py", "--ids", "77,78", "--url-tags", "sub1={{ad.id}}", "--confirm", "TAGS",
        ]
        plain_ad = {
            "id": "77", "name": "Plain Ad", "account_id": "1",
            "creative": {"id": "500", "object_story_spec": {"page_id": "2"}, "url_tags": "sub1=OLD"},
        }

        def get_side_effect(oid, **_kw):
            if oid == "77":
                return plain_ad
            raise edit_tags.graph.GraphError(500, {"error": {"message": "boom", "code": 1}}, "read 78")

        with (
            mock.patch.object(edit_tags.sys, "argv", argv),
            mock.patch.object(edit_tags.graph, "require_write_authority"),
            mock.patch.object(edit_tags.graph, "get", side_effect=get_side_effect),
            mock.patch.object(edit_tags.graph, "post", side_effect=[{"id": "600"}, {}]),
        ):
            self.assertEqual(edit_tags.main(), 1)

    # --- clone -----------------------------------------------------------

    def test_clone_builds_positional_and_optional_args(self) -> None:
        args = self.parse([
            "clone", "campaign", "1234", "--times", "2", "--prefix", "S2|",
            "--start", "2030-01-01T00:00:00+00:00",
        ])
        with mock.patch.object(
            metaops, "run_child",
            return_value=fake_child('{"schema": "clone.result/v1", "ok": true}\n'),
        ) as run_child:
            code, payload = args.handler(args)
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        script, child_args, _timeout = run_child.call_args[0]
        self.assertEqual(script, "clone.py")
        self.assertEqual(
            child_args[:-2],
            ["campaign", "1234", "--times", "2", "--expected-account", "act_1", "--prefix", "S2|", "--start", "2030-01-01T00:00:00+00:00"],
        )
        # A real clone always carries a resume file, keyed by the request.
        self.assertEqual(child_args[-2], "--state")
        self.assertIn("/clones/campaign-1234.", child_args[-1])

    def test_clone_requires_workspace(self) -> None:
        args = self.parse(["clone", "ad", "42"])
        args.workspace_obj = None
        with self.assertRaises(metaops.MetaOpsError):
            args.handler(args)

    def test_clone_child_failure_nonzero_exit(self) -> None:
        args = self.parse(["clone", "ad", "42"])
        with mock.patch.object(
            metaops, "run_child",
            return_value=fake_child('{"schema": "clone.result/v1", "ok": false}\n', returncode=1),
        ):
            code, payload = args.handler(args)
        self.assertEqual(code, 1)
        self.assertFalse(payload["ok"])

    def test_clone_rejects_source_outside_expected_account(self) -> None:
        with mock.patch.object(clone.graph, "get", return_value={"id": "42", "account_id": "2"}):
            with self.assertRaisesRegex(SystemExit, "refusing cross-profile clone"):
                clone.require_expected_account("42", "act_1")

    def test_clone_skips_deleted_and_archived_children(self) -> None:
        rows = [
            {"id": "active", "effective_status": "ACTIVE"},
            {"id": "deleted", "effective_status": "DELETED"},
            {"id": "archived", "status": "ARCHIVED"},
        ]
        self.assertEqual([row["id"] for row in clone.copyable(rows, "ad")], ["active"])

    def test_ad_copy_omits_deep_copy_parameter(self) -> None:
        with mock.patch.object(clone.graph, "post", return_value={"copied_ad_id": "99"}) as post:
            self.assertEqual(clone.copy_obj("42", {"adset_id": "7"}, False, "ad"), "99")
        self.assertNotIn("deep_copy", post.call_args.args[1])

    def test_campaign_copy_keeps_shallow_copy_parameter(self) -> None:
        with mock.patch.object(clone.graph, "post", return_value={"copied_campaign_id": "99"}) as post:
            self.assertEqual(clone.copy_obj("42", {}, False, "campaign"), "99")
        self.assertEqual(post.call_args.args[1]["deep_copy"], False)

    def test_edit_child_rejects_opaque_id_outside_expected_account_before_post(self) -> None:
        argv = [
            "edit.py", "--ids", "42", "--status", "PAUSED", "--confirm", "PAUSE",
            "--expected-account", "act_1",
        ]
        foreign = {
            "id": "42", "account_id": "2", "name": "foreign", "status": "ACTIVE",
            "daily_budget": "100", "effective_status": "ACTIVE",
        }
        with (
            mock.patch.object(edit.sys, "argv", argv),
            mock.patch.object(edit.graph, "require_write_authority"),
            mock.patch.object(edit.graph, "get", return_value=foreign),
            mock.patch.object(edit.graph, "post") as post,
        ):
            self.assertEqual(edit.main(), 1)
        post.assert_not_called()

    # --- exact rename / bid / schedule (cmd_edit + edit.py) -----------------------

    def _run_edit_child(self, argv: list[str], gets: list, posts: list | None = None):
        posts = posts if posts is not None else [{}]
        with (
            mock.patch.object(edit.sys, "argv", ["edit.py", *argv]),
            mock.patch.object(edit.graph, "require_write_authority"),
            mock.patch.object(edit.graph, "get", side_effect=gets),
            mock.patch.object(edit.graph, "post", side_effect=posts) as post,
        ):
            code = edit.main()
        return code, post

    def _run_wrapper(self, argv: list[str], stdout: str = '{"schema": "edit.result/v1", "ok": true}\n'):
        args = self.parse(argv)
        with mock.patch.object(metaops, "run_child", return_value=fake_child(stdout)) as run_child:
            code, payload = args.handler(args)
        return code, payload, run_child.call_args[0]

    def test_edit_rename_name_builds_args(self) -> None:
        code, _payload, (_script, child_args, _t) = self._run_wrapper(
            ["edit", "rename", "--ids", "77", "--name", "EN0039-<buyer>-1"])
        self.assertEqual(code, 0)
        self.assertEqual(child_args, ["--ids", "77", "--expected-account", "act_1", "--name", "EN0039-<buyer>-1"])

    def test_edit_rename_name_needs_single_id(self) -> None:
        args = self.parse(["edit", "rename", "--ids", "1,2", "--name", "X"])
        with self.assertRaises(metaops.MetaOpsError):
            args.handler(args)

    def test_edit_rename_set_takes_ids_from_pairs(self) -> None:
        _c, _p, (_s, child_args, _t) = self._run_wrapper(
            ["edit", "rename", "--set", "11=EN0039-<buyer>-1", "--set", "22=EN0040-<buyer>-1"])
        self.assertEqual(child_args, [
            "--ids", "11,22", "--expected-account", "act_1",
            "--set", "11=EN0039-<buyer>-1", "--set", "22=EN0040-<buyer>-1"])

    def test_edit_rename_forms_are_exclusive_and_validated(self) -> None:
        for argv in (
            ["edit", "rename", "--ids", "1", "--name", "X", "--prefix", "P"],
            ["edit", "rename", "--ids", "1"],
            ["edit", "rename", "--set", "notanid=Name"],
            ["edit", "rename", "--set", "12="],
            ["edit", "rename", "--set", "12=" + "n" * 401],
        ):
            args = self.parse(argv)
            with self.assertRaises(metaops.MetaOpsError, msg=str(argv)):
                args.handler(args)

    def test_edit_child_name_posts_exact_name(self) -> None:
        code, post = self._run_edit_child(
            ["--ids", "42", "--name", "EN0039-<buyer>-1", "--expected-account", "act_1"],
            gets=[{"id": "42", "account_id": "1", "name": "EN0038-<buyer>-1", "status": "ACTIVE"},
                  {"name": "EN0039-<buyer>-1", "status": "ACTIVE", "effective_status": "PENDING_REVIEW"}])
        self.assertEqual(code, 0)
        self.assertEqual(post.call_args.args[:2], ("42", {"name": "EN0039-<buyer>-1"}))

    def test_edit_child_set_map_renames_each_id(self) -> None:
        obj = lambda i: {"id": i, "account_id": "1", "name": f"old{i}", "status": "ACTIVE"}
        code, post = self._run_edit_child(
            ["--ids", "11,22", "--set", "11=A-1", "--set", "22=B-2", "--expected-account", "act_1"],
            gets=[obj("11"), {"name": "A-1", "status": "ACTIVE"}, obj("22"), {"name": "B-2", "status": "ACTIVE"}],
            posts=[{}, {}])
        self.assertEqual(code, 0)
        self.assertEqual([c.args[:2] for c in post.call_args_list], [("11", {"name": "A-1"}), ("22", {"name": "B-2"})])

    def test_edit_child_name_refuses_several_ids(self) -> None:
        with self.assertRaises(SystemExit):
            self._run_edit_child(["--ids", "1,2", "--name", "X"], gets=[])

    def test_edit_bid_requires_confirm_and_positive_value(self) -> None:
        for argv in (["edit", "bid", "--ids", "9", "--bid-minor", "15000"],
                     ["edit", "bid", "--ids", "9", "--bid-minor", "0", "--confirm", "BID"]):
            args = self.parse(argv)
            with self.assertRaises(metaops.MetaOpsError, msg=str(argv)):
                args.handler(args)

    def test_edit_bid_builds_args(self) -> None:
        _c, _p, (_s, child_args, _t) = self._run_wrapper(
            ["edit", "bid", "--ids", "9", "--bid-minor", "15000", "--confirm", "BID"])
        self.assertEqual(child_args, ["--ids", "9", "--expected-account", "act_1", "--bid-minor", "15000"])

    def test_edit_child_bid_posts_bid_amount_and_reads_it_back(self) -> None:
        code, post = self._run_edit_child(
            ["--ids", "9", "--bid-minor", "15000", "--expected-account", "act_1"],
            gets=[{"id": "9", "account_id": "1", "name": "AS", "status": "ACTIVE", "daily_budget": None},
                  {"bid_amount": 20000},
                  {"name": "AS", "status": "ACTIVE", "bid_amount": 15000}])
        self.assertEqual(code, 0)
        self.assertEqual(post.call_args.args[:2], ("9", {"bid_amount": 15000}))

    def test_edit_child_bid_on_non_adset_is_refused_before_post(self) -> None:
        bad = edit.graph.GraphError(400, {"error": {"code": 100, "message": "nonexisting field"}}, "bid")
        code, post = self._run_edit_child(
            ["--ids", "9", "--bid-minor", "15000", "--expected-account", "act_1"],
            gets=[{"id": "9", "account_id": "1", "name": "AD", "status": "ACTIVE"}, bad])
        self.assertEqual(code, 1)
        post.assert_not_called()

    def test_edit_schedule_requires_confirm_and_offset(self) -> None:
        for argv in (
            ["edit", "schedule", "--ids", "9", "--start-time", "2026-10-01T08:00:00-07:00"],
            ["edit", "schedule", "--ids", "9", "--start-time", "2026-10-01T08:00:00", "--confirm", "SCHEDULE"],
            ["edit", "schedule", "--ids", "9", "--confirm", "SCHEDULE"],
        ):
            args = self.parse(argv)
            with self.assertRaises(metaops.MetaOpsError, msg=str(argv)):
                args.handler(args)

    def test_edit_schedule_builds_args(self) -> None:
        _c, _p, (_s, child_args, _t) = self._run_wrapper([
            "edit", "schedule", "--ids", "9", "--start-time", "2026-10-01T08:00:00-07:00",
            "--end-time", "2026-10-08T00:00:00-07:00", "--confirm", "SCHEDULE"])
        self.assertEqual(child_args, [
            "--ids", "9", "--expected-account", "act_1", "--start-time", "2026-10-01T08:00:00-07:00",
            "--end-time", "2026-10-08T00:00:00-07:00"])

    def test_edit_child_schedule_posts_times_and_refuses_past_end(self) -> None:
        code, post = self._run_edit_child(
            ["--ids", "9", "--start-time", "2099-10-01T08:00:00-07:00", "--expected-account", "act_1"],
            gets=[{"id": "9", "account_id": "1", "name": "AS", "status": "PAUSED"},
                  {"optimization_goal": "OFFSITE_CONVERSIONS"},  # ad-set probe (schedule is ad-set only)
                  {"name": "AS", "status": "PAUSED", "start_time": "2099-10-01T08:00:00-0700"}])
        self.assertEqual(code, 0)
        self.assertEqual(post.call_args.args[:2], ("9", {"start_time": "2099-10-01T08:00:00-07:00"}))
        with self.assertRaises(SystemExit):
            self._run_edit_child(["--ids", "9", "--end-time", "2020-01-01T00:00:00+00:00"], gets=[])

    # --- targeting: age / gender / device / geo / audience -------------------------

    def test_edit_targeting_new_flags_build_args_including_zero(self) -> None:
        _c, _p, (_s, child_args, _t) = self._run_wrapper([
            "edit", "targeting", "--ids", "5", "--age-min", "21", "--geo-regions", "3879",
            "--advantage-audience", "0", "--device-platforms", "mobile", "--confirm", "TARGETING"],
            stdout='{"schema": "edit_targeting.result/v1", "ok": true}\n')
        for flag, value in (("--age-min", "21"), ("--geo-regions", "3879"),
                            ("--advantage-audience", "0"), ("--device-platforms", "mobile")):
            self.assertEqual(child_args[child_args.index(flag) + 1], value)

    def _run_targeting_child(self, argv: list[str], current: dict):
        # The read-back echoes what was POSTed, like Graph does when it accepts every field
        # (edit_targeting now compares the read-back with the request and flags `not_applied`).
        sent: dict = {}

        def fake_post(_oid, payload, **_kw):
            sent.update(payload)
            return {}

        def fake_get(_oid, **kw):
            if kw["params"]["fields"] == "name,targeting,account_id":
                return {"id": "5", "name": "AS", "targeting": current, "account_id": "1"}
            return {"id": "5", "name": "AS", "targeting": sent.get("targeting", current)}

        with (
            mock.patch.object(edit_targeting.sys, "argv", ["edit_targeting.py", *argv]),
            mock.patch.object(edit_targeting.graph, "require_write_authority"),
            mock.patch.object(edit_targeting.graph, "get", side_effect=fake_get),
            mock.patch.object(edit_targeting.graph, "post", side_effect=fake_post) as post,
        ):
            code = edit_targeting.main()
        return code, post

    def test_edit_targeting_child_geo_regions_replaces_whole_geo_selection(self) -> None:
        current = {"geo_locations": {"countries": ["US"], "regions": [{"key": "3879"}],
                                     "location_types": ["home", "recent"]}, "age_min": 21}
        code, post = self._run_targeting_child(
            ["--ids", "5", "--geo-regions", "3880,3881", "--confirm", "TARGETING", "--expected-account", "act_1"],
            current)
        self.assertEqual(code, 0)
        sent = post.call_args.args[1]["targeting"]
        self.assertEqual(sent["geo_locations"], {"regions": [{"key": "3880"}, {"key": "3881"}],
                                                 "location_types": ["home", "recent"]})
        self.assertEqual(sent["age_min"], 21)

    def test_edit_targeting_child_advantage_audience_keeps_sibling_automation_keys(self) -> None:
        current = {"geo_locations": {"regions": [{"key": "3879"}]},
                   "targeting_automation": {"advantage_audience": 1, "individual_setting": {"age": 1}}}
        code, post = self._run_targeting_child(
            ["--ids", "5", "--advantage-audience", "0", "--age-max", "60", "--confirm", "TARGETING",
             "--expected-account", "act_1"], current)
        self.assertEqual(code, 0)
        sent = post.call_args.args[1]["targeting"]
        self.assertEqual(sent["targeting_automation"], {"advantage_audience": 0, "individual_setting": {"age": 1}})
        self.assertEqual(sent["age_max"], 60)

    def test_edit_targeting_child_rejects_out_of_range_age(self) -> None:
        with self.assertRaises(SystemExit):
            self._run_targeting_child(
                ["--ids", "5", "--age-min", "9", "--confirm", "TARGETING"], {"geo_locations": {}})

    # --- creative / ad copy through edit tags|creative -----------------------------

    def test_edit_creative_alias_and_copy_flags_build_args(self) -> None:
        msg = self.root / "text.txt"
        msg.write_text("Hello story\n", encoding="utf-8")
        _c, _p, (script, child_args, _t) = self._run_wrapper([
            "edit", "creative", "--ids", "7", "--message-file", str(msg), "--description", "",
            "--caption", "example.com", "--link", "https://x.example/", "--image-hash", "abc",
            "--allow-disapproved", "--confirm", "CREATIVE"],
            stdout='{"schema": "edit_tags.result/v1", "ok": true}\n')
        self.assertEqual(script, "edit_tags.py")
        self.assertEqual(child_args, [
            "--ids", "7", "--message-file", str(msg.resolve()), "--description", "", "--caption", "example.com",
            "--link", "https://x.example/", "--image-hash", "abc", "--allow-disapproved",
            "--confirm", "TAGS", "--expected-account", "act_1"])

    def test_edit_creative_missing_message_file_is_refused(self) -> None:
        args = self.parse(["edit", "creative", "--ids", "7", "--message-file", str(self.root / "nope.txt"),
                           "--confirm", "TAGS"])
        with self.assertRaises(metaops.MetaOpsError):
            args.handler(args)

    def _link_ad(self, status: str = "ACTIVE") -> dict:
        return {"id": "77", "name": "Ad", "account_id": "1", "effective_status": status,
                "creative": {"id": "500", "name": "C", "url_tags": "sub1=OLD",
                             "object_story_spec": {"page_id": "2", "link_data": {
                                 "link": "https://old.example/", "message": "old text", "name": "Old head",
                                 "description": "old desc", "caption": "old.example", "image_hash": "h1",
                                 "picture": "https://cdn/x.jpg",
                                 "call_to_action": {"type": "LEARN_MORE", "value": {"link": "https://old.example/"}}}}}}

    def _run_tags_child(self, argv: list[str], ad: dict):
        with (
            mock.patch.object(edit_tags.sys, "argv", ["edit_tags.py", *argv]),
            mock.patch.object(edit_tags.graph, "require_write_authority"),
            mock.patch.object(edit_tags.graph, "get", side_effect=[ad, {"name": "Ad", "creative": {"id": "600"}}]),
            mock.patch.object(edit_tags.graph, "post", side_effect=[{"id": "600"}, {}]) as post,
        ):
            code = edit_tags.main()
        return code, post

    def test_edit_tags_child_rewrites_ad_copy_on_the_clone(self) -> None:
        msg = self.root / "new.txt"
        msg.write_text("new story\n", encoding="utf-8")
        code, post = self._run_tags_child(
            ["--ids", "77", "--message-file", str(msg), "--headline", "New head", "--description", "",
             "--caption", "new.example", "--link", "https://new.example/", "--image-hash", "h2",
             "--cta", "SEE_DETAILS", "--confirm", "TAGS"], self._link_ad())
        self.assertEqual(code, 0)
        ld = post.call_args_list[0].args[1]["object_story_spec"]["link_data"]
        self.assertEqual(ld["message"], "new story")
        self.assertEqual(ld["name"], "New head")
        self.assertNotIn("description", ld)
        self.assertEqual(ld["caption"], "new.example")
        self.assertEqual(ld["link"], "https://new.example/")
        self.assertEqual(ld["call_to_action"], {"type": "SEE_DETAILS", "value": {"link": "https://new.example/"}})
        self.assertEqual(ld["image_hash"], "h2")
        self.assertNotIn("picture", ld)
        self.assertEqual(post.call_args_list[0].args[1]["url_tags"], "sub1=OLD")

    def test_edit_tags_child_skips_disapproved_unless_allowed(self) -> None:
        with (
            mock.patch.object(edit_tags.sys, "argv",
                              ["edit_tags.py", "--ids", "77", "--headline", "H", "--confirm", "TAGS"]),
            mock.patch.object(edit_tags.graph, "require_write_authority"),
            mock.patch.object(edit_tags.graph, "get", return_value=self._link_ad("DISAPPROVED")),
            mock.patch.object(edit_tags.graph, "post") as post,
        ):
            self.assertEqual(edit_tags.main(), 0)
        post.assert_not_called()
        code, post = self._run_tags_child(
            ["--ids", "77", "--headline", "H", "--allow-disapproved", "--confirm", "TAGS"],
            self._link_ad("DISAPPROVED"))
        self.assertEqual(code, 0)
        self.assertEqual(post.call_args_list[0].args[1]["object_story_spec"]["link_data"]["name"], "H")

    def test_edit_tags_child_refuses_blank_message(self) -> None:
        with self.assertRaises(SystemExit):
            self._run_tags_child(["--ids", "77", "--message", "   ", "--confirm", "TAGS"], self._link_ad())

    # --- rules -------------------------------------------------------------

    def test_rules_ladder_pause_requires_confirm(self) -> None:
        args = self.parse([
            "rules", "ladder", "--target-minor", "1200", "--event", "results",
            "--level", "ADSET", "--mode", "pause",
        ])
        with self.assertRaises(metaops.MetaOpsError):
            args.handler(args)

    def test_rules_ladder_notify_no_confirm_needed_and_account_from_profile(self) -> None:
        args = self.parse([
            "rules", "ladder", "--target-minor", "1200", "--event", "results", "--level", "ADSET",
        ])
        with mock.patch.object(
            metaops, "run_child",
            return_value=fake_child('{"schema": "rules.result/v1", "ok": true}\n'),
        ) as run_child:
            code, _payload = args.handler(args)
        self.assertEqual(code, 0)
        script, child_args, _timeout = run_child.call_args[0]
        self.assertEqual(script, "rules.py")
        self.assertEqual(child_args, [
            "--account", "act_1", "--target-minor", "1200", "--event", "results",
            "--level", "ADSET", "--rungs", "0-6", "--mode", "notify", "--prefix", "LADDER|",
        ])

    def test_rules_ladder_passes_ids_to_the_bound_child(self) -> None:
        args = self.parse([
            "rules", "ladder", "--target-minor", "1200", "--event", "results", "--level", "ADSET",
            "--ids", "42",
        ])
        with mock.patch.object(
            metaops, "run_child", return_value=fake_child('{"schema": "rules.result/v1", "ok": true}\n')
        ) as child:
            args.handler(args)
        self.assertIn("--ids", child.call_args.args[1])
        self.assertEqual(child.call_args.args[1][child.call_args.args[1].index("--ids") + 1], "42")

    def test_rules_child_rejects_ids_outside_account_before_listing_or_posting(self) -> None:
        argv = [
            "rules.py", "--account", "act_1", "--target-minor", "1200", "--ids", "42", "--dry-run",
        ]
        with (
            mock.patch.object(rules.sys, "argv", argv),
            mock.patch.object(rules.graph, "get", return_value={"id": "42", "account_id": "2"}) as get,
            mock.patch.object(rules.graph, "post") as post,
        ):
            with self.assertRaisesRegex(SystemExit, "cross-profile rule"):
                rules.main()
        self.assertEqual(get.call_count, 1)
        post.assert_not_called()

    def test_rules_ladder_pause_with_confirm_passes(self) -> None:
        args = self.parse([
            "rules", "ladder", "--target-minor", "1200", "--event", "results", "--level", "ADSET",
            "--mode", "pause", "--ids", "42", "--confirm", "RULES",  # a pause ladder needs a scope
        ])
        with mock.patch.object(
            metaops, "run_child",
            return_value=fake_child('{"schema": "rules.result/v1", "ok": true}\n'),
        ) as run_child:
            code, _payload = args.handler(args)
        self.assertEqual(code, 0)
        _script, child_args, _timeout = run_child.call_args[0]
        self.assertIn("--mode", child_args)
        self.assertEqual(child_args[child_args.index("--mode") + 1], "pause")

    def test_rules_list_uses_profile_account(self) -> None:
        args = self.parse(["rules", "list"])
        with mock.patch.object(
            metaops, "run_child",
            return_value=fake_child('{"schema": "rules.result/v1", "ok": true, "rules": []}\n'),
        ) as run_child:
            code, payload = args.handler(args)
        self.assertEqual(code, 0)
        _script, child_args, _timeout = run_child.call_args[0]
        self.assertEqual(child_args, ["--account", "act_1", "--list"])
        self.assertEqual(payload["data"]["rules"], [])

    def test_rules_history_since_passthrough(self) -> None:
        args = self.parse(["rules", "history", "--since", "2026-09-01T00:00:00+00:00"])
        with mock.patch.object(
            metaops, "run_child",
            return_value=fake_child('{"schema": "rules.result/v1", "ok": true}\n'),
        ) as run_child:
            args.handler(args)
        _script, child_args, _timeout = run_child.call_args[0]
        self.assertEqual(
            child_args, ["--account", "act_1", "--history", "--since", "2026-09-01T00:00:00+00:00"]
        )

    def test_rules_execute_child_args(self) -> None:
        args = self.parse(["rules", "execute", "--rule-id", "999", "--confirm", "EXECUTE"])
        with mock.patch.object(
            metaops, "run_child",
            return_value=fake_child('{"schema": "rules.result/v1", "ok": true}\n'),
        ) as run_child:
            args.handler(args)
        _script, child_args, _timeout = run_child.call_args[0]
        self.assertEqual(child_args, ["--account", "act_1", "--execute", "999", "--confirm", "EXECUTE"])

    def test_rules_delete_requires_confirm_delete(self) -> None:
        args = self.parse(["rules", "delete", "--prefix", "LADDER|"])
        with self.assertRaises(metaops.MetaOpsError):
            args.handler(args)

    def test_rules_delete_with_confirm_passes(self) -> None:
        args = self.parse(["rules", "delete", "--prefix", "LADDER|", "--confirm", "DELETE"])
        with mock.patch.object(
            metaops, "run_child",
            return_value=fake_child('{"schema": "rules.result/v1", "ok": true, "deleted": []}\n'),
        ) as run_child:
            code, payload = args.handler(args)
        self.assertEqual(code, 0)
        _script, child_args, _timeout = run_child.call_args[0]
        self.assertEqual(child_args, ["--account", "act_1", "--delete-prefix", "LADDER|"])
        self.assertEqual(payload["data"]["deleted"], [])


if __name__ == "__main__":
    unittest.main()

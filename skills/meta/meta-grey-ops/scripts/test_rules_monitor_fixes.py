#!/usr/bin/env python3
"""Regression tests for the rules / monitor / operate review fixes (12 rule identity and live
guards, 13 monitor ERROR verdict, 14 stale --out-json). Offline: graph.get / graph.post are
replaced by an in-memory rules library; every test fails on the code as it was before the fixes.
"""

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

import cmd_edit
import cmd_operate
import metaops
import monitor
import rules

os.environ.setdefault("META_TOKEN", "TEST_TOKEN")


def graph_error(status: int = 500, code: int = 1, message: str = "boom") -> Exception:
    return rules.graph.GraphError(status, {"error": {"code": code, "message": message}}, "test")


class RulesLibrary:
    """Account act_1 with a rules library that POSTs append to and GETs read back."""

    def __init__(self, existing: list[dict] | None = None, currency: str = "USD"):
        self.library = list(existing or [])
        self.currency = currency
        self.posts: list[tuple[str, dict]] = []
        self.executes: list[str] = []

    def get(self, path, params=None, context=""):
        if path == "act_1":
            return {"id": "act_1", "currency": self.currency}
        if path == "act_1/adrules_library":
            return {"data": list(self.library)}
        if path in ("42", "43"):
            return {"id": path, "account_id": "1"}
        raise AssertionError(f"unexpected GET {path}")

    def post(self, path, data=None, **_kw):
        if path.endswith("/execute"):
            self.executes.append(path)
            return {}
        self.posts.append((path, data))
        rule_id = f"R{len(self.library) + 1}"
        self.library.append({**data, "id": rule_id})
        return {"id": rule_id}


def run_rules(argv: list[str], lib: RulesLibrary):
    out, err = io.StringIO(), io.StringIO()
    with (
        mock.patch.object(rules.sys, "argv", ["rules.py", *argv]),
        mock.patch.object(rules.graph, "get", side_effect=lib.get),
        mock.patch.object(rules.graph, "post", side_effect=lib.post),
        mock.patch.object(rules.time, "sleep"),
        contextlib.redirect_stdout(out), contextlib.redirect_stderr(err),
    ):
        code = rules.main()
    return code, out.getvalue()


def last_json(stdout: str) -> dict:
    for line in reversed(stdout.splitlines()):
        if line.startswith("{"):
            return json.loads(line)
    raise AssertionError("no JSON result line")


LADDER = ["--account", "act_1", "--target-minor", "1200", "--rungs", "0-2", "--prefix", "L|"]


class RuleIdentity(unittest.TestCase):  # fix 12
    def test_names_end_in_a_scope_hash_and_dedup_still_works(self) -> None:
        lib = RulesLibrary()
        code, out = run_rules(LADDER, lib)
        self.assertEqual(code, 0)
        names = [payload["name"] for _p, payload in lib.posts]
        self.assertEqual(len(names), 3)
        self.assertTrue(all(len(n.split("|")[-1]) == 8 for n in names), names)
        code, out = run_rules(LADDER, lib)  # identical repeat: idempotent skip, nothing new armed
        self.assertEqual(code, 0)
        self.assertEqual(len(lib.posts), 3)
        self.assertEqual(len(last_json(out)["skipped_existing"]), 3)

    def test_scopes_that_differ_never_share_a_name(self) -> None:
        variants = [
            [], ["--time-preset", "LAST_7D"], ["--event", "link_click"], ["--level", "AD"],
            ["--ids", "42"], ["--ids", "42,43"], ["--confidence", "0.9"], ["--mode", "pause", "--all-adsets"],
            ["--mode", "pause", "--ids", "42"],
        ]
        lib = RulesLibrary()
        for extra in variants:
            before = len(lib.posts)
            code, _out = run_rules([*LADDER, *extra], lib)
            self.assertEqual(code, 0, extra)
            self.assertEqual(len(lib.posts) - before, 3, f"{extra}: scope collided with an earlier rule name")
        names = [payload["name"] for _p, payload in lib.posts]
        self.assertEqual(len(names), len(set(names)))

    def test_scope_hash_covers_every_scope_field_and_ignores_id_order(self) -> None:
        base = dict(level="ADSET", event="results", ids=["1", "2"], time_preset="LIFETIME",
                    currency="USD", confidence=0.95, mode="notify")
        ref = rules.scope_hash(**base)
        self.assertEqual(ref, rules.scope_hash(**{**base, "ids": ["2", "1"]}))
        for field, other in (("level", "AD"), ("event", "link_click"), ("ids", ["1"]), ("ids", None),
                             ("time_preset", "LAST_7D"), ("currency", "EUR"), ("confidence", 0.9),
                             ("mode", "pause")):
            self.assertNotEqual(ref, rules.scope_hash(**{**base, field: other}), field)

    def test_account_currency_is_part_of_the_scope(self) -> None:
        usd, eur = RulesLibrary(currency="USD"), RulesLibrary(currency="EUR")
        run_rules(LADDER, usd)
        run_rules(LADDER, eur)
        self.assertNotEqual(usd.posts[0][1]["name"], eur.posts[0][1]["name"])

    def test_same_name_with_different_filters_aborts_before_any_post(self) -> None:
        lib = RulesLibrary()
        run_rules(LADDER, lib)
        armed = len(lib.posts)
        with self.assertRaises(SystemExit) as ctx:
            run_rules([*LADDER, "--impressions-floor", "100"], lib)  # asks for a filter the armed rule lacks
        self.assertIn("DIFFERENT", str(ctx.exception))
        self.assertEqual(len(lib.posts), armed)

    def test_existing_rule_with_extra_filters_counts_as_identical(self) -> None:
        lib = RulesLibrary()
        run_rules([*LADDER, "--impressions-floor", "100"], lib)  # Graph-returned rule carries one more filter
        before = len(lib.posts)
        code, _out = run_rules(LADDER, lib)
        self.assertEqual((code, len(lib.posts)), (0, before))

    def test_collision_on_a_later_rung_still_creates_nothing(self) -> None:
        lib = RulesLibrary()
        run_rules(LADDER, lib)
        lib.library = lib.library[-1:]  # only the last rung's rule survives
        before = len(lib.posts)
        with self.assertRaises(SystemExit):
            run_rules([*LADDER, "--impressions-floor", "100"], lib)
        self.assertEqual(len(lib.posts), before)

    def test_graph_returning_numbers_as_strings_is_still_identical(self) -> None:
        lib = RulesLibrary()
        run_rules(LADDER, lib)
        for rule in lib.library:  # Graph hands filter values back as strings
            for f in rule["evaluation_spec"]["filters"]:
                if isinstance(f["value"], int):
                    f["value"] = str(f["value"])
        before = len(lib.posts)
        code, _out = run_rules(LADDER, lib)
        self.assertEqual((code, len(lib.posts)), (0, before))

    def test_rule_armed_before_the_hash_existed_is_recognised_when_identical(self) -> None:
        probe = RulesLibrary()
        run_rules(LADDER, probe)
        legacy = []
        for rule in probe.library:  # same rules, old-style name (no trailing hash)
            legacy.append({**rule, "name": rule["name"].rsplit("|", 1)[0]})
        lib = RulesLibrary(legacy)
        code, out = run_rules(LADDER, lib)
        self.assertEqual(code, 0)
        self.assertEqual(lib.posts, [])
        self.assertEqual(len(last_json(out)["skipped_existing"]), 3)

    def test_legacy_rule_with_different_filters_does_not_block_or_count(self) -> None:
        probe = RulesLibrary()
        run_rules([*LADDER, "--time-preset", "LAST_7D"], probe)
        legacy = [{**r, "name": r["name"].rsplit("|", 1)[0]} for r in probe.library]
        lib = RulesLibrary(legacy)
        code, _out = run_rules(LADDER, lib)  # LIFETIME ladder next to a LAST_7D legacy one
        self.assertEqual((code, len(lib.posts)), (0, 3))

    def test_dry_run_creates_nothing_and_shows_the_hashed_name(self) -> None:
        lib = RulesLibrary()
        code, out = run_rules([*LADDER, "--dry-run"], lib)
        self.assertEqual(code, 0)
        self.assertEqual(lib.posts, [])
        self.assertIn(last_json(out)["scope_hash"], out)


class RuleExecuteGuard(unittest.TestCase):  # fix 12
    def lib(self, execution_type: str | None) -> RulesLibrary:
        rule = {"id": "R9", "name": "L|k0", "status": "ENABLED", "evaluation_spec": {"filters": []},
                "schedule_spec": {"schedule_type": "SEMI_HOURLY"}}
        if execution_type:
            rule["execution_spec"] = {"execution_type": execution_type}
        return RulesLibrary([rule])

    ARGV = ["--account", "act_1", "--execute", "R9", "--confirm", "EXECUTE"]

    def test_a_pause_rule_is_refused_without_live(self) -> None:
        for kind in ("PAUSE", "CHANGE_BUDGET", None):
            lib = self.lib(kind)
            with self.assertRaises(SystemExit, msg=str(kind)) as ctx:
                run_rules(self.ARGV, lib)
            self.assertIn("--live", str(ctx.exception))
            self.assertEqual(lib.executes, [], kind)

    def test_a_pause_rule_fires_with_live(self) -> None:
        lib = self.lib("PAUSE")
        with mock.patch.object(rules, "history_rows", return_value=[]):
            code, out = run_rules([*self.ARGV, "--live"], lib)
        self.assertEqual(code, 0)
        self.assertEqual(lib.executes, ["R9/execute"])
        self.assertEqual(last_json(out)["execution_type"], "PAUSE")

    def test_a_notification_rule_needs_no_live(self) -> None:
        lib = self.lib("NOTIFICATION")
        with mock.patch.object(rules, "history_rows", return_value=[]):
            code, _out = run_rules(self.ARGV, lib)
        self.assertEqual((code, lib.executes), (0, ["R9/execute"]))


class PauseScope(unittest.TestCase):  # fix 12
    def test_pause_ladder_without_scope_is_refused_before_any_call(self) -> None:
        lib = RulesLibrary()
        with mock.patch.object(rules.graph, "get", side_effect=AssertionError("no network")):
            with self.assertRaises(SystemExit) as ctx, mock.patch.object(
                    rules.sys, "argv", ["rules.py", *LADDER, "--mode", "pause"]):
                rules.main()
        self.assertIn("--all-adsets", str(ctx.exception))
        self.assertEqual(lib.posts, [])

    def test_pause_ladder_with_ids_or_explicit_all_adsets_is_armed(self) -> None:
        for scope in (["--ids", "42"], ["--all-adsets"]):
            lib = RulesLibrary()
            code, _out = run_rules([*LADDER, "--mode", "pause", *scope], lib)
            self.assertEqual((code, len(lib.posts)), (0, 3), scope)
            self.assertTrue(all(p["execution_spec"]["execution_type"] == "PAUSE" for _x, p in lib.posts))

    def test_ids_and_all_adsets_together_are_refused(self) -> None:
        with self.assertRaises(SystemExit):
            run_rules([*LADDER, "--mode", "pause", "--ids", "42", "--all-adsets"], RulesLibrary())

    def test_notify_ladder_needs_no_scope(self) -> None:
        code, _out = run_rules(LADDER, RulesLibrary())
        self.assertEqual(code, 0)

    def test_ladder_only_pause_preview_touches_nothing(self) -> None:
        with mock.patch.object(rules.sys, "argv", ["rules.py", "--ladder-only", "--target-minor", "1200",
                                                   "--mode", "pause"]), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(rules.main(), 0)

    def test_confidence_must_be_a_probability(self) -> None:
        for bad in ("0", "1", "1.5", "-0.2"):
            with self.assertRaises(SystemExit, msg=bad):
                run_rules([*LADDER, "--confidence", bad], RulesLibrary())


class RulesWrapper(unittest.TestCase):  # fix 12, metaops rules ladder|execute
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        path = pathlib.Path(self.tmp.name) / "workspace.json"
        path.write_text(json.dumps({
            "schema": metaops.meta_workspace.WORKSPACE_SCHEMA, "name": "contract",
            "api_version": metaops.graph.API_VERSION, "blocked_accounts": [],
            "profiles": {"test": {
                "business_id": "10", "app_id": "11", "system_user_id": "12", "ad_account_id": "act_1",
                "page_id": "2", "dataset_id": "3", "currency": "USD", "timezone": "Europe/Warsaw"}},
            "defaults": {"profile": "test", "state_dir": ".metaops"},
        }), encoding="utf-8")
        self.workspace = metaops.meta_workspace.load_workspace(str(path))
        self.ap = argparse.ArgumentParser()
        cmd_edit.register(self.ap.add_subparsers(dest="command", required=True), metaops)

    def parse(self, argv: list[str]) -> argparse.Namespace:
        args = self.ap.parse_args(argv)
        args.workspace_obj, args.profile, args.timeout = self.workspace, "test", 30
        return args

    def run_wrapper(self, argv: list[str]) -> list[str]:
        args = self.parse(argv)
        child = metaops.ChildResult(argv=[], returncode=0, stdout='{"schema": "rules.result/v1", "ok": true}\n',
                                    stderr="")
        with mock.patch.object(metaops, "run_child", return_value=child) as run_child, \
                mock.patch.object(metaops, "echo_child"):
            args.handler(args)
        return run_child.call_args[0][1]

    def refused(self, argv: list[str]) -> None:
        args = self.parse(argv)
        with mock.patch.object(metaops, "run_child", side_effect=AssertionError("child must not run")):
            with self.assertRaises(metaops.MetaOpsError):
                args.handler(args)

    BASE = ["rules", "ladder", "--target-minor", "1200", "--event", "results"]

    def test_ladder_exposes_the_flags_rules_py_supports(self) -> None:
        child_args = self.run_wrapper([*self.BASE, "--time-preset", "LAST_7D", "--impressions-floor", "50",
                                       "--confidence", "0.9", "--schedule", "HOURLY"])
        for flag, value in (("--time-preset", "LAST_7D"), ("--impressions-floor", "50"),
                            ("--confidence", "0.9"), ("--schedule", "HOURLY")):
            self.assertEqual(child_args[child_args.index(flag) + 1], value)

    def test_ladder_without_the_new_flags_sends_none_of_them(self) -> None:
        child_args = self.run_wrapper(self.BASE)
        for flag in ("--time-preset", "--impressions-floor", "--confidence", "--schedule", "--all-adsets"):
            self.assertNotIn(flag, child_args)

    def test_ladder_flag_values_are_validated(self) -> None:
        self.refused([*self.BASE, "--confidence", "1.5"])
        self.refused([*self.BASE, "--impressions-floor", "0"])
        self.refused([*self.BASE, "--time-preset", " "])

    def test_pause_ladder_needs_ids_or_all_adsets(self) -> None:
        self.refused([*self.BASE, "--mode", "pause", "--confirm", "RULES"])
        self.assertIn("--all-adsets", self.run_wrapper([*self.BASE, "--mode", "pause", "--confirm", "RULES",
                                                        "--all-adsets"]))
        self.assertIn("--ids", self.run_wrapper([*self.BASE, "--mode", "pause", "--confirm", "RULES",
                                                 "--ids", "42"]))
        self.refused([*self.BASE, "--mode", "pause", "--confirm", "RULES", "--ids", "42", "--all-adsets"])

    def test_execute_passes_live_only_when_asked(self) -> None:
        plain = self.run_wrapper(["rules", "execute", "--rule-id", "9", "--confirm", "EXECUTE"])
        live = self.run_wrapper(["rules", "execute", "--rule-id", "9", "--confirm", "EXECUTE", "--live"])
        self.assertNotIn("--live", plain)
        self.assertEqual(live[-1], "--live")


# --------------------------------------------------------------------------- monitor


class FakeSweepGraph:
    """An account that reads fine; `fail_on` names the sweep call that then raises a GraphError."""

    def __init__(self, fail_on: str | None = None, disapproved: int = 0):
        self.fail_on = fail_on
        self.disapproved = disapproved

    def get(self, path, params=None, context=""):
        params = params or {}
        if path == "act_1":
            return {"id": "act_1", "name": "Acct", "account_status": 1, "currency": "USD",
                    "timezone_name": "UTC", "timezone_offset_hours_utc": 0}
        if self.fail_on == context:
            raise graph_error()
        if path.endswith("/insights"):
            return {"data": [{"spend": "5.00"}]}
        if path.endswith("/ads"):
            ads = [{"effective_status": "ACTIVE"}] * 3 + [{"effective_status": "DISAPPROVED"}] * self.disapproved
            return {"data": ads}
        if path.endswith("/adsets"):
            return {"data": []}
        raise AssertionError(f"unexpected GET {path}")


class MonitorErrorVerdict(unittest.TestCase):  # fix 13
    def sweep(self, **kw) -> dict:
        with mock.patch.object(monitor.graph, "get", side_effect=FakeSweepGraph(**kw).get):
            return monitor.sweep("act_1")

    def test_a_clean_sweep_is_still_ok(self) -> None:
        row = self.sweep()
        self.assertEqual(row["verdict"], "OK")
        self.assertNotIn("error", row)

    def test_a_graph_error_mid_sweep_is_never_ok(self) -> None:
        for failing in ("ads status", "adset issues", "adset delivery", "spend today", "spend yesterday"):
            row = self.sweep(fail_on=failing)
            self.assertIn("ERROR", row["verdict"].split(","), failing)
            self.assertNotEqual(row["verdict"], "OK", failing)
            self.assertIn("error", row)

    def test_real_verdicts_found_on_partial_data_stay_beside_error(self) -> None:
        row = self.sweep(fail_on="adset issues", disapproved=2)  # ads counted (2 rejects) before the failure
        self.assertEqual(row["verdict"].split(","), ["REJECTS", "ERROR"])
        self.assertNotIn("OK", row["verdict"].split(","))

    def run_main(self, gr: FakeSweepGraph):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        log, out_json = pathlib.Path(tmp.name) / "log.jsonl", pathlib.Path(tmp.name) / "rows.json"
        buf = io.StringIO()
        argv = ["monitor.py", "--accounts", "act_1", "--log", str(log), "--json", str(out_json)]
        with (mock.patch.object(monitor.sys, "argv", argv),
              mock.patch.object(monitor.graph, "get", side_effect=gr.get),
              contextlib.redirect_stdout(buf)):
            code = monitor.main()
        return code, buf.getvalue(), json.loads(out_json.read_text())

    def test_main_exits_non_zero_and_names_the_error_in_the_summary(self) -> None:
        code, out, rows = self.run_main(FakeSweepGraph(fail_on="ads status"))
        self.assertEqual(code, 1)
        self.assertIn("ERROR", out)
        self.assertIn("1 need attention", out)
        self.assertIn("act_1", out.split("ERROR/UNREACHABLE:")[1])
        self.assertIn("ERROR", rows[0]["verdict"])

    def test_main_exits_zero_for_a_clean_sweep(self) -> None:
        code, out, rows = self.run_main(FakeSweepGraph())
        self.assertEqual(code, 0)
        self.assertNotIn("ERROR", out)
        self.assertEqual(rows[0]["verdict"], "OK")


# --------------------------------------------------------------------------- cmd_operate


class FakeWorkspace:
    def __init__(self, state_root: pathlib.Path):
        self.state_root = state_root
        self.data = {"profiles": {"test": {"ad_account_id": "act_1"}}}

    def profile(self, requested=None):
        return "test", {"ad_account_id": "act_1"}


class StaleOutJson(unittest.TestCase):  # fix 14
    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.root = pathlib.Path(self.td.name)
        self.workspace = FakeWorkspace(self.root)
        self.out = self.root / "rows.json"
        self.out.write_text(json.dumps([{"account": "act_1", "verdict": "OK"}]), encoding="utf-8")

    def args(self):
        ns = mock.Mock()
        ns.workspace_obj, ns.profile, ns.timeout = self.workspace, None, 30
        ns.accounts, ns.stall_impressions, ns.telegram, ns.log = "act_1", 40, False, None
        ns.out_json = str(self.out)
        return ns

    def test_a_crashed_child_cannot_leave_stale_rows_that_read_as_fresh(self) -> None:
        crashed = metaops.ChildResult(argv=["monitor.py"], returncode=1, stdout="", stderr="Traceback")
        with mock.patch.object(metaops, "run_child", return_value=crashed), \
                mock.patch.object(metaops, "echo_child"):
            code, payload = cmd_operate.command_monitor(self.args(), metaops)
        self.assertEqual(code, 1)
        self.assertFalse(payload["ok"])
        self.assertFalse(self.out.exists())

    def test_the_file_is_gone_before_the_child_starts(self) -> None:
        seen = {}

        def child(script, child_args, timeout):
            seen["existed"] = self.out.exists()
            self.out.write_text(json.dumps([{"account": "act_1", "verdict": "STALL"}]), encoding="utf-8")
            return metaops.ChildResult(argv=["monitor.py"], returncode=1, stdout="", stderr="")

        with mock.patch.object(metaops, "run_child", side_effect=child), mock.patch.object(metaops, "echo_child"):
            code, payload = cmd_operate.command_monitor(self.args(), metaops)
        self.assertFalse(seen["existed"])
        self.assertEqual(payload["data"]["verdict_counts"], {"STALL": 1})

    def test_error_verdict_flows_into_the_operate_summary(self) -> None:
        def child(script, child_args, timeout):
            self.out.write_text(json.dumps([{"account": "act_1", "verdict": "REJECTS,ERROR"}]), encoding="utf-8")
            return metaops.ChildResult(argv=["monitor.py"], returncode=1, stdout="", stderr="")

        with mock.patch.object(metaops, "run_child", side_effect=child), mock.patch.object(metaops, "echo_child"):
            code, payload = cmd_operate.command_monitor(self.args(), metaops)
        self.assertEqual(code, 1)
        self.assertEqual(payload["data"]["verdict_counts"], {"REJECTS": 1, "ERROR": 1})


if __name__ == "__main__":
    unittest.main()

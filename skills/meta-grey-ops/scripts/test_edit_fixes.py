#!/usr/bin/env python3
"""Regression tests for the edit/operate review fixes (edit.py, edit_tags.py, edit_targeting.py and
the cmd_edit wrappers). Offline: graph.get / graph.post are replaced by an in-memory FakeGraph.

Every test here fails on the code as it was before the fixes; the fix number is in the test name
(matches the review list: 1 budget step, 2 --set, 3 --budget-pct, 4 ad-set-only flags, 5 --all
statuses, 6 rejected ads, 7 no-op / read-back, 8 empty copy flags, 9 geo regions, 10 Advantage+,
11 empty targeting values).
"""

from __future__ import annotations
import os as _os, tempfile as _tempfile
_os.environ["METAOPS_PACE_DIR"] = _tempfile.mkdtemp(prefix="metaops-pace-test-")
_os.environ.setdefault("METAOPS_CREATE_GAP_HOURS", "0")

import argparse
import contextlib
import copy
import io
import json
import os
import pathlib
import tempfile
import unittest
from unittest import mock

import cmd_edit
import edit
import edit_tags
import edit_targeting
import metaops

os.environ.setdefault("META_TOKEN", "TEST_TOKEN")


def graph_error(code: int = 100, message: str = "nonexisting field") -> Exception:
    return edit.graph.GraphError(400, {"error": {"code": code, "message": message}}, "test")


class FakeGraph:
    """Nodes by id. `get` returns the node (edges: `edges[path]`); a node's `_lacks` lists field
    names Graph answers #100 for. `post` merges the payload into the node, like an accepted edit."""

    def __init__(self, nodes: dict | None = None, edges: dict | None = None):
        self.nodes = copy.deepcopy(nodes or {})
        self.edges = edges or {}
        self.gets: list[tuple[str, dict]] = []
        self.posts: list[tuple[str, dict]] = []
        self.next_id = 900

    def get(self, path, params=None, context=""):
        params = params or {}
        self.gets.append((path, params))
        if path in self.edges:
            return self.edges[path]
        node = self.nodes[path]
        wanted = set((params.get("fields") or "").split(","))
        if wanted & set(node.get("_lacks", ())):
            raise graph_error()
        return {k: v for k, v in node.items() if k != "_lacks"}

    def post(self, path, data=None, **_kw):
        self.posts.append((path, copy.deepcopy(data)))
        if path.endswith("/adcreatives"):
            self.next_id += 1
            new_id = str(self.next_id)
            self.nodes[new_id] = {"id": new_id, **copy.deepcopy(data)}
            return {"id": new_id}
        node = self.nodes.setdefault(path, {})
        for key, value in (data or {}).items():
            if key == "creative" and isinstance(value, dict):
                node["creative"] = copy.deepcopy(self.nodes.get(value["creative_id"], {"id": value["creative_id"]}))
            else:
                node[key] = copy.deepcopy(value)
        return {}


def run_main(module, argv: list[str], fake: FakeGraph, **patches):
    """Run module.main() against `fake`; returns (exit_code_or_SystemExit_message, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    stack = contextlib.ExitStack()
    with stack:
        stack.enter_context(mock.patch.object(module.sys, "argv", [module.__name__ + ".py", *argv]))
        stack.enter_context(mock.patch.object(module.graph, "require_write_authority"))
        stack.enter_context(mock.patch.object(module.graph, "get", side_effect=fake.get))
        stack.enter_context(mock.patch.object(module.graph, "post", side_effect=fake.post))
        for name, value in patches.items():
            stack.enter_context(mock.patch.object(module, name, value))
        stack.enter_context(contextlib.redirect_stdout(out))
        stack.enter_context(contextlib.redirect_stderr(err))
        code = module.main()
    return code, out.getvalue(), err.getvalue()


def last_json(stdout: str) -> dict:
    for line in reversed(stdout.splitlines()):
        if line.startswith("{"):
            return json.loads(line)
    raise AssertionError("no JSON result line in stdout")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)
    cmd_edit.register(sub, metaops)
    return ap


def make_workspace(root: pathlib.Path):
    path = root / "workspace.json"
    path.write_text(json.dumps({
        "schema": metaops.meta_workspace.WORKSPACE_SCHEMA, "name": "contract",
        "api_version": metaops.graph.API_VERSION, "blocked_accounts": [],
        "profiles": {"test": {
            "business_id": "10", "app_id": "11", "system_user_id": "12", "ad_account_id": "act_1",
            "page_id": "2", "dataset_id": "3", "currency": "USD", "timezone": "Europe/Warsaw"}},
        "defaults": {"profile": "test", "state_dir": ".metaops"},
    }), encoding="utf-8")
    return metaops.meta_workspace.load_workspace(str(path))


def fake_child(stdout: str = '{"schema": "edit.result/v1", "ok": true}\n', returncode: int = 0):
    return metaops.ChildResult(argv=[], returncode=returncode, stdout=stdout, stderr="")


class WrapperBase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.workspace = make_workspace(self.root)
        self.ap = build_parser()

    def parse(self, argv: list[str]) -> argparse.Namespace:
        args = self.ap.parse_args(argv)
        args.workspace_obj = self.workspace
        args.profile = "test"
        args.timeout = 30
        return args

    def run_wrapper(self, argv: list[str], stdout: str = '{"schema": "edit.result/v1", "ok": true}\n'):
        args = self.parse(argv)
        with (mock.patch.object(metaops, "run_child", return_value=fake_child(stdout)) as run_child,
              mock.patch.object(metaops, "echo_child")):
            code, payload = args.handler(args)
        return code, payload, run_child

    def assert_refused_before_child(self, argv: list[str]) -> str:
        args = self.parse(argv)
        with mock.patch.object(metaops, "run_child", side_effect=AssertionError("child must not run")):
            with self.assertRaises(metaops.MetaOpsError) as ctx:
                args.handler(args)
        return str(ctx.exception)


# --------------------------------------------------------------------------- edit.py

def budget_node(daily_budget: int | str, oid: str = "9") -> dict:
    return {oid: {"id": oid, "account_id": "1", "name": "AS", "status": "ACTIVE",
                  "effective_status": "ACTIVE", "daily_budget": str(daily_budget)}}


class BudgetStepGuard(unittest.TestCase):  # fix 1
    BASE = ["--ids", "9", "--expected-account", "act_1"]

    def run_budget(self, current: int, *flags: str, hour: int = 10):
        fake = FakeGraph(budget_node(current))
        code, _out, err = run_main(edit, [*self.BASE, *flags], fake, account_hour=lambda _obj: hour)
        return code, fake, err

    def test_pct_20_on_10368_is_not_refused_as_20_004_percent(self) -> None:
        code, fake, err = self.run_budget(10368, "--budget-pct", "+20")
        self.assertEqual(code, 0, err)
        self.assertEqual(fake.posts, [("9", {"daily_budget": 12442})])

    def test_pct_20_never_exceeds_20_percent_on_small_budgets(self) -> None:
        # 104 * 1.2 = 124.8 -> round() would be 125 (+20.19%): the lower integer is taken instead
        code, fake, err = self.run_budget(104, "--budget-pct", "+20")
        self.assertEqual(code, 0, err)
        self.assertEqual(fake.posts, [("9", {"daily_budget": 124})])

    def test_ramp_step_20_never_stalls_on_rounding(self) -> None:
        stalled = []
        for current in [1000, 1013, 2999, 4567, 7777, 9999, 10368, 12345, 33333, 104, 105, 111, 199]:
            code, _fake, _err = self.run_budget(current, "--budget-pct", "+20")
            if code != 0:
                stalled.append(current)
        self.assertEqual(stalled, [])

    def test_explicit_minor_within_rounding_of_20_percent_is_allowed(self) -> None:
        code, fake, _err = self.run_budget(10368, "--budget-minor", "12442")
        self.assertEqual(code, 0)
        self.assertEqual(fake.posts, [("9", {"daily_budget": 12442})])

    def test_raise_above_20_percent_is_still_refused_without_force(self) -> None:
        code, fake, _err = self.run_budget(10000, "--budget-pct", "+25")
        self.assertEqual(code, 1)
        self.assertEqual(fake.posts, [])
        code, fake, _err = self.run_budget(10000, "--budget-minor", "12100")  # +21%
        self.assertEqual(code, 1)
        self.assertEqual(fake.posts, [])

    def test_raise_above_20_percent_passes_with_force_step(self) -> None:
        code, fake, _err = self.run_budget(10000, "--budget-pct", "+50", "--force-step")
        self.assertEqual(code, 0)
        self.assertEqual(fake.posts, [("9", {"daily_budget": 15000})])

    def test_cut_up_to_half_needs_no_force_step(self) -> None:
        for flags, expected in ((("--budget-pct", "-50"), 5000), (("--budget-pct", "-40"), 6000),
                                (("--budget-minor", "6000"), 6000)):
            code, fake, err = self.run_budget(10000, *flags)
            self.assertEqual(code, 0, f"{flags}: {err}")
            self.assertEqual(fake.posts, [("9", {"daily_budget": expected})])

    def test_cut_deeper_than_half_needs_force_step(self) -> None:
        for flags in (("--budget-pct", "-90"), ("--budget-minor", "1000")):
            code, fake, _err = self.run_budget(10000, *flags)
            self.assertEqual((code, fake.posts), (1, []), flags)
        code, fake, _err = self.run_budget(10000, "--budget-pct", "-90", "--force-step")
        self.assertEqual((code, fake.posts), (0, [("9", {"daily_budget": 1000})]))

    def test_budget_is_never_posted_below_one_minor_unit(self) -> None:
        for flags in (("--budget-pct", "-99.99", "--force-step"), ("--budget-minor", "1", "--force-step")):
            code, fake, _err = self.run_budget(1000 if "-99.99" in flags else 10000, *flags)
            if flags[0] == "--budget-pct":
                self.assertEqual((code, fake.posts), (1, []), flags)
            else:
                self.assertEqual((code, fake.posts), (0, [("9", {"daily_budget": 1})]), flags)

    def test_cut_never_triggers_the_late_day_check(self) -> None:
        def boom(_obj):
            raise AssertionError("late-day check must not run for a cut")
        fake = FakeGraph(budget_node(10000))
        code, _out, _err = run_main(edit, [*self.BASE, "--budget-pct", "-30"], fake, account_hour=boom)
        self.assertEqual(code, 0)

    def test_raise_late_in_the_account_day_is_still_refused(self) -> None:
        code, fake, _err = self.run_budget(10000, "--budget-pct", "+10", hour=23)
        self.assertEqual(code, 1)
        self.assertEqual(fake.posts, [])
        code, fake, _err = self.run_budget(10000, "--budget-pct", "+10", "--force-step", hour=23)
        self.assertEqual(code, 0)

    def test_budget_minor_must_be_positive_and_exclusive_with_pct(self) -> None:
        for flags in (("--budget-minor", "0"), ("--budget-minor", "-5"),
                      ("--budget-minor", "500", "--budget-pct", "+10")):
            fake = FakeGraph(budget_node(10000))
            with self.assertRaises(SystemExit, msg=str(flags)):
                run_main(edit, [*self.BASE, *flags], fake)
            self.assertEqual(fake.posts, [])


class SetNames(unittest.TestCase):  # fix 2
    def nodes(self):
        return {i: {"id": i, "account_id": "1", "name": f"old{i}", "status": "ACTIVE"} for i in ("11", "22", "33")}

    def test_set_id_outside_resolved_ids_fails_loudly(self) -> None:
        fake = FakeGraph(self.nodes())
        with self.assertRaises(SystemExit) as ctx:
            run_main(edit, ["--ids", "11", "--set", "22=Renamed"], fake)
        self.assertIn("22", str(ctx.exception))
        self.assertEqual(fake.posts, [])
        self.assertEqual(fake.gets, [])

    def test_ids_without_a_set_name_fail_when_set_is_the_only_change(self) -> None:
        fake = FakeGraph(self.nodes())
        with self.assertRaises(SystemExit) as ctx:
            run_main(edit, ["--ids", "11,33", "--set", "11=A-1"], fake)
        self.assertIn("33", str(ctx.exception))
        self.assertEqual(fake.posts, [])

    def test_duplicate_set_id_is_refused(self) -> None:
        with self.assertRaises(SystemExit):
            run_main(edit, ["--ids", "11", "--set", "11=A", "--set", "11=B"], FakeGraph(self.nodes()))

    def test_set_with_exactly_matching_ids_still_renames(self) -> None:
        fake = FakeGraph(self.nodes())
        code, _out, _err = run_main(edit, ["--ids", "11,22", "--set", "11=A-1", "--set", "22=B-2"], fake)
        self.assertEqual(code, 0)
        self.assertEqual([p for p in fake.posts], [("11", {"name": "A-1"}), ("22", {"name": "B-2"})])

    def test_extra_ids_are_fine_when_another_change_applies_to_them(self) -> None:
        fake = FakeGraph(self.nodes())
        code, _out, _err = run_main(
            edit, ["--ids", "11,33", "--set", "11=A-1", "--status", "PAUSED", "--confirm", "PAUSE"], fake)
        self.assertEqual(code, 0)
        self.assertEqual(fake.posts, [("11", {"status": "PAUSED", "name": "A-1"}), ("33", {"status": "PAUSED"})])


class BudgetPctParsing(WrapperBase):  # fix 3
    BAD = ("", "   ", "abc", "nan", "inf", "-100", "-150", "+", "20%", "1,5")

    def test_child_rejects_bad_pct_before_touching_anything(self) -> None:
        for bad in self.BAD:
            fake = FakeGraph(budget_node(10000))
            with self.assertRaises(SystemExit, msg=repr(bad)):
                run_main(edit, ["--ids", "9", "--budget-pct", bad], fake)
            self.assertEqual((fake.gets, fake.posts), ([], []), repr(bad))

    def test_wrapper_rejects_bad_pct_before_the_child_runs(self) -> None:
        for bad in self.BAD:
            self.assert_refused_before_child(
                ["edit", "budget", "--ids", "9", "--budget-pct", bad, "--confirm", "SPEND"])

    def test_wrapper_rejects_non_positive_minor(self) -> None:
        self.assert_refused_before_child(["edit", "budget", "--ids", "9", "--budget-minor", "0", "--confirm", "SPEND"])

    def test_ramp_allows_big_cuts_but_not_big_raises(self) -> None:
        _c, _p, run_child = self.run_wrapper(["edit", "ramp", "--ids", "9", "--step", "-40", "--confirm", "RAMP"])
        self.assertEqual(run_child.call_args[0][1][-2:], ["--budget-pct", "-40"])
        self.assert_refused_before_child(["edit", "ramp", "--ids", "9", "--step", "25", "--confirm", "RAMP"])
        self.assert_refused_before_child(["edit", "ramp", "--ids", "9", "--step", "0", "--confirm", "RAMP"])


class AdSetOnlyFlags(unittest.TestCase):  # fix 4
    def nodes(self):
        base = {"account_id": "1", "status": "PAUSED", "effective_status": "PAUSED"}
        return {
            "AS": {"id": "AS", "name": "adset", "optimization_goal": "OFFSITE_CONVERSIONS", "bid_amount": 100, **base},
            "AD": {"id": "AD", "name": "ad", "_lacks": ["optimization_goal", "bid_amount", "daily_budget",
                                                      "lifetime_budget"], **base},
            "CA": {"id": "CA", "name": "camp", "_lacks": ["optimization_goal", "bid_amount"], **base},
        }

    def test_start_and_end_time_are_refused_on_non_adsets_before_any_post(self) -> None:
        for oid in ("AD", "CA"):
            fake = FakeGraph(self.nodes())
            code, _out, err = run_main(
                edit, ["--ids", oid, "--start-time", "2099-10-01T08:00:00-07:00",
                       "--end-time", "2099-10-08T00:00:00-07:00"], fake)
            self.assertEqual(code, 1, oid)
            self.assertEqual(fake.posts, [], oid)
            self.assertIn("ad sets only", err)
            self.assertTrue(any("optimization_goal" in p.get("fields", "") for _path, p in fake.gets))

    def test_end_time_alone_on_a_campaign_is_refused(self) -> None:
        fake = FakeGraph(self.nodes())
        code, _out, _err = run_main(edit, ["--ids", "CA", "--end-time", "2099-10-08T00:00:00-07:00"], fake)
        self.assertEqual(code, 1)
        self.assertEqual(fake.posts, [])

    def test_bid_is_refused_on_non_adsets(self) -> None:
        for oid in ("AD", "CA"):
            fake = FakeGraph(self.nodes())
            code, _out, _err = run_main(edit, ["--ids", oid, "--bid-minor", "15000"], fake)
            self.assertEqual((code, fake.posts), (1, []), oid)

    def test_schedule_on_an_adset_still_posts(self) -> None:
        fake = FakeGraph(self.nodes())
        code, out, _err = run_main(edit, ["--ids", "AS", "--start-time", "2099-10-01T08:00:00-07:00"], fake)
        self.assertEqual(code, 0)
        self.assertEqual(fake.posts, [("AS", {"start_time": "2099-10-01T08:00:00-07:00"})])
        self.assertTrue(last_json(out)["ok"])

    def test_mixed_list_updates_the_adset_and_refuses_the_ad(self) -> None:
        fake = FakeGraph(self.nodes())
        code, out, _err = run_main(edit, ["--ids", "AS,AD", "--bid-minor", "15000"], fake)
        self.assertEqual(code, 1)
        self.assertEqual(fake.posts, [("AS", {"bid_amount": 15000})])
        rows = {r["id"]: r for r in last_json(out)["results"]}
        self.assertTrue(rows["AS"]["ok"])
        self.assertFalse(rows["AD"]["ok"])

    def test_status_change_needs_no_adset_probe(self) -> None:
        fake = FakeGraph(self.nodes())
        code, _out, _err = run_main(edit, ["--ids", "AD", "--status", "PAUSED", "--confirm", "PAUSE"], fake)
        self.assertEqual(code, 0)
        self.assertFalse(any("optimization_goal" in p.get("fields", "") for _path, p in fake.gets))

    def test_empty_time_flag_is_rejected_not_ignored(self) -> None:
        with self.assertRaises(SystemExit):
            run_main(edit, ["--ids", "AS", "--start-time", "", "--bid-minor", "100"], FakeGraph(self.nodes()))


class AllStatusScope(WrapperBase):  # fix 5
    def statuses_sent(self, fake: FakeGraph, edge: str) -> list[str]:
        params = [p for path, p in fake.gets if path == f"act_1/{edge}"][0]
        return json.loads(params["effective_status"])

    def test_ids_from_account_takes_a_statuses_parameter(self) -> None:
        fake = FakeGraph(edges={"act_1/ads": {"data": [{"id": "1"}]}})
        with mock.patch.object(edit.graph, "get", side_effect=fake.get):
            edit.ids_from_account("act_1", "ad", statuses=["ACTIVE"])
            self.assertEqual(self.statuses_sent(fake, "ads"), ["ACTIVE"])
            fake.gets.clear()
            edit.ids_from_account("act_1", "ad")
            self.assertIn("IN_PROCESS", self.statuses_sent(fake, "ads"))

    def test_edit_status_all_keeps_the_wide_kill_switch_list(self) -> None:
        fake = FakeGraph(
            nodes={"5": {"id": "5", "account_id": "1", "name": "C", "status": "ACTIVE"}},
            edges={"act_1/campaigns": {"data": [{"id": "5"}]}})
        code, _out, _err = run_main(
            edit, ["--account", "act_1", "--level", "campaign", "--all", "--status", "PAUSED", "--confirm", "PAUSE"],
            fake)
        self.assertEqual(code, 0)
        sent = self.statuses_sent(fake, "campaigns")
        for status in ("ACTIVE", "IN_PROCESS", "PENDING_REVIEW", "WITH_ISSUES", "ADSET_PAUSED"):
            self.assertIn(status, sent)

    def test_tags_all_selects_active_ads_only(self) -> None:
        fake = FakeGraph(edges={"act_1/ads": {"data": []}})
        with self.assertRaises(SystemExit):  # empty account -> "no ids"; the query is what we check
            run_main(edit_tags, ["--account", "act_1", "--all", "--url-tags", "a=b", "--confirm", "TAGS"], fake)
        self.assertEqual(self.statuses_sent(fake, "ads"), ["ACTIVE"])

    def test_targeting_all_selects_active_adsets_only(self) -> None:
        fake = FakeGraph(edges={"act_1/adsets": {"data": []}})
        with self.assertRaises(SystemExit):
            run_main(edit_targeting, ["--account", "act_1", "--all", "--user-os", "iOS", "--confirm", "TARGETING"],
                     fake)
        self.assertEqual(self.statuses_sent(fake, "adsets"), ["ACTIVE"])

    def test_help_texts_say_what_all_really_selects(self) -> None:
        def help_of(*path: str) -> str:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf), self.assertRaises(SystemExit):
                self.ap.parse_args([*path, "--help"])
            return " ".join(buf.getvalue().split())
        status = help_of("edit", "status")
        self.assertNotIn("every ACTIVE object", status)
        self.assertIn("paused parent", status)
        self.assertIn("ACTIVE ad set", help_of("edit", "targeting"))
        self.assertIn("ACTIVE ad", help_of("edit", "tags"))


# --------------------------------------------------------------------------- edit_tags.py

def link_ad(status: str = "ACTIVE", **extra) -> dict:
    ad = {"id": "77", "name": "Ad", "account_id": "1", "effective_status": status,
          "creative": {"id": "500", "name": "C", "url_tags": "sub1=OLD",
                       "object_story_spec": {"page_id": "2", "link_data": {
                           "link": "https://old.example/", "message": "old text", "name": "Old head",
                           "description": "old desc", "caption": "old.example", "image_hash": "h1",
                           "call_to_action": {"type": "LEARN_MORE", "value": {"link": "https://old.example/"}}}}}}
    ad.update(extra)
    return ad


class TagsChild(unittest.TestCase):
    def run_tags(self, argv: list[str], ad: dict):
        fake = FakeGraph({"77": ad})
        code, out, err = run_main(edit_tags, ["--ids", "77", *argv, "--confirm", "TAGS"], fake)
        return code, fake, out, err

    # fix 6
    def test_ad_review_feedback_skips_a_paused_rejected_ad(self) -> None:
        feedback = {"global": {"Personal attributes": "rejected"}}
        for status in ("ADSET_PAUSED", "PAUSED", "CAMPAIGN_PAUSED", "ACTIVE"):
            code, fake, out, _err = self.run_tags(
                ["--headline", "New"], link_ad(status, ad_review_feedback=feedback,
                                               issues_info=[{"error_summary": "x"}]))
            self.assertEqual(code, 0, status)
            self.assertEqual(fake.posts, [], status)
            row = last_json(out)["results"][0]
            self.assertTrue(row.get("skipped"), status)
            self.assertEqual(row["ad_review_feedback"], feedback)

    def test_review_fields_are_requested_with_the_ad(self) -> None:
        _code, fake, _out, _err = self.run_tags(["--headline", "New"], link_ad())
        fields = fake.gets[0][1]["fields"]
        self.assertIn("ad_review_feedback", fields)
        self.assertIn("issues_info", fields)

    def test_allow_disapproved_still_edits_a_rejected_ad(self) -> None:
        code, fake, _out, _err = self.run_tags(
            ["--headline", "New", "--allow-disapproved"],
            link_ad("PAUSED", ad_review_feedback={"global": {"x": "y"}}))
        self.assertEqual(code, 0)
        self.assertEqual(len(fake.posts), 2)

    def test_empty_review_feedback_does_not_block(self) -> None:
        code, fake, _out, _err = self.run_tags(["--headline", "New"], link_ad(ad_review_feedback={}, issues_info=[]))
        self.assertEqual(code, 0)
        self.assertEqual(len(fake.posts), 2)

    # fix 7
    def test_identical_values_are_a_no_change_skip_without_clone_or_swap(self) -> None:
        cases = (["--headline", "Old head"], ["--url-tags", "sub1=OLD"], ["--message", "old text"],
                 ["--description", "old desc"], ["--caption", "old.example"], ["--cta", "LEARN_MORE"],
                 ["--link", "https://old.example/"], ["--image-hash", "h1"],
                 ["--headline", "Old head", "--url-tags", "sub1=OLD", "--message", "old text"])
        for argv in cases:
            code, fake, out, _err = self.run_tags(argv, link_ad())
            self.assertEqual(code, 0, argv)
            self.assertEqual(fake.posts, [], argv)
            row = last_json(out)["results"][0]
            self.assertEqual((row["skipped"], row["reason"]), (True, "no change"), argv)

    def test_removing_a_description_that_is_not_there_is_no_change(self) -> None:
        ad = link_ad()
        del ad["creative"]["object_story_spec"]["link_data"]["description"]
        code, fake, out, _err = self.run_tags(["--description", ""], ad)
        self.assertEqual((code, fake.posts), (0, []))
        self.assertEqual(last_json(out)["results"][0]["reason"], "no change")

    def test_no_change_is_reported_in_dry_run_too(self) -> None:
        code, fake, out, _err = self.run_tags(["--headline", "Old head", "--dry-run"], link_ad())
        self.assertEqual((code, fake.posts), (0, []))
        self.assertEqual(last_json(out)["results"][0]["reason"], "no change")

    def test_a_change_deep_in_a_long_message_is_not_mistaken_for_no_change(self) -> None:
        old = "x" * 200 + "A"
        ad = link_ad()
        ad["creative"]["object_story_spec"]["link_data"]["message"] = old
        code, fake, _out, _err = self.run_tags(["--message", "x" * 200 + "B"], ad)  # same length, same first 60
        self.assertEqual(code, 0)
        self.assertEqual(len(fake.posts), 2)

    def test_partial_overlap_still_clones(self) -> None:
        code, fake, _out, _err = self.run_tags(["--headline", "Old head", "--message", "new text"], link_ad())
        self.assertEqual(code, 0)
        self.assertEqual(len(fake.posts), 2)

    def test_readback_carries_and_prints_effective_status(self) -> None:
        fake = FakeGraph({"77": link_ad()})
        real_get = fake.get

        def get_after_swap(path, params=None, context=""):
            node = real_get(path, params, context)
            if context == "readback":  # Graph reports the swapped ad as re-reviewing
                assert "effective_status" in params["fields"]
                node = {**node, "effective_status": "IN_PROCESS"}
            return node

        fake.get = get_after_swap
        code, out, _err = run_main(edit_tags, ["--ids", "77", "--headline", "Z", "--confirm", "TAGS"], fake)
        self.assertEqual(code, 0)
        self.assertIn("effective_status=IN_PROCESS", out)
        self.assertEqual(last_json(out)["results"][0]["effective_status"], "IN_PROCESS")

    def test_review_warning_names_the_lost_post_state(self) -> None:
        text = edit_tags.REVIEW_WARNING
        self.assertIn("new creative", text.lower())
        self.assertIn("new post", text)
        self.assertIn("likes", text)
        self.assertIn("unverified", text)

    # fix 8
    def test_empty_strings_are_rejected_for_value_flags(self) -> None:
        for flag in ("--headline", "--cta", "--link", "--image-hash", "--url-tags", "--template-url", "--message-file"):
            fake = FakeGraph({"77": link_ad()})
            argv = ["--ids", "77", "--message", "fresh text", flag, "", "--confirm", "TAGS"]
            if flag == "--message-file":
                argv = ["--ids", "77", "--headline", "H", flag, "", "--confirm", "TAGS"]
            with self.assertRaises(SystemExit, msg=flag):
                run_main(edit_tags, argv, fake)
            self.assertEqual((fake.gets, fake.posts), ([], []), flag)

    def test_empty_description_and_caption_still_mean_remove(self) -> None:
        code, fake, _out, _err = self.run_tags(["--description", "", "--caption", ""], link_ad())
        self.assertEqual(code, 0)
        ld = fake.posts[0][1]["object_story_spec"]["link_data"]
        self.assertNotIn("description", ld)
        self.assertNotIn("caption", ld)


class TagsWrapper(WrapperBase):  # fix 8, wrapper side
    def test_wrapper_rejects_empty_value_flags_before_the_child(self) -> None:
        for flag in ("--headline", "--cta", "--link", "--image-hash", "--url-tags", "--template-url", "--message"):
            self.assert_refused_before_child(
                ["edit", "tags", "--ids", "7", "--description", "d", flag, "  ", "--confirm", "TAGS"])

    def test_wrapper_still_passes_empty_description_and_caption(self) -> None:
        _c, _p, run_child = self.run_wrapper(
            ["edit", "creative", "--ids", "7", "--description", "", "--caption", "", "--confirm", "TAGS"],
            stdout='{"schema": "edit_tags.result/v1", "ok": true}\n')
        child_args = run_child.call_args[0][1]
        self.assertEqual(child_args[child_args.index("--description") + 1], "")
        self.assertEqual(child_args[child_args.index("--caption") + 1], "")


# --------------------------------------------------------------------------- edit_targeting.py

def adset(targeting: dict, oid: str = "5") -> dict:
    return {oid: {"id": oid, "name": "AS", "account_id": "1", "targeting": targeting}}


class TargetingChild(unittest.TestCase):
    def run_targeting(self, argv: list[str], targeting: dict, fake: FakeGraph | None = None):
        fake = fake or FakeGraph(adset(targeting))
        code, out, err = run_main(edit_targeting, ["--ids", "5", *argv, "--confirm", "TARGETING",
                                                   "--expected-account", "act_1"], fake)
        return code, fake, out, err

    # fix 9
    def test_geo_regions_keeps_only_regions_and_location_types(self) -> None:
        geo = {"countries": ["US"], "electoral_districts": [{"key": "d1"}], "place_page_ids": ["1"],
               "custom_locations": [{"latitude": 1}], "regions": [{"key": "3879"}], "location_types": ["home"],
               "some_future_key": True}
        code, fake, _out, _err = self.run_targeting(["--geo-regions", "3880"], {"geo_locations": geo, "age_min": 21})
        self.assertEqual(code, 0)
        sent = fake.posts[0][1]["targeting"]
        self.assertEqual(sent["geo_locations"], {"regions": [{"key": "3880"}], "location_types": ["home"]})
        self.assertEqual(sent["age_min"], 21)

    def test_merge_targeting_geo_whitelist_without_location_types(self) -> None:
        merged = edit_targeting.merge_targeting(
            {"geo_locations": {"geo_markets": [{"key": "DMA1"}], "zips": [{"key": "US:1"}]}},
            {"geo_locations.regions": [{"key": "1"}]})
        self.assertEqual(merged["geo_locations"], {"regions": [{"key": "1"}]})

    def test_geo_regions_with_all_is_refused_in_the_child(self) -> None:
        fake = FakeGraph(edges={"act_1/adsets": {"data": [{"id": "5"}]}}, nodes=adset({"geo_locations": {}}))
        with self.assertRaises(SystemExit) as ctx:
            run_main(edit_targeting, ["--account", "act_1", "--all", "--geo-regions", "3879",
                                      "--confirm", "TARGETING"], fake)
        self.assertIn("--all", str(ctx.exception))
        self.assertEqual((fake.gets, fake.posts), ([], []))

    # fix 10
    def test_advantage_plus_with_narrow_age_is_refused(self) -> None:
        on = {"geo_locations": {"regions": [{"key": "1"}]}, "targeting_automation": {"advantage_audience": 1}}
        for argv in (["--age-min", "30"], ["--age-max", "60"], ["--age-min", "26", "--age-max", "64"]):
            code, fake, out, _err = self.run_targeting(argv, on)
            self.assertEqual(code, 1, argv)
            self.assertEqual(fake.posts, [], argv)
            self.assertIn("Advantage+", last_json(out)["results"][0]["error"])

    def test_advantage_flag_given_together_with_narrow_age_is_refused(self) -> None:
        off = {"geo_locations": {"regions": [{"key": "1"}]}, "targeting_automation": {"advantage_audience": 0}}
        code, fake, _out, _err = self.run_targeting(["--advantage-audience", "1", "--age-max", "60"], off)
        self.assertEqual((code, fake.posts), (1, []))

    def test_unrelated_edit_is_not_blocked_by_a_stored_advantage_age_clash(self) -> None:
        code, fake, _out, _err = self.run_targeting(
            ["--device-platforms", "mobile"],
            {"geo_locations": {}, "age_min": 30, "targeting_automation": {"advantage_audience": 1}})
        self.assertEqual((code, len(fake.posts)), (0, 1))

    def test_age_edit_on_advantage_plus_is_refused_even_with_a_stored_clash(self) -> None:
        code, fake, _out, _err = self.run_targeting(
            ["--age-max", "50"],
            {"geo_locations": {}, "age_min": 30, "targeting_automation": {"advantage_audience": 1}})
        self.assertEqual((code, fake.posts), (1, []))

    def test_advantage_plus_allows_the_clamp_compatible_range(self) -> None:
        on = {"geo_locations": {}, "targeting_automation": {"advantage_audience": 1}}
        code, fake, _out, _err = self.run_targeting(["--age-min", "25", "--age-max", "65"], on)
        self.assertEqual(code, 0)
        self.assertEqual(len(fake.posts), 1)

    def test_switching_advantage_off_allows_a_narrow_age(self) -> None:
        on = {"geo_locations": {}, "targeting_automation": {"advantage_audience": 1}}
        code, fake, _out, _err = self.run_targeting(["--advantage-audience", "0", "--age-min", "30"], on)
        self.assertEqual(code, 0)
        self.assertEqual(len(fake.posts), 1)

    def test_dry_run_reports_the_advantage_conflict_too(self) -> None:
        on = {"geo_locations": {}, "targeting_automation": {"advantage_audience": 1}}
        code, fake, _out, _err = self.run_targeting(["--age-min", "40", "--dry-run"], on)
        self.assertEqual((code, fake.posts), (1, []))

    def test_readback_difference_is_reported_as_not_applied(self) -> None:
        fake = FakeGraph(adset({"geo_locations": {}, "age_min": 18}))
        real_post = fake.post

        def clamping_post(path, data=None, **kw):  # Graph accepts the POST but keeps age_min 25
            real_post(path, data, **kw)
            fake.nodes[path]["targeting"]["age_min"] = 25
            return {}

        fake.post = clamping_post
        code, fake, out, _err = self.run_targeting(["--age-min", "21", "--device-platforms", "mobile"], {}, fake)
        self.assertEqual(code, 1)
        row = last_json(out)["results"][0]
        self.assertFalse(row["ok"])
        self.assertEqual(row["not_applied"], ["age_min"])
        self.assertEqual(row["not_applied_detail"]["age_min"], {"requested": 21, "actual": 25})

    def test_graph_decorating_the_readback_is_not_a_false_not_applied(self) -> None:
        fake = FakeGraph(adset({"geo_locations": {}, "user_os": ["Android"]}))
        real_post = fake.post

        def decorating_post(path, data=None, **kw):
            real_post(path, data, **kw)
            tg = fake.nodes[path]["targeting"]
            tg["geo_locations"]["regions"] = [{"key": "3879", "name": "Oklahoma", "country": "US",
                                               "supports_region": True}]
            tg["user_os"] = list(reversed(tg["user_os"]))
            tg["genders"] = [str(g) for g in tg["genders"]]
            return {}

        fake.post = decorating_post
        code, fake, out, _err = self.run_targeting(
            ["--geo-regions", "3879", "--user-os", "iOS,Android", "--genders", "1,2"], {}, fake)
        self.assertEqual(code, 0)
        row = last_json(out)["results"][0]
        self.assertTrue(row["ok"])
        self.assertNotIn("not_applied", row)

    # fix 11
    def test_empty_values_are_refused_not_turned_into_empty_lists(self) -> None:
        for flag in ("--user-os", "--genders", "--facebook-positions", "--instagram-positions",
                     "--device-platforms", "--geo-regions", "--age-min", "--age-max", "--advantage-audience"):
            for empty in ("", " , "):
                fake = FakeGraph(adset({"geo_locations": {}}))
                with self.assertRaises(SystemExit, msg=f"{flag} {empty!r}"):
                    run_main(edit_targeting, ["--ids", "5", flag, empty, "--confirm", "TARGETING"], fake)
                self.assertEqual(fake.posts, [], flag)

    def test_publisher_platforms_empty_is_refused(self) -> None:
        with self.assertRaises(SystemExit):
            run_main(edit_targeting, ["--ids", "5", "--publisher-platforms", "", "--confirm", "TARGETING"],
                     FakeGraph(adset({"geo_locations": {}})))


class TargetingWrapper(WrapperBase):
    def test_wrapper_refuses_geo_regions_with_all(self) -> None:  # fix 9
        message = self.assert_refused_before_child(
            ["edit", "targeting", "--all", "--geo-regions", "3879", "--confirm", "TARGETING"])
        self.assertIn("--all", message)

    def test_wrapper_allows_geo_regions_with_explicit_ids(self) -> None:
        _c, _p, run_child = self.run_wrapper(
            ["edit", "targeting", "--ids", "5,6", "--geo-regions", "3879", "--confirm", "TARGETING"],
            stdout='{"schema": "edit_targeting.result/v1", "ok": true}\n')
        self.assertIn("--geo-regions", run_child.call_args[0][1])

    def test_wrapper_refuses_empty_values(self) -> None:  # fix 11
        for flag in ("--user-os", "--genders", "--publisher-platforms", "--facebook-positions",
                     "--instagram-positions", "--device-platforms", "--geo-regions", "--age-min",
                     "--age-max", "--advantage-audience"):
            self.assert_refused_before_child(["edit", "targeting", "--ids", "5", flag, "", "--confirm", "TARGETING"])


if __name__ == "__main__":
    unittest.main()

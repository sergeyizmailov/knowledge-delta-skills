#!/usr/bin/env python3
"""Offline contract tests for cmd_operate.py. No network or real credentials."""

from __future__ import annotations
import os as _os, tempfile as _tempfile
_os.environ["METAOPS_PACE_DIR"] = _tempfile.mkdtemp(prefix="metaops-pace-test-")
_os.environ.setdefault("METAOPS_CREATE_GAP_HOURS", "0")

import json
import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("META_TOKEN", "TEST_TOKEN")

import cmd_operate
import metaops


class FakeWorkspace:
    def __init__(self, state_root: pathlib.Path, profile_data: dict):
        self._state_root = state_root
        self._profile_data = profile_data
        self.data = {"profiles": {"test": dict(profile_data)}}

    @property
    def state_root(self) -> pathlib.Path:
        return self._state_root

    def profile(self, requested=None):
        return "test", dict(self._profile_data)


def make_args(**overrides):
    ns = mock.Mock()
    ns.profile = None
    ns.timeout = 30
    for key, value in overrides.items():
        setattr(ns, key, value)
    return ns


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.root = pathlib.Path(self.td.name)
        self.workspace = FakeWorkspace(
            self.root, {"ad_account_id": "act_1", "page_id": "2", "dataset_id": "3"}
        )

    def test_review_summary_and_exit_code_on_disapproved(self):
        ads = {
            "111": {"id": "111", "account_id": "1", "name": "A", "effective_status": "ACTIVE",
                    "configured_status": "ACTIVE", "issues_info": None, "ad_review_feedback": None},
            "222": {"id": "222", "account_id": "1", "name": "B", "effective_status": "DISAPPROVED",
                    "configured_status": "ACTIVE", "issues_info": None,
                    "ad_review_feedback": {"global": "bad landing page"}},
        }

        def fake_get(path, params=None, context=""):
            return ads[path]

        args = make_args(
            workspace_obj=self.workspace, state=None, ids="111,222", all=False,
            previews=False, format="DESKTOP_FEED_STANDARD,MOBILE_FEED_STANDARD",
        )
        with mock.patch.object(metaops.graph, "get", side_effect=fake_get):
            code, payload = cmd_operate.command_review(args, metaops)

        self.assertEqual(code, 1)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["data"]["summary"], {"ACTIVE": 1, "DISAPPROVED": 1})
        self.assertEqual(payload["data"]["blocking"], 1)
        self.assertEqual(payload["error"]["kind"], "ad_review")

    def test_review_ok_when_nothing_blocking(self):
        ads = {"111": {"id": "111", "account_id": "1", "name": "A", "effective_status": "ACTIVE",
                       "configured_status": "ACTIVE", "issues_info": None, "ad_review_feedback": None}}
        args = make_args(
            workspace_obj=self.workspace, state=None, ids="111", all=False,
            previews=False, format="DESKTOP_FEED_STANDARD",
        )
        with mock.patch.object(metaops.graph, "get", side_effect=lambda path, params=None, context="": ads[path]):
            code, payload = cmd_operate.command_review(args, metaops)
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])

    def test_review_all_reads_review_fields_on_the_account_edge(self):
        args = make_args(
            workspace_obj=self.workspace, state=None, ids=None, all=True,
            previews=False, format="DESKTOP_FEED_STANDARD",
        )
        response = {"data": [
            {"id": "111", "account_id": "1", "name": "A", "effective_status": "ACTIVE", "configured_status": "ACTIVE"},
            {"id": "222", "account_id": "1", "name": "B", "effective_status": "DISAPPROVED", "configured_status": "ACTIVE"},
        ]}
        with mock.patch.object(metaops.graph, "get", return_value=response) as get:
            code, payload = cmd_operate.command_review(args, metaops)
        self.assertEqual(code, 1)
        get.assert_called_once_with(
            "act_1/ads", params={"fields": cmd_operate.AD_REVIEW_FIELDS, "limit": 500},
            context="review ads",
        )
        self.assertEqual(payload["data"]["blocking"], 1)

    def test_review_all_reports_empty_account_accurately(self):
        args = make_args(
            workspace_obj=self.workspace, state=None, ids=None, all=True,
            previews=False, format="DESKTOP_FEED_STANDARD",
        )
        with mock.patch.object(metaops.graph, "get", return_value={"data": []}):
            with self.assertRaisesRegex(metaops.MetaOpsError, "no ads found on act_1"):
                cmd_operate.command_review(args, metaops)

    def test_review_rejects_unknown_ad_format(self):
        args = make_args(
            workspace_obj=self.workspace, state=None, ids="111", all=False,
            previews=True, format="NOT_A_REAL_FORMAT",
        )
        with self.assertRaises(metaops.MetaOpsError):
            cmd_operate.command_review(args, metaops)

    def test_review_rejects_an_ad_from_another_profile_account(self):
        args = make_args(
            workspace_obj=self.workspace, state=None, ids="111", all=False,
            previews=False, format="DESKTOP_FEED_STANDARD",
        )
        ad = {"id": "111", "account_id": "2", "effective_status": "ACTIVE"}
        with mock.patch.object(metaops.graph, "get", return_value=ad):
            with self.assertRaisesRegex(metaops.MetaOpsError, "cross-profile"):
                cmd_operate.command_review(args, metaops)

    def test_review_requires_workspace(self):
        args = make_args(workspace_obj=None, state=None, ids="111", all=False,
                         previews=False, format="")
        with self.assertRaises(metaops.MetaOpsError):
            cmd_operate.command_review(args, metaops)


class MonitorTelegramTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.root = pathlib.Path(self.td.name)
        self.workspace = FakeWorkspace(self.root, {"ad_account_id": "act_1", "page_id": "2"})

    def test_telegram_missing_env_raises_before_any_network(self):
        os.environ.pop("TG_BOT_TOKEN", None)
        os.environ.pop("TG_CHAT_ID", None)
        args = make_args(
            workspace_obj=self.workspace, accounts="act_1,act_2", stall_impressions=40,
            telegram=True, log=None, out_json=None,
        )

        def boom(*a, **kw):
            raise AssertionError("run_child must not be called when telegram env is missing")

        with mock.patch.object(metaops, "run_child", side_effect=boom):
            with self.assertRaises(metaops.MetaOpsError):
                cmd_operate.command_monitor(args, metaops)

    def test_telegram_payload_shape_and_exit_code(self):
        os.environ["TG_BOT_TOKEN"] = "FAKE_TG_TOKEN"
        os.environ["TG_CHAT_ID"] = "999"
        self.addCleanup(os.environ.pop, "TG_BOT_TOKEN", None)
        self.addCleanup(os.environ.pop, "TG_CHAT_ID", None)
        self.workspace.data["profiles"]["second"] = {"ad_account_id": "act_2"}

        rows = [
            {"account": "act_1", "verdict": "OK", "status_label": "ACTIVE",
             "spend_yesterday": 10.0, "spend_today": 9.0, "currency": "USD", "ads": {}},
            {"account": "act_2", "verdict": "STALL", "status_label": "ACTIVE",
             "spend_yesterday": 5.0, "spend_today": 5.0, "currency": "USD",
             "ads": {"DISAPPROVED": 0, "WITH_ISSUES": 0}, "stalled_adsets": [{"id": "a1"}]},
        ]

        def fake_run_child(script, child_args, timeout):
            self.assertEqual(script, "monitor.py")
            json_path = pathlib.Path(child_args[child_args.index("--json") + 1])
            json_path.write_text(json.dumps(rows), encoding="utf-8")
            return metaops.ChildResult(argv=["monitor.py"], returncode=1, stdout="", stderr="")

        posted = {}

        class FakeSession:
            def post(self, url, json=None, timeout=None):
                posted["url"] = url
                posted["payload"] = json
                return mock.Mock(json=lambda: {"ok": True, "result": {}})

        args = make_args(
            workspace_obj=self.workspace, accounts="act_1,act_2", stall_impressions=40,
            telegram=True, log=None, out_json=None,
        )
        with mock.patch.object(metaops, "run_child", side_effect=fake_run_child), \
             mock.patch.object(metaops, "echo_child", lambda c: None), \
             mock.patch.object(metaops.graph, "plain_session", return_value=FakeSession()):
            code, payload = cmd_operate.command_monitor(args, metaops)

        self.assertEqual(code, 1)
        self.assertIn("FAKE_TG_TOKEN", posted["url"])
        self.assertEqual(posted["payload"]["chat_id"], "999")
        self.assertEqual(posted["payload"]["parse_mode"], "HTML")
        self.assertIn("STALL", posted["payload"]["text"])
        self.assertEqual(posted["payload"]["link_preview_options"], {"is_disabled": True})
        self.assertEqual(payload["data"]["telegram"]["sent"], 1)
        self.assertEqual(payload["data"]["verdict_counts"]["STALL"], 1)


class ConfirmLiteralTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.workspace = FakeWorkspace(
            pathlib.Path(self.td.name), {"ad_account_id": "act_1", "page_id": "2"}
        )

    def test_comments_hide_requires_literal_confirm(self):
        args = make_args(
            workspace_obj=self.workspace, comments_mode="hide", ads="1,2", all=False,
            matching="scam", all_comments=False, confirm="NOPE", dry_run=False,
        )
        with mock.patch.object(metaops, "run_child", side_effect=AssertionError("must not run")):
            with self.assertRaises(metaops.MetaOpsError):
                cmd_operate.command_comments(args, metaops)

    def test_comments_delete_requires_matching(self):
        args = make_args(
            workspace_obj=self.workspace, comments_mode="delete", ads="1,2", all=False,
            matching=None, all_comments=False, confirm="DELETE", dry_run=False,
        )
        with mock.patch.object(metaops, "run_child", side_effect=AssertionError("must not run")):
            with self.assertRaises(metaops.MetaOpsError):
                cmd_operate.command_comments(args, metaops)

    def test_comments_hide_accepts_literal_confirm_and_runs(self):
        args = make_args(
            workspace_obj=self.workspace, comments_mode="hide", ads="1,2", all=False,
            matching="scam", all_comments=False, confirm="HIDE", dry_run=False,
        )
        summary_line = json.dumps({"schema": "comments.result/v1", "mode": "hide",
                                   "posts_checked": 1, "acted": 2, "dry_run": False})

        def fake_run_child(script, child_args, timeout):
            self.assertEqual(script, "comments.py")
            self.assertIn("--hide-matching", child_args)
            return metaops.ChildResult(argv=[], returncode=0, stdout=summary_line, stderr="")

        with mock.patch.object(metaops, "run_child", side_effect=fake_run_child), \
             mock.patch.object(metaops, "echo_child", lambda c: None):
            code, payload = cmd_operate.command_comments(args, metaops)
        self.assertEqual(code, 0)
        self.assertEqual(payload["data"]["summary"]["acted"], 2)

    def test_page_set_requires_literal_confirm(self):
        args = make_args(
            workspace_obj=self.workspace, page_mode="set", page=None,
            avatar="a.jpg", cover=None, about=None, website=None, confirm="NOPE",
        )
        with mock.patch.object(metaops, "run_child", side_effect=AssertionError("must not run")):
            with self.assertRaises(metaops.MetaOpsError):
                cmd_operate.command_page(args, metaops)

    def test_page_set_requires_at_least_one_field(self):
        args = make_args(
            workspace_obj=self.workspace, page_mode="set", page=None,
            avatar=None, cover=None, about=None, website=None, confirm="PAGE",
            clear_website=False, remove_cover=False,
        )
        with mock.patch.object(metaops, "run_child", side_effect=AssertionError("must not run")):
            with self.assertRaises(metaops.MetaOpsError):
                cmd_operate.command_page(args, metaops)

    def test_page_set_clear_website_and_remove_cover_reach_the_child(self):
        args = make_args(
            workspace_obj=self.workspace, page_mode="set", page=None,
            avatar=None, cover=None, about=None, website=None, confirm="PAGE",
            clear_website=True, remove_cover=True,
        )
        with mock.patch.object(metaops, "run_child",
                               return_value=metaops.ChildResult(["page.py"], 0, "{}", "")) as child:
            code, _ = cmd_operate.command_page(args, metaops)
        self.assertEqual(code, 0)
        argv = child.call_args[0][1]
        self.assertIn("--clear-website", argv)
        self.assertIn("--remove-cover", argv)


class LeaderboardTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.root = pathlib.Path(self.td.name)
        self.workspace = FakeWorkspace(self.root, {"ad_account_id": "act_1", "page_id": "2"})

    def test_leaderboard_aggregates_by_ad_name_across_accounts(self):
        self.workspace.data["profiles"]["second"] = {"ad_account_id": "act_2"}
        fixtures = {
            "act_1": [
                {"ad_name": "creative_03_v1", "spend": "10.5", "impressions": "100", "clicks": "5",
                 "account_currency": "USD", "actions": [{"action_type": "lead", "value": "2"}]},
                {"ad_name": "creative_03_v2", "spend": "1.0", "impressions": "10", "clicks": "0",
                 "account_currency": "USD", "actions": []},
            ],
            "act_2": [
                {"ad_name": "creative_03_v1", "spend": "20.25", "impressions": "200", "clicks": "8",
                 "account_currency": "USD", "actions": [{"action_type": "lead", "value": "3"}]},
            ],
        }

        def fake_run_child(script, child_args, timeout):
            self.assertEqual(script, "insights.py")
            account = child_args[child_args.index("--account") + 1]
            json_path = pathlib.Path(child_args[child_args.index("--json") + 1])
            json_path.parent.mkdir(parents=True, exist_ok=True)
            json_path.write_text(json.dumps(fixtures[account]), encoding="utf-8")
            summary = json.dumps({"schema": "insights.result/v1", "account": account, "rows": len(fixtures[account])})
            return metaops.ChildResult(argv=[], returncode=0, stdout=summary, stderr="")

        accounts_path = self.root / "accounts.json"
        accounts_path.write_text(json.dumps([{"account_id": "act_1"}, {"account_id": "act_2"}]),
                                 encoding="utf-8")
        args = make_args(
            workspace_obj=self.workspace, accounts=str(accounts_path), date_preset="yesterday",
            csv=None, top=20, insights_mode="leaderboard",
        )
        with mock.patch.object(metaops, "run_child", side_effect=fake_run_child), \
             mock.patch.object(metaops, "echo_child", lambda c: None):
            code, payload = cmd_operate.command_insights(args, metaops)

        self.assertEqual(code, 0)
        board = payload["data"]["leaderboard"]
        self.assertEqual(board[0]["ad_name"], "creative_03_v1")
        self.assertAlmostEqual(board[0]["spend"], 30.75)
        self.assertEqual(board[0]["impressions"], 300)
        self.assertEqual(board[0]["clicks"], 13)
        self.assertEqual(board[0]["accounts"], ["act_1", "act_2"])
        self.assertAlmostEqual(board[0]["actions"]["lead"], 5.0)
        self.assertEqual(board[1]["ad_name"], "creative_03_v2")

    def test_leaderboard_refuses_to_sum_different_currencies(self):
        self.workspace.data["profiles"]["second"] = {"ad_account_id": "act_2"}
        fixtures = {
            "act_1": [{"ad_name": "creative", "spend": "10", "account_currency": "USD"}],
            "act_2": [{"ad_name": "creative", "spend": "10", "account_currency": "EUR"}],
        }

        def fake_run_child(script, child_args, timeout):
            account = child_args[child_args.index("--account") + 1]
            json_path = pathlib.Path(child_args[child_args.index("--json") + 1])
            json_path.write_text(json.dumps(fixtures[account]), encoding="utf-8")
            return metaops.ChildResult(argv=[], returncode=0, stdout="{}", stderr="")

        accounts_path = self.root / "accounts.json"
        accounts_path.write_text(json.dumps([{"account_id": "act_1"}, {"account_id": "act_2"}]), encoding="utf-8")
        args = make_args(
            workspace_obj=self.workspace, accounts=str(accounts_path), date_preset="yesterday",
            csv=None, top=20, insights_mode="leaderboard",
        )
        with mock.patch.object(metaops, "run_child", side_effect=fake_run_child), \
             mock.patch.object(metaops, "echo_child", lambda c: None):
            code, payload = cmd_operate.command_insights(args, metaops)
        self.assertEqual(code, 1)
        self.assertEqual(payload["phase"], "currency_mismatch")
        self.assertEqual(payload["data"]["currencies"], ["EUR", "USD"])

    def test_leaderboard_rejects_an_undeclared_account_before_reads(self):
        args = make_args(
            workspace_obj=self.workspace, accounts="act_99", date_preset="yesterday",
            csv=None, top=20, insights_mode="leaderboard",
        )
        with mock.patch.object(metaops, "run_child") as child:
            with self.assertRaisesRegex(metaops.MetaOpsError, "not declared"):
                cmd_operate.command_insights(args, metaops)
        child.assert_not_called()




class FatigueTests(unittest.TestCase):
    @staticmethod
    def rows(ad, adset, days, spend, impr, clicks, reach, leads=0):
        # `reach` is kept per-row only so a test written against the OLD (buggy, summing)
        # behavior would visibly disagree; fatigue_verdicts must never read reach off these
        # daily ad-level rows (meta-ads/12 §5: never sum reach).
        return [{"date_start": f"2026-08-{d:02d}", "ad_id": ad, "ad_name": f"c_{ad}", "adset_id": adset,
                 "spend": spend, "impressions": impr, "clicks": clicks, "reach": reach,
                 "actions": [{"action_type": "lead", "value": leads}]} for d in days]

    @staticmethod
    def adset_row(adset, spend, impr, reach):
        return {"adset_id": adset, "spend": spend, "impressions": impr, "reach": reach}

    def test_watch_needs_two_of_three_without_adset_halves(self):
        # No adset_halves supplied → frequency_up can never be true (reach is not summed from
        # daily rows), so at most 2 of 3 signals fire and ROTATE-CANDIDATE is unreachable here.
        import cmd_operate
        base = self.rows("a1", "s1", range(1, 8), 10, 500, 25, 400, 2)
        recent = self.rows("a1", "s1", range(8, 15), 10, 500, 15, 250, 1)   # ctr down, cpc/cpa up
        v = cmd_operate.fatigue_verdicts(base + recent, min_spend=20, event="lead")
        self.assertEqual(v[0]["verdict"], "WATCH")
        self.assertEqual(set(v[0]["signals"]), {"ctr_down", "cost_up"})
        self.assertNotIn("frequency", v[0]["baseline"])
        self.assertNotIn("reach", v[0]["baseline"])

    def test_ok_on_no_signals(self):
        import cmd_operate
        steady = self.rows("a2", "s2", range(1, 15), 10, 500, 25, 400)
        self.assertEqual(cmd_operate.fatigue_verdicts(steady)[0]["verdict"], "OK")

    def test_no_data_on_thin_recent_half(self):
        import cmd_operate
        thin = self.rows("a1", "s1", range(1, 8), 10, 500, 25, 400) + self.rows("a1", "s1", range(8, 15), 1, 50, 2, 40)
        self.assertEqual(cmd_operate.fatigue_verdicts(thin)[0]["verdict"], "NO-DATA")

    def test_adset_halves_drive_saturation_and_frequency_and_rotate_candidate(self):
        # adset_halves rows are the ad-set-level, time_increment=all_days pulls: one row per
        # half, reach already deduplicated by Graph over that half's date range.
        import cmd_operate
        base = self.rows("a1", "s1", range(1, 8), 10, 500, 25, 400, 2)      # ctr 5%, cpa 5
        recent = self.rows("a1", "s1", range(8, 15), 10, 500, 15, 250, 1)   # ctr 3%, cpa 10
        adset_halves = {
            "s1": {
                "baseline": self.adset_row("s1", 70, 3500, 2800),   # freq 1.25
                "recent": self.adset_row("s1", 70, 3500, 1750),     # freq 2.0, spend flat, reach -37.5%
            }
        }
        v = cmd_operate.fatigue_verdicts(base + recent, min_spend=20, event="lead", adset_halves=adset_halves)
        self.assertEqual(v[0]["verdict"], "ROTATE-CANDIDATE")
        self.assertEqual(set(v[0]["signals"]), {"frequency_up", "ctr_down", "cost_up"})
        self.assertIn("POSSIBLE-SATURATION", v[0]["flags"])
        self.assertAlmostEqual(v[0]["baseline"]["frequency"], 1.25)
        self.assertAlmostEqual(v[0]["recent"]["frequency"], 2.0)

    def test_adset_halves_missing_for_adset_means_no_flag_or_frequency_signal(self):
        import cmd_operate
        base = self.rows("a1", "s1", range(1, 8), 10, 500, 25, 400, 2)
        recent = self.rows("a1", "s1", range(8, 15), 10, 500, 15, 250, 1)
        v = cmd_operate.fatigue_verdicts(base + recent, min_spend=20, event="lead", adset_halves={})
        self.assertNotIn("POSSIBLE-SATURATION", v[0]["flags"])
        self.assertNotIn("frequency", v[0]["baseline"])


class FatiguePullTests(unittest.TestCase):
    """_insights_fatigue must issue one ad-set pull PER HALF; a single whole-window pull
    with time_increment=all_days yields one row per ad set, leaving `recent` empty and
    silently disabling frequency and saturation."""

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.root = pathlib.Path(self.td.name)
        self.workspace = FakeWorkspace(self.root, {"ad_account_id": "act_1"})

    def _run(self, days=14):
        calls = []

        def fake_run_child(script, child_args, timeout):
            level = child_args[child_args.index("--level") + 1]
            since = child_args[child_args.index("--since") + 1]
            until = child_args[child_args.index("--until") + 1]
            calls.append((level, since, until,
                          child_args[child_args.index("--time-increment") + 1]
                          if "--time-increment" in child_args else None))
            json_path = pathlib.Path(child_args[child_args.index("--json") + 1])
            json_path.parent.mkdir(parents=True, exist_ok=True)
            if level == "ad":
                rows = FatigueTests.rows("a1", "s1", range(1, 8), 10, 500, 25, 400, 2) + \
                    FatigueTests.rows("a1", "s1", range(8, 15), 10, 500, 15, 250, 1)
            else:
                reach = 400 if since < until and calls[-1][1] == since and len(calls) == 2 else 250
                rows = [{"date_start": since, "date_stop": until, "adset_id": "s1",
                         "spend": 70, "impressions": 3500, "reach": reach}]
            json_path.write_text(json.dumps(rows), encoding="utf-8")
            return metaops.ChildResult(argv=[], returncode=0, stdout="{}", stderr="")

        args = make_args(workspace_obj=self.workspace, days=days, min_spend=20, event="lead",
                         top=20, insights_mode="fatigue")
        with mock.patch.object(metaops, "run_child", side_effect=fake_run_child), \
             mock.patch.object(metaops, "echo_child", lambda c: None):
            code, payload = cmd_operate.command_insights(args, metaops)
        return code, payload, calls

    def test_adset_pull_is_split_into_two_half_ranges(self):
        code, payload, calls = self._run()
        self.assertEqual(code, 0)
        adset_calls = [c for c in calls if c[0] == "adset"]
        self.assertEqual(len(adset_calls), 2, "one ad-set pull per half, not one over the window")
        self.assertTrue(all(c[3] == "all_days" for c in adset_calls))
        # The two ranges must be disjoint and cover baseline then recent.
        self.assertEqual(adset_calls[0][1], payload["data"]["baseline_range"][0])
        self.assertEqual(adset_calls[0][2], payload["data"]["baseline_range"][1])
        self.assertEqual(adset_calls[1][1], payload["data"]["recent_range"][0])
        self.assertEqual(adset_calls[1][2], payload["data"]["recent_range"][1])
        self.assertLess(adset_calls[0][2], adset_calls[1][1])
        self.assertTrue(payload["data"]["adset_saturation_available"])

    def test_halves_follow_delivery_days_not_the_calendar_midpoint(self):
        """Delivery only in the last 8 days of a 14-day window: the ad-set pulls must be cut
        on the same day as the ad-level halves, or reach/frequency get compared across a
        different period than CTR/CPA."""
        calls = []
        days = list(range(7, 15))  # 2026-08-07 .. 2026-08-14, nothing before

        def fake_run_child(script, child_args, timeout):
            level = child_args[child_args.index("--level") + 1]
            since = child_args[child_args.index("--since") + 1]
            until = child_args[child_args.index("--until") + 1]
            calls.append((level, since, until))
            json_path = pathlib.Path(child_args[child_args.index("--json") + 1])
            json_path.parent.mkdir(parents=True, exist_ok=True)
            if level == "ad":
                rows = FatigueTests.rows("a1", "s1", days, 10, 500, 25, 400, 2)
            else:
                rows = [{"date_start": since, "adset_id": "s1", "spend": 40,
                         "impressions": 2000, "reach": 300}]
            json_path.write_text(json.dumps(rows), encoding="utf-8")
            return metaops.ChildResult(argv=[], returncode=0, stdout="{}", stderr="")

        args = make_args(workspace_obj=self.workspace, days=14, min_spend=20, event="lead",
                         top=20, insights_mode="fatigue")
        with mock.patch.object(metaops, "run_child", side_effect=fake_run_child), \
             mock.patch.object(metaops, "echo_child", lambda c: None):
            code, payload = cmd_operate.command_insights(args, metaops)

        self.assertEqual(code, 0)
        adset_calls = [c for c in calls if c[0] == "adset"]
        self.assertEqual(len(adset_calls), 2)
        # 8 delivery days -> cut at dates[4] = 2026-08-11, NOT the calendar midpoint.
        self.assertEqual(adset_calls[1][1], "2026-08-11")
        self.assertEqual(adset_calls[0][2], "2026-08-10")
        self.assertEqual(payload["data"]["recent_range"][0], "2026-08-11")

    def test_a_half_that_failed_to_pull_disables_saturation(self):
        def fake_run_child(script, child_args, timeout):
            level = child_args[child_args.index("--level") + 1]
            json_path = pathlib.Path(child_args[child_args.index("--json") + 1])
            json_path.parent.mkdir(parents=True, exist_ok=True)
            if level == "adset":
                return metaops.ChildResult(argv=[], returncode=1, stdout="", stderr="boom")
            json_path.write_text(json.dumps(
                FatigueTests.rows("a1", "s1", range(1, 8), 10, 500, 25, 400, 2) +
                FatigueTests.rows("a1", "s1", range(8, 15), 10, 500, 15, 250, 1)), encoding="utf-8")
            return metaops.ChildResult(argv=[], returncode=0, stdout="{}", stderr="")

        args = make_args(workspace_obj=self.workspace, days=14, min_spend=20, event="lead",
                         top=20, insights_mode="fatigue")
        with mock.patch.object(metaops, "run_child", side_effect=fake_run_child), \
             mock.patch.object(metaops, "echo_child", lambda c: None):
            code, payload = cmd_operate.command_insights(args, metaops)
        self.assertEqual(code, 0)
        self.assertFalse(payload["data"]["adset_saturation_available"])
        self.assertNotIn("POSSIBLE-SATURATION", payload["data"]["ads"][0]["flags"])


if __name__ == "__main__":
    unittest.main()

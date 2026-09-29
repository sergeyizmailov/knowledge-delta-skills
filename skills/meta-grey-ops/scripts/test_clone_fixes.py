#!/usr/bin/env python3
"""Regression tests for clone.py: rejected ads are never copied, and campaign copies are
paced exactly like launch.py creates. Offline; every test fails on the pre-fix code."""

from __future__ import annotations
import os as _os, tempfile as _tempfile
_os.environ["METAOPS_PACE_DIR"] = _tempfile.mkdtemp(prefix="metaops-pace-test-")
_os.environ.setdefault("METAOPS_CREATE_GAP_HOURS", "0")

import contextlib
import io
import json
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("META_TOKEN", "TEST_TOKEN")

import clone  # noqa: E402
import graph  # noqa: E402

START = "2030-01-01T08:00:00+00:00"


def ad(ad_id: str, effective: str = "ACTIVE", status: str = "ACTIVE", name: str | None = None) -> dict:
    return {"id": ad_id, "name": name or f"ad {ad_id}", "status": status, "effective_status": effective}


class CloneFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        env = mock.patch.dict(os.environ, {
            "METAOPS_PACE_DIR": str(self.root / "pace"),
            "METAOPS_CREATE_GAP_HOURS": "3",
            "METAOPS_PACE_OVERRIDE": "",
        })
        env.start()
        self.addCleanup(env.stop)
        self.copies: list[tuple[str, str]] = []

    def copy_obj(self, obj_id, payload, dry, label):
        self.copies.append((label, obj_id))
        return None if dry else f"new-{obj_id}"

    def run_clone(self, argv, adsets=None, ads=None, source=None, node=None):
        """Run clone.main() with Graph reads and /copies mocked. Returns (exit code, result JSON)."""
        adsets = adsets if adsets is not None else [{"id": "as1", "name": "Set", "status": "PAUSED",
                                                     "effective_status": "PAUSED"}]
        ads = ads if ads is not None else [ad("a1")]

        def children(edge, obj_id, account=None):
            return list(adsets if edge == "adsets" else ads)

        out = io.StringIO()
        with (
            mock.patch.object(sys, "argv", ["clone.py", *argv]),
            mock.patch.object(clone, "require_expected_account", return_value=source),
            mock.patch.object(clone, "copy_obj", side_effect=self.copy_obj),
            mock.patch.object(clone, "children", side_effect=children),
            mock.patch.object(clone.graph, "get", return_value=node or {}) as get,
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            code = clone.main()
        self.get = get
        return code, json.loads(out.getvalue().strip().splitlines()[-1])

    def copied(self, label: str) -> list[str]:
        return [obj_id for kind, obj_id in self.copies if kind == label]


class RejectedAdTests(CloneFixture):
    def test_copyable_skips_disapproved_and_with_issues_ads(self) -> None:
        rows = [ad("ok"), ad("paused", "PAUSED", "PAUSED"), ad("bad", "DISAPPROVED"),
                ad("issues", "WITH_ISSUES"), ad("lower", "disapproved")]
        self.assertEqual([row["id"] for row in clone.copyable(rows, "ad")], ["ok", "paused"])

    def test_the_rule_is_about_ads_not_adsets_or_campaigns(self) -> None:
        rows = [{"id": "s1", "effective_status": "WITH_ISSUES", "status": "ACTIVE"}]
        self.assertEqual(clone.copyable(rows, "adset"), rows)
        self.assertEqual(clone.copyable(rows, "campaign"), rows)

    def test_split_copyable_reports_kind_id_name_and_reason(self) -> None:
        keep, skipped = clone.split_copyable(
            [ad("ok"), ad("bad", "DISAPPROVED", name="Rejected creative"), ad("del", "ACTIVE", "DELETED")],
            "ad")
        self.assertEqual([row["id"] for row in keep], ["ok"])
        self.assertEqual(skipped, [
            {"kind": "ad", "id": "bad", "name": "Rejected creative", "reason": "DISAPPROVED"},
            {"kind": "ad", "id": "del", "name": "ad del", "reason": "DELETED"},
        ])

    def test_campaign_clone_copies_clean_ads_and_lists_the_skipped_ones(self) -> None:
        code, result = self.run_clone(
            ["campaign", "111", "--expected-account", "act_1", "--start", START],
            ads=[ad("ok"), ad("bad", "DISAPPROVED"), ad("issues", "WITH_ISSUES")])
        self.assertEqual(code, 0)
        self.assertEqual(self.copied("ad"), ["ok"])
        self.assertEqual([(s["id"], s["reason"]) for s in result["skipped"]],
                         [("bad", "DISAPPROVED"), ("issues", "WITH_ISSUES")])
        self.assertEqual(result["results"][0]["ads"], ["new-ok"])
        # skipped ads are report rows, never "created ids" (they drive in_flight reconciliation)
        self.assertNotIn("bad", clone.created_ids(result["results"][0]))

    def test_adset_clone_skips_rejected_ads(self) -> None:
        code, result = self.run_clone(
            ["adset", "555", "--expected-account", "act_1"],
            ads=[ad("bad", "DISAPPROVED"), ad("ok")])
        self.assertEqual(code, 0)
        self.assertEqual(self.copied("ad"), ["ok"])
        self.assertEqual([s["id"] for s in result["skipped"]], ["bad"])

    def test_skipped_report_is_kept_in_the_resume_state(self) -> None:
        state = self.root / "clone-state.json"
        self.run_clone(["campaign", "111", "--expected-account", "act_1", "--state", str(state),
                        "--start", START], ads=[ad("bad", "DISAPPROVED"), ad("ok")])
        saved = clone.load_clone_state(str(state))
        self.assertEqual([s["id"] for s in saved["completed"]["1"]["skipped"]], ["bad"])
        self.assertEqual(saved["in_flight"], {})

    def test_clone_ad_refuses_a_disapproved_or_with_issues_source(self) -> None:
        for effective in ("DISAPPROVED", "WITH_ISSUES"):
            with self.subTest(effective=effective):
                self.copies.clear()
                code, result = self.run_clone(
                    ["ad", "42", "--expected-account", "act_1"],
                    source={"id": "42", "account_id": "1", "name": "Bad", "status": "ACTIVE",
                            "effective_status": effective})
                self.assertEqual(code, 1)
                self.assertFalse(result["ok"])
                self.assertEqual(self.copies, [])
                self.assertEqual(result["skipped"], [
                    {"kind": "ad", "id": "42", "name": "Bad", "reason": effective}])

    def test_clone_ad_reads_the_status_itself_without_an_account_binding(self) -> None:
        code, result = self.run_clone(
            ["ad", "42"], node={"id": "42", "name": "Bad", "status": "ACTIVE",
                                "effective_status": "DISAPPROVED"})
        self.assertEqual(code, 1)
        self.assertEqual(self.copies, [])
        self.assertEqual(result["skipped"][0]["reason"], "DISAPPROVED")
        self.assertIn("effective_status", self.get.call_args.kwargs["params"]["fields"])

    def test_clone_ad_copies_a_clean_source(self) -> None:
        code, result = self.run_clone(
            ["ad", "42", "--expected-account", "act_1"],
            source={"id": "42", "account_id": "1", "status": "PAUSED", "effective_status": "PAUSED"})
        self.assertEqual(code, 0)
        self.assertEqual(self.copied("ad"), ["42"])
        self.assertEqual(result["skipped"], [])


class CampaignPacingTests(CloneFixture):
    def argv(self, *extra, times=2):
        return ["campaign", "111", "--times", str(times), "--expected-account", "act_1",
                "--start", START, *extra]

    def test_second_campaign_copy_is_blocked_by_the_create_gap(self) -> None:
        state = self.root / "clone-state.json"
        code, result = self.run_clone(self.argv("--state", str(state)))
        self.assertEqual(code, 1)
        self.assertEqual(self.copied("campaign"), ["111"], "copy 2 must not be created")
        self.assertFalse(result["ok"])
        self.assertTrue(result["stopped"].startswith("pacing:"), result)
        saved = clone.load_clone_state(str(state))
        self.assertIn("1", saved["completed"])
        self.assertNotIn("2", saved["in_flight"], "a pacing refusal leaves nothing to reconcile")
        self.assertIn("act_1", graph._pace_load()["last_campaign_create"])

    def test_pace_override_lets_every_copy_through(self) -> None:
        with mock.patch.dict(os.environ, {"METAOPS_PACE_OVERRIDE": "1"}):
            code, result = self.run_clone(self.argv())
        self.assertEqual(code, 0)
        self.assertEqual(self.copied("campaign"), ["111", "111"])
        self.assertNotIn("stopped", result)

    def test_a_recent_create_on_the_account_blocks_the_first_copy(self) -> None:
        graph.record_campaign_create("act_1")
        state = self.root / "clone-state.json"
        code, result = self.run_clone(self.argv("--state", str(state), times=1))
        self.assertEqual(code, 1)
        self.assertEqual(self.copies, [])
        self.assertIn("pacing", result["stopped"])
        self.assertEqual(clone.load_clone_state(str(state))["in_flight"], {})

    def test_other_accounts_are_not_blocked(self) -> None:
        graph.record_campaign_create("act_2")
        code, _ = self.run_clone(self.argv(times=1))
        self.assertEqual(code, 0)
        self.assertEqual(self.copied("campaign"), ["111"])

    def test_dry_run_neither_checks_nor_records(self) -> None:
        graph.record_campaign_create("act_1")
        before = graph._pace_load()["last_campaign_create"]["act_1"]
        code, _ = self.run_clone(self.argv("--dry-run"))
        self.assertEqual(code, 0)
        self.assertEqual(graph._pace_load()["last_campaign_create"]["act_1"], before)

    def test_adset_and_ad_clones_are_not_campaign_paced(self) -> None:
        graph.record_campaign_create("act_1")
        code, _ = self.run_clone(["adset", "555", "--times", "2", "--expected-account", "act_1"])
        self.assertEqual(code, 0)
        code, _ = self.run_clone(
            ["ad", "42", "--times", "2", "--expected-account", "act_1"],
            source={"id": "42", "account_id": "1", "effective_status": "PAUSED", "status": "PAUSED"})
        self.assertEqual(code, 0)

    def test_check_before_and_record_after_each_campaign_copy_like_launch(self) -> None:
        order: list[str] = []
        with (
            mock.patch.dict(os.environ, {"METAOPS_PACE_OVERRIDE": "1"}),
            mock.patch.object(graph, "check_campaign_create_pace",
                              side_effect=lambda account: order.append(f"check {account}")),
            mock.patch.object(graph, "record_campaign_create",
                              side_effect=lambda account: order.append(f"record {account}")),
        ):
            orig = self.copy_obj

            def spy(obj_id, payload, dry, label):
                order.append(f"copy {label}")
                return orig(obj_id, payload, dry, label)

            self.copy_obj = spy
            self.run_clone(self.argv(times=2), adsets=[], ads=[])
        self.assertEqual(order, ["check act_1", "copy campaign", "record act_1",
                                 "check act_1", "copy campaign", "record act_1"])

    def test_account_falls_back_to_the_source_campaigns_own_account(self) -> None:
        code, _ = self.run_clone(
            ["campaign", "111", "--times", "1", "--start", START],
            source=None, node={"id": "111", "account_id": "777"})
        self.assertEqual(code, 0)
        self.assertIn("act_777", graph._pace_load()["last_campaign_create"])
        self.assertEqual(self.get.call_args.kwargs["params"], {"fields": "id,account_id"})


if __name__ == "__main__":
    unittest.main()


class ChildrenUnionsTheAccountEdge(unittest.TestCase):
    """Field 2026-09-29 on CF1: `{adset}/ads` answered empty while `act_ID/ads` listed the ad. A clone that
    trusted the per-parent edge copied ad sets without ads."""

    def test_missing_children_come_from_the_account_edge(self) -> None:
        calls = []

        def fake_get(path, params=None, context=""):
            calls.append((path, dict(params or {})))
            if path == "999/ads":
                return {"data": []}
            return {"data": [{"id": "7", "name": "EN0037", "effective_status": "ACTIVE"}]}

        with mock.patch.object(clone.graph, "get", side_effect=fake_get), contextlib.redirect_stderr(io.StringIO()) as err:
            rows = clone.children("ads", "999", "act_5")
        self.assertEqual([r["id"] for r in rows], ["7"])
        self.assertEqual(calls[1][0], "act_5/ads")
        self.assertIn('"adset.id"', calls[1][1]["filtering"])
        self.assertIn("per-parent edge is unreliable", err.getvalue())

    def test_no_duplicates_when_both_edges_agree(self) -> None:
        row = {"id": "7", "name": "x", "effective_status": "ACTIVE"}
        with mock.patch.object(clone.graph, "get", return_value={"data": [row]}):
            self.assertEqual(len(clone.children("ads", "999", "act_5")), 1)

    def test_without_account_only_the_parent_edge_is_read(self) -> None:
        with mock.patch.object(clone.graph, "get", return_value={"data": []}) as get:
            clone.children("ads", "999")
        self.assertEqual(get.call_count, 1)

#!/usr/bin/env python3
"""Offline tests for the four read-only inspection features:

    review --tree            (cmd_operate.py flags, cmd_inspect.py logic)
    insights pull            (--breakdown / --time-increment / windows / --fields)
    activity                 (cmd_inspect.py)
    images list              (cmd_inspect.py)

No network, no credentials: `graph.get` (or the requests session under it) is mocked.
"""

from __future__ import annotations

import os as _os
import tempfile as _tempfile

_os.environ["METAOPS_PACE_DIR"] = _tempfile.mkdtemp(prefix="metaops-pace-test-")
_os.environ.setdefault("METAOPS_CREATE_GAP_HOURS", "0")

import argparse
import ast
import contextlib
import io
import json
import os
import pathlib
import re
import tempfile
import types
import unittest
from unittest import mock

os.environ.setdefault("META_TOKEN", "TEST_TOKEN")

import cmd_inspect  # noqa: E402
import cmd_operate  # noqa: E402
import graph  # noqa: E402
import insights  # noqa: E402
import metaops  # noqa: E402

REDUCE = {"error": {
    "message": "Please reduce the amount of data you're asking for, then retry your request",
    "code": 1,
}}


def gerr(payload: dict, status: int = 400) -> graph.GraphError:
    return graph.GraphError(status, payload, "test")


class FakeWorkspace:
    def __init__(self, state_root: pathlib.Path, account: str = "act_1"):
        self._state_root = state_root
        self._profile = {"ad_account_id": account, "page_id": "2", "dataset_id": "3"}
        self.data = {"profiles": {"test": dict(self._profile)}}

    @property
    def state_root(self) -> pathlib.Path:
        return self._state_root

    def profile(self, requested=None):
        return "test", dict(self._profile)


class Base(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.ws = FakeWorkspace(pathlib.Path(self.td.name))
        for patcher in (mock.patch.object(cmd_inspect, "PAGE_PAUSE", 0),
                        mock.patch.object(cmd_inspect, "_warn"),
                        mock.patch.object(insights.time, "sleep")):
            patcher.start()
            self.addCleanup(patcher.stop)

    def args(self, **kw):
        base = {"workspace_obj": self.ws, "profile": None, "json": True, "timeout": 30}
        base.update(kw)
        return types.SimpleNamespace(**base)

    def run_text(self, fn, *a, **kw):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = fn(*a, **kw)
        return result, buf.getvalue()


class Router:
    """graph.get stand-in: `routes` maps a path to a dict, or a callable(params) -> dict or raising."""

    def __init__(self, routes: dict):
        self.routes = routes
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, path, params=None, context=""):
        self.calls.append((path, dict(params or {})))
        route = self.routes[path]
        return route(dict(params or {})) if callable(route) else route

    def to(self, path):
        return [p for pth, p in self.calls if pth == path]


# ------------------------------------------------------------------------------ fixtures


def ad(ad_id, name="ad", eff="ACTIVE", feedback=None, issues=None, adset_id="21", campaign_id="11"):
    return {"id": ad_id, "name": name, "adset_id": adset_id, "campaign_id": campaign_id,
            "status": "ACTIVE", "effective_status": eff,
            "configured_status": "ACTIVE", "issues_info": issues, "ad_review_feedback": feedback,
            "creative": {"id": f"cr{ad_id}", "name": f"creative {ad_id}"},
            "updated_time": "2026-09-29T10:00:00+0000"}


def adset(set_id, name="set", eff="ACTIVE", campaign_id="11", **kw):
    row = {
        "id": set_id, "name": name, "campaign_id": campaign_id, "status": "ACTIVE",
        "effective_status": eff,
        "configured_status": "ACTIVE", "daily_budget": "2000", "bid_amount": "500",
        "bid_strategy": "LOWEST_COST_WITH_BID_CAP", "optimization_goal": "OFFSITE_CONVERSIONS",
        "billing_event": "IMPRESSIONS", "start_time": "2026-09-29T07:00:00+0300",
        "learning_stage_info": {"status": "LEARNING", "conversions": 3},
        "attribution_spec": [{"event_type": "CLICK_THROUGH", "window_days": 7},
                             {"event_type": "VIEW_THROUGH", "window_days": 1}],
        "targeting": {
            "geo_locations": {"countries": ["US"], "regions": [{"key": "3879", "name": "Oklahoma"}],
                              "location_types": ["home", "recent"]},
            "age_min": 21, "age_max": 65, "genders": [1],
            "publisher_platforms": ["facebook", "instagram"],
            "facebook_positions": ["feed"], "instagram_positions": ["stream", "reels"],
            "device_platforms": ["mobile"], "targeting_automation": {"advantage_audience": 0},
        },
    }
    row.update(kw)
    return row


def campaign(cid, name="camp", **kw):
    row = {"id": cid, "name": name, "status": "ACTIVE", "effective_status": "ACTIVE",
           "configured_status": "ACTIVE", "daily_budget": "5000", "bid_strategy": "LOWEST_COST_WITH_BID_CAP",
           "objective": "OUTCOME_SALES"}
    row.update(kw)
    return row


def flat_routes(camps, adsets, ads, currency="USD"):
    """The three flat edges the tree reads. Each value is a dict or a callable(params)."""
    return {"act_1": {"currency": currency, "id": "act_1"},
            "act_1/campaigns": {"data": camps},
            "act_1/adsets": {"data": adsets},
            "act_1/ads": {"data": ads}}


def five_ads():
    """The CF1 shape: one campaign, five ad sets, one ACTIVE ad each."""
    sets = [adset(str(20 + i), name=f"AS{i}") for i in range(1, 6)]
    ads = [ad(str(30 + i), f"ad {i}", adset_id=str(20 + i)) for i in range(1, 6)]
    return [campaign("11", name="CF1 longread 1-5-1")], sets, ads


def cursor_pages(pages):
    """callable(params) serving `pages` (a list of row lists) linked by cursors P1, P2, ..."""
    def serve(params):
        index = int((params.get("after") or "P0")[1:])
        body = {"data": pages[index]}
        if index + 1 < len(pages):
            body["paging"] = {"cursors": {"after": f"P{index + 1}"}, "next": "https://graph.facebook.com/x"}
        return body
    return serve


# ------------------------------------------------------------------------------ review --tree


class ReviewTreeTests(Base):
    def make_flat(self):
        camps = [campaign("11")]
        sets = [adset("21"), adset("22", name="empty set", attribution_spec=None)]
        ads = [ad("31", "good"),
               ad("32", "bad", eff="DISAPPROVED", feedback={"global": {"1": "Spam"}}),
               ad("33", "issue", eff="WITH_ISSUES", issues=[{"error_code": 1}])]
        return flat_routes(camps, sets, ads)

    def run_tree(self, routes, **kw):
        router = Router(routes)
        args = self.args(campaign=None, statuses=None, **kw)
        with mock.patch.object(metaops.graph, "get", side_effect=router):
            return router, cmd_inspect.command_review_tree(args, metaops)

    def test_tree_shape_money_and_exit_code(self):
        _, (code, payload) = self.run_tree(self.make_flat())
        self.assertEqual(code, 1)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["kind"], "ad_review")
        data = payload["data"]
        self.assertTrue(data["complete"])
        self.assertEqual(data["counts"], {"campaigns": 1, "adsets": 2, "ads": 3,
                                          "unattached_adsets": 0, "unattached_ads": 0})
        self.assertEqual(data["loaded"], {"campaigns": 1, "adsets": 2, "ads": 3})
        self.assertEqual(data["blocking"], 2)
        self.assertEqual(data["summary"], {"ACTIVE": 1, "DISAPPROVED": 1, "WITH_ISSUES": 1})
        self.assertEqual({f["id"] for f in data["flagged_ads"]}, {"32", "33"})
        camp = data["tree"][0]
        # money stays in minor units, as ints, in JSON
        self.assertEqual(camp["daily_budget"], 5000)
        self.assertEqual(camp["adsets"][0]["daily_budget"], 2000)
        self.assertEqual(camp["adsets"][0]["bid_amount"], 500)
        self.assertEqual(data["currency"], "USD")
        self.assertEqual(data["currency_offset"], 100)
        aset = camp["adsets"][0]
        self.assertEqual(aset["learning_stage_info"]["status"], "LEARNING")
        self.assertEqual(aset["attribution_spec"],
                         [{"event_type": "CLICK_THROUGH", "window_days": 7},
                          {"event_type": "VIEW_THROUGH", "window_days": 1}])
        self.assertIsNone(data["tree"][0]["adsets"][1]["attribution_spec"])
        self.assertEqual(aset["targeting"]["regions"], ["Oklahoma"])
        self.assertEqual(aset["targeting"]["countries"], ["US"])
        self.assertEqual((aset["targeting"]["age_min"], aset["targeting"]["age_max"]), (21, 65))
        self.assertEqual(aset["targeting"]["genders"], [1])
        self.assertEqual(aset["targeting"]["publisher_platforms"], ["facebook", "instagram"])
        self.assertEqual(aset["targeting"]["positions"],
                         {"facebook_positions": ["feed"], "instagram_positions": ["stream", "reels"]})
        self.assertEqual(aset["targeting"]["device_platforms"], ["mobile"])
        self.assertEqual(aset["targeting"]["advantage_audience"], 0)
        bad = aset["ads"][1]
        self.assertEqual(bad["creative"], {"id": "cr32", "name": "creative 32"})
        self.assertEqual((bad["adset_id"], bad["campaign_id"]), ("21", "11"))
        self.assertTrue(bad["flags"]["blocking"] and bad["flags"]["feedback"])

    def test_requests_are_three_flat_edges_never_nested(self):
        router, _ = self.run_tree(self.make_flat())
        self.assertEqual([p for p, _ in router.calls],
                         ["act_1", "act_1/campaigns", "act_1/adsets", "act_1/ads"])
        self.assertEqual(router.to("act_1"), [{"fields": "currency"}])
        for path in ("act_1/campaigns", "act_1/adsets", "act_1/ads"):
            (params,) = router.to(path)
            # no parent{child{...}} expansion: only the ad's own creative{id,name} is nested
            self.assertIsNone(re.search(r"\b(campaigns|adsets|ads)\s*[.{(]", params["fields"]), path)
            self.assertNotIn("DELETED", params["effective_status"])
            self.assertIn("ARCHIVED", params["effective_status"])
        self.assertEqual(router.to("act_1/campaigns")[0]["limit"], 100)
        self.assertEqual(router.to("act_1/adsets")[0]["limit"], 50)
        self.assertEqual(router.to("act_1/ads")[0]["limit"], 100)
        self.assertIn("campaign_id", router.to("act_1/adsets")[0]["fields"].split(","))
        ad_fields = router.to("act_1/ads")[0]["fields"]
        for needed in ("adset_id", "campaign_id", "issues_info", "ad_review_feedback",
                       "creative{id,name}", "updated_time", "configured_status"):
            self.assertIn(needed, ad_fields)
        for needed in ("daily_budget", "lifetime_budget", "bid_amount", "bid_strategy",
                       "optimization_goal", "billing_event", "start_time", "end_time",
                       "learning_stage_info", "attribution_spec", "targeting"):
            self.assertIn(needed, router.to("act_1/adsets")[0]["fields"])
        for needed in ("daily_budget", "lifetime_budget", "bid_strategy", "objective"):
            self.assertIn(needed, router.to("act_1/campaigns")[0]["fields"])

    def test_regression_empty_nested_ads_do_not_empty_the_tree(self):
        """CF1 2026-09-29: nested adsets{ads{}} came back empty for 4 of 5 ad sets whose ads were
        all ACTIVE. A Graph that still answers that way must not matter: ads come from /ads."""
        camps, sets, ads = five_ads()
        camps[0]["adsets"] = {"data": [dict(sets[0], ads={"data": [ads[0]]})] +
                              [dict(s, ads={"data": []}) for s in sets[1:]]}     # the broken answer
        for s in sets:
            s["ads"] = {"data": []}
        router, (code, payload) = self.run_tree(flat_routes(camps, sets, ads))
        data = payload["data"]
        self.assertEqual(code, 0)
        self.assertEqual(data["counts"]["ads"], 5)
        self.assertEqual(data["summary"], {"ACTIVE": 5})
        self.assertEqual([len(s["ads"]) for s in data["tree"][0]["adsets"]], [1, 1, 1, 1, 1])
        self.assertEqual(data["warnings"], [])
        with mock.patch.object(metaops.graph, "get", side_effect=Router(flat_routes(camps, sets, ads))):
            (_, _), text = self.run_text(cmd_inspect.command_review_tree,
                                         self.args(json=False, campaign=None, statuses=None), metaops)
        self.assertNotIn("(no ads)", text)
        self.assertEqual(len([ln for ln in text.splitlines() if ln.startswith("    A ")]), 5)
        self.assertIn("1 campaigns, 5 ad sets, 5 ads", text.splitlines()[0])
        self.assertIn("No DISAPPROVED/WITH_ISSUES ad among the 5 ad(s) loaded", payload["next_action"])

    def test_every_edge_is_paged_on_its_own_cursor(self):
        camps = cursor_pages([[campaign("11")], [campaign("12")]])
        sets = cursor_pages([[adset("21")], [adset("22", campaign_id="12")]])
        ads = cursor_pages([[ad("31")], [ad("32", adset_id="22", campaign_id="12")], [ad("33")]])
        routes = {"act_1": {"currency": "USD"}, "act_1/campaigns": camps, "act_1/adsets": sets,
                  "act_1/ads": ads}
        router, (code, payload) = self.run_tree(routes)
        data = payload["data"]
        self.assertEqual(code, 0)
        self.assertTrue(data["complete"])
        self.assertEqual(data["counts"]["campaigns"], 2)
        self.assertEqual([[a["id"] for s in c["adsets"] for a in s["ads"]] for c in data["tree"]],
                         [["31", "33"], ["32"]])
        self.assertEqual([p.get("after") for p in router.to("act_1/ads")], [None, "P1", "P2"])
        self.assertEqual([p.get("after") for p in router.to("act_1/campaigns")], [None, "P1"])

    def test_duplicate_rows_from_overlapping_pages_are_counted_once(self):
        routes = flat_routes([campaign("11")], [adset("21")], [ad("31"), ad("31")])
        _, (_, payload) = self.run_tree(routes)
        self.assertEqual(payload["data"]["counts"]["ads"], 1)

    def test_orphans_are_shown_under_unattached_not_dropped(self):
        camps = [campaign("11")]
        sets = [adset("21"),
                adset("23", name="lost set", campaign_id="888")]                 # campaign not loaded
        ads = [ad("31"),
               ad("32", "lost ad", adset_id="999", eff="DISAPPROVED"),          # ad set not loaded
               ad("33", "in lost set", adset_id="23", campaign_id="888")]
        router = Router(flat_routes(camps, sets, ads))
        with mock.patch.object(metaops.graph, "get", side_effect=router):
            (code, payload), text = self.run_text(
                cmd_inspect.command_review_tree,
                self.args(json=False, campaign=None, statuses=None), metaops)
        data = payload["data"]
        self.assertEqual(data["counts"], {"campaigns": 1, "adsets": 2, "ads": 3,
                                          "unattached_adsets": 1, "unattached_ads": 1})
        self.assertEqual([a["id"] for a in data["unattached"]["ads"]], ["32"])
        self.assertEqual([s["id"] for s in data["unattached"]["adsets"]], ["23"])
        self.assertEqual([a["id"] for a in data["unattached"]["adsets"][0]["ads"]], ["33"])
        self.assertEqual(data["blocking"], 1)                    # the orphan DISAPPROVED ad counts
        self.assertEqual(code, 1)
        self.assertTrue(any("not in the loaded set" in w for w in data["warnings"]))
        self.assertIn("U UNATTACHED", text)
        self.assertIn("UNATTACHED 1 ad sets, 1 ads", text.splitlines()[0])
        lost = next(ln for ln in text.splitlines() if "lost ad" in ln)
        self.assertIn("parent adset 999 not loaded", lost)
        self.assertIn("!! DISAPPROVED", lost)
        self.assertNotIn("No DISAPPROVED", payload["next_action"])

    def test_a_page_that_fails_to_load_fails_the_command(self):
        def ads_edge(params):
            if params.get("after") == "P1":
                raise gerr({"error": {"message": "bad token", "code": 190}})
            return cursor_pages([[ad("31")], [ad("32")]])(params)

        routes = flat_routes([campaign("11")], [adset("21")], [])
        routes["act_1/ads"] = ads_edge
        with mock.patch.object(metaops.graph, "get", side_effect=Router(routes)):
            with self.assertRaises(graph.GraphError):
                cmd_inspect.command_review_tree(self.args(campaign=None, statuses=None), metaops)
        # and through main(): a graph failure envelope, never a "reviewed" one
        envelope = metaops.graph_failure("review", gerr({"error": {"message": "x", "code": 190}}))
        self.assertFalse(envelope["ok"])

    def test_capped_or_looping_load_is_incomplete_and_never_ok(self):
        looping = {"data": [ad("31")], "paging": {"cursors": {"after": "SAME"}, "next": "https://x"}}
        for name, patcher in (
                ("cap", mock.patch.dict(cmd_inspect.TREE_CAPS, {"ad": 1})),
                ("loop", mock.patch.dict(cmd_inspect.TREE_CAPS, {}))):
            routes = flat_routes([campaign("11")], [adset("21")], [])
            routes["act_1/ads"] = (
                cursor_pages([[ad("31")], [ad("32")]]) if name == "cap" else (lambda p: looping))
            with patcher, mock.patch.object(metaops.graph, "get", side_effect=Router(routes)):
                (code, payload), text = self.run_text(
                    cmd_inspect.command_review_tree,
                    self.args(json=False, campaign=None, statuses=None), metaops)
            self.assertEqual(code, 1, name)
            self.assertFalse(payload["ok"], name)
            self.assertEqual((payload["phase"], payload["error"]["kind"]), ("incomplete", "incomplete"), name)
            self.assertFalse(payload["data"]["complete"], name)
            self.assertFalse(payload["data"]["load"]["ads"]["complete"], name)
            self.assertIn("INCOMPLETE", text.splitlines()[0], name)
            self.assertNotIn("No DISAPPROVED", payload["next_action"], name)
            self.assertNotIn("No blocking review state", payload["next_action"], name)
            self.assertTrue(any("INCOMPLETE" in w for w in payload["data"]["warnings"]), name)

    def test_active_ad_set_without_ads_is_flagged(self):
        routes = flat_routes([campaign("11")], [adset("21"), adset("22")], [ad("31")])
        _, (_, payload) = self.run_tree(routes)
        warnings = payload["data"]["warnings"]
        self.assertTrue(any("ACTIVE ad set(s) have no ads" in w and "22" in w for w in warnings))

    def test_single_campaign_uses_the_campaign_edges_and_is_bound_to_the_account(self):
        node = dict(campaign("11"), account_id="1")
        routes = {"act_1": {"currency": "USD"}, "11": node,
                  "11/adsets": {"data": [adset("21")]}, "11/ads": {"data": [ad("31")]}}
        router = Router(routes)
        with mock.patch.object(metaops.graph, "get", side_effect=router):
            code, payload = cmd_inspect.command_review_tree(
                self.args(campaign="11", statuses=None), metaops)
        self.assertEqual(code, 0)
        self.assertEqual(payload["data"]["campaign_id"], "11")
        self.assertEqual(payload["data"]["counts"]["ads"], 1)
        self.assertTrue(router.to("11")[0]["fields"].startswith("account_id,"))
        self.assertNotIn("act_1/campaigns", [p for p, _ in router.calls])

        foreign = Router({"act_1": {"currency": "USD"}, "11": dict(campaign("11"), account_id="999")})
        with mock.patch.object(metaops.graph, "get", side_effect=foreign):
            with self.assertRaisesRegex(metaops.MetaOpsError, "cross-profile"):
                cmd_inspect.command_review_tree(self.args(campaign="11", statuses=None), metaops)
        self.assertEqual([p for p, _ in foreign.calls], ["act_1", "11"])   # nothing else was read

    def test_campaign_id_must_be_numeric(self):
        with self.assertRaises(metaops.MetaOpsError):
            cmd_inspect.command_review_tree(self.args(campaign="11/../x", statuses=None), metaops)

    def test_statuses_default_and_ad_level_filter(self):
        default = cmd_inspect.resolve_statuses(metaops, None)
        self.assertIsNone(default["shown"])
        for level in ("campaign", "adset", "ad"):
            self.assertNotIn("DELETED", default[level])
        self.assertIn("ARCHIVED", default["campaign"])
        self.assertIn("CAMPAIGN_PAUSED", default["adset"])
        picked = cmd_inspect.resolve_statuses(metaops, "disapproved, paused, disapproved")
        self.assertEqual(picked["ad"], ["DISAPPROVED", "PAUSED"])
        self.assertEqual(picked["shown"], ["DISAPPROVED", "PAUSED"])
        # parents are never narrowed: they must stay reachable when only a child matches
        self.assertEqual(picked["campaign"], default["campaign"])
        self.assertEqual(picked["adset"], default["adset"])
        deleted = cmd_inspect.resolve_statuses(metaops, "DELETED")
        self.assertEqual(deleted["ad"], ["DELETED"])
        self.assertIn("DELETED", deleted["campaign"])
        self.assertIn("DELETED", deleted["adset"])
        with self.assertRaises(metaops.MetaOpsError):
            cmd_inspect.resolve_statuses(metaops, "ACTIVE,NOPE")
        with self.assertRaises(metaops.MetaOpsError):
            cmd_inspect.resolve_statuses(metaops, " , ")

    def status_flat(self):
        camps = [campaign("11", name="live campaign"),
                 campaign("12", name="paused campaign", effective_status="PAUSED")]
        sets = [adset("21", name="live set"), adset("22", name="clean set"),
                adset("23", name="paused set", campaign_id="12", eff="CAMPAIGN_PAUSED")]
        ads = [ad("31"), ad("32", eff="DISAPPROVED"), ad("34", eff="WITH_ISSUES"),
               ad("33", adset_id="22"),
               ad("35", eff="CAMPAIGN_PAUSED", adset_id="23", campaign_id="12")]
        return flat_routes(camps, sets, ads)

    def test_with_issues_plus_disapproved_still_reaches_ads_under_active_parents(self):
        router = Router(self.status_flat())          # a server that ignores every filter
        with mock.patch.object(metaops.graph, "get", side_effect=router):
            _, payload = cmd_inspect.command_review_tree(
                self.args(campaign=None, statuses="DISAPPROVED,WITH_ISSUES"), metaops)
        (camp_params,) = router.to("act_1/campaigns")
        self.assertIn("ACTIVE", camp_params["effective_status"])         # campaigns not narrowed
        (ad_params,) = router.to("act_1/ads")
        self.assertEqual(ad_params["effective_status"], ["DISAPPROVED", "WITH_ISSUES"])
        tree = payload["data"]["tree"]
        self.assertEqual([c["id"] for c in tree], ["11"])                # paused campaign pruned
        self.assertEqual([s["id"] for s in tree[0]["adsets"]], ["21"])   # clean set pruned
        self.assertEqual([a["id"] for a in tree[0]["adsets"][0]["ads"]], ["32", "34"])
        self.assertEqual(payload["data"]["blocking"], 2)
        self.assertEqual(payload["data"]["loaded"]["ads"], 2)

    def test_status_filter_keeps_an_object_that_matches_itself(self):
        router = Router(self.status_flat())
        with mock.patch.object(metaops.graph, "get", side_effect=router):
            (_, payload), out = self.run_text(
                cmd_inspect.command_review_tree,
                self.args(json=False, campaign=None, statuses="PAUSED"), metaops)
        tree = payload["data"]["tree"]
        self.assertEqual([c["id"] for c in tree], ["12"])            # PAUSED campaign, own match
        self.assertEqual(tree[0]["adsets"], [])
        self.assertIn("(no ad sets match --statuses)", out)

    def test_status_filter_active_keeps_clean_ad_sets_and_drops_the_rest(self):
        with mock.patch.object(metaops.graph, "get", side_effect=Router(self.status_flat())):
            _, payload = cmd_inspect.command_review_tree(
                self.args(campaign=None, statuses="ACTIVE"), metaops)
        tree = payload["data"]["tree"]
        self.assertEqual([c["id"] for c in tree], ["11"])
        self.assertEqual([(s["id"], [a["id"] for a in s["ads"]]) for s in tree[0]["adsets"]],
                         [("21", ["31"]), ("22", ["33"])])

    def test_reduce_data_error_retries_once_and_stays_small_for_the_other_edges(self):
        calls = []

        def campaigns(params):
            calls.append(params)
            if len(calls) == 1:
                raise gerr(REDUCE)
            return {"data": [campaign("11")]}

        routes = flat_routes([], [adset("21")], [ad("31")])
        routes["act_1/campaigns"] = campaigns
        router, (code, payload) = self.run_tree(routes)
        self.assertEqual(code, 0)
        self.assertEqual([c["limit"] for c in calls], [100, 25])
        self.assertEqual(router.to("act_1/adsets")[0]["limit"], 15)
        self.assertEqual(router.to("act_1/ads")[0]["limit"], 25)
        self.assertTrue(any("reduce the amount of data" in w for w in payload["data"]["warnings"]))

    def test_reduce_data_error_twice_is_raised_not_looped(self):
        calls = []

        def campaigns(params):
            calls.append(params)
            raise gerr(REDUCE)

        routes = flat_routes([], [], [])
        routes["act_1/campaigns"] = campaigns
        with mock.patch.object(metaops.graph, "get", side_effect=Router(routes)):
            with self.assertRaises(graph.GraphError):
                cmd_inspect.command_review_tree(self.args(campaign=None, statuses=None), metaops)
        self.assertEqual(len(calls), 2)

    def test_other_graph_errors_are_not_retried(self):
        calls = []

        def campaigns(params):
            calls.append(params)
            raise gerr({"error": {"message": "nope", "code": 190}})

        routes = flat_routes([], [], [])
        routes["act_1/campaigns"] = campaigns
        with mock.patch.object(metaops.graph, "get", side_effect=Router(routes)):
            with self.assertRaises(graph.GraphError):
                cmd_inspect.command_review_tree(self.args(campaign=None, statuses=None), metaops)
        self.assertEqual(len(calls), 1)

    def test_text_output_is_one_indented_line_per_object_with_markers(self):
        router = Router(self.make_flat())
        with mock.patch.object(metaops.graph, "get", side_effect=router):
            (code, payload), out = self.run_text(
                cmd_inspect.command_review_tree,
                self.args(json=False, campaign=None, statuses=None), metaops)
        self.assertEqual(code, 1)
        lines = out.splitlines()
        camp = [ln for ln in lines if ln.startswith("C ")]
        sets = [ln for ln in lines if ln.startswith("  S ")]
        ads = [ln for ln in lines if ln.startswith("    A ")]
        self.assertEqual((len(camp), len(sets), len(ads)), (1, 2, 3))
        self.assertIn("50.00 USD/day", camp[0])                  # human units, account currency
        self.assertIn("20.00 USD/day", sets[0])
        self.assertIn("bid 5.00 USD", sets[0])
        self.assertIn("learn LEARNING", sets[0])
        self.assertIn("attr CLICK_THROUGH:7 VIEW_THROUGH:1", sets[0])
        self.assertIn("attr account default", next(ln for ln in lines if "empty set" in ln))
        self.assertIn("Oklahoma", sets[0])
        self.assertIn("21-65", sets[0])
        self.assertIn("adv_aud 0", sets[0])
        self.assertNotIn("2000", sets[0])                        # no raw minor units in text
        bad = next(ln for ln in ads if "bad" in ln)
        self.assertIn("!! DISAPPROVED", bad)
        self.assertIn("!! FEEDBACK", bad)
        self.assertIn("Spam", bad)
        self.assertIn("!! WITH_ISSUES", next(ln for ln in ads if "issue" in ln))
        self.assertNotIn("!!", next(ln for ln in ads if "good" in ln))
        self.assertIn("(no ads)", out)                           # the empty ad set says so
        self.assertIn("BLOCKING 2", lines[0])
        self.assertNotIn("INCOMPLETE", lines[0])

    def test_json_mode_prints_nothing_to_stdout(self):
        with mock.patch.object(metaops.graph, "get", side_effect=Router(self.make_flat())):
            _, out = self.run_text(cmd_inspect.command_review_tree,
                                   self.args(json=True, campaign=None, statuses=None), metaops)
        self.assertEqual(out, "")

    def test_whole_unit_currency_is_rendered_without_cents(self):
        routes = flat_routes([campaign("11", daily_budget="500")],
                             [adset("21", daily_budget="300", bid_amount="20")], [ad("31")],
                             currency="JPY")
        with mock.patch.object(metaops.graph, "get", side_effect=Router(routes)):
            (_, payload), out = self.run_text(
                cmd_inspect.command_review_tree,
                self.args(json=False, campaign=None, statuses=None), metaops)
        self.assertEqual(payload["data"]["currency_offset"], 1)
        self.assertEqual(payload["data"]["tree"][0]["adsets"][0]["daily_budget"], 300)
        self.assertIn("300 JPY/day", out)
        self.assertIn("500 JPY/day", out)
        self.assertNotIn("3.00", out)

    def test_missing_currency_degrades_to_raw_minor_units(self):
        routes = flat_routes([campaign("11")], [adset("21")], [ad("31")])
        routes["act_1"] = {"id": "act_1"}
        with mock.patch.object(metaops.graph, "get", side_effect=Router(routes)):
            (_, payload), out = self.run_text(
                cmd_inspect.command_review_tree,
                self.args(json=False, campaign=None, statuses=None), metaops)
        self.assertIn("minor units", out)
        self.assertTrue(any("currency unknown" in w for w in payload["data"]["warnings"]))

    def test_clean_account_exits_zero_and_says_what_it_loaded(self):
        camps, sets, ads = five_ads()
        _, (code, payload) = self.run_tree(flat_routes(camps, sets, ads))
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        self.assertIsNone(payload["error"])
        self.assertEqual(payload["phase"], "tree")
        self.assertIn("5 ad(s) loaded", payload["next_action"])

    def test_requires_workspace(self):
        with self.assertRaises(metaops.MetaOpsError):
            cmd_inspect.command_review_tree(
                self.args(workspace_obj=None, campaign=None, statuses=None), metaops)

    def test_review_entry_dispatch_and_flag_guards(self):
        with mock.patch.object(cmd_inspect, "command_review_tree", return_value=(0, {"t": 1})) as tree:
            out = cmd_operate.command_review_entry(
                self.args(tree=True, previews=False, campaign=None, statuses=None), metaops)
        self.assertEqual(out, (0, {"t": 1}))
        tree.assert_called_once()
        with self.assertRaisesRegex(metaops.MetaOpsError, "--previews"):
            cmd_operate.command_review_entry(
                self.args(tree=True, previews=True, campaign=None, statuses=None), metaops)
        with self.assertRaisesRegex(metaops.MetaOpsError, "belong to review --tree"):
            cmd_operate.command_review_entry(
                self.args(tree=False, previews=False, campaign="1", statuses=None), metaops)
        with mock.patch.object(cmd_operate, "command_review", return_value=(0, {"flat": 1})) as flat:
            out = cmd_operate.command_review_entry(
                self.args(tree=False, previews=False, campaign=None, statuses=None), metaops)
        self.assertEqual(out, (0, {"flat": 1}))
        flat.assert_called_once()

    def test_parser_accepts_tree_flags_and_keeps_the_old_forms(self):
        parser = metaops.parser()
        ns = parser.parse_args(["review", "--tree", "--campaign", "9", "--statuses", "ACTIVE,PAUSED"])
        self.assertTrue(ns.tree)
        self.assertEqual((ns.campaign, ns.statuses), ("9", "ACTIVE,PAUSED"))
        old = parser.parse_args(["review", "--ids", "1,2"])
        self.assertFalse(old.tree)
        self.assertEqual(old.ids, "1,2")
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parser.parse_args(["review", "--tree", "--ids", "1"])
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parser.parse_args(["review"])

    def test_registered_handler_runs_the_tree(self):
        ns = metaops.parser().parse_args(["review", "--tree"])
        ns.workspace_obj, ns.json = self.ws, True
        router = Router(flat_routes([campaign("11")], [adset("21")], [ad("31")]))
        with mock.patch.object(metaops.graph, "get", side_effect=router):
            code, payload = ns.handler(ns)
        self.assertEqual((code, payload["command"], payload["phase"]), (0, "review", "tree"))

    def test_existing_flat_review_is_unchanged(self):
        ads = {"111": {"id": "111", "account_id": "1", "name": "A", "effective_status": "ACTIVE",
                       "configured_status": "ACTIVE", "issues_info": None, "ad_review_feedback": None}}
        ns = metaops.parser().parse_args(["review", "--ids", "111"])
        ns.workspace_obj = self.ws
        with mock.patch.object(metaops.graph, "get",
                               side_effect=lambda path, params=None, context="": ads[path]):
            code, payload = ns.handler(ns)
        self.assertEqual(code, 0)
        self.assertEqual(payload["data"]["summary"], {"ACTIVE": 1})


# ------------------------------------------------------------------------------ insights


class InsightsValidationTests(unittest.TestCase):
    def test_breakdown_allow_list(self):
        self.assertEqual(insights.parse_breakdowns("publisher_platform, Platform_Position"),
                         ["publisher_platform", "platform_position"])
        for name in ("country", "region", "publisher_platform", "platform_position",
                     "impression_device", "age", "gender",
                     "hourly_stats_aggregated_by_advertiser_time_zone"):
            self.assertEqual(insights.parse_breakdowns(name), [name])
        for bad in ("placement", "country,nope", "", " , ", "age,age"):
            with self.assertRaises(ValueError, msg=bad):
                insights.parse_breakdowns(bad)

    def test_no_combination_is_rejected_locally_only_advised(self):
        # The repo documents no forbidden combination, so nothing may be refused on that basis.
        names = insights.parse_breakdowns("age,gender,country,region,impression_device")
        self.assertEqual(len(names), 5)
        self.assertEqual(insights.breakdown_advisories(["platform_position"]) and 1, 1)
        self.assertEqual(insights.breakdown_advisories(["platform_position", "publisher_platform"]), [])
        self.assertEqual(insights.breakdown_advisories(["age"]), [])

    def test_time_increment(self):
        for good in ("1", "7", "monthly", "all_days", "ALL_DAYS"):
            insights.parse_time_increment(good, strict=True)
        self.assertEqual(insights.parse_time_increment("7", strict=True), 7)
        self.assertEqual(insights.parse_time_increment("monthly"), "monthly")
        for bad in ("3", "0", "weekly", "", "1.5"):
            with self.assertRaises(ValueError, msg=bad):
                insights.parse_time_increment(bad, strict=True)
        self.assertEqual(insights.parse_time_increment("3"), 3)  # the script itself stays permissive

    def test_attribution_windows(self):
        self.assertEqual(insights.parse_windows("7d_click,1d_view,7d_click"), ["7d_click", "1d_view"])
        self.assertEqual(insights.parse_windows("1d_ev"), ["1d_ev"])
        with self.assertRaisesRegex(ValueError, "2026-01-12"):
            insights.parse_windows("7d_click,7d_view")
        with self.assertRaisesRegex(ValueError, "2026-01-12"):
            insights.parse_windows("28d_view")
        for bad in ("7d", "click", "", "1d_click,90d_click"):
            with self.assertRaises(ValueError, msg=bad):
                insights.parse_windows(bad)
        self.assertEqual(insights.windows_from_days(None, None), ["1d_click", "1d_view"])
        self.assertEqual(insights.windows_from_days(7, 1), ["7d_click", "1d_view"])
        self.assertEqual(insights.windows_from_days(28, None), ["28d_click", "1d_view"])
        with self.assertRaises(ValueError):
            insights.windows_from_days(3, 1)
        with self.assertRaisesRegex(ValueError, "2026-01-12"):
            insights.windows_from_days(1, 7)

    def test_extra_fields_allow_list(self):
        self.assertEqual(insights.parse_extra_fields("reach,outbound_clicks,reach"),
                         ["reach", "outbound_clicks"])
        with self.assertRaisesRegex(ValueError, "removed at API v26"):
            insights.parse_extra_fields("total_video_impressions")
        with self.assertRaises(ValueError):
            insights.parse_extra_fields("spend,definitely_not_a_field")
        fields = insights.request_fields(["outbound_clicks", "spend"])
        self.assertEqual(fields[: len(insights.FIELDS)], insights.FIELDS)
        self.assertEqual(fields.count("spend"), 1)
        self.assertIn("outbound_clicks", fields)
        self.assertEqual(insights.request_fields(), insights.FIELDS)

    def test_flatten_actions_keeps_a_column_per_window(self):
        row = {"spend": "1", "actions": [{"action_type": "lead", "value": "5", "7d_click": "4",
                                          "1d_view": "1"}]}
        flat = insights.flatten_actions(row)
        self.assertEqual(flat["actions:lead"], "5")
        self.assertEqual(flat["actions:lead:7d_click"], "4")
        self.assertEqual(flat["actions:lead:1d_view"], "1")
        self.assertNotIn("actions", flat)

    def ns(self, **kw):
        base = dict(since=None, until=None, date_preset=None, time_increment="1", click_window=None,
                    view_window=None, action_attribution_windows=None, breakdown=None, fields=None)
        base.update(kw)
        return argparse.Namespace(**base)

    def test_build_request(self):
        params, fields, echo = insights.build_request(self.ns(
            breakdown="publisher_platform,platform_position", time_increment="all_days",
            action_attribution_windows="7d_click,1d_view", fields="reach", since="2026-09-01",
            until="2026-09-07"))
        self.assertEqual(params["breakdowns"], "publisher_platform,platform_position")
        self.assertEqual(params["time_increment"], "all_days")
        self.assertEqual(params["action_attribution_windows"], ["7d_click", "1d_view"])
        self.assertEqual(params["time_range"], {"since": "2026-09-01", "until": "2026-09-07"})
        self.assertNotIn("date_preset", params)
        self.assertIn("reach", fields)
        self.assertEqual(echo["breakdowns"], ["publisher_platform", "platform_position"])
        # defaults are exactly what the script used before the new flags
        params, fields, _ = insights.build_request(self.ns())
        self.assertEqual(params, {"action_attribution_windows": ["1d_click", "1d_view"],
                                  "time_increment": 1, "date_preset": "yesterday"})
        self.assertEqual(fields, insights.FIELDS)
        with self.assertRaises(ValueError):
            insights.build_request(self.ns(action_attribution_windows="7d_click", click_window=7))
        with self.assertRaises(ValueError):
            insights.build_request(self.ns(since="2026-09-01"))

    def _fetch_with(self, side_effect):
        with mock.patch.object(graph, "get", side_effect=side_effect) as get:
            rows = insights.fetch("act_1", "ad", {"date_preset": "yesterday"})
        return rows, get

    def test_fetch_retries_once_with_a_smaller_page_on_code_1(self):
        seen = []

        def fake(path, params=None, context=""):
            seen.append(dict(params))
            if len(seen) == 1:
                raise gerr(REDUCE)
            return {"data": [{"spend": "1"}]}

        rows, _ = self._fetch_with(fake)
        self.assertEqual(rows, [{"spend": "1"}])
        self.assertEqual([p["limit"] for p in seen], [500, 100])

    def test_fetch_second_code_1_and_other_errors_raise(self):
        with self.assertRaises(graph.GraphError):
            self._fetch_with(mock.Mock(side_effect=[gerr(REDUCE), gerr(REDUCE)]))
        get = mock.Mock(side_effect=[gerr({"error": {"message": "x", "code": 100}})])
        with self.assertRaises(graph.GraphError):
            self._fetch_with(get)
        self.assertEqual(get.call_count, 1)

    def test_fetch_follows_cursors_and_uses_requested_fields(self):
        pages = [{"data": [{"a": 1}], "paging": {"cursors": {"after": "C"}, "next": "https://x"}},
                 {"data": [{"a": 2}]}]
        seen = []

        def fake(path, params=None, context=""):
            seen.append(dict(params))
            return pages[len(seen) - 1]

        with mock.patch.object(graph, "get", side_effect=fake):
            rows = insights.fetch("act_1", "ad", {}, ["spend", "reach"])
        self.assertEqual(rows, [{"a": 1}, {"a": 2}])
        self.assertEqual(seen[0]["fields"], "spend,reach")
        self.assertEqual(seen[1]["after"], "C")

    def test_fetch_goes_through_graph_call_so_the_insights_throttle_header_is_honoured(self):
        header = {"x-fb-ads-insights-throttle": json.dumps(
            {"app_id_util_pct": 12.0, "acc_id_util_pct": 90.0, "ads_api_access_tier": "standard_access"})}

        class Resp:
            status_code, ok, text = 200, True, "{}"
            headers = header

            def json(self):
                return {"data": [{"spend": "1"}]}

        session = mock.Mock()
        session.request.return_value = Resp()
        with mock.patch.object(graph, "session", return_value=session), \
                mock.patch.object(graph.time, "sleep") as sleep:
            rows = insights.fetch("act_1", "ad", {"breakdowns": "country"})
        self.assertEqual(rows, [{"spend": "1"}])
        sleep.assert_called_once()
        self.assertAlmostEqual(sleep.call_args[0][0], 54.0)   # 60 s * 90 %
        method, url = session.request.call_args[0][:2]
        self.assertEqual(method, "GET")
        self.assertTrue(url.endswith("/act_1/insights"))
        self.assertEqual(session.request.call_args[1]["params"]["breakdowns"], "country")


class InsightsPullWrapperTests(Base):
    def pull_args(self, **kw):
        base = dict(level="ad", date_preset=None, since=None, until=None, csv=None, breakdown=None,
                    time_increment=None, action_attribution_windows=None, click_window=None,
                    view_window=None, fields=None, insights_mode="pull")
        base.update(kw)
        return self.args(**base)

    def run_pull(self, **kw):
        captured = {}
        summary = json.dumps({"schema": "insights.result/v1", "rows": 3})

        def fake_child(script, child_args, timeout):
            captured["script"], captured["args"] = script, child_args
            return metaops.ChildResult(["python", script], 0, summary + "\n", "")

        with mock.patch.object(metaops, "run_child", side_effect=fake_child), \
                mock.patch.object(metaops, "echo_child"):
            code, payload = cmd_operate.command_insights(self.pull_args(**kw), metaops)
        return code, payload, captured

    def flag(self, argv, name):
        return argv[argv.index(name) + 1]

    def test_new_flags_are_forwarded_to_the_child(self):
        code, payload, cap = self.run_pull(
            breakdown="publisher_platform,platform_position", time_increment="all_days",
            action_attribution_windows="7d_click,1d_view", fields="reach,outbound_clicks")
        self.assertEqual(code, 0)
        argv = cap["args"]
        self.assertEqual(cap["script"], "insights.py")
        self.assertEqual(self.flag(argv, "--breakdown"), "publisher_platform,platform_position")
        self.assertEqual(self.flag(argv, "--time-increment"), "all_days")
        self.assertEqual(self.flag(argv, "--action-attribution-windows"), "7d_click,1d_view")
        self.assertEqual(self.flag(argv, "--fields"), "reach,outbound_clicks")
        self.assertEqual(self.flag(argv, "--date-preset"), "yesterday")
        self.assertEqual(payload["data"]["request"]["breakdowns"],
                         ["publisher_platform", "platform_position"])
        self.assertIn("Breakdown rows are for reading", payload["next_action"])

    def test_plain_pull_sends_exactly_what_it_sent_before(self):
        code, payload, cap = self.run_pull()
        argv = cap["args"]
        for absent in ("--breakdown", "--time-increment", "--action-attribution-windows", "--fields"):
            self.assertNotIn(absent, argv)
        self.assertEqual(argv[:4], ["--account", "act_1", "--level", "ad"])
        self.assertIn("Push spend as cost", payload["next_action"])

    def test_click_window_shorthand_becomes_an_explicit_list(self):
        _, _, cap = self.run_pull(click_window=7)
        self.assertEqual(self.flag(cap["args"], "--action-attribution-windows"), "7d_click,1d_view")

    def test_invalid_input_is_rejected_before_any_child_or_graph_call(self):
        bad_cases = [
            dict(breakdown="placement"),
            dict(breakdown="country,country"),
            dict(time_increment="3"),
            dict(action_attribution_windows="7d_view"),
            dict(action_attribution_windows="7d_click", click_window=7),
            dict(view_window=7),
            dict(fields="nope"),
            dict(fields="total_video_impressions"),
        ]
        for kw in bad_cases:
            with mock.patch.object(metaops, "run_child") as child, \
                    mock.patch.object(metaops.graph, "get") as get:
                with self.assertRaises(metaops.MetaOpsError, msg=str(kw)):
                    cmd_operate.command_insights(self.pull_args(**kw), metaops)
            child.assert_not_called()
            get.assert_not_called()

    def test_parser_flags(self):
        parser = metaops.parser()
        ns = parser.parse_args([
            "insights", "pull", "--level", "ad", "--breakdown", "publisher_platform,platform_position",
            "--time-increment", "monthly", "--action-attribution-windows", "1d_click", "--fields", "reach"])
        self.assertEqual(ns.breakdown, "publisher_platform,platform_position")
        self.assertEqual(ns.time_increment, "monthly")
        self.assertIsNone(ns.click_window)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parser.parse_args(["insights", "pull", "--level", "ad", "--view-window", "7"])
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parser.parse_args(["insights", "pull", "--level", "ad", "--click-window", "3"])

    def test_help_documents_the_sub11_join_and_marks_the_mapping_unverified(self):
        text = cmd_operate.PULL_HELP
        self.assertIn("sub11", text)
        self.assertIn("{{placement}}", text)
        self.assertIn("UNVERIFIED", text)
        self.assertIn("platform_position", text)
        # nothing invented: the only macro value mentioned is the one the repo documents
        self.assertEqual(sorted(set(re.findall(r"[A-Z][a-z]+_[A-Z][a-z]+_[A-Z][a-z]+", text))),
                         ["Facebook_Mobile_Feed"])


# ------------------------------------------------------------------------------ activity


def event(when, kind="update_ad_run_status", actor="Anna", actor_id="9", obj="123", **kw):
    row = {"event_time": when, "event_type": kind, "translated_event_type": kind.replace("_", " "),
           "object_id": obj, "object_name": "Ad " + obj, "object_type": "AD", "actor_id": actor_id,
           "actor_name": actor, "extra_data": json.dumps({"old_value": "ACTIVE", "new_value": "PAUSED"}),
           "application_name": "Ads Manager"}
    row.update(kw)
    return row


class ActivityTests(Base):
    def act_args(self, **kw):
        base = dict(since="2026-09-27", until="2026-09-27", event_types=None, limit=200)
        base.update(kw)
        return self.args(**base)

    def test_window_sort_filter_summary_and_params(self):
        events = [
            event("2026-09-27T09:00:00+0000", "update_ad_run_status"),
            event("2026-09-27T13:38:42+0000", "ad_review_declined", actor="Facebook", actor_id="0"),
            event("2026-09-27T13:40:52+0000", "ad_account_update_status", actor="Facebook", actor_id="0"),
            event("2026-09-26T23:59:59+0000", "update_ad_run_status"),   # before the window
            event("2026-09-28T00:00:00+0000", "update_ad_run_status"),   # until is exclusive next day
            event("2026-09-27T11:00:00+0000", "update_ad_set_budget", actor="Anna"),
        ]
        router = Router({"act_1/activities": {"data": events}})
        with mock.patch.object(metaops.graph, "get", side_effect=router):
            code, payload = cmd_inspect.command_activity(self.act_args(), metaops)
        self.assertEqual(code, 0)
        data = payload["data"]
        (params,) = router.to("act_1/activities")
        for field in ("event_time", "event_type", "translated_event_type", "object_id", "object_name",
                      "object_type", "actor_id", "actor_name", "extra_data", "application_name"):
            self.assertIn(field, params["fields"].split(","))
        self.assertEqual(params["since"], 1790467200)       # 2026-09-27T00:00:00Z
        self.assertEqual(params["until"], 1790553600)       # 2026-09-28T00:00:00Z (--until day inclusive)
        self.assertEqual(data["scanned"], 6)
        self.assertEqual(data["matched"], 4)
        times = [e["event_time"] for e in data["events"]]
        self.assertEqual(times, sorted(times, reverse=True))     # newest first
        self.assertEqual(times[0], "2026-09-27T13:40:52+0000")
        self.assertEqual(data["summary"]["by_event_type"]["ad_review_declined"], 1)
        self.assertEqual(data["summary"]["by_actor"], {"Facebook (0)": 2, "Anna (9)": 2})
        self.assertEqual(data["summary"]["by_application"], {"Ads Manager": 4})
        self.assertEqual(data["events"][0]["extra"], {"old_value": "ACTIVE", "new_value": "PAUSED"})
        self.assertFalse(data["truncated"])

    def test_event_types_filter_is_client_side(self):
        events = [event("2026-09-27T09:00:00+0000", "update_ad_run_status"),
                  event("2026-09-27T10:00:00+0000", "ad_account_update_status")]
        router = Router({"act_1/activities": {"data": events}})
        with mock.patch.object(metaops.graph, "get", side_effect=router):
            _, payload = cmd_inspect.command_activity(
                self.act_args(event_types="ad_account_update_status,create_ad"), metaops)
        self.assertEqual([e["event_type"] for e in payload["data"]["events"]], ["ad_account_update_status"])
        self.assertNotIn("event_type", router.calls[0][1])
        with mock.patch.object(metaops.graph, "get", side_effect=router):
            _, payload = cmd_inspect.command_activity(
                self.act_args(event_types="update_ad_run_stauts"), metaops)   # typo
        self.assertEqual(payload["data"]["matched"], 0)
        self.assertTrue(any("update_ad_run_status" in w for w in payload["data"]["warnings"]))

    def test_limit_keeps_the_newest_even_if_graph_sends_oldest_first(self):
        events = [event(f"2026-09-27T0{h}:00:00+0000", obj=str(h)) for h in range(1, 6)]
        router = Router({"act_1/activities": {"data": events}})   # ascending order
        with mock.patch.object(metaops.graph, "get", side_effect=router):
            _, payload = cmd_inspect.command_activity(self.act_args(limit=2), metaops)
        data = payload["data"]
        self.assertEqual([e["object_id"] for e in data["events"]], ["5", "4"])
        self.assertEqual((data["matched"], data["returned"], data["truncated"]), (5, 2, True))
        self.assertTrue(any("raise --limit" in w for w in data["warnings"]))

    def test_pagination_reduce_retry_and_scan_cap(self):
        pages = {
            None: {"data": [event("2026-09-27T09:00:00+0000")],
                   "paging": {"cursors": {"after": "P2"}, "next": "https://x"}},
            "P2": {"data": [event("2026-09-27T10:00:00+0000")]},
        }
        calls = []

        def activities(params):
            calls.append(dict(params))
            if len(calls) == 1:
                raise gerr(REDUCE)
            return pages[params.get("after")]

        router = Router({"act_1/activities": activities})
        with mock.patch.object(metaops.graph, "get", side_effect=router):
            _, payload = cmd_inspect.command_activity(self.act_args(), metaops)
        self.assertEqual(payload["data"]["matched"], 2)
        self.assertEqual([c["limit"] for c in calls], [200, 50, 50])
        self.assertEqual(calls[2]["after"], "P2")

        endless = {"data": [event("2026-09-27T09:00:00+0000")],
                   "paging": {"cursors": {"after": "N"}, "next": "https://x"}}
        counter = iter(range(1000))

        def more(params):
            return {**endless, "paging": {"cursors": {"after": f"N{next(counter)}"}, "next": "https://x"}}

        with mock.patch.object(cmd_inspect, "ACTIVITY_SCAN_CAP", 3), \
                mock.patch.object(metaops.graph, "get", side_effect=Router({"act_1/activities": more})):
            _, payload = cmd_inspect.command_activity(self.act_args(), metaops)
        self.assertTrue(payload["data"]["truncated"])
        self.assertTrue(any("scan cap" in w for w in payload["data"]["warnings"]))

    def test_text_output(self):
        events = [event("2026-09-27T13:40:52+0000", "ad_account_update_status", actor="Facebook",
                        actor_id="0")]
        router = Router({"act_1/activities": {"data": events}})
        with mock.patch.object(metaops.graph, "get", side_effect=router):
            (_, _), out = self.run_text(cmd_inspect.command_activity, self.act_args(json=False), metaops)
        self.assertIn("2026-09-27 13:40:52Z", out)
        self.assertIn("ad_account_update_status", out)
        self.assertIn("Facebook (0)", out)
        self.assertIn('"ACTIVE" -> "PAUSED"', out)
        self.assertIn("by event type: ad_account_update_status 1", out)

    def test_argument_validation(self):
        for kw in (dict(since="yesterday"), dict(limit=0), dict(limit=99999),
                   dict(since="2026-09-28", until="2026-09-27"), dict(event_types="Bad Name!")):
            with mock.patch.object(metaops.graph, "get") as get:
                with self.assertRaises(metaops.MetaOpsError, msg=str(kw)):
                    cmd_inspect.command_activity(self.act_args(**kw), metaops)
            get.assert_not_called()
        with self.assertRaises(metaops.MetaOpsError):
            cmd_inspect.command_activity(self.act_args(workspace_obj=None), metaops)

    def test_parse_when(self):
        utc = cmd_inspect.dt.timezone.utc
        d = cmd_inspect.parse_when(metaops, "2026-09-27", "--since")
        self.assertEqual(d, cmd_inspect.dt.datetime(2026, 9, 27, tzinfo=utc))
        self.assertEqual(cmd_inspect.parse_when(metaops, "2026-09-27", "--until", end=True),
                         cmd_inspect.dt.datetime(2026, 9, 28, tzinfo=utc))
        self.assertEqual(cmd_inspect.parse_when(metaops, "2026-09-27T13:00:00+03:00", "--since"),
                         cmd_inspect.dt.datetime(2026, 9, 27, 10, tzinfo=utc))
        self.assertEqual(cmd_inspect.parse_when(metaops, "2026-09-27T13:00:00Z", "--since"),
                         cmd_inspect.dt.datetime(2026, 9, 27, 13, tzinfo=utc))
        self.assertEqual(cmd_inspect.parse_when(metaops, "2026-09-27T13:00:00", "--since"),
                         cmd_inspect.dt.datetime(2026, 9, 27, 13, tzinfo=utc))
        with self.assertRaises(metaops.MetaOpsError):
            cmd_inspect.parse_when(metaops, "2026-13-45", "--since")

    def test_parser(self):
        ns = metaops.parser().parse_args(
            ["activity", "--since", "2026-09-27", "--event-types", "a,b", "--limit", "5"])
        self.assertEqual((ns.since, ns.until, ns.event_types, ns.limit), ("2026-09-27", None, "a,b", 5))
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            metaops.parser().parse_args(["activity"])


# ------------------------------------------------------------------------------ images


def img(hash_, name, created="2026-09-27T10:00:00+0000", **kw):
    row = {"hash": hash_, "name": name, "created_time": created, "status": "ACTIVE", "width": 1080,
           "height": 1350, "original_width": 1080, "original_height": 1350,
           "permalink_url": f"https://www.facebook.com/ads/image/?d={hash_}"}
    row.update(kw)
    return row


def img_ad(ad_id, creative, eff="ACTIVE"):
    return {"id": ad_id, "name": f"ad {ad_id}", "effective_status": eff, "creative": creative}


class ImagesTests(Base):
    def imgs_args(self, **kw):
        base = dict(since=None, unused=False, limit=100)
        base.update(kw)
        return self.args(**base)

    def routes(self, images=None, ads=None):
        images = images if images is not None else [
            img("h_top", "top level", "2026-09-29T10:00:00+0000"),
            img("h_link", "link data", "2026-09-28T10:00:00+0000"),
            img("h_card", "carousel", "2026-09-27T10:00:00+0000"),
            img("h_feed", "asset feed", "2026-09-26T10:00:00+0000"),
            img("h_two", "two ads", "2026-09-25T10:00:00+0000"),
            img("h_unused", "nobody", "2026-09-24T10:00:00+0000"),
        ]
        ads = ads if ads is not None else [
            img_ad("1", {"id": "c1", "image_hash": "h_top"}),
            img_ad("2", {"id": "c2", "object_story_spec": {"link_data": {"image_hash": "h_link"}}}),
            img_ad("3", {"id": "c3", "object_story_spec": {"link_data": {"child_attachments": [
                {"image_hash": "h_card"}, {"image_hash": "h_two"}]}}}, eff="PAUSED"),
            img_ad("4", {"id": "c4", "asset_feed_spec": {"images": [{"hash": "h_feed"}, {"hash": "h_two"}]}}),
            img_ad("5", {"id": "c5", "object_story_spec": {"link_data": {"image_hash": "h_gone"}}}),
            img_ad("6", None),
        ]
        return Router({"act_1/adimages": {"data": images}, "act_1/ads": {"data": ads}})

    def test_join_used_unused_and_orphan_hashes(self):
        router = self.routes()
        with mock.patch.object(metaops.graph, "get", side_effect=router):
            code, payload = cmd_inspect.command_images_list(self.imgs_args(), metaops)
        self.assertEqual(code, 0)
        data = payload["data"]
        by_hash = {i["hash"]: i for i in data["images"]}
        self.assertTrue(all(by_hash[h]["used"] for h in ("h_top", "h_link", "h_card", "h_feed", "h_two")))
        self.assertFalse(by_hash["h_unused"]["used"])
        self.assertEqual(by_hash["h_two"]["ad_count"], 2)
        self.assertEqual(by_hash["h_two"]["active_ad_count"], 1)
        self.assertEqual({a["id"] for a in by_hash["h_two"]["ads"]}, {"3", "4"})
        self.assertEqual(data["summary"], {
            "images": 6, "used": 5, "unused": 1, "referenced_not_in_library": 1,
            "ads_scanned": 6, "ads_scan_complete": True, "images_scan_complete": True})
        self.assertEqual([i["hash"] for i in data["images"]][:2], ["h_top", "h_link"])   # newest first
        self.assertEqual(by_hash["h_top"]["permalink_url"], "https://www.facebook.com/ads/image/?d=h_top")
        self.assertNotIn("url", by_hash["h_top"])                # only permalink_url is exposed
        (img_params,) = router.to("act_1/adimages")
        for field in ("name", "hash", "created_time", "status", "width", "height", "original_width",
                      "original_height", "permalink_url"):
            self.assertIn(field, img_params["fields"].split(","))
        self.assertNotIn("url", img_params["fields"].split(","))
        (ad_params,) = router.to("act_1/ads")
        self.assertIn("creative{id,name,image_hash,object_story_spec,asset_feed_spec}", ad_params["fields"])
        self.assertNotIn("DELETED", ad_params["effective_status"])

    def test_unused_since_and_limit(self):
        with mock.patch.object(metaops.graph, "get", side_effect=self.routes()):
            _, payload = cmd_inspect.command_images_list(self.imgs_args(unused=True), metaops)
        self.assertEqual([i["hash"] for i in payload["data"]["images"]], ["h_unused"])
        self.assertEqual(payload["data"]["summary"]["images"], 6)
        with mock.patch.object(metaops.graph, "get", side_effect=self.routes()):
            _, payload = cmd_inspect.command_images_list(self.imgs_args(since="2026-09-27"), metaops)
        self.assertEqual({i["hash"] for i in payload["data"]["images"]}, {"h_top", "h_link", "h_card"})
        self.assertEqual(payload["data"]["summary"]["images"], 3)
        with mock.patch.object(metaops.graph, "get", side_effect=self.routes()):
            _, payload = cmd_inspect.command_images_list(self.imgs_args(limit=2), metaops)
        self.assertEqual(len(payload["data"]["images"]), 2)
        self.assertEqual(payload["data"]["summary"]["images"], 6)

    def test_permalink_url_is_dropped_once_if_graph_rejects_it(self):
        seen = []

        def images(params):
            seen.append(dict(params))
            if "permalink_url" in params["fields"]:
                raise gerr({"error": {"code": 100, "message": "nonexisting field (permalink_url)"}})
            return {"data": [img("h1", "one", permalink_url=None)]}

        router = Router({"act_1/adimages": images, "act_1/ads": {"data": []}})
        with mock.patch.object(metaops.graph, "get", side_effect=router):
            code, payload = cmd_inspect.command_images_list(self.imgs_args(), metaops)
        self.assertEqual(code, 0)
        self.assertEqual(len(seen), 2)
        self.assertNotIn("permalink_url", seen[1]["fields"])
        self.assertTrue(any("permalink_url" in w for w in payload["data"]["warnings"]))

    def test_unrelated_code_100_is_not_swallowed(self):
        def images(params):
            raise gerr({"error": {"code": 100, "message": "Invalid parameter"}})

        router = Router({"act_1/adimages": images, "act_1/ads": {"data": []}})
        with mock.patch.object(metaops.graph, "get", side_effect=router):
            with self.assertRaises(graph.GraphError):
                cmd_inspect.command_images_list(self.imgs_args(), metaops)

    def test_paging_reduce_retry_and_incomplete_ad_scan_warns(self):
        ad_calls = []

        def ads(params):
            ad_calls.append(dict(params))
            if len(ad_calls) == 1:
                raise gerr(REDUCE)
            return {"data": [img_ad(str(len(ad_calls)), {"image_hash": "h1"})],
                    "paging": {"cursors": {"after": f"A{len(ad_calls)}"}, "next": "https://x"}}

        router = Router({"act_1/adimages": {"data": [img("h1", "one"), img("h2", "two")]},
                         "act_1/ads": ads})
        with mock.patch.object(cmd_inspect, "ADS_SCAN_CAP", 2), \
                mock.patch.object(metaops.graph, "get", side_effect=router):
            _, payload = cmd_inspect.command_images_list(self.imgs_args(), metaops)
        self.assertEqual(ad_calls[0]["limit"], 50)
        self.assertEqual(ad_calls[1]["limit"], 15)
        data = payload["data"]
        self.assertFalse(data["summary"]["ads_scan_complete"])
        self.assertTrue(any("may be used by an ad that was not scanned" in w for w in data["warnings"]))

    def test_creative_hashes(self):
        self.assertEqual(cmd_inspect.creative_hashes(None), set())
        self.assertEqual(cmd_inspect.creative_hashes({"id": "1", "object_story_id": "1_2"}), set())
        got = cmd_inspect.creative_hashes({
            "image_hash": "a",
            "object_story_spec": {"link_data": {"image_hash": "b", "child_attachments": [
                {"image_hash": "c"}]}, "video_data": {"image_hash": "d"}},
            "asset_feed_spec": {"images": [{"hash": "e"}, {"url": "x"}]},
        })
        self.assertEqual(got, {"a", "b", "c", "d", "e"})

    def test_text_output_marks_unused(self):
        with mock.patch.object(metaops.graph, "get", side_effect=self.routes()):
            (_, _), out = self.run_text(cmd_inspect.command_images_list,
                                        self.imgs_args(json=False), metaops)
        unused = [ln for ln in out.splitlines() if ln.startswith("h_unused")]
        self.assertEqual(len(unused), 1)
        self.assertIn("UNUSED", unused[0])
        self.assertIn("1080x1350", unused[0])
        used = next(ln for ln in out.splitlines() if ln.startswith("h_two"))
        self.assertIn("ads 1/2", used)
        self.assertIn("6 in scope, 5 used, 1 unused", out.splitlines()[0])

    def test_argument_validation_and_parser(self):
        for kw in (dict(limit=0), dict(limit=99999), dict(since="last week")):
            with mock.patch.object(metaops.graph, "get") as get:
                with self.assertRaises(metaops.MetaOpsError, msg=str(kw)):
                    cmd_inspect.command_images_list(self.imgs_args(**kw), metaops)
            get.assert_not_called()
        ns = metaops.parser().parse_args(["images", "list", "--unused", "--limit", "5", "--since", "2026-09-01"])
        self.assertTrue(ns.unused)
        self.assertEqual((ns.limit, ns.since), (5, "2026-09-01"))
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            metaops.parser().parse_args(["images"])

    def test_media_upload_command_is_untouched(self):
        ns = metaops.parser().parse_args(["media", "--image", "a.jpg"])
        self.assertEqual(ns.command, "media")
        self.assertEqual(ns.image, ["a.jpg"])
        self.assertFalse(hasattr(ns, "images_action"))


# ------------------------------------------------------------------------------ read-only guarantees


class ReadOnlyTests(Base):
    def test_module_uses_only_get_side_of_graph_and_no_write_paths(self):
        source = pathlib.Path(cmd_inspect.__file__).read_text(encoding="utf-8")
        self.assertLessEqual(set(re.findall(r"\bgraph\.(\w+)", source)),
                             {"get", "next_page_params", "normalize_account", "GraphError"})
        imported = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imported |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                imported.add((node.module or "").split(".")[0])
        self.assertEqual(imported, {"__future__", "datetime", "json", "re", "sys", "time",
                                    "collections", "typing", "insights"})
        for forbidden in ("run_child", ".post(", "authorize_writes", "subprocess", "requests",
                          "METAOPS_AUTH_FD", "METAOPS_PACE_OVERRIDE"):
            self.assertNotIn(forbidden, source)
        self.assertNotIn("import launch", source)

    def test_every_transport_call_is_a_get(self):
        """Run all three commands through the real graph.call with a fake requests session."""
        sessions = mock.Mock()

        class Resp:
            status_code, ok, text, headers = 200, True, "{}", {}

            def __init__(self, payload):
                self.payload = payload

            def json(self):
                return self.payload

        def request(method, url, **kw):
            path = url.split("/v26.0/")[-1] if "/v26.0/" in url else url.rsplit("/", 1)[-1]
            if path == "act_1":
                return Resp({"currency": "USD"})
            if path.endswith("/campaigns"):
                return Resp({"data": [campaign("11")]})
            if path.endswith("/adsets"):
                return Resp({"data": [adset("21")]})
            if path.endswith("/ads"):
                return Resp({"data": [ad("31")]})
            if path.endswith("/activities"):
                return Resp({"data": [event("2026-09-27T09:00:00+0000")]})
            if path.endswith("/adimages"):
                return Resp({"data": [img("h1", "one")]})
            return Resp({"data": []})

        sessions.request.side_effect = request
        with mock.patch.object(graph, "session", return_value=sessions), \
                mock.patch.object(metaops.graph, "post", side_effect=AssertionError("write attempted")):
            cmd_inspect.command_review_tree(self.args(campaign=None, statuses=None), metaops)
            cmd_inspect.command_activity(
                self.args(since="2026-09-27", until="2026-09-27", event_types=None, limit=5), metaops)
            cmd_inspect.command_images_list(self.args(since=None, unused=False, limit=5), metaops)
        methods = {call[0][0] for call in sessions.request.call_args_list}
        self.assertEqual(methods, {"GET"})
        self.assertGreaterEqual(sessions.request.call_count, 5)

    def test_workspace_free_commands_are_registered_as_lifecycle(self):
        for name in ("activity", "images", "review", "insights"):
            self.assertIn(name, metaops.WORKSPACE_LIFECYCLE_COMMANDS)


if __name__ == "__main__":
    unittest.main()

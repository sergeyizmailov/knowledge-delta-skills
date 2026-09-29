#!/usr/bin/env python3
"""Offline regression tests for verify.py: placements, bid policy, display link / description /
conversion_domain, Advantage+ OPT_IN leaks and the Instagram identity. Graph is mocked."""

from __future__ import annotations
import os as _os, tempfile as _tempfile
_os.environ["METAOPS_PACE_DIR"] = _tempfile.mkdtemp(prefix="metaops-pace-test-")
_os.environ.setdefault("METAOPS_CREATE_GAP_HOURS", "0")
_os.environ.setdefault("META_TOKEN", "TEST_TOKEN")

import contextlib
import copy
import io
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

import launch
import verify

IG = "17841400000000000"


def spec_dict(**top) -> dict:
    spec = {
        "run_id": "vfix", "account_id": "act_1", "page_id": "2", "pixel_id": "3", "currency": "USD",
        "campaign": {"name": "Campaign", "objective": "OUTCOME_SALES", "special_ad_categories": [],
                     "daily_budget_minor": 6000},
        "adsets": [{
            "name": "Ad set", "optimization_goal": "OFFSITE_CONVERSIONS",
            "custom_event_type": "PURCHASE", "start_time": "2030-01-01T08:00:00+00:00",
            "attribution": {"click_days": 7, "view_days": 1},
            "targeting": {"geo_locations": {"countries": ["US"]}, "advantage_audience": False},
            "ads": [{"name": "Ad", "creative": {
                "kind": "link_image", "image_hash": "hash", "link": "https://example.com/",
                "message": "story", "headline": "Read before you judge", "cta": "SEE_DETAILS"}}],
        }],
    }
    spec.update(top)
    return spec


class VerifyHarness(unittest.TestCase):
    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.root = pathlib.Path(self._td.name)

    def build(self, spec: dict):
        """Write the spec + state and return (spec_path, state_path, read-back objects) for a
        tree that matches the spec field for field."""
        spec_path = self.root / "spec.json"
        spec_path.write_text(json.dumps(spec), encoding="utf-8")
        loaded = launch.load_spec(str(spec_path))
        state_path = self.root / "state.json"
        state_path.write_text(json.dumps({
            "objects": {"campaign": "1", "adset[0]": "2", "ad[0.0]": "3"},
            "spec_sha": launch.spec_hash(loaded), "spec_account": "act_1"}), encoding="utf-8")
        aset = loaded["adsets"][0]
        camp = loaded["campaign"]
        c = aset["ads"][0]["creative"]
        link_data = {"link": c["link"], "message": c["message"], "name": c["headline"],
                     "image_hash": c["image_hash"],
                     "call_to_action": {"type": c["cta"], "value": {"link": c["link"]}}}
        if c.get("display_link"):
            link_data["caption"] = c["display_link"]
        if c.get("description"):
            link_data["description"] = c["description"]
        adset_rb = {
            "id": "2", "name": "Ad set", "status": "ACTIVE", "effective_status": "ACTIVE",
            "optimization_goal": aset["optimization_goal"], "billing_event": "IMPRESSIONS",
            "start_time": aset["start_time"],
            "attribution_spec": launch.build_attribution(aset),
            "promoted_object": {"pixel_id": "3", "custom_event_type": aset["custom_event_type"]},
            "targeting": launch.build_targeting(aset),
        }
        # A spec that omitted placements still reads back with pinned ones in a healthy tree;
        # the negative tests below break this on purpose.
        rb_t = adset_rb["targeting"]
        rb_t.setdefault("publisher_platforms", ["facebook", "instagram"])
        rb_t.setdefault("facebook_positions", ["feed"])
        rb_t.setdefault("instagram_positions", ["stream"])
        if aset.get("bid_amount_minor"):
            adset_rb["bid_amount"] = aset["bid_amount_minor"]
        objects = {
            "1": {"id": "1", "name": "Campaign", "objective": camp["objective"], "status": "ACTIVE",
                  "effective_status": "ACTIVE", "daily_budget": camp["daily_budget_minor"],
                  "bid_strategy": camp.get("bid_strategy", "LOWEST_COST_WITHOUT_CAP"),
                  "special_ad_categories": []},
            "2": adset_rb,
            "3": {"id": "3", "name": "Ad", "status": "ACTIVE", "effective_status": "ACTIVE",
                  "creative": {
                      "id": "9",
                      "object_story_spec": {"page_id": "2", "instagram_user_id": IG, "link_data": link_data},
                      "degrees_of_freedom_spec": {"creative_features_spec": {
                          f: {"enroll_status": "OPT_OUT"} for f in self.opt_out_names(c)}},
                      "contextual_multi_ads": {"enroll_status": "OPT_OUT"}}},
        }
        return spec_path, state_path, objects

    @staticmethod
    def opt_out_names(c: dict) -> list[str]:
        """What a healthy tree reads back as OPT_OUT (independent of launch.resolved_opt_out)."""
        names = c["opt_out_features"] if c.get("opt_out_features") is not None else launch.DEFAULT_OPT_OUT
        return [f for f in names if f not in (c.get("opt_in_features") or [])]

    def run_verify(self, spec_path, state_path, objects) -> tuple[int, str]:
        out = io.StringIO()
        with (
            mock.patch.object(sys, "argv", ["verify.py", "--state", str(state_path), "--spec", str(spec_path)]),
            mock.patch.object(verify.graph, "get", side_effect=lambda p, **kw: objects[p]),
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            code = verify.main()
        return code, out.getvalue()

    def creative(self, objects) -> dict:
        return objects["3"]["creative"]

    def link_data(self, objects) -> dict:
        return objects["3"]["creative"]["object_story_spec"]["link_data"]


class BaselineTests(VerifyHarness):
    def test_a_matching_tree_passes(self) -> None:
        spec = spec_dict()
        spec["adsets"][0]["placements"] = "fb_ig_all"
        code, text = self.run_verify(*self.build(spec))
        self.assertEqual(code, 0, text)
        self.assertIn("placements", text)


class PlacementReadbackTests(VerifyHarness):
    """The spec omits every placement key, so nothing in the spec can be diffed: the read-back
    itself must be checked."""

    def test_missing_publisher_platforms_on_readback_fails_when_the_spec_pinned_them(self) -> None:
        spec = spec_dict()
        spec["adsets"][0]["placements"] = "fb_ig_feeds"
        spec_path, state_path, objects = self.build(spec)
        del objects["2"]["targeting"]["publisher_platforms"]
        code, text = self.run_verify(spec_path, state_path, objects)
        self.assertEqual(code, 1)
        self.assertIn("publisher_platforms missing on read-back", text)

    def test_missing_publisher_platforms_is_only_a_warning_for_an_unpinned_spec(self) -> None:
        spec_path, state_path, objects = self.build(spec_dict())
        del objects["2"]["targeting"]["publisher_platforms"]
        code, text = self.run_verify(spec_path, state_path, objects)
        self.assertEqual(code, 0, text)
        self.assertIn("WARN", text)

    def test_missing_publisher_platforms_fails_under_strict_lint(self) -> None:
        spec = spec_dict()
        spec["lint"] = "strict"
        spec_path, state_path, objects = self.build(spec)
        del objects["2"]["targeting"]["publisher_platforms"]
        code, text = self.run_verify(spec_path, state_path, objects)
        self.assertEqual(code, 1)
        self.assertIn("publisher_platforms missing on read-back", text)

    def test_unlisted_audience_network_messenger_threads_fail(self) -> None:
        for extra in ("audience_network", "messenger", "threads"):
            spec_path, state_path, objects = self.build(spec_dict())
            t = objects["2"]["targeting"]
            t["publisher_platforms"] = ["facebook", "instagram", extra]
            t["facebook_positions"] = ["feed"]
            t["instagram_positions"] = ["stream"]
            t[f"{extra}_positions"] = ["x"]
            code, text = self.run_verify(spec_path, state_path, objects)
            self.assertEqual(code, 1, extra)
            self.assertIn(extra, text)

    def test_positions_the_spec_listed_must_be_on_the_readback(self) -> None:
        spec = spec_dict()
        spec["adsets"][0]["placements"] = "fb_ig_feeds"
        spec_path, state_path, objects = self.build(spec)
        del objects["2"]["targeting"]["instagram_positions"]
        code, text = self.run_verify(spec_path, state_path, objects)
        self.assertEqual(code, 1)
        self.assertIn("explicit instagram_positions in the spec", text)

    def test_platform_without_positions_passes_when_the_spec_never_listed_them(self) -> None:
        spec_path, state_path, objects = self.build(spec_dict())
        objects["2"]["targeting"].pop("instagram_positions", None)
        code, text = self.run_verify(spec_path, state_path, objects)
        self.assertEqual(code, 0, text)

    def test_platform_the_spec_listed_is_accepted(self) -> None:
        spec = spec_dict()
        spec["adsets"][0]["targeting"].update({
            "publisher_platforms": ["facebook", "instagram", "audience_network"],
            "facebook_positions": ["feed"], "instagram_positions": ["stream"],
            "audience_network_positions": ["classic"]})
        code, text = self.run_verify(*self.build(spec))
        self.assertEqual(code, 0, text)

    def test_explicit_positions_on_readback_pass_when_the_spec_omitted_the_keys(self) -> None:
        spec_path, state_path, objects = self.build(spec_dict())
        code, text = self.run_verify(spec_path, state_path, objects)
        self.assertEqual(code, 0, text)

    def test_check_placements_helper_without_a_spec(self) -> None:
        d = verify.Diff()
        with contextlib.redirect_stdout(io.StringIO()):
            verify.check_placements(d, None, {"publisher_platforms": ["facebook", "instagram"],
                                              "facebook_positions": ["feed"],
                                              "instagram_positions": ["stream"]})
        self.assertEqual(d.bad, 0)
        d = verify.Diff()
        with contextlib.redirect_stdout(io.StringIO()):
            verify.check_placements(d, None, {})
        self.assertEqual(d.bad, 1)


class BidPolicyVerifyTests(VerifyHarness):
    def test_uncapped_adset_does_not_pass_under_require_cap(self) -> None:
        spec = {"campaign": {"bid_policy": "require_cap"}, "budget_mode": "CBO"}
        camp = {"bid_strategy": "LOWEST_COST_WITHOUT_CAP"}
        for a in ({}, {"bid_amount": None}):
            d = verify.Diff()
            with contextlib.redirect_stdout(io.StringIO()):
                verify.check_bid_policy(d, spec, {}, camp, a)
            self.assertEqual(d.bad, 1)
        d = verify.Diff()
        with contextlib.redirect_stdout(io.StringIO()):
            verify.check_bid_policy(d, spec, {}, {"bid_strategy": "LOWEST_COST_WITH_BID_CAP"}, {"bid_amount": 20000})
        self.assertEqual(d.bad, 0)

    def test_abo_reads_the_strategy_from_the_adset(self) -> None:
        spec = {"campaign": {}, "budget_mode": "ABO"}
        s = {"bid_policy": "require_cap"}
        d = verify.Diff()
        with contextlib.redirect_stdout(io.StringIO()):
            verify.check_bid_policy(d, spec, s, {"bid_strategy": "COST_CAP"},
                                    {"bid_strategy": "LOWEST_COST_WITHOUT_CAP", "bid_amount": 5})
        self.assertEqual(d.bad, 1)

    def test_no_policy_no_check(self) -> None:
        d = verify.Diff()
        with contextlib.redirect_stdout(io.StringIO()):
            verify.check_bid_policy(d, {"campaign": {}, "budget_mode": "CBO"}, {}, {}, {})
        self.assertEqual(d.bad, 0)

    def test_capped_tree_passes_end_to_end(self) -> None:
        spec = spec_dict()
        spec["campaign"].update({"bid_strategy": "LOWEST_COST_WITH_BID_CAP", "bid_policy": "require_cap"})
        spec["adsets"][0]["bid_amount_minor"] = 20000
        code, text = self.run_verify(*self.build(spec))
        self.assertEqual(code, 0, text)
        self.assertIn("bid cap enforced", text)

    def test_end_to_end_readback_that_lost_the_cap_fails(self) -> None:
        spec = spec_dict()
        spec["campaign"].update({"bid_strategy": "LOWEST_COST_WITH_BID_CAP", "bid_policy": "require_cap"})
        spec["adsets"][0]["bid_amount_minor"] = 20000
        spec_path, state_path, objects = self.build(spec)
        del objects["2"]["bid_amount"]
        objects["1"]["bid_strategy"] = "LOWEST_COST_WITHOUT_CAP"
        code, text = self.run_verify(spec_path, state_path, objects)
        self.assertEqual(code, 1)
        self.assertIn("uncapped on read-back", text)


class CopyFieldVerifyTests(VerifyHarness):
    def spec(self, **creative) -> dict:
        spec = spec_dict()
        spec["adsets"][0]["ads"][0]["creative"].update(creative)
        return spec

    def test_display_link_mismatch_fails(self) -> None:
        spec_path, state_path, objects = self.build(self.spec(display_link="example.com"))
        self.link_data(objects)["caption"] = "other.com"
        code, text = self.run_verify(spec_path, state_path, objects)
        self.assertEqual(code, 1)
        self.assertRegex(text, r"MISMATCH\s+display_link \(caption\): expected 'example.com', got 'other.com'")

    def test_missing_caption_fails_and_strict_says_so(self) -> None:
        spec_path, state_path, objects = self.build(self.spec(display_link="example.com"))
        del self.link_data(objects)["caption"]
        code, text = self.run_verify(spec_path, state_path, objects)
        self.assertEqual(code, 1)
        self.assertNotIn("MISSING  link_data.caption", text)
        strict = self.spec(display_link="example.com")
        strict["lint"] = "strict"
        spec_path, state_path, objects = self.build(strict)
        del self.link_data(objects)["caption"]
        code, text = self.run_verify(spec_path, state_path, objects)
        self.assertEqual(code, 1)
        self.assertIn("MISSING  link_data.caption", text)

    def test_matching_display_link_and_description_pass(self) -> None:
        code, text = self.run_verify(*self.build(self.spec(display_link="example.com", description="d")))
        self.assertEqual(code, 0, text)

    def test_description_mismatch_fails(self) -> None:
        spec_path, state_path, objects = self.build(self.spec(description="expected text"))
        self.link_data(objects)["description"] = "something else"
        code, text = self.run_verify(spec_path, state_path, objects)
        self.assertEqual(code, 1)
        self.assertRegex(text, r"MISMATCH\s+description")

    def test_unset_copy_fields_are_not_compared(self) -> None:
        spec_path, state_path, objects = self.build(self.spec())
        self.link_data(objects)["caption"] = "whatever.com"
        self.link_data(objects)["description"] = "whatever"
        code, text = self.run_verify(spec_path, state_path, objects)
        self.assertEqual(code, 0, text)

    def test_conversion_domain_is_diffed(self) -> None:
        spec = spec_dict()
        spec["conversion_domain"] = "example.com"
        spec_path, state_path, objects = self.build(spec)
        objects["3"]["conversion_domain"] = "example.com"
        code, text = self.run_verify(spec_path, state_path, objects)
        self.assertEqual(code, 0, text)
        objects["3"]["conversion_domain"] = "other.com"
        code, text = self.run_verify(spec_path, state_path, objects)
        self.assertEqual(code, 1)
        self.assertRegex(text, r"MISMATCH\s+conversion_domain")
        del objects["3"]["conversion_domain"]
        code, _ = self.run_verify(spec_path, state_path, objects)
        self.assertEqual(code, 1)

    def test_ad_level_conversion_domain_wins_over_the_spec_level_one(self) -> None:
        spec = spec_dict()
        spec["conversion_domain"] = "spec.com"
        spec["adsets"][0]["ads"][0]["conversion_domain"] = "ad.com"
        spec_path, state_path, objects = self.build(spec)
        objects["3"]["conversion_domain"] = "ad.com"
        code, text = self.run_verify(spec_path, state_path, objects)
        self.assertEqual(code, 0, text)


class OptInLeakTests(VerifyHarness):
    def test_unknown_opt_in_feature_is_a_leak(self) -> None:
        spec_path, state_path, objects = self.build(spec_dict())
        feats = self.creative(objects)["degrees_of_freedom_spec"]["creative_features_spec"]
        feats["brand_new_meta_feature"] = {"enroll_status": "OPT_IN"}
        code, text = self.run_verify(spec_path, state_path, objects)
        self.assertEqual(code, 1)
        self.assertIn("brand_new_meta_feature", text)

    def test_listed_feature_reading_back_opt_in_is_still_a_leak(self) -> None:
        spec_path, state_path, objects = self.build(spec_dict())
        feats = self.creative(objects)["degrees_of_freedom_spec"]["creative_features_spec"]
        feats["image_animation"] = {"enroll_status": "OPT_IN"}
        code, text = self.run_verify(spec_path, state_path, objects)
        self.assertEqual(code, 1)
        self.assertIn("image_animation", text)

    def test_opt_in_features_option_allows_a_feature(self) -> None:
        spec = spec_dict()
        spec["adsets"][0]["ads"][0]["creative"]["opt_in_features"] = ["brand_new_meta_feature"]
        spec_path, state_path, objects = self.build(spec)
        feats = self.creative(objects)["degrees_of_freedom_spec"]["creative_features_spec"]
        feats["brand_new_meta_feature"] = {"enroll_status": "OPT_IN"}
        code, text = self.run_verify(spec_path, state_path, objects)
        self.assertEqual(code, 0, text)

    def test_feature_left_out_of_a_custom_opt_out_list_may_stay_opt_in(self) -> None:
        spec = spec_dict()
        spec["adsets"][0]["ads"][0]["creative"]["opt_out_features"] = ["image_animation", "text_generation"]
        spec_path, state_path, objects = self.build(spec)
        feats = self.creative(objects)["degrees_of_freedom_spec"]["creative_features_spec"]
        feats["adapt_to_placement"] = {"enroll_status": "OPT_IN"}     # in the default list, dropped on purpose
        code, text = self.run_verify(spec_path, state_path, objects)
        self.assertEqual(code, 0, text)
        feats["image_animation"] = {"enroll_status": "OPT_IN"}          # named in the custom list: leak
        code, text = self.run_verify(spec_path, state_path, objects)
        self.assertEqual(code, 1)

    def test_expected_set_uses_the_same_product_video_logic_as_launch(self) -> None:
        feats = {"media_type_automation": {"enroll_status": "OPT_IN"}}
        catalog_video = {"kind": "catalog_single", "product_video": True}
        self.assertEqual(verify.leaked_opt_in(feats, catalog_video), [])
        self.assertEqual(verify.leaked_opt_in(feats, {"kind": "catalog_single"}), ["media_type_automation"])
        self.assertEqual(verify.leaked_opt_in(feats, {"kind": "link_image", "product_video": True}),
                         ["media_type_automation"])
        self.assertEqual(verify.leaked_opt_in(feats, None), ["media_type_automation"])

    def test_opt_out_readback_is_not_a_leak(self) -> None:
        feats = {"x": {"enroll_status": "OPT_OUT"}, "y": {}, "z": None}
        self.assertEqual(verify.leaked_opt_in(feats, {}), [])


class InstagramIdentityTests(VerifyHarness):
    def test_missing_instagram_user_id_is_a_failure_not_a_warning(self) -> None:
        spec_path, state_path, objects = self.build(spec_dict())
        del objects["3"]["creative"]["object_story_spec"]["instagram_user_id"]
        code, text = self.run_verify(spec_path, state_path, objects)
        self.assertEqual(code, 1)
        self.assertIn("no instagram_user_id", text)
        self.assertNotIn("WARN  no instagram_user_id", text)


if __name__ == "__main__":
    unittest.main()

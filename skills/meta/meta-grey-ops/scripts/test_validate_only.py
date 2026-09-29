#!/usr/bin/env python3
"""`--validate-only` on edit.py / edit_targeting.py: the payload goes to Meta with
execution_options=[validate_only], the object is never changed, and a Meta rejection is a per-id failure.
Offline: reuses the FakeGraph from test_edit_fixes."""

from __future__ import annotations
import os as _os, tempfile as _tempfile
_os.environ["METAOPS_PACE_DIR"] = _tempfile.mkdtemp(prefix="metaops-pace-test-")
_os.environ.setdefault("METAOPS_CREATE_GAP_HOURS", "0")

import unittest
from unittest import mock

import cmd_edit
import edit
import edit_tags
import edit_targeting
import metaops
from test_edit_fixes import FakeGraph, WrapperBase, graph_error, last_json, run_main

ADSET = {
    "name": "1234 OK LR6a", "status": "ACTIVE", "effective_status": "ACTIVE", "account_id": "1",
    "daily_budget": "10000", "optimization_goal": "OFFSITE_CONVERSIONS", "bid_amount": "20000",
    "targeting": {"age_min": 21, "age_max": 65, "geo_locations": {"regions": [{"key": "3879"}], "location_types": ["home"]},
                  "publisher_platforms": ["facebook", "instagram"]},
}


class ValidateAware(FakeGraph):
    """Like Meta: a POST carrying validate_only is checked and applies nothing."""

    def post(self, path, data=None, **kw):
        if "execution_options" in (data or {}):
            self.posts.append((path, dict(data)))
            return {}
        return super().post(path, data, **kw)


class FailingValidate(FakeGraph):
    """Rejects any POST that carries validate_only, like Meta answering #100 on a bad payload."""

    def post(self, path, data=None, **kw):
        self.posts.append((path, dict(data or {})))
        if "execution_options" in (data or {}):
            raise graph_error(100, "Invalid parameter")
        return {}


class EditValidateOnly(unittest.TestCase):
    def test_bid_is_validated_and_never_applied(self) -> None:
        fake = ValidateAware({"5": dict(ADSET)})
        code, out, _ = run_main(edit, ["--ids", "5", "--bid-minor", "15000", "--validate-only"], fake)
        self.assertEqual(code, 0)
        (path, payload), = fake.posts
        self.assertEqual(path, "5")
        self.assertEqual(payload["execution_options"], ["validate_only"])
        self.assertEqual(payload["bid_amount"], 15000)
        self.assertEqual(fake.nodes["5"]["bid_amount"], "20000")  # unchanged
        res = last_json(out)
        self.assertTrue(res["validate_only"] and res["dry_run"])
        self.assertTrue(res["results"][0]["validated"])

    def test_rejection_is_a_failed_row_not_a_crash(self) -> None:
        fake = FailingValidate({"5": dict(ADSET)})
        code, out, err = run_main(edit, ["--ids", "5", "--bid-minor", "1", "--validate-only"], fake)
        self.assertEqual(code, 1)
        row = last_json(out)["results"][0]
        self.assertFalse(row["ok"])
        self.assertFalse(row["validated"])
        self.assertIn("rejects", err)

    def test_plain_dry_run_still_sends_nothing(self) -> None:
        fake = FakeGraph({"5": dict(ADSET)})
        code, _, _ = run_main(edit, ["--ids", "5", "--bid-minor", "15000", "--dry-run"], fake)
        self.assertEqual(code, 0)
        self.assertEqual(fake.posts, [])

    def test_schedule_payload_is_validated(self) -> None:
        fake = FakeGraph({"5": dict(ADSET)})
        code, _, _ = run_main(edit, ["--ids", "5", "--start-time", "2099-01-01T08:00:00-07:00", "--validate-only"], fake)
        self.assertEqual(code, 0)
        self.assertIn("start_time", fake.posts[0][1])
        self.assertEqual(fake.posts[0][1]["execution_options"], ["validate_only"])


class TargetingValidateOnly(unittest.TestCase):
    ARGV = ["--ids", "5", "--age-min", "25", "--confirm", "TARGETING", "--validate-only"]

    def test_full_targeting_is_validated_not_applied(self) -> None:
        fake = ValidateAware({"5": dict(ADSET)})
        code, out, _ = run_main(edit_targeting, self.ARGV, fake)
        self.assertEqual(code, 0)
        (path, payload), = fake.posts
        self.assertEqual(payload["execution_options"], ["validate_only"])
        self.assertEqual(payload["targeting"]["age_min"], 25)
        self.assertEqual(fake.nodes["5"]["targeting"]["age_min"], 21)
        self.assertTrue(last_json(out)["results"][0]["validated"])

    def test_rejection_fails_the_row(self) -> None:
        fake = FailingValidate({"5": dict(ADSET)})
        code, out, _ = run_main(edit_targeting, self.ARGV, fake)
        self.assertEqual(code, 1)
        self.assertFalse(last_json(out)["results"][0]["validated"])


class AgeRangeFollowsBounds(unittest.TestCase):
    """Live validate_only 29/09 on an Advantage+ ad set: age_min 21 -> 25 with the derived age_range still
    [21, 65] is rejected (code 100 / 1359201). The merge must pull the window inside the new bounds."""

    BASE = {"age_min": 21, "age_max": 65, "age_range": [21, 65]}

    def test_raising_age_min_pulls_the_window_up(self) -> None:
        after = edit_targeting.merge_targeting(self.BASE, {"age_min": 25})
        self.assertEqual(after["age_range"], [25, 65])

    def test_lowering_age_max_pulls_the_window_down(self) -> None:
        after = edit_targeting.merge_targeting(self.BASE, {"age_max": 60})
        self.assertEqual(after["age_range"], [21, 60])

    def test_window_that_no_longer_fits_is_dropped(self) -> None:
        after = edit_targeting.merge_targeting({"age_min": 21, "age_max": 30, "age_range": [21, 30]}, {"age_min": 40, "age_max": 45})
        self.assertNotIn("age_range", after)

    def test_untouched_when_age_is_not_edited(self) -> None:
        after = edit_targeting.merge_targeting(self.BASE, {"genders": [1]})
        self.assertEqual(after["age_range"], [21, 65])

    def test_no_window_no_key(self) -> None:
        after = edit_targeting.merge_targeting({"age_min": 21, "age_max": 65}, {"age_min": 25})
        self.assertNotIn("age_range", after)


class SourcingSpecModes(unittest.TestCase):
    SPEC = {"brand": {"enroll_status": "OPT_OUT"}, "enable_social_feedback_preservation": True,
            "featured_offering_spec": {"enroll_status": "OPT_IN", "default_status": "OPT_IN"}}

    def test_drop_omits_it(self) -> None:
        self.assertIsNone(edit_tags._sourcing_spec_for("drop", self.SPEC))

    def test_opt_out_flips_every_opt_in_and_keeps_the_rest(self) -> None:
        out = edit_tags._sourcing_spec_for("opt_out", self.SPEC)
        self.assertEqual(out["featured_offering_spec"]["enroll_status"], "OPT_OUT")
        self.assertTrue(out["enable_social_feedback_preservation"])
        self.assertEqual(self.SPEC["featured_offering_spec"]["enroll_status"], "OPT_IN")  # source untouched

    def test_flag_only_carries_just_the_preservation_flag(self) -> None:
        out = edit_tags._sourcing_spec_for("flag_only", self.SPEC)
        self.assertEqual(out, {"featured_offering_spec": {"enroll_status": "OPT_OUT"},
                               "enable_social_feedback_preservation": True})
        self.assertEqual(edit_tags._sourcing_spec_for("flag_only", {"brand": {}}),
                         {"featured_offering_spec": {"enroll_status": "OPT_OUT"}})


AD = {
    "name": "EN0038-<buyer>-1", "account_id": "1", "effective_status": "ACTIVE",
    "creative": {"id": "77", "name": "c", "url_tags": "a=b", "object_story_spec": {
        "page_id": "2", "link_data": {"message": "hi", "link": "https://x.test/", "name": "Read before you judge"}},
        "creative_sourcing_spec": {"featured_offering_spec": {"enroll_status": "OPT_IN"},
                                   "enable_social_feedback_preservation": True}},
}


class CreativeValidateOnly(unittest.TestCase):
    ARGV = ["--ids", "9", "--enhancements-off", "--confirm", "TAGS", "--validate-only"]

    def test_creative_is_validated_and_nothing_is_swapped(self) -> None:
        fake = ValidateAware({"9": dict(AD)})
        code, out, _ = run_main(edit_tags, self.ARGV + ["--sourcing-mode", "flag_only"], fake)
        self.assertEqual(code, 0)
        (path, payload), = fake.posts
        self.assertEqual(path, "act_1/adcreatives")
        self.assertEqual(payload["execution_options"], ["validate_only"])
        self.assertEqual(payload["creative_sourcing_spec"]["enable_social_feedback_preservation"], True)
        self.assertTrue(last_json(out)["results"][0]["validated"])

    def test_default_mode_still_drops_the_spec(self) -> None:
        fake = ValidateAware({"9": dict(AD)})
        run_main(edit_tags, self.ARGV, fake)
        self.assertNotIn("creative_sourcing_spec", fake.posts[0][1])

    def test_rejected_creative_fails_the_row(self) -> None:
        fake = FailingValidate({"9": dict(AD)})
        code, out, _ = run_main(edit_tags, self.ARGV, fake)
        self.assertEqual(code, 1)
        self.assertFalse(last_json(out)["results"][0]["validated"])


class WrapperForwardsFlag(WrapperBase):
    def _child_args(self, argv: list[str]) -> list[str]:
        _, _, run_child = self.run_wrapper(argv)
        return list(run_child.call_args[0][1])

    def test_bid_targeting_schedule_budget_rename_forward_it(self) -> None:
        cases = [
            ["edit", "bid", "--ids", "5", "--bid-minor", "100", "--confirm", "BID", "--validate-only"],
            ["edit", "schedule", "--ids", "5", "--start-time", "2099-01-01T08:00:00-07:00", "--confirm", "SCHEDULE", "--validate-only"],
            ["edit", "targeting", "--ids", "5", "--age-min", "25", "--confirm", "TARGETING", "--validate-only"],
            ["edit", "budget", "--ids", "5", "--budget-pct", "-10", "--validate-only"],
            ["edit", "rename", "--ids", "5", "--name", "X", "--validate-only"],
            ["edit", "creative", "--ids", "5", "--enhancements-off", "--confirm", "TAGS", "--validate-only"],
        ]
        for argv in cases:
            with self.subTest(argv[1]):
                self.assertIn("--validate-only", self._child_args(argv))

    def test_flag_absent_by_default(self) -> None:
        self.assertNotIn("--validate-only", self._child_args(
            ["edit", "bid", "--ids", "5", "--bid-minor", "100", "--confirm", "BID", "--dry-run"]))


if __name__ == "__main__":
    unittest.main()

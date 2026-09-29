#!/usr/bin/env python3
"""Offline regression tests for the launch-path fixes (placements, bid policy, longread lint,
account gate, reused-campaign staging, spec hygiene, bulk/media/mutate_set/comments).

Everything is mocked; nothing here touches the network or the Graph API.
"""

from __future__ import annotations
import os as _os, tempfile as _tempfile
_os.environ["METAOPS_PACE_DIR"] = _tempfile.mkdtemp(prefix="metaops-pace-test-")
_os.environ.setdefault("METAOPS_CREATE_GAP_HOURS", "0")
_os.environ.setdefault("META_TOKEN", "TEST_TOKEN")

import contextlib
import copy
import inspect
import io
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

import bulk
import comments
import launch
import media
import mutate_set

HERE = pathlib.Path(__file__).resolve().parent

ALL_FB = ["feed", "instream_video", "marketplace", "story", "search", "biz_disco_feed",
          "facebook_reels", "facebook_reels_overlay", "profile_feed", "notification"]
ALL_IG = ["stream", "story", "reels", "explore_home", "profile_feed", "ig_search"]


def adset_dict(i: int = 0, **over) -> dict:
    a = {
        "name": f"Ad set {i}",
        "optimization_goal": "OFFSITE_CONVERSIONS",
        "custom_event_type": "COMPLETE_REGISTRATION",
        "start_time": "2030-01-01T08:00:00+00:00",
        "targeting": {"geo_locations": {"countries": ["US"]}, "advantage_audience": False},
        "ads": [{"name": f"ad-{i}", "creative": {
            "kind": "link_image", "image_hash": f"hash{i}", "link": "https://example.com/",
            "message": "story", "headline": "Read before you judge", "cta": "SEE_DETAILS"}}],
    }
    a.update(over)
    return a


def base_spec(adsets: int = 1, **top) -> dict:
    spec = {
        "run_id": "fix-test", "account_id": "act_1", "page_id": "2", "pixel_id": "3",
        "currency": "USD",
        "campaign": {"name": "Campaign", "objective": "OUTCOME_SALES",
                     "special_ad_categories": [], "daily_budget_minor": 6000},
        "adsets": [adset_dict(i) for i in range(adsets)],
    }
    spec.update(top)
    return spec


class TmpCase(unittest.TestCase):
    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.root = pathlib.Path(self._td.name)

    def write(self, obj: object, name: str = "spec.json") -> pathlib.Path:
        path = self.root / name
        path.write_text(json.dumps(obj), encoding="utf-8")
        return path

    def load(self, spec: dict) -> dict:
        return launch.load_spec(str(self.write(spec)))


class PlacementTests(TmpCase):
    def targeting(self, **aset_over) -> dict:
        aset = adset_dict(0, **aset_over)
        return launch.build_targeting(aset)

    def test_fb_ig_all_preset_is_the_exact_position_lists(self) -> None:
        t = self.targeting(placements="fb_ig_all")
        self.assertEqual(t["publisher_platforms"], ["facebook", "instagram"])
        self.assertEqual(t["facebook_positions"], ALL_FB)
        self.assertEqual(t["instagram_positions"], ALL_IG)
        for key in ("messenger_positions", "audience_network_positions", "threads_positions"):
            self.assertNotIn(key, t)

    def test_fb_ig_feeds_preset(self) -> None:
        t = self.targeting(placements="fb_ig_feeds")
        self.assertEqual(t["publisher_platforms"], ["facebook", "instagram"])
        self.assertEqual(t["facebook_positions"], ["feed"])
        self.assertEqual(t["instagram_positions"], ["stream"])

    def test_explicit_targeting_keys_win_over_the_preset(self) -> None:
        aset = adset_dict(0, placements="fb_ig_all")
        aset["targeting"]["instagram_positions"] = ["reels"]
        aset["targeting"]["publisher_platforms"] = ["facebook", "instagram"]
        t = launch.build_targeting(aset)
        self.assertEqual(t["instagram_positions"], ["reels"])
        self.assertEqual(t["facebook_positions"], ALL_FB)

    def test_explicit_narrower_platform_list_drops_the_other_platforms_positions(self) -> None:
        aset = adset_dict(0, placements="fb_ig_all")
        aset["targeting"]["publisher_platforms"] = ["instagram"]
        t = launch.build_targeting(aset)
        self.assertEqual(t["publisher_platforms"], ["instagram"])
        self.assertNotIn("facebook_positions", t)
        self.assertEqual(t["instagram_positions"], ALL_IG)

    def test_unknown_preset_is_a_spec_error(self) -> None:
        with self.assertRaisesRegex(launch.SpecError, "placements must be one of"):
            self.load(base_spec(adsets=1) | {"adsets": [adset_dict(0, placements="everything")]})

    def test_load_spec_accepts_a_preset(self) -> None:
        spec = self.load(base_spec() | {"adsets": [adset_dict(0, placements="fb_ig_all")]})
        self.assertEqual(spec["adsets"][0]["placements"], "fb_ig_all")

    def test_positions_for_an_untargeted_platform_are_an_error(self) -> None:
        aset = adset_dict(0)
        aset["targeting"].update({"publisher_platforms": ["instagram"], "facebook_positions": ["feed"]})
        with self.assertRaisesRegex(launch.SpecError, "facebook_positions.*not in publisher_platforms"):
            self.load(base_spec() | {"adsets": [aset]})

    def test_positions_without_any_platform_list_are_an_error(self) -> None:
        aset = adset_dict(0)
        aset["targeting"]["instagram_positions"] = ["stream"]
        with self.assertRaisesRegex(launch.SpecError, "instagram_positions"):
            self.load(base_spec() | {"adsets": [aset]})

    def test_targeted_platform_with_empty_positions_is_an_error(self) -> None:
        aset = adset_dict(0)
        aset["targeting"].update({"publisher_platforms": ["facebook", "instagram"],
                                  "facebook_positions": []})
        with self.assertRaisesRegex(launch.SpecError, "non-empty list of positions"):
            self.load(base_spec() | {"adsets": [aset]})

    def test_instagram_is_still_mandatory(self) -> None:
        aset = adset_dict(0)
        aset["targeting"]["publisher_platforms"] = ["facebook"]
        with self.assertRaisesRegex(launch.SpecError, "must include 'instagram'"):
            self.load(base_spec() | {"adsets": [aset]})

    def test_omitted_publisher_platforms_is_a_plan_warning(self) -> None:
        spec = self.load(base_spec())
        text = "\n".join(launch.spec_warnings(spec))
        self.assertIn("publisher_platforms is omitted", text)
        self.assertIn("Audience Network", text)

    def test_pinned_placements_raise_no_placement_warning(self) -> None:
        spec = self.load(base_spec() | {"adsets": [adset_dict(0, placements="fb_ig_feeds")]})
        self.assertNotIn("publisher_platforms is omitted", "\n".join(launch.spec_warnings(spec)))

    def test_main_prints_the_warning_before_running(self) -> None:
        path = self.write(base_spec())
        err = io.StringIO()
        with (
            mock.patch.object(sys, "argv", ["launch.py", "--spec", str(path), "--dry-run",
                                            "--state", str(self.root / "st.json")]),
            mock.patch.object(launch.graph, "require_write_authority"),
            mock.patch.object(launch, "run"),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(err),
        ):
            self.assertEqual(launch.main(), 0)
        self.assertIn("WARNING: adsets[0]: publisher_platforms is omitted", err.getvalue())


class BidPolicyTests(TmpCase):
    def cbo(self, strategy: str | None, amount: int | None, policy: str | None = "require_cap") -> dict:
        spec = base_spec(adsets=2)
        if strategy:
            spec["campaign"]["bid_strategy"] = strategy
        if policy:
            spec["campaign"]["bid_policy"] = policy
        for a in spec["adsets"]:
            if amount:
                a["bid_amount_minor"] = amount
        return spec

    def test_require_cap_rejects_an_uncapped_cbo_campaign(self) -> None:
        with self.assertRaisesRegex(launch.SpecError, "require_cap.*campaign.bid_strategy"):
            self.load(self.cbo(None, None))

    def test_require_cap_rejects_a_cap_strategy_without_an_amount(self) -> None:
        with self.assertRaises(launch.SpecError):
            self.load(self.cbo("LOWEST_COST_WITH_BID_CAP", None))

    def test_require_cap_rejects_an_amount_without_a_cap_strategy(self) -> None:
        with self.assertRaisesRegex(launch.SpecError, "carries no cap"):
            self.load(self.cbo("LOWEST_COST_WITHOUT_CAP", 20000))

    def test_require_cap_accepts_a_capped_spec(self) -> None:
        spec = self.load(self.cbo("LOWEST_COST_WITH_BID_CAP", 20000))
        self.assertEqual(launch.bid_policy(spec, spec["adsets"][0]), "require_cap")
        spec = self.load(self.cbo("COST_CAP", 5000))
        self.assertEqual(spec["budget_mode"], "CBO")

    def test_require_cap_at_ad_set_level_under_abo(self) -> None:
        spec = base_spec(adsets=2)
        del spec["campaign"]["daily_budget_minor"]
        for a in spec["adsets"]:
            a["daily_budget_minor"] = 3000
        spec["adsets"][1]["bid_policy"] = "require_cap"
        with self.assertRaisesRegex(launch.SpecError, r"adsets\[1\].bid_strategy=LOWEST_COST_WITHOUT_CAP"):
            self.load(spec)
        spec["adsets"][1].update({"bid_strategy": "COST_CAP", "bid_amount_minor": 900})
        self.load(spec)  # ad set 0 has no policy and stays uncapped: allowed

    def test_unknown_policy_value_is_rejected(self) -> None:
        with self.assertRaisesRegex(launch.SpecError, "bid_policy"):
            self.load(self.cbo("LOWEST_COST_WITH_BID_CAP", 100, policy="cap_maybe"))

    def purchase_spec(self, **camp) -> dict:
        spec = base_spec(adsets=2)
        spec["campaign"].update(camp)
        for a in spec["adsets"]:
            a["custom_event_type"] = "PURCHASE"
        return spec

    def test_uncapped_purchase_warns_once_for_a_cbo_campaign(self) -> None:
        spec = self.load(self.purchase_spec())
        hits = [w for w in launch.spec_warnings(spec) if "LOWEST_COST_WITHOUT_CAP" in w]
        self.assertEqual(len(hits), 1, hits)
        self.assertIn("adsets[0,1]", hits[0])
        self.assertIn("PURCHASE", hits[0])

    def test_capped_purchase_does_not_warn_about_the_bid(self) -> None:
        spec = self.purchase_spec(bid_strategy="LOWEST_COST_WITH_BID_CAP")
        for a in spec["adsets"]:
            a["bid_amount_minor"] = 20000
        text = "\n".join(launch.spec_warnings(self.load(spec)))
        self.assertNotIn("LOWEST_COST_WITHOUT_CAP", text)

    def test_purchase_without_attribution_warns_and_explicit_attribution_does_not(self) -> None:
        text = "\n".join(launch.spec_warnings(self.load(self.purchase_spec())))
        self.assertIn("PURCHASE without an explicit `attribution`", text)
        self.assertIn("7d click / 1d view", text)
        spec = self.purchase_spec()
        for a in spec["adsets"]:
            a["attribution"] = {"click_days": 7, "view_days": 1}
        self.assertNotIn("without an explicit", "\n".join(launch.spec_warnings(self.load(spec))))

    def test_non_purchase_registration_goal_gets_no_attribution_warning(self) -> None:
        text = "\n".join(launch.spec_warnings(self.load(base_spec())))
        self.assertNotIn("PURCHASE", text)

    def test_campaign_bid_amount_minor_is_rejected_with_a_clear_message(self) -> None:
        spec = base_spec()
        spec["campaign"]["bid_amount_minor"] = 500
        with self.assertRaisesRegex(launch.SpecError, "campaign.bid_amount_minor is not a campaign field"):
            self.load(spec)


class LintTests(TmpCase):
    def spec_with(self, lint: str | None = None, **creative) -> dict:
        spec = base_spec()
        spec["adsets"][0]["ads"][0]["creative"].update(creative)
        if lint:
            spec["lint"] = lint
        return spec

    def warnings(self, spec: dict) -> str:
        return "\n".join(launch.spec_warnings(self.load(spec)))

    def test_clean_longread_copy_raises_nothing(self) -> None:
        for headline in ("Read before you judge", "Sunset Downs"):
            spec = self.spec_with("strict", headline=headline)
            text = self.warnings(spec)
            self.assertNotIn("lint:", text)

    def test_long_headline_warns_by_default_and_errors_in_strict(self) -> None:
        headline = "x" * 41
        self.assertIn("41 chars", self.warnings(self.spec_with(headline=headline)))
        self.assertEqual(launch.lint_findings(self.load(self.spec_with(headline="x" * 40))), [])
        with self.assertRaisesRegex(launch.SpecError, "41 chars"):
            self.load(self.spec_with("strict", headline=headline))

    def test_offer_phrases_in_headline_or_description(self) -> None:
        cases = [
            ("headline", "$2000 Welcome Bonus"), ("headline", "Get exclusive access"),
            ("headline", "Offer valid today"), ("description", "valid until Friday"),
            ("description", "PLAY ONLINE now"), ("headline", "50 free spins"),
            ("headline", "Deposit match"), ("headline", "Casino nights"),
            ("description", "The Jackpot story"), ("headline", "Win $50 with a big bonus"),
        ]
        for field, text in cases:
            spec = self.spec_with(**{field: text})
            self.assertIn("lint:", self.warnings(spec), f"{field}={text!r} not flagged")
            with self.assertRaises(launch.SpecError, msg=f"{field}={text!r} not an error in strict"):
                self.load(self.spec_with("strict", **{field: text}))

    def test_neutral_headlines_are_not_flagged(self) -> None:
        for text in ("Read before you judge", "Check this out!", "I claimed nothing", "An exclusive look"):
            self.assertEqual(launch.lint_findings(self.load(self.spec_with(headline=text))), [], text)

    def test_dollar_amount_far_from_the_word_bonus_is_not_flagged(self) -> None:
        text = self.warnings(self.spec_with(headline="$50 " + "a" * 30 + " bonus"))
        self.assertNotIn("banned wording", text)
        text = self.warnings(self.spec_with(description="I paid $50 and it was a long story about my bonus"))
        self.assertNotIn("banned wording", text)

    def test_message_body_is_not_linted(self) -> None:
        spec = self.spec_with("strict", message="I got a $2000 welcome bonus at the casino, jackpot!")
        self.assertEqual(launch.lint_findings(self.load(spec)), [])

    def test_strict_requires_headline_and_message(self) -> None:
        with self.assertRaisesRegex(launch.SpecError, "headline is empty"):
            self.load(self.spec_with("strict", headline=""))
        with self.assertRaisesRegex(launch.SpecError, "message is empty"):
            self.load(self.spec_with("strict", message="  "))
        # default mode keeps accepting an empty headline / message
        self.load(self.spec_with(None, headline="", message=""))

    def test_lint_value_is_validated(self) -> None:
        with self.assertRaisesRegex(launch.SpecError, "spec.lint"):
            self.load(self.spec_with("loose"))

    def test_carousel_card_headlines_are_linted_and_catalog_is_not(self) -> None:
        spec = base_spec()
        spec["adsets"][0]["ads"][0]["creative"] = {
            "kind": "link_carousel", "link": "https://example.com/", "message": "m",
            "cards": [{"image_hash": "a", "headline": "Casino"}, {"image_hash": "b", "headline": "ok"}]}
        self.assertIn("cards[0].headline", self.warnings(spec))
        spec["adsets"][0]["ads"][0]["creative"] = {
            "kind": "catalog_single", "link": "https://example.com/", "product_set_id": "1",
            "headline": "Casino {{product.name}}"}
        self.assertNotIn("lint:", self.warnings(spec))

    def test_display_link_on_link_video(self) -> None:
        spec = base_spec()
        spec["adsets"][0]["ads"][0]["creative"] = {
            "kind": "link_video", "video_id": "9", "image_hash": "t", "link": "https://example.com/",
            "message": "m", "headline": "h", "display_link": "example.com"}
        loaded = self.load(spec)
        ad = loaded["adsets"][0]["ads"][0]
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            payload = launch.build_creative(loaded, ad, None)
        self.assertIn("display_link", err.getvalue())
        self.assertNotIn("caption", payload["object_story_spec"]["video_data"])
        spec["lint"] = "strict"
        with self.assertRaisesRegex(launch.SpecError, "display_link has no place on a link_video"):
            self.load(spec)
        strict_loaded = copy.deepcopy(loaded)
        strict_loaded["lint"] = "strict"
        with self.assertRaisesRegex(launch.SpecError, "link_video"):
            launch.build_creative(strict_loaded, strict_loaded["adsets"][0]["ads"][0], None)


class RunHarness(TmpCase):
    """Drive launch.run() with the network mocked out and every event recorded in order."""

    def run_launch(self, spec: dict, state, fail_on: str | None = None, post_error=None, dry=False):
        events: list[tuple] = []

        def fake_create(node, path, payload, st, dry_run):
            if node == fail_on:
                raise SystemExit(1)
            cached = st.get(node)
            if cached:
                return cached
            events.append(("create", node, payload))
            kind = node.split("[")[0]
            idx = node.split("[")[1].rstrip("]") if "[" in node else ""
            obj_id = {"campaign": "C1", "adset": f"S{idx}", "creative": f"K{idx}", "ad": f"A{idx}"}[kind]
            st.put(node, obj_id)
            return obj_id

        def fake_post(path, data=None, **kw):
            events.append(("post", path, data))
            if post_error is not None and data == {"status": "ACTIVE"} and post_error(path):
                raise launch.graph.GraphError(400, {"error": {"message": "nope", "code": 100}}, "x")
            return {"success": True}

        with (
            mock.patch.object(launch, "account_currency", return_value="USD"),
            mock.patch.object(launch, "resolve_identity",
                              side_effect=lambda sp, create=True: "17841400000000000"
                              if sp.get("instagram_user_id") else None),
            mock.patch.object(launch, "_create", side_effect=fake_create),
            mock.patch.object(launch.graph, "post", side_effect=fake_post),
            mock.patch.object(launch.graph, "check_campaign_create_pace"),
            mock.patch.object(launch.graph, "record_campaign_create"),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            try:
                launch.run(spec, state, dry)
            finally:
                self.events = events
        return events

    @staticmethod
    def flips(events) -> list[str]:
        return [e[1] for e in events if e[0] == "post" and e[2] == {"status": "ACTIVE"}]

    @staticmethod
    def order(events) -> list[str]:
        return [e[1] if e[0] == "create" else f"flip:{e[1]}" for e in events
                if e[0] == "create" or e[2] == {"status": "ACTIVE"}]


class ReusedCampaignStagingTests(RunHarness):
    def reused(self, adsets: int = 2, **top) -> dict:
        raw = base_spec(adsets=adsets, **top)
        raw["campaign"]["id"] = "777"
        return self.load(raw)

    def test_adsets_are_created_paused_and_flipped_after_their_ads(self) -> None:
        spec = self.reused()
        state = launch.State(str(self.root / "st.json"))
        events = self.run_launch(spec, state)
        created = {e[1]: e[2] for e in events if e[0] == "create"}
        self.assertEqual(created["adset[0]"]["status"], "PAUSED")
        self.assertEqual(created["adset[1]"]["status"], "PAUSED")
        self.assertEqual(created["ad[0.0]"]["status"], "ACTIVE")
        self.assertEqual(
            self.order(events),
            ["adset[0]", "creative[0.0]", "ad[0.0]", "flip:S0",
             "adset[1]", "creative[1.0]", "ad[1.0]", "flip:S1"])
        self.assertEqual(state.data["adsets_activated"], {"adset[0]": "S0", "adset[1]": "S1"})
        self.assertNotIn("777", self.flips(events))  # the live campaign itself is never posted

    def test_failure_mid_run_leaves_only_complete_adsets_live(self) -> None:
        spec = self.reused()
        state = launch.State(str(self.root / "st.json"))
        with self.assertRaises(SystemExit):
            self.run_launch(spec, state, fail_on="ad[1.0]")
        self.assertEqual(self.flips(self.events), ["S0"])
        created = {e[1]: e[2] for e in self.events if e[0] == "create"}
        self.assertEqual(created["adset[1]"]["status"], "PAUSED")
        self.assertNotIn("adset[1]", state.data.get("adsets_activated", {}))

    def test_resume_flips_only_what_is_left_and_only_once(self) -> None:
        spec = self.reused()
        path = str(self.root / "st.json")
        with self.assertRaises(SystemExit):
            self.run_launch(spec, launch.State(path), fail_on="ad[1.0]")
        events = self.run_launch(spec, launch.State(path))
        self.assertEqual([e[1] for e in events if e[0] == "create"], ["ad[1.0]"])
        self.assertEqual(self.flips(events), ["S1"])
        again = self.run_launch(spec, launch.State(path))
        self.assertEqual(self.flips(again), [])

    def test_flip_failure_is_recorded_and_retried_alone(self) -> None:
        spec = self.reused(adsets=1)
        path = str(self.root / "st.json")
        with self.assertRaises(SystemExit):
            self.run_launch(spec, launch.State(path), post_error=lambda p: p == "S0")
        state = launch.State(path)
        self.assertEqual(state.data["errors"][-1]["key"], "adset_activate[0]")
        self.assertNotIn("adsets_activated", state.data)
        events = self.run_launch(spec, launch.State(path))
        self.assertEqual([e for e in events if e[0] == "create"], [])
        self.assertEqual(self.flips(events), ["S0"])

    def test_default_new_campaign_path_is_unchanged(self) -> None:
        spec = self.load(base_spec(adsets=2))
        state = launch.State(str(self.root / "st.json"))
        events = self.run_launch(spec, state)
        created = {e[1]: e[2] for e in events if e[0] == "create"}
        self.assertEqual(created["campaign"]["status"], "PAUSED")
        self.assertEqual(created["adset[0]"]["status"], "ACTIVE")
        self.assertEqual(created["ad[1.0]"]["status"], "ACTIVE")
        self.assertEqual(self.flips(events), ["C1"])  # only the campaign flip, and it is last
        self.assertEqual(events[-1][1], "C1")
        self.assertNotIn("adsets_activated", state.data)

    def test_paused_override_on_a_reused_campaign_flips_nothing(self) -> None:
        spec = self.reused(create_status="PAUSED")
        events = self.run_launch(spec, launch.State(str(self.root / "st.json")))
        created = {e[1]: e[2] for e in events if e[0] == "create"}
        self.assertEqual(created["adset[0]"]["status"], "PAUSED")
        self.assertEqual(self.flips(events), [])

    def test_dry_run_posts_nothing(self) -> None:
        spec = self.reused()
        events = self.run_launch(spec, launch.State(str(self.root / "st.json")), dry=True)
        self.assertEqual([e for e in events if e[0] == "post"], [])

    def test_live_summary_counts_flipped_adsets_of_a_reused_campaign(self) -> None:
        spec = self.reused()
        path = str(self.root / "st.json")
        with self.assertRaises(SystemExit):
            self.run_launch(spec, launch.State(path), fail_on="ad[1.0]")
        text = launch.live_summary(spec, launch.State(path))
        self.assertIn("1 ad set(s) ACTIVE (1 still PAUSED", text)


class AccountGateTests(RunHarness):
    def acct(self, **fields) -> dict:
        return {"currency": "USD", "timezone_name": "America/New_York", "account_status": 1,
                "disable_reason": 0, **fields}

    def test_one_get_reads_status_and_disable_reason_with_the_currency(self) -> None:
        spec = self.load(base_spec())
        with mock.patch.object(launch.graph, "get", return_value=self.acct()) as get, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(launch.account_currency(spec), "USD")
        fields = get.call_args.kwargs["params"]["fields"].split(",")
        self.assertEqual(get.call_count, 1)
        for f in ("currency", "account_status", "disable_reason"):
            self.assertIn(f, fields)

    def test_non_active_account_is_refused_with_the_reason(self) -> None:
        spec = self.load(base_spec())
        for status in (2, 3, 7, 9, 101):
            with mock.patch.object(launch.graph, "get",
                                   return_value=self.acct(account_status=status, disable_reason=1)):
                with self.assertRaisesRegex(launch.SpecError, rf"account_status={status}.*disable_reason=1"):
                    launch.account_currency(spec)

    def test_run_creates_nothing_and_writes_no_state_for_a_disabled_account(self) -> None:
        spec = self.load(base_spec())
        path = self.root / "st.json"
        with (
            mock.patch.object(launch.graph, "get", return_value=self.acct(account_status=2, disable_reason=1)),
            mock.patch.object(launch, "resolve_identity", return_value=None),
            mock.patch.object(launch, "_create") as create,
            mock.patch.object(launch.graph, "post") as post,
            self.assertRaisesRegex(launch.SpecError, "not active"),
        ):
            launch.run(spec, launch.State(str(path)), False)
        create.assert_not_called()
        post.assert_not_called()
        self.assertFalse(path.exists())


class HygieneTests(TmpCase):
    def test_spend_target_and_cap_must_be_integer_minor_units(self) -> None:
        for key, bad in (("daily_min_spend_target", 12.5), ("daily_spend_cap", "600"),
                         ("daily_spend_cap", 0), ("daily_min_spend_target", True)):
            spec = base_spec()
            spec["adsets"][0][key] = bad
            with self.assertRaisesRegex(launch.SpecError, rf"adsets\[0\].{key}", msg=f"{key}={bad!r}"):
                self.load(spec)
        spec = base_spec()
        spec["adsets"][0].update({"daily_min_spend_target": 500, "daily_spend_cap": 900})
        self.load(spec)

    def test_abo_bid_amount_is_validated_at_load_time(self) -> None:
        spec = base_spec()
        del spec["campaign"]["daily_budget_minor"]
        spec["adsets"][0].update({"daily_budget_minor": 3000, "bid_strategy": "COST_CAP",
                                  "bid_amount_minor": 12.5})
        with self.assertRaisesRegex(launch.SpecError, r"adsets\[0\].bid_amount_minor must be an INTEGER"):
            self.load(spec)
        spec["adsets"][0]["bid_amount_minor"] = "900"
        with self.assertRaisesRegex(launch.SpecError, "INTEGER"):
            self.load(spec)
        spec["adsets"][0]["bid_amount_minor"] = 900
        self.load(spec)

    def test_advantage_audience_must_be_a_real_boolean_or_0_1(self) -> None:
        for bad in ("false", "true", "0", None, 2, 1.0, [], "no"):
            aset = adset_dict(0)
            aset["targeting"]["advantage_audience"] = bad
            with self.assertRaisesRegex(launch.SpecError, "advantage_audience must be true/false",
                                        msg=repr(bad)):
                self.load(base_spec() | {"adsets": [aset]})
        for good, flag in ((True, 1), (False, 0), (1, 1), (0, 0)):
            aset = adset_dict(0)
            aset["targeting"]["advantage_audience"] = good
            self.assertEqual(
                launch.build_targeting(aset)["targeting_automation"]["advantage_audience"], flag)

    def test_nested_advantage_audience_is_validated_too(self) -> None:
        aset = adset_dict(0)
        del aset["targeting"]["advantage_audience"]
        aset["targeting"]["targeting_automation"] = {"advantage_audience": "false"}
        with self.assertRaisesRegex(launch.SpecError, "advantage_audience must be true/false"):
            self.load(base_spec() | {"adsets": [aset]})

    def test_spend_target_reaches_the_adset_payload_as_an_int(self) -> None:
        raw = base_spec()
        raw["adsets"][0]["daily_spend_cap"] = 900
        spec = self.load(raw)
        seen = {}

        def fake_create(node, path, payload, st, dry):
            seen[node.split("[")[0]] = payload
            return "1"

        with (
            mock.patch.object(launch, "account_currency", return_value="USD"),
            mock.patch.object(launch, "resolve_identity", return_value=None),
            mock.patch.object(launch, "_create", side_effect=fake_create),
            mock.patch.object(launch.graph, "post", return_value={}),
            mock.patch.object(launch.graph, "check_campaign_create_pace"),
            mock.patch.object(launch.graph, "record_campaign_create"),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            launch.run(spec, launch.State(str(self.root / "s.json")), False)
        self.assertEqual(seen["adset"]["daily_spend_cap"], 900)

    def test_no_reference_to_the_deprecated_create_pbia_command_remains(self) -> None:
        self.assertNotIn("create-pbia", inspect.getsource(launch))

    def test_auto_identity_without_a_pbia_stops_with_the_ui_instructions(self) -> None:
        spec = self.load(base_spec() | {"instagram_user_id": "auto"})
        with (
            mock.patch.object(launch, "account_currency", return_value="USD"),
            mock.patch.object(launch, "resolve_identity", return_value=None),
            self.assertRaisesRegex(launch.SpecError, r"Use Facebook Page"),
        ):
            launch.run(spec, launch.State(str(self.root / "s.json")), True)

    def test_resolve_identity_message_points_to_the_ui_not_a_dead_command(self) -> None:
        spec = base_spec() | {"instagram_user_id": "auto"}
        with (
            mock.patch.object(launch.graph, "page_token", return_value="pt"),
            mock.patch.object(launch.graph, "call", return_value={}),
            self.assertRaises(SystemExit) as ctx,
        ):
            launch.resolve_identity(spec)
        self.assertIn("Use Facebook Page", str(ctx.exception))
        self.assertNotIn("create-pbia", str(ctx.exception))


class OptInFeatureOptionTests(unittest.TestCase):
    def test_resolved_opt_out_matches_what_finish_sends(self) -> None:
        c = {"kind": "link_image"}
        self.assertEqual(launch.resolved_opt_out(c), launch.DEFAULT_OPT_OUT)
        payload = launch._finish({}, c)
        sent = list(payload["degrees_of_freedom_spec"]["creative_features_spec"])
        self.assertEqual(sent, launch.DEFAULT_OPT_OUT)

    def test_product_video_drops_media_type_automation_on_catalog_only(self) -> None:
        cat = {"kind": "catalog_single", "product_video": True}
        self.assertNotIn("media_type_automation", launch.resolved_opt_out(cat))
        self.assertIn("media_type_automation", launch.resolved_opt_out({"kind": "link_image", "product_video": True}))

    def test_opt_in_features_are_removed_from_the_opt_out_list(self) -> None:
        got = launch.resolved_opt_out({"kind": "link_image", "opt_in_features": ["image_animation"]})
        self.assertNotIn("image_animation", got)
        self.assertEqual(len(got), len(launch.DEFAULT_OPT_OUT) - 1)
        with self.assertRaises(launch.SpecError):
            launch.resolved_opt_out({"opt_in_features": "image_animation"})


class ExampleSpecTests(RunHarness):
    PATH = HERE / "specs" / "example-us-longread-cbo.json"

    def test_example_loads_without_warnings_and_matches_the_brief(self) -> None:
        spec = launch.load_spec(str(self.PATH))
        self.assertEqual(spec["budget_mode"], "CBO")
        self.assertEqual(spec["lint"], "strict")
        camp = spec["campaign"]
        self.assertEqual(camp["daily_budget_minor"], 6000)
        self.assertEqual(camp["bid_strategy"], "LOWEST_COST_WITH_BID_CAP")
        self.assertEqual(camp["bid_policy"], "require_cap")
        self.assertEqual(len(spec["adsets"]), 5)
        names, hashes = set(), set()
        for aset in spec["adsets"]:
            self.assertEqual(aset["bid_amount_minor"], 20000)
            self.assertEqual(aset["custom_event_type"], "PURCHASE")
            self.assertEqual(aset["attribution"], {"click_days": 7, "view_days": 1})
            self.assertEqual(aset["placements"], "fb_ig_all")
            self.assertFalse(aset["targeting"]["advantage_audience"])
            self.assertEqual((aset["targeting"]["age_min"], aset["targeting"]["age_max"]), (21, 65))
            self.assertEqual(len(aset["ads"]), 1)
            c = aset["ads"][0]["creative"]
            self.assertEqual(c["kind"], "link_image")
            self.assertEqual(c["headline"], "Read before you judge")
            self.assertEqual(c["cta"], "SEE_DETAILS")
            self.assertEqual(c["display_link"], "example.com")
            names.add(aset["ads"][0]["name"])
            hashes.add(c["image_hash"])
        self.assertEqual((len(names), len(hashes)), (5, 5))
        self.assertEqual(launch.spec_warnings(spec), [])

    def test_example_builds_every_payload_offline(self) -> None:
        spec = launch.load_spec(str(self.PATH))
        aset = spec["adsets"][0]
        t = launch.build_targeting(aset)
        self.assertEqual(t["publisher_platforms"], ["facebook", "instagram"])
        self.assertEqual(t["facebook_positions"], ALL_FB)
        self.assertEqual(launch.build_attribution(aset), [
            {"event_type": "CLICK_THROUGH", "window_days": 7},
            {"event_type": "VIEW_THROUGH", "window_days": 1}])
        for a in spec["adsets"]:
            for ad in a["ads"]:
                story = launch.build_creative(spec, ad, "17841400000000000")["object_story_spec"]
                self.assertEqual(story["link_data"]["caption"], "example.com")
                self.assertEqual(story["link_data"]["call_to_action"]["type"], "SEE_DETAILS")

    def test_example_dry_run_flow_passes_offline(self) -> None:
        spec = launch.load_spec(str(self.PATH))
        events = self.run_launch(spec, launch.State(str(self.root / "st.json")), dry=True)
        self.assertEqual([e for e in events if e[0] == "post"], [])
        adset_payload = next(e[2] for e in events if e[1] == "adset[0]")
        self.assertEqual(adset_payload["bid_amount"], 20000)
        self.assertNotIn("daily_budget", adset_payload)

    def test_example_has_no_casino_wording_anywhere(self) -> None:
        text = self.PATH.read_text(encoding="utf-8").lower()
        for word in ("casino", "bonus", "jackpot", "slots", "spins", "claim", "exclusive", "welcome"):
            self.assertNotIn(word, text)


class BulkMediaTests(TmpCase):
    def template(self) -> dict:
        spec = base_spec(adsets=3)
        for i, a in enumerate(spec["adsets"]):
            a["name"] = f"{{tag}}|S{i}"
            a["ads"][0]["name"] = "{tag}|img"          # same ad name in every ad set
            a["ads"][0]["creative"]["image_hash"] = "REPLACE_ME"
        return spec

    def resolve(self, media_map: dict):
        row = {"account_id": "act_9", "tag": "J41", "media": media_map}
        with mock.patch.object(bulk, "BULK_DIR", str(self.root / "bulk")):
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                spec, _ = bulk.resolve(self.template(), row, "run")
        return spec, err.getvalue()

    def hashes(self, spec: dict) -> list[str]:
        return [a["ads"][0]["creative"]["image_hash"] for a in spec["adsets"]]

    def test_keys_use_the_expanded_ad_name(self) -> None:
        spec, err = self.resolve({"J41|img": {"image_hash": "H"}})
        self.assertEqual(self.hashes(spec), ["H", "H", "H"])

    def test_tag_placeholder_in_a_media_key_still_works(self) -> None:
        spec, _ = self.resolve({"{tag}|img": {"image_hash": "H"}})
        self.assertEqual(self.hashes(spec), ["H", "H", "H"])

    def test_adset_index_keys_give_each_adset_its_own_media(self) -> None:
        spec, err = self.resolve({"0:J41|img": {"image_hash": "H0"}, "1:J41|img": {"image_hash": "H1"},
                                  "2:J41|img": {"image_hash": "H2"}})
        self.assertEqual(self.hashes(spec), ["H0", "H1", "H2"])
        self.assertEqual(err, "")

    def test_name_shared_by_several_ads_is_warned_about(self) -> None:
        _, err = self.resolve({"J41|img": {"image_hash": "H"}})
        self.assertIn("SAME media", err)
        self.assertIn("<adset index>", err)

    def test_a_miss_is_warned_not_silent(self) -> None:
        spec, err = self.resolve({"0:J41|img": {"image_hash": "H0"}, "9:J41|nope": {"image_hash": "X"}})
        self.assertEqual(self.hashes(spec), ["H0", "REPLACE_ME", "REPLACE_ME"])
        self.assertIn("no entry for ad 'J41|img' (adset 1)", err)
        self.assertIn("matched no ad", err)
        self.assertIn("'9:J41|nope'", err)


    def test_unexpanded_names_are_not_judged(self) -> None:
        """metaops' workspace check calls apply_media before {tag} expansion: no false alarms."""
        spec = self.template()
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            bulk.apply_media(spec, {"J41|img": {"image_hash": "H"}})
        self.assertEqual(err.getvalue(), "")
        with contextlib.redirect_stderr(err):
            bulk.apply_media(spec, {"{tag}|img": {"image_hash": "H"}})
        self.assertEqual(self.hashes(spec), ["H", "H", "H"])

    def test_plain_name_key_still_applies_to_a_single_ad(self) -> None:
        spec = base_spec()
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            bulk.apply_media(spec, {"ad-0": {"image_hash": "H"}})
        self.assertEqual(spec["adsets"][0]["ads"][0]["creative"]["image_hash"], "H")
        self.assertEqual(err.getvalue(), "")


class ManifestMergeTests(TmpCase):
    def manifest(self, account: str, images=(), videos=()) -> dict:
        return {"account_id": account,
                "images": [{"file": f, "image_hash": h} for f, h in images],
                "videos": [{"file": f, "video_id": v} for f, v in videos]}

    def test_second_run_keeps_the_first_runs_entries(self) -> None:
        path = str(self.root / "media.json")
        media.write_manifest(path, self.manifest("act_1", images=[("a.jpg", "HA")]))
        merged = media.write_manifest(path, self.manifest("act_1", images=[("b.jpg", "HB")],
                                                          videos=[("v.mp4", "V1")]))
        self.assertEqual({e["file"] for e in merged["images"]}, {"a.jpg", "b.jpg"})
        self.assertEqual([e["video_id"] for e in merged["videos"]], ["V1"])
        on_disk = json.loads(pathlib.Path(path).read_text())
        self.assertEqual({e["image_hash"] for e in on_disk["images"]}, {"HA", "HB"})

    def test_reuploading_a_file_replaces_its_entry(self) -> None:
        path = str(self.root / "media.json")
        media.write_manifest(path, self.manifest("act_1", images=[("a.jpg", "old"), ("b.jpg", "HB")]))
        merged = media.write_manifest(path, self.manifest("act_1", images=[("a.jpg", "new")]))
        by_file = {e["file"]: e["image_hash"] for e in merged["images"]}
        self.assertEqual(by_file, {"a.jpg": "new", "b.jpg": "HB"})

    def test_other_account_or_unreadable_manifest_is_refused_not_overwritten(self) -> None:
        path = self.root / "media.json"
        media.write_manifest(str(path), self.manifest("act_1", images=[("a.jpg", "HA")]))
        with self.assertRaisesRegex(SystemExit, "account-scoped"):
            media.write_manifest(str(path), self.manifest("act_2", images=[("b.jpg", "HB")]))
        self.assertIn("HA", path.read_text())
        path.write_text("{not json")
        with self.assertRaisesRegex(SystemExit, "not readable JSON"):
            media.write_manifest(str(path), self.manifest("act_1"))
        self.assertEqual(path.read_text(), "{not json")

    def test_main_merges_across_two_invocations(self) -> None:
        manifest = str(self.root / "media.json")

        def run(image: str) -> None:
            argv = ["media.py", "--account", "act_1", "--image", image, "--manifest", manifest]
            with (
                mock.patch.object(sys, "argv", argv),
                mock.patch.object(media, "upload_image",
                                  side_effect=lambda acct, p: {"file": p, "image_hash": "H" + p}),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(media.main(), 0)

        run("a.jpg")
        run("b.jpg")
        files = {e["file"] for e in json.loads(pathlib.Path(manifest).read_text())["images"]}
        self.assertEqual(files, {"a.jpg", "b.jpg"})


class MutateSetTests(TmpCase):
    def test_filter_and_retailer_ids_together_are_rejected_before_any_call(self) -> None:
        flt = self.write({"retailer_id": {"is_any": ["a"]}}, "filter.json")
        argv = ["mutate_set.py", "--set-id", "5", "--filter", str(flt), "--retailer-ids", "a,b"]
        err = io.StringIO()
        with (
            mock.patch.object(sys, "argv", argv),
            mock.patch.object(mutate_set.graph, "get") as get,
            mock.patch.object(mutate_set.graph, "post") as post,
            contextlib.redirect_stderr(err),
            self.assertRaises(SystemExit) as ctx,
        ):
            mutate_set.main()
        self.assertNotEqual(ctx.exception.code, 0)
        self.assertIn("mutually exclusive", err.getvalue())
        get.assert_not_called()
        post.assert_not_called()


class CommentsTests(TmpCase):
    PAGE = "555"

    def run_comments(self, *flags: str):
        rows = [
            {"id": "c1", "message": "nice", "from": {"id": "9", "name": "Fan"}, "created_time": "2026-09-01T00:00:00"},
            {"id": "c2", "message": "thanks for asking", "from": {"id": self.PAGE, "name": "Page"},
             "created_time": "2026-09-01T00:01:00"},
            {"id": "c3", "message": "scam", "from": {"id": "10", "name": "Hater"},
             "created_time": "2026-09-01T00:02:00", "is_hidden": False},
        ]
        argv = ["comments.py", "--ads", "1", "--page", self.PAGE, *flags]
        out = io.StringIO()
        with (
            mock.patch.object(sys, "argv", argv),
            mock.patch.object(comments.graph, "page_token", return_value="pt"),
            mock.patch.object(comments, "story_id", return_value="post1"),
            mock.patch.object(comments, "comments", return_value=rows),
            mock.patch.object(comments.graph, "call", return_value={}) as call,
            contextlib.redirect_stdout(out),
        ):
            self.assertEqual(comments.main(), 0)
        summary = json.loads(out.getvalue().strip().splitlines()[-1])
        return summary, call

    def test_dry_run_counts_what_would_be_acted_on(self) -> None:
        summary, call = self.run_comments("--hide-all", "--dry-run")
        self.assertEqual(summary["acted"], 2)
        self.assertTrue(summary["dry_run"])
        call.assert_not_called()

    def test_hide_all_skips_the_pages_own_comments(self) -> None:
        summary, call = self.run_comments("--hide-all")
        hidden = [c.args[1] for c in call.call_args_list]
        self.assertEqual(hidden, ["c1", "c3"])
        self.assertEqual(summary["acted"], 2)

    def test_matching_mode_dry_run_count(self) -> None:
        summary, call = self.run_comments("--hide-matching", "scam", "--dry-run")
        self.assertEqual(summary["acted"], 1)
        call.assert_not_called()


if __name__ == "__main__":
    unittest.main()

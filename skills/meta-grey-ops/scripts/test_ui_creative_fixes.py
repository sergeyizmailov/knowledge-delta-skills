#!/usr/bin/env python3
"""Offline tests: clone-and-swap on Ads Manager (UI-built) creatives, and edit.py on unreadable ids."""

from __future__ import annotations
import os as _os, tempfile as _tempfile
_os.environ["METAOPS_PACE_DIR"] = _tempfile.mkdtemp(prefix="metaops-pace-test-")
_os.environ.setdefault("METAOPS_CREATE_GAP_HOURS", "0")

import contextlib
import copy
import io
import json
import unittest
from unittest import mock

import edit
import edit_tags
import verify

_os.environ.setdefault("META_TOKEN", "TEST_TOKEN")

UI_CREATIVE = {
    "id": "500", "name": "Read before you judge", "url_tags": "campaign_id={{campaign.id}}",
    "object_story_spec": {"page_id": "2", "instagram_user_id": "3", "link_data": {
        "link": "https://x.example/", "message": "story text", "name": "Read before you judge",
        "call_to_action": {"type": "SEE_DETAILS", "value": {"link": "https://x.example/"}}}},
    "applink_treatment": "web_only",
    "destination_spec": {"website": {"optimization": {"status": "OPT_OUT", "type": "website_destination_optimization"}},
                         "native_commerce_experience": {"shop": {"enroll_status": "OPT_OUT"}}},
    "creative_sourcing_spec": {"brand": {"enroll_status": "OPT_OUT"}, "catalog": {"enroll_status": "OPT_OUT"},
                               "source_url": "https://x.example/", "enable_social_feedback_preservation": True},
    "format_transformation_spec": [{"data_source": ["none"], "format": "carousel"},
                                   {"data_source": ["none"], "format": "video_slideshow"}],
    "media_sourcing_spec": {"titles": [{"text": "Read before you judge"}]},
}
INERT = {"applink_treatment", "destination_spec", "creative_sourcing_spec",
         "format_transformation_spec", "media_sourcing_spec"}


def run_tags(argv, ad, gets_after=None, posts=None):
    gets = [ad] + (gets_after if gets_after is not None else [{"name": "Ad", "creative": {"id": "600"}}])
    err = io.StringIO()
    with (
        mock.patch.object(edit_tags.sys, "argv", ["edit_tags.py", *argv]),
        mock.patch.object(edit_tags.graph, "require_write_authority"),
        mock.patch.object(edit_tags.graph, "get", side_effect=gets),
        mock.patch.object(edit_tags.graph, "post", side_effect=posts or [{"id": "600"}, {}]) as post,
        contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()),
    ):
        code = edit_tags.main()
    return code, post, err.getvalue()


def ui_ad(**over):
    creative = copy.deepcopy(UI_CREATIVE)
    creative.update(over)
    return {"id": "77", "name": "Ad", "account_id": "1", "effective_status": "ACTIVE", "creative": creative}


class InertUiFieldTests(unittest.TestCase):
    def test_all_off_ads_manager_defaults_are_inert(self) -> None:
        self.assertEqual(edit_tags._inert_ui_fields(copy.deepcopy(UI_CREATIVE)), INERT)

    def test_an_active_flag_is_not_inert(self) -> None:
        creative = copy.deepcopy(UI_CREATIVE)
        creative["creative_sourcing_spec"]["brand"]["enroll_status"] = "OPT_IN"
        creative["destination_spec"]["website"]["optimization"]["status"] = "OPT_IN"
        self.assertEqual(edit_tags._inert_ui_fields(creative), INERT - {"creative_sourcing_spec", "destination_spec"})

    def test_real_content_is_not_inert(self) -> None:
        creative = copy.deepcopy(UI_CREATIVE)
        creative["applink_treatment"] = "deeplink_with_web_fallback"
        creative["format_transformation_spec"][0]["data_source"] = ["catalog"]
        creative["media_sourcing_spec"]["titles"].append({"text": "another title"})
        self.assertEqual(edit_tags._inert_ui_fields(creative),
                         {"destination_spec", "creative_sourcing_spec"})


class UiCreativeCloneTests(unittest.TestCase):
    def test_headline_edit_clones_an_ads_manager_ad_without_the_inert_fields(self) -> None:
        code, post, _err = run_tags(["--ids", "77", "--headline", "New head", "--confirm", "TAGS"], ui_ad())
        self.assertEqual(code, 0)
        create = post.call_args_list[0].args[1]
        self.assertEqual(create["object_story_spec"]["link_data"]["name"], "New head")
        for field in INERT:
            self.assertNotIn(field, create)
        self.assertEqual(create["url_tags"], "campaign_id={{campaign.id}}")

    def test_an_active_flag_still_blocks_the_clone(self) -> None:
        ad = ui_ad()
        ad["creative"]["destination_spec"]["website"]["optimization"]["status"] = "OPT_IN"
        code, post, err = run_tags(["--ids", "77", "--headline", "New head", "--confirm", "TAGS"], ad, gets_after=[])
        self.assertEqual(code, 0)
        post.assert_not_called()
        self.assertIn("destination_spec", err)


class EnhancementsOffTests(unittest.TestCase):
    def spotlight_ad(self):
        ad = ui_ad()
        ad["creative"]["creative_sourcing_spec"]["featured_offering_spec"] = {
            "enroll_status": "OPT_IN", "default_status": "OPT_IN"}
        return ad

    def test_without_the_flag_an_enrolled_ad_is_left_alone(self) -> None:
        code, post, err = run_tags(["--ids", "77", "--headline", "H", "--confirm", "TAGS"], self.spotlight_ad(),
                                   gets_after=[])
        self.assertEqual(code, 0)
        post.assert_not_called()
        self.assertIn("creative_sourcing_spec", err)

    def test_enhancements_off_alone_clones_without_the_sourcing_spec(self) -> None:
        code, post, _err = run_tags(["--ids", "77", "--enhancements-off", "--confirm", "TAGS"], self.spotlight_ad())
        self.assertEqual(code, 0)
        create = post.call_args_list[0].args[1]
        self.assertNotIn("creative_sourcing_spec", create)
        self.assertEqual(create["object_story_spec"]["link_data"]["name"], "Read before you judge")

    def test_enhancements_off_on_a_clean_ad_is_a_no_op(self) -> None:
        code, post, err = run_tags(["--ids", "77", "--enhancements-off", "--confirm", "TAGS"], ui_ad(), gets_after=[])
        self.assertEqual(code, 0)
        post.assert_not_called()
        self.assertIn("no change", err)


class SourcingLeakTests(unittest.TestCase):
    CSS = {"brand": {"enroll_status": "OPT_OUT"}, "source_url": "https://x.example/",
           "featured_offering_spec": {"enroll_status": "OPT_IN", "default_status": "OPT_IN"}}

    def test_ads_manager_spotlights_enrolment_is_flagged(self) -> None:
        self.assertEqual(verify.leaked_sourcing_opt_in(self.CSS, None), ["featured_offering_spec"])

    def test_spec_can_keep_it_on_deliberately(self) -> None:
        self.assertEqual(verify.leaked_sourcing_opt_in(self.CSS, {"opt_in_features": ["featured_offering"]}), [])

    def test_api_built_creatives_read_back_clean(self) -> None:
        clean = {"brand": {"enroll_status": "OPT_OUT"}, "featured_offering_spec": {"enroll_status": "OPT_OUT"}}
        self.assertEqual(verify.leaked_sourcing_opt_in(clean, None), [])
        self.assertEqual(verify.leaked_sourcing_opt_in(None, None), [])


class UnreadableIdTests(unittest.TestCase):
    def test_a_foreign_or_missing_id_is_a_clean_failure_not_a_traceback(self) -> None:
        import graph
        boom = graph.GraphError(400, {"error": {"code": 110, "message": "Unsupported get request"}}, "read 999")
        err = io.StringIO()
        with (
            mock.patch.object(edit.sys, "argv", ["edit.py", "--ids", "999", "--name", "X", "--expected-account", "act_1"]),
            mock.patch.object(edit.graph, "require_write_authority"),
            mock.patch.object(edit.graph, "get", side_effect=boom),
            mock.patch.object(edit.graph, "post") as post,
            contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()) as out,
        ):
            code = edit.main()
        self.assertEqual(code, 1)
        post.assert_not_called()
        self.assertIn("cannot read this object", err.getvalue())
        self.assertFalse(json.loads(out.getvalue().strip().splitlines()[-1])["ok"])


if __name__ == "__main__":
    unittest.main()

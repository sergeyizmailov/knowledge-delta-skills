#!/usr/bin/env python3
"""Offline contract tests for cmd_catalog.py. No network or real credentials."""

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

import cmd_catalog
import metaops


def _profile() -> dict:
    return {
        "business_id": "10",
        "app_id": "11",
        "system_user_id": "12",
        "ad_account_id": "act_1",
        "page_id": "2",
        "dataset_id": "3",
        "catalog_id": "100",
        "feed_id": "200",
        "product_sets": {"main": "300"},
        "currency": "USD",
        "timezone": "Europe/Warsaw",
    }


class FakeWorkspace:
    def __init__(self, profile: dict) -> None:
        self._profile = profile
        self.path = pathlib.Path("workspace.json")

    def profile(self, requested=None):
        return "test", self._profile


def args_for(**overrides) -> object:
    base = {
        "workspace_obj": FakeWorkspace(_profile()),
        "profile": "test",
        "confirm": "BATCH",
    }
    base.update(overrides)
    return type("Args", (), base)()


class CatalogCreateTests(unittest.TestCase):
    def test_create_requires_literal_confirm(self) -> None:
        args = args_for(name="Shop", vertical="commerce", confirm="please")
        with mock.patch.object(cmd_catalog, "_profile", return_value=("test", _profile())):
            with self.assertRaisesRegex(metaops.MetaOpsError, "literal --confirm CREATE"):
                cmd_catalog.command_catalog_create(args, metaops)

    def test_create_posts_owned_product_catalogs(self) -> None:
        args = args_for(name="Shop", vertical="commerce", confirm="CREATE")
        with (
            mock.patch.object(
                metaops,
                "require_provisioning_admin",
                return_value={"system_user_id": "12", "role": "ADMIN"},
            ) as gate,
            mock.patch.object(cmd_catalog, "_paginate", return_value=[]),
            mock.patch.object(metaops.graph, "post", return_value={"id": "999"}) as post,
        ):
            code, payload = cmd_catalog.command_catalog_create(args, metaops)
        self.assertEqual(code, 0)
        gate.assert_called_once_with(args.workspace_obj, "test")
        self.assertEqual(post.call_args.args[0], "10/owned_product_catalogs")
        self.assertEqual(post.call_args.args[1], {"name": "Shop", "vertical": "commerce"})
        self.assertEqual(payload["data"]["catalog_id"], "999")
        self.assertIn("workspace.json", payload["next_action"])

    def test_create_rejects_non_admin_before_post(self) -> None:
        args = args_for(name="Shop", vertical="commerce", confirm="CREATE")
        with (
            mock.patch.object(
                metaops,
                "require_provisioning_admin",
                side_effect=metaops.MetaOpsError("provisioning requires an ADMIN System User"),
            ),
            mock.patch.object(metaops.graph, "post") as post,
        ):
            with self.assertRaisesRegex(metaops.MetaOpsError, "ADMIN System User"):
                cmd_catalog.command_catalog_create(args, metaops)
        post.assert_not_called()


class CatalogFeedTests(unittest.TestCase):
    def test_feed_create_builds_schedule_object_not_prestringified(self) -> None:
        args = args_for(name="Feed", url="https://x/export?format=csv", schedule="daily",
                        hour=6, update_only=True, confirm="CREATE")
        with (
            mock.patch.object(cmd_catalog, "_paginate", return_value=[]),
            mock.patch.object(metaops.graph, "post", return_value={"id": "555"}) as post,
        ):
            code, payload = cmd_catalog.command_catalog_feed_create(args, metaops)
        self.assertEqual(code, 0)
        self.assertEqual(post.call_args.args[0], "100/product_feeds")
        sent = post.call_args.args[1]
        self.assertIsInstance(sent["schedule"], dict)
        self.assertEqual(sent["schedule"], {"url": args.url, "interval": "DAILY", "hour": 6})
        self.assertEqual(sent["deletion_enabled"], False)
        self.assertEqual(payload["data"]["feed_id"], "555")

    def test_feed_create_requires_confirm(self) -> None:
        args = args_for(name="Feed", url="https://x", schedule="hourly", hour=None,
                        update_only=False, confirm="no")
        with self.assertRaisesRegex(metaops.MetaOpsError, "literal --confirm CREATE"):
            cmd_catalog.command_catalog_feed_create(args, metaops)

    def test_feed_uploads_requires_feed_id(self) -> None:
        profile = _profile()
        profile["feed_id"] = None
        args = args_for(workspace_obj=FakeWorkspace(profile), feed_id=None, limit=25)
        with self.assertRaisesRegex(metaops.MetaOpsError, "no feed id"):
            cmd_catalog.command_catalog_feed_uploads(args, metaops)

    def test_feed_uploads_rejects_a_different_profile_feed(self) -> None:
        args = args_for(feed_id="999", limit=25)
        with self.assertRaisesRegex(metaops.MetaOpsError, "does not match"):
            cmd_catalog.command_catalog_feed_uploads(args, metaops)


class CatalogSetTests(unittest.TestCase):
    def test_set_create_encodes_filter_once_as_dict(self) -> None:
        args = args_for(name="Set", filter=None, retailer_ids="a,b,c", confirm="CREATE")
        with (
            mock.patch.object(cmd_catalog, "_paginate", return_value=[]),
            mock.patch.object(metaops.graph, "post", return_value={"id": "321"}) as post,
        ):
            code, payload = cmd_catalog.command_catalog_set_create(args, metaops)
        self.assertEqual(code, 0)
        sent = post.call_args.args[1]
        self.assertIsInstance(sent["filter"], dict)
        self.assertEqual(sent["filter"], {"retailer_id": {"is_any": ["a", "b", "c"]}})
        self.assertEqual(payload["data"]["set_id"], "321")

    def test_set_create_rejects_both_or_neither_filter_source(self) -> None:
        args = args_for(name="Set", filter=None, retailer_ids=None, confirm="CREATE")
        with self.assertRaisesRegex(metaops.MetaOpsError, "exactly one"):
            cmd_catalog.command_catalog_set_create(args, metaops)
        with tempfile.TemporaryDirectory() as td:
            filter_path = pathlib.Path(td) / "f.json"
            filter_path.write_text(json.dumps({"retailer_id": {"is_any": ["x"]}}), encoding="utf-8")
            args = args_for(name="Set", filter=str(filter_path), retailer_ids="a", confirm="CREATE")
            with self.assertRaisesRegex(metaops.MetaOpsError, "exactly one"):
                cmd_catalog.command_catalog_set_create(args, metaops)

    def test_set_create_filter_file_must_be_object(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            filter_path = pathlib.Path(td) / "f.json"
            filter_path.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")
            args = args_for(name="Set", filter=str(filter_path), retailer_ids=None, confirm="CREATE")
            with self.assertRaisesRegex(metaops.MetaOpsError, "JSON object"):
                cmd_catalog.command_catalog_set_create(args, metaops)

    def test_set_create_resolves_filter_path_through_context(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            filter_path = pathlib.Path(td) / "filter.json"
            filter_path.write_text(json.dumps({"retailer_id": {"is_any": ["x"]}}), encoding="utf-8")
            args = args_for(name="Set", filter="~/filter.json", retailer_ids=None, confirm="CREATE")
            with (
                mock.patch.object(metaops, "resolve_input", return_value=filter_path) as resolve,
                mock.patch.object(cmd_catalog, "_paginate", return_value=[]),
                mock.patch.object(metaops.graph, "post", return_value={"id": "321"}),
            ):
                cmd_catalog.command_catalog_set_create(args, metaops)
            resolve.assert_called_once_with("~/filter.json")


class CatalogMissingIdTests(unittest.TestCase):
    def test_missing_catalog_id_raises(self) -> None:
        profile = _profile()
        profile["catalog_id"] = None
        args = args_for(workspace_obj=FakeWorkspace(profile), set_id=None, limit=10)
        with self.assertRaisesRegex(metaops.MetaOpsError, "no catalog id"):
            cmd_catalog.command_catalog_products_list(args, metaops)


class CatalogProductsBatchTests(unittest.TestCase):
    def test_batch_requires_literal_confirm_before_reading_or_writing(self) -> None:
        args = args_for(file="not-read.json", method="DELETE", wait=1, confirm="DELETE")
        with mock.patch.object(metaops.graph, "post") as post:
            with self.assertRaisesRegex(metaops.MetaOpsError, "literal --confirm BATCH"):
                cmd_catalog.command_catalog_products_batch(args, metaops)
        post.assert_not_called()

    def test_batch_requires_valid_method(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            items_path = pathlib.Path(td) / "items.json"
            items_path.write_text(json.dumps([{"id": "SKU1"}]), encoding="utf-8")
            args = args_for(file=str(items_path), method="PATCH", wait=1)
            with self.assertRaisesRegex(metaops.MetaOpsError, "--method must be"):
                cmd_catalog.command_catalog_products_batch(args, metaops)

    def test_batch_rejects_empty_or_non_list_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            bad = pathlib.Path(td) / "bad.json"
            bad.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
            args = args_for(file=str(bad), method="UPDATE", wait=1)
            with self.assertRaisesRegex(metaops.MetaOpsError, "non-empty JSON array"):
                cmd_catalog.command_catalog_products_batch(args, metaops)

    def test_batch_sends_item_type_product_item_and_polls_to_finish(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            items_path = pathlib.Path(td) / "items.json"
            items = [{"id": "SKU1", "availability": "in stock"}, {"id": "SKU2"}]
            items_path.write_text(json.dumps(items), encoding="utf-8")
            args = args_for(file=str(items_path), method="UPDATE", wait=30)

            statuses = [
                {"data": [{"handle": "H1", "status": "in_progress"}]},
                {"data": [{"handle": "H1", "status": "finished", "errors_total_count": 0,
                           "warnings_total_count": 0, "errors": [], "ids_of_invalid_requests": []}]},
            ]
            with (
                mock.patch.object(metaops.graph, "post", return_value={"handles": ["H1"]}) as post,
                mock.patch.object(metaops.graph, "get", side_effect=lambda *a, **k: statuses.pop(0)) as get,
                mock.patch.object(cmd_catalog.time, "sleep"),
            ):
                code, payload = cmd_catalog.command_catalog_products_batch(args, metaops)
            self.assertEqual(code, 0)
            sent = post.call_args.args[1]
            self.assertEqual(sent["item_type"], "PRODUCT_ITEM")
            self.assertEqual(sent["allow_upsert"], True)
            self.assertEqual(len(sent["requests"]), 2)
            self.assertEqual(sent["requests"][0], {"method": "UPDATE", "data": items[0]})
            self.assertEqual(get.call_args.kwargs["params"], {
                "handle": "H1", "fields": cmd_catalog.BATCH_STATUS_FIELDS,
            })
            self.assertTrue(payload["data"]["finished"])
            self.assertEqual(payload["data"]["errors_total_count"], 0)
            self.assertEqual(payload["phase"], "finished")

    def test_batch_delete_does_not_set_allow_upsert(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            items_path = pathlib.Path(td) / "items.json"
            items_path.write_text(json.dumps([{"id": "SKU1"}]), encoding="utf-8")
            args = args_for(file=str(items_path), method="DELETE", wait=5)
            with (
                mock.patch.object(metaops.graph, "post", return_value={"handles": ["H2"]}) as post,
                mock.patch.object(
                    metaops.graph, "get",
                    return_value={"handle": "H2", "status": "finished", "errors_total_count": 0},
                ),
            ):
                code, _ = cmd_catalog.command_catalog_products_batch(args, metaops)
            self.assertEqual(code, 0)
            self.assertNotIn("allow_upsert", post.call_args.args[1])

    def test_batch_still_running_after_wait_is_not_ok(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            items_path = pathlib.Path(td) / "items.json"
            items_path.write_text(json.dumps([{"id": "SKU1"}]), encoding="utf-8")
            args = args_for(file=str(items_path), method="UPDATE", wait=0)
            with (
                mock.patch.object(metaops.graph, "post", return_value={"handles": ["H3"]}),
                mock.patch.object(metaops.graph, "get", return_value={"handle": "H3", "status": "in_progress"}),
            ):
                code, payload = cmd_catalog.command_catalog_products_batch(args, metaops)
            self.assertEqual(code, 1)
            self.assertFalse(payload["data"]["finished"])
            self.assertEqual(payload["phase"], "still_running")

    def test_batch_reports_per_item_errors_as_not_ok(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            items_path = pathlib.Path(td) / "items.json"
            items_path.write_text(json.dumps([{"id": "SKU1"}]), encoding="utf-8")
            args = args_for(file=str(items_path), method="UPDATE", wait=5)
            with (
                mock.patch.object(metaops.graph, "post", return_value={"handles": ["H4"]}),
                mock.patch.object(
                    metaops.graph, "get",
                    return_value={"handle": "H4", "status": "finished", "errors_total_count": 1,
                                  "errors": [{"message": "bad price"}]},
                ),
            ):
                code, payload = cmd_catalog.command_catalog_products_batch(args, metaops)
            self.assertEqual(code, 1)
            self.assertEqual(payload["error"]["kind"], "batch_errors")
            self.assertEqual(payload["data"]["errors"], [{"message": "bad price"}])


class CatalogAccessTests(unittest.TestCase):
    def test_access_checks_business_ownership_and_system_user_assignment(self) -> None:
        args = args_for()
        catalog_resp = {"id": "100", "business": {"id": "10"}, "product_count": 5}
        with (
            mock.patch.object(metaops.graph, "get", return_value=catalog_resp),
            mock.patch.object(cmd_catalog, "_paginate", return_value=[{"id": "100"}]),
        ):
            code, payload = cmd_catalog.command_catalog_access(args, metaops)
        self.assertEqual(code, 0)
        self.assertTrue(payload["data"]["checks"]["catalog_owned_by_business"])
        self.assertTrue(payload["data"]["checks"]["catalog_assigned_to_system_user"])

    def test_access_flags_wrong_business(self) -> None:
        args = args_for()
        catalog_resp = {"id": "100", "business": {"id": "999"}, "product_count": 5}
        with (
            mock.patch.object(metaops.graph, "get", return_value=catalog_resp),
            mock.patch.object(cmd_catalog, "_paginate", return_value=[]),
        ):
            code, payload = cmd_catalog.command_catalog_access(args, metaops)
        self.assertEqual(code, 1)
        self.assertFalse(payload["data"]["checks"]["catalog_owned_by_business"])
        self.assertEqual(payload["error"]["kind"], "asset_gate")


class RegisterTests(unittest.TestCase):
    def test_register_wires_into_metaops_parser(self) -> None:
        # metaops.parser() already auto-imports cmd_catalog via COMMAND_MODULES and
        # calls register(sub, metaops) itself (see metaops.py's `for module_name in
        # COMMAND_MODULES` loop) — calling register() again here would conflict on
        # the already-added "catalog" subparser, so just exercise the wired parser.
        ap = metaops.parser()
        parsed = ap.parse_args([
            "--workspace", "x", "catalog", "set", "create",
            "--name", "N", "--retailer-ids", "a", "--confirm", "CREATE",
        ])
        self.assertEqual(parsed.catalog_action, "set")
        self.assertEqual(parsed.catalog_set_action, "create")
        self.assertTrue(callable(parsed.handler))

class BatchItemIdTests(unittest.TestCase):
    def test_started_is_not_finished(self):
        import cmd_catalog
        self.assertFalse(cmd_catalog._batch_finished("started"))
        self.assertFalse(cmd_catalog._batch_finished("in_progress"))
        self.assertTrue(cmd_catalog._batch_finished("finished"))
        self.assertTrue(cmd_catalog._batch_finished("complete"))

    def test_batch_items_require_id_and_map_retailer_id(self):
        import json as _json
        import pathlib
        import tempfile

        import cmd_catalog
        import metaops
        with tempfile.TemporaryDirectory() as td:
            good = pathlib.Path(td) / "ok.json"
            good.write_text(_json.dumps([{"retailer_id": "SKU1", "availability": "in stock"}, {"id": "SKU2"}]))
            items = cmd_catalog._load_batch_items(str(good), metaops)
            self.assertEqual([i["id"] for i in items], ["SKU1", "SKU2"])
            self.assertNotIn("retailer_id", items[0])
            bad = pathlib.Path(td) / "bad.json"
            bad.write_text(_json.dumps([{"availability": "in stock"}]))
            with self.assertRaisesRegex(metaops.MetaOpsError, "needs `id`"):
                cmd_catalog._load_batch_items(str(bad), metaops)


if __name__ == "__main__":
    unittest.main(verbosity=2)

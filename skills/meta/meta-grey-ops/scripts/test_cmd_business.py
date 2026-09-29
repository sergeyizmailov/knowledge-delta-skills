#!/usr/bin/env python3
"""Offline contract tests for cmd_business.py. No network or real credentials."""

from __future__ import annotations
import os as _os, tempfile as _tempfile
_os.environ["METAOPS_PACE_DIR"] = _tempfile.mkdtemp(prefix="metaops-pace-test-")
_os.environ.setdefault("METAOPS_CREATE_GAP_HOURS", "0")

import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("META_TOKEN", "TEST_TOKEN")

import cmd_business
import metaops


def make_args(**kwargs):
    return type("Args", (), kwargs)()


class CmdBusinessTests(unittest.TestCase):
    def setUp(self) -> None:
        provisioning_patch = mock.patch.object(
            metaops,
            "require_provisioning_admin",
            return_value={"system_user_id": "12", "role": "ADMIN"},
        )
        self.provisioning = provisioning_patch.start()
        self.addCleanup(provisioning_patch.stop)

    def workspace(self, root: pathlib.Path) -> metaops.meta_workspace.Workspace:
        path = root / "workspace.json"
        path.write_text(
            __import__("json").dumps(
                {
                    "schema": metaops.meta_workspace.WORKSPACE_SCHEMA,
                    "name": "contract",
                    "api_version": metaops.graph.API_VERSION,
                    "blocked_accounts": [],
                    "profiles": {
                        "test": {
                            "business_id": "10",
                            "app_id": "11",
                            "system_user_id": "12",
                            "ad_account_id": "act_1",
                            "page_id": "2",
                            "dataset_id": "3",
                            "currency": "USD",
                            "timezone": "Europe/Warsaw",
                        }
                    },
                    "defaults": {"profile": "test", "state_dir": ".metaops"},
                }
            ),
            encoding="utf-8",
        )
        return metaops.meta_workspace.load_workspace(str(path))

    # --- workspace precondition -------------------------------------------------

    def test_every_handler_requires_workspace(self) -> None:
        handlers = [
            (cmd_business._business_assets, {}),
            (cmd_business._adaccount_create, {"confirm": "CREATE"}),
            (cmd_business._pixel_create, {"confirm": "CREATE"}),
            (cmd_business._pixel_share, {"confirm": "SHARE"}),
            (cmd_business._pixel_shared, {}),
            (cmd_business._capi_test, {}),
            (cmd_business._user_invite, {"confirm": "SHARE"}),
            (cmd_business._user_assign, {"confirm": "SHARE"}),
            (cmd_business._partner_share, {"confirm": "SHARE"}),
        ]
        for handler, extra in handlers:
            args = make_args(workspace_obj=None, profile=None, **extra)
            with self.assertRaisesRegex(metaops.MetaOpsError, "requires --workspace"):
                handler(metaops, args)

    # --- confirm literal enforcement --------------------------------------------

    def test_confirm_literal_enforced_for_creates(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            workspace = self.workspace(pathlib.Path(td))
            with mock.patch.object(metaops.graph, "post") as post:
                args = make_args(
                    workspace_obj=workspace, profile="test", confirm="WRONG",
                    name="n", currency="USD", timezone_id=1, end_advertiser=None,
                    media_agency=None, partner=None, funding_id=None,
                )
                with self.assertRaisesRegex(metaops.MetaOpsError, "literal --confirm CREATE"):
                    cmd_business._adaccount_create(metaops, args)
                post.assert_not_called()

                args = make_args(
                    workspace_obj=workspace, profile="test", confirm="WRONG",
                    name="n", is_crm=False,
                )
                with self.assertRaisesRegex(metaops.MetaOpsError, "literal --confirm CREATE"):
                    cmd_business._pixel_create(metaops, args)
                post.assert_not_called()

    def test_confirm_literal_enforced_for_sharing_ops(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            workspace = self.workspace(pathlib.Path(td))
            with mock.patch.object(metaops.graph, "post") as post, \
                 mock.patch.object(metaops, "run_child") as run_child:
                args = make_args(
                    workspace_obj=workspace, profile="test", confirm="WRONG",
                    account="act_2", timeout=10,
                )
                with self.assertRaisesRegex(metaops.MetaOpsError, "literal --confirm SHARE"):
                    cmd_business._pixel_share(metaops, args)
                run_child.assert_not_called()

                args = make_args(
                    workspace_obj=workspace, profile="test", confirm="WRONG",
                    email="a@b.com", role="EMPLOYEE",
                )
                with self.assertRaisesRegex(metaops.MetaOpsError, "literal --confirm SHARE"):
                    cmd_business._user_invite(metaops, args)

                args = make_args(
                    workspace_obj=workspace, profile="test", confirm="WRONG",
                    user_id="99", asset="adaccount", tasks="MANAGE",
                )
                with self.assertRaisesRegex(metaops.MetaOpsError, "literal --confirm SHARE"):
                    cmd_business._user_assign(metaops, args)
                args = make_args(
                    workspace_obj=workspace, profile="test", confirm="WRONG",
                    partner_business="20", asset="page", tasks="ADVERTISE",
                )
                with self.assertRaisesRegex(metaops.MetaOpsError, "literal --confirm SHARE"):
                    cmd_business._partner_share(metaops, args)
                post.assert_not_called()

    def test_page_tasks_reject_ad_account_only_values(self) -> None:
        with self.assertRaisesRegex(metaops.MetaOpsError, "not valid for page"):
            cmd_business._tasks_list(metaops, "DRAFT,AA_ANALYZE", "page")
        self.assertEqual(cmd_business._tasks_list(metaops, "ADVERTISE,ANALYZE", "page"), ["ADVERTISE", "ANALYZE"])

    # --- payload shapes ----------------------------------------------------------

    def test_adaccount_create_payload_and_new_bm_cap_next_action(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            workspace = self.workspace(pathlib.Path(td))
            args = make_args(
                workspace_obj=workspace, profile="test", confirm="CREATE",
                name="Acct", currency="USD", timezone_id=1,
                end_advertiser="30", media_agency=None, partner=None, funding_id=None,
            )
            with (
                mock.patch.object(cmd_business, "_list_edge", return_value=[]),
                mock.patch.object(metaops.graph, "post", return_value={"id": "123"}) as post,
            ):
                code, payload = cmd_business._adaccount_create(metaops, args)
            self.assertEqual(code, 0)
            self.assertTrue(payload["ok"])
            post.assert_called_once()
            path, body = post.call_args.args[0], post.call_args.args[1]
            self.assertEqual(path, "10/adaccount")
            self.assertEqual(body["name"], "Acct")
            self.assertEqual(body["currency"], "USD")
            self.assertEqual(body["timezone_id"], 1)
            self.assertEqual(body["end_advertiser"], "30")
            self.assertNotIn("media_agency", body)
            self.assertEqual(payload["data"]["ad_account_id"], "act_123")
            self.assertIn("1 ad account", payload["next_action"])
            self.provisioning.assert_called_once_with(workspace, "test")

    def test_pixel_create_payload(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            workspace = self.workspace(pathlib.Path(td))
            args = make_args(
                workspace_obj=workspace, profile="test", confirm="CREATE",
                name="Px", is_crm=True,
            )
            with (
                mock.patch.object(cmd_business, "_list_edge", return_value=[]),
                mock.patch.object(metaops.graph, "post", return_value={"id": "555"}) as post,
            ):
                code, payload = cmd_business._pixel_create(metaops, args)
            self.assertEqual(code, 0)
            path, body = post.call_args.args[0], post.call_args.args[1]
            self.assertEqual(path, "10/adspixels")
            self.assertEqual(body, {"name": "Px", "is_crm": True})
            self.assertEqual(payload["data"]["dataset_id"], "555")
            self.provisioning.assert_called_once_with(workspace, "test")

    def test_capi_test_event_shape_has_hashed_user_data_and_test_code(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            workspace = self.workspace(pathlib.Path(td))
            args = make_args(
                workspace_obj=workspace, profile="test",
                event="Lead", test_code="TEST1234", url=None,
            )
            with mock.patch.object(
                metaops.graph, "post", return_value={"events_received": 1, "fbtrace_id": "tr"}
            ) as post:
                code, payload = cmd_business._capi_test(metaops, args)
            self.assertEqual(code, 0)
            path, body = post.call_args.args[0], post.call_args.args[1]
            self.assertEqual(path, "3/events")
            self.assertEqual(body["test_event_code"], "TEST1234")
            self.assertEqual(len(body["data"]), 1)
            event = body["data"][0]
            self.assertEqual(event["event_name"], "Lead")
            self.assertEqual(event["action_source"], "website")
            self.assertIn("event_source_url", event)
            self.assertIn("event_time", event)
            em = event["user_data"]["em"][0]
            self.assertEqual(len(em), 64)  # sha256 hex digest length
            self.assertNotIn("metaops-capi-test@example.invalid", str(event))
            self.assertEqual(payload["data"]["events_received"], 1)

    def test_user_invite_payload(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            workspace = self.workspace(pathlib.Path(td))
            args = make_args(
                workspace_obj=workspace, profile="test", confirm="SHARE",
                email="agent@example.com", role="ADMIN",
            )
            with mock.patch.object(metaops.graph, "post", return_value={"id": "777"}) as post:
                code, payload = cmd_business._user_invite(metaops, args)
            self.assertEqual(code, 0)
            path, body = post.call_args.args[0], post.call_args.args[1]
            self.assertEqual(path, "10/business_users")
            self.assertEqual(body, {"email": "agent@example.com", "role": "ADMIN"})
            self.assertEqual(payload["data"]["user_id"], "777")
            self.provisioning.assert_called_once_with(workspace, "test")

    def test_user_assign_tasks_list_and_no_business_field(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            workspace = self.workspace(pathlib.Path(td))
            args = make_args(
                workspace_obj=workspace, profile="test", confirm="SHARE",
                user_id="999", asset="adaccount", tasks="manage, advertise",
            )
            with mock.patch.object(metaops.graph, "post", return_value={}) as post:
                code, payload = cmd_business._user_assign(metaops, args)
            self.assertEqual(code, 0)
            path, body = post.call_args.args[0], post.call_args.args[1]
            self.assertEqual(path, "act_1/assigned_users")
            self.assertEqual(body, {"user": "999", "tasks": ["MANAGE", "ADVERTISE"]})
            self.assertNotIn("business", body)
            self.provisioning.assert_called_once_with(workspace, "test")

    def test_user_assign_resolves_page_and_pixel_asset_ids(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            workspace = self.workspace(pathlib.Path(td))
            with mock.patch.object(metaops.graph, "post", return_value={}) as post:
                args = make_args(
                    workspace_obj=workspace, profile="test", confirm="SHARE",
                    user_id="1", asset="page", tasks="MANAGE",
                )
                cmd_business._user_assign(metaops, args)
                self.assertEqual(post.call_args.args[0], "2/assigned_users")

                args = make_args(
                    workspace_obj=workspace, profile="test", confirm="SHARE",
                    user_id="1", asset="pixel", tasks="EDIT",
                )
                cmd_business._user_assign(metaops, args)
                self.assertEqual(post.call_args.args[0], "3/assigned_users")

    def test_partner_share_payload_uses_agencies_edge(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            workspace = self.workspace(pathlib.Path(td))
            args = make_args(
                workspace_obj=workspace, profile="test", confirm="SHARE",
                partner_business="404", asset="pixel", tasks="advertise,analyze",
            )
            with mock.patch.object(metaops.graph, "post", return_value={}) as post:
                code, payload = cmd_business._partner_share(metaops, args)
            self.assertEqual(code, 0)
            path, body = post.call_args.args[0], post.call_args.args[1]
            self.assertEqual(path, "3/agencies")
            self.assertEqual(body, {"business": "404", "permitted_tasks": ["ADVERTISE", "ANALYZE"]})
            self.provisioning.assert_called_once_with(workspace, "test")

    def test_partner_share_rejects_empty_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            workspace = self.workspace(pathlib.Path(td))
            args = make_args(
                workspace_obj=workspace, profile="test", confirm="SHARE",
                partner_business="404", asset="pixel", tasks="  , ",
            )
            with self.assertRaisesRegex(metaops.MetaOpsError, "at least one task"):
                cmd_business._partner_share(metaops, args)

    # --- pixel share reuses probe.py via run_child --------------------------------

    def test_pixel_share_invokes_probe_attach_pixel(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            workspace = self.workspace(root)
            args = make_args(
                workspace_obj=workspace, profile="test", confirm="SHARE",
                account="act_1", timeout=10,
            )

            def fake_run_child(script, argv, timeout):
                self.assertEqual(script, "probe.py")
                self.assertIn("--attach-pixel", argv)
                self.assertEqual(argv[argv.index("--account") + 1], "act_1")
                self.assertEqual(argv[argv.index("--dataset") + 1], "3")
                self.assertEqual(argv[argv.index("--business") + 1], "10")
                report_path = pathlib.Path(argv[argv.index("--json") + 1])
                report_path.parent.mkdir(parents=True, exist_ok=True)
                report_path.write_text(
                    __import__("json").dumps(
                        [{"gate": "pixel attached to account", "state": "PASS",
                          "detail": "3 attached to act_1 just now"}]
                    ),
                    encoding="utf-8",
                )
                return metaops.ChildResult([script, *argv], 0, "", "")

            with mock.patch.object(metaops, "run_child", side_effect=fake_run_child):
                code, payload = cmd_business._pixel_share(metaops, args)
            self.assertEqual(code, 0)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["data"]["probe_gate"]["state"], "PASS")
            self.provisioning.assert_called_once_with(workspace, "test")

    def test_pixel_share_propagates_child_failure(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            workspace = self.workspace(pathlib.Path(td))
            args = make_args(
                workspace_obj=workspace, profile="test", confirm="SHARE",
                account="act_1", timeout=10,
            )
            with mock.patch.object(
                metaops, "run_child",
                return_value=metaops.ChildResult(["probe.py"], 1, "", "boom"),
            ):
                code, payload = cmd_business._pixel_share(metaops, args)
            self.assertEqual(code, 1)
            self.assertFalse(payload["ok"])

    def test_pixel_share_rejects_account_outside_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            workspace = self.workspace(pathlib.Path(td))
            args = make_args(
                workspace_obj=workspace, profile="test", confirm="SHARE",
                account="act_2", timeout=10,
            )
            with self.assertRaisesRegex(metaops.MetaOpsError, "not declared by this workspace"):
                cmd_business._pixel_share(metaops, args)

    def test_pixel_task_enum_rejects_manage(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            workspace = self.workspace(pathlib.Path(td))
            args = make_args(
                workspace_obj=workspace, profile="test", confirm="SHARE",
                user_id="1", asset="pixel", tasks="MANAGE",
            )
            with self.assertRaisesRegex(metaops.MetaOpsError, "not valid for pixel"):
                cmd_business._user_assign(metaops, args)

    # --- reads / listing -----------------------------------------------------------

    def test_business_assets_lists_every_edge(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            workspace = self.workspace(pathlib.Path(td))
            args = make_args(workspace_obj=workspace, profile="test")

            def fake_get(path, params=None, context=""):
                edge = path.split("/", 1)[1]
                return {"data": [{"id": f"{edge}-1"}]}

            with mock.patch.object(metaops.graph, "get", side_effect=fake_get) as get:
                code, payload = cmd_business._business_assets(metaops, args)
            self.assertEqual(code, 0)
            for edge in cmd_business.BUSINESS_ASSET_EDGES:
                self.assertEqual(payload["data"][edge], [{"id": f"{edge}-1"}])
            self.assertEqual(get.call_count, len(cmd_business.BUSINESS_ASSET_EDGES))

    def test_business_assets_follows_pagination(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            self.workspace(pathlib.Path(td))
            calls = {"n": 0}

            def fake_get(path, params=None, context=""):
                calls["n"] += 1
                if "after" not in params:
                    return {"data": [{"id": "a"}], "paging": {"cursors": {"after": "cursor"}, "next": "https://x/next"}}
                return {"data": [{"id": "b"}]}

            with mock.patch.object(metaops.graph, "get", side_effect=fake_get):
                rows = cmd_business._list_edge(metaops, "10", "owned_pixels", "id,name")
            self.assertEqual(rows, [{"id": "a"}, {"id": "b"}])

    def test_pixel_shared_lists_shared_accounts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            workspace = self.workspace(pathlib.Path(td))
            args = make_args(workspace_obj=workspace, profile="test")
            with mock.patch.object(
                metaops.graph, "get", return_value={"data": [{"id": "act_2", "name": "n"}]}
            ) as get:
                code, payload = cmd_business._pixel_shared(metaops, args)
            self.assertEqual(code, 0)
            self.assertEqual(payload["data"]["shared_accounts"], [{"id": "act_2", "name": "n"}])
            get.assert_called_once()
            self.assertEqual(get.call_args.args[0], "3/shared_accounts")


if __name__ == "__main__":
    unittest.main()

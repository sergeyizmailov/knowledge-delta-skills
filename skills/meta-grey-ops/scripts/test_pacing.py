"""Throttle cooldown + campaign-create pacing (FIELD 2026-09-27 automation ban)."""
from __future__ import annotations
import os as _os, tempfile as _tempfile
_os.environ["METAOPS_PACE_DIR"] = _tempfile.mkdtemp(prefix="metaops-pace-test-")
_os.environ.setdefault("METAOPS_CREATE_GAP_HOURS", "0")

import json
import os
import tempfile
import time
import unittest
from unittest import mock

os.environ.setdefault("META_TOKEN", "TEST_TOKEN")
import graph  # noqa: E402


class _Resp:
    def __init__(self, payload, status=200, headers=None):
        self._payload = payload
        self.status_code = status
        self.ok = status < 400
        self.headers = headers or {}
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


THROTTLE = {"error": {"code": 17, "error_subcode": 2446079, "message": "too many calls"}}


class PacingTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.env = mock.patch.dict(os.environ, {"METAOPS_PACE_DIR": self.dir,
                                                "METAOPS_CREATE_GAP_HOURS": "3",
                                                "METAOPS_PACE_OVERRIDE": ""})
        self.env.start()
        graph._LAST_ACCOUNT = None
        self.auth = mock.patch.object(graph, "require_write_authority", lambda *a, **k: None)
        self.auth.start()

    def tearDown(self):
        self.auth.stop()
        self.env.stop()

    def _session(self, *responses):
        sess = mock.Mock()
        sess.request.side_effect = list(responses)
        return mock.patch.object(graph, "session", return_value=sess), sess

    def test_throttle_is_not_retried_and_sets_account_cooldown(self):
        patcher, sess = self._session(_Resp(THROTTLE, 400))
        with patcher, mock.patch.object(graph.time, "sleep") as sleep:
            with self.assertRaises(graph.GraphError) as cm:
                graph.get("act_1/insights")
        self.assertEqual(cm.exception.code, 17)
        self.assertEqual(sess.request.call_count, 1)
        sleep.assert_not_called()
        self.assertGreater(graph.cooldown_remaining("act_1"), 29 * 60)
        self.assertEqual(graph.cooldown_remaining("act_2"), 0)

    def test_cooldown_blocks_without_sending(self):
        graph._set_cooldown("act_1", 600, "test")
        patcher, sess = self._session(_Resp({"data": []}))
        with patcher:
            with self.assertRaises(graph.CooldownError) as cm:
                graph.get("act_1/ads")
            self.assertFalse(cm.exception.outcome_unknown)
            sess.request.assert_not_called()
            # object path without act_ inherits the last account seen in this process
            with self.assertRaises(graph.CooldownError):
                graph.get("123456/ads")
            graph._LAST_ACCOUNT = None
            self.assertEqual(graph.get("act_2/ads"), {"data": []})

    def test_override_bypasses_cooldown(self):
        graph._set_cooldown("act_1", 600, "test")
        patcher, _ = self._session(_Resp({"data": []}))
        with patcher, mock.patch.dict(os.environ, {"METAOPS_PACE_OVERRIDE": "1"}):
            self.assertEqual(graph.get("act_1/ads"), {"data": []})

    def test_app_level_throttle_is_global(self):
        patcher, _ = self._session(_Resp({"error": {"code": 4, "message": "app limit"}}, 400))
        with patcher:
            with self.assertRaises(graph.GraphError):
                graph.get("act_1/ads")
        self.assertGreater(graph.cooldown_remaining("act_9"), 0)

    def test_campaign_create_gap(self):
        graph.check_campaign_create_pace("act_1")          # nothing recorded yet
        graph.record_campaign_create("1")
        with self.assertRaises(graph.PacingError):
            graph.check_campaign_create_pace("act_1")
        graph.check_campaign_create_pace("act_2")          # other account unaffected
        with mock.patch.dict(os.environ, {"METAOPS_PACE_OVERRIDE": "1"}):
            graph.check_campaign_create_pace("act_1")
        data = graph._pace_load()
        data["last_campaign_create"]["act_1"] = time.time() - 3 * 3600 - 1
        graph._pace_save(data)
        graph.check_campaign_create_pace("act_1")

    def test_per_object_613_waits_once_without_cooldown(self):
        busy = {"error": {"code": 613, "error_subcode": 4841018, "message": "1 calls per 30 seconds"}}
        patcher, sess = self._session(_Resp(busy, 400), _Resp({"success": True}))
        with patcher, mock.patch.object(graph.time, "sleep") as sleep:
            self.assertEqual(graph.post("123", {"status": "DELETED"}, idempotent=True), {"success": True})
        sleep.assert_called_once_with(35)
        self.assertEqual(graph._pace_load().get("cooldown", {}), {})

    def test_account_throttle_on_object_path_without_context_is_object_scoped(self):
        patcher, _ = self._session(_Resp(THROTTLE, 400), _Resp({"data": []}))
        with patcher:
            with self.assertRaises(graph.GraphError):
                graph.get("777/ads")
            self.assertEqual(graph.cooldown_remaining("act_2"), 0)
            with self.assertRaises(graph.CooldownError):
                graph.get("777/insights")
            self.assertEqual(graph.get("act_2/ads"), {"data": []})


if __name__ == "__main__":
    unittest.main()

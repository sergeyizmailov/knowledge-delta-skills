"""Throttle cooldown + campaign-create pacing (FIELD 2026-09-27 automation ban)."""
from __future__ import annotations
import os as _os, tempfile as _tempfile
_os.environ["METAOPS_PACE_DIR"] = _tempfile.mkdtemp(prefix="metaops-pace-test-")
_os.environ.setdefault("METAOPS_CREATE_GAP_HOURS", "0")

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import textwrap
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


    # --- x-fb-ads-insights-throttle (Insights calls) -------------------------------------

    INSIGHTS_THROTTLE = "x-fb-ads-insights-throttle"

    def _throttle_header(self, app=12.0, acc=10.0):
        return {self.INSIGHTS_THROTTLE: json.dumps(
            {"app_id_util_pct": app, "acc_id_util_pct": acc, "ads_api_access_tier": "standard_access"})}

    def test_insights_throttle_header_counts_as_usage(self):
        # the worst of app / account utilisation wins; the tier string is ignored
        self.assertEqual(graph._worst_usage(self._throttle_header(app=12.0, acc=91.5)), 91.5)
        self.assertEqual(graph._worst_usage(self._throttle_header(app=93.0, acc=10.0)), 93.0)

    def test_insights_throttle_header_pauses_at_the_shared_threshold(self):
        patcher, _ = self._session(_Resp({"data": []}, headers=self._throttle_header(acc=90.0)))
        with patcher, mock.patch.object(graph.time, "sleep") as sleep:
            self.assertEqual(graph.get("act_1/insights"), {"data": []})
        sleep.assert_called_once()
        self.assertAlmostEqual(sleep.call_args[0][0], 54.0)

    def test_insights_throttle_header_below_threshold_or_malformed_does_not_sleep(self):
        for headers in (self._throttle_header(app=40.0, acc=50.0),
                        {self.INSIGHTS_THROTTLE: "not json"},
                        {self.INSIGHTS_THROTTLE: json.dumps({"ads_api_access_tier": "standard_access"})}):
            patcher, _ = self._session(_Resp({"data": []}, headers=headers))
            with patcher, mock.patch.object(graph.time, "sleep") as sleep:
                graph.get("act_1/insights")
            sleep.assert_not_called()

    # --- locked, per-process pacing writes -----------------------------------------------

    def test_pace_writes_use_a_tmp_file_unique_to_process_and_call(self):
        seen = []
        real_replace = os.replace

        def spy(src, dst):
            seen.append(os.path.basename(src))
            real_replace(src, dst)

        with mock.patch.object(graph.os, "replace", spy):
            graph._pace_save({"a": 1})
            graph._pace_save({"a": 2})
        self.assertEqual(len(seen), 2)
        self.assertEqual(len(set(seen)), 2, seen)
        self.assertNotIn("pacing.json.tmp", seen)
        self.assertTrue(all(str(os.getpid()) in name for name in seen), seen)
        self.assertEqual(graph._pace_load(), {"a": 2})

    def _child_env(self):
        return {**os.environ, "METAOPS_PACE_DIR": self.dir, "PYTHONPATH": str(pathlib.Path(__file__).parent)}

    def test_pace_lock_excludes_a_second_process(self):
        script = "import graph; graph._set_cooldown('act_7', 600, 'child'); print('done')"
        with graph._pace_lock():
            proc = subprocess.Popen([sys.executable, "-c", script], env=self._child_env(),
                                    cwd=pathlib.Path(__file__).parent, text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            time.sleep(1.0)
            still_waiting = proc.poll() is None
            self.assertNotIn("act_7", graph._pace_load().get("cooldown", {}))
        out, err = proc.communicate(timeout=30)
        self.assertTrue(still_waiting, "the second process wrote while the first held the pacing lock")
        self.assertEqual(proc.returncode, 0, err)
        self.assertGreater(graph.cooldown_remaining("act_7"), 500)

    def test_pace_lock_is_reentrant_inside_one_process(self):
        with graph._pace_lock():
            graph._set_cooldown("act_1", 60, "nested")
            graph.record_campaign_create("act_1")
            graph._pace_save(graph._pace_load())
        self.assertGreater(graph.cooldown_remaining("act_1"), 0)
        self.assertIn("act_1", graph._pace_load()["last_campaign_create"])

    def test_concurrent_processes_lose_no_cooldown_or_create_record(self):
        script = textwrap.dedent("""
            import sys, graph
            tag = sys.argv[1]
            for i in range(25):
                graph._set_cooldown(f"act_{tag}{i}", 600, "stress")
                graph.record_campaign_create(f"{tag}{i}")
        """)
        procs = [subprocess.Popen([sys.executable, "-c", script, tag], env=self._child_env(),
                                  cwd=pathlib.Path(__file__).parent, text=True,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                 for tag in "1234"]
        for proc in procs:
            _, err = proc.communicate(timeout=120)
            self.assertEqual(proc.returncode, 0, err)
        data = graph._pace_load()
        self.assertEqual(len(data["cooldown"]), 100)
        self.assertEqual(len(data["last_campaign_create"]), 100)

    def test_clear_cooldown_removes_key_and_reason(self):
        graph._set_cooldown("act_5", 600, "why")
        graph._set_cooldown("act_6", 600, "other")
        self.assertTrue(graph.clear_cooldown("act_5"))
        self.assertFalse(graph.clear_cooldown("act_5"))
        data = graph._pace_load()
        self.assertNotIn("act_5", data["cooldown"])
        self.assertNotIn("act_5", data["cooldown_reason"])
        self.assertIn("act_6", data["cooldown"])


if __name__ == "__main__":
    unittest.main()

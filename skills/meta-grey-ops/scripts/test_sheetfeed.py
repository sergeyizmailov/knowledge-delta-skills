#!/usr/bin/env python3
"""Offline contract tests for sheetfeed.py. No Google credentials or network."""

from __future__ import annotations
import os as _os, tempfile as _tempfile
_os.environ["METAOPS_PACE_DIR"] = _tempfile.mkdtemp(prefix="metaops-pace-test-")
_os.environ.setdefault("METAOPS_CREATE_GAP_HOURS", "0")

import unittest
from unittest import mock

import sheetfeed


class Response:
    def __init__(self, status: int, payload: dict | None = None, *, headers: dict | None = None, text: str = ""):
        self.status_code = status
        self.payload = payload or {}
        self.headers = headers or {}
        self.text = text

    def json(self) -> dict:
        return self.payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


def bare_sheet(session) -> sheetfeed.Sheet:
    sheet = sheetfeed.Sheet.__new__(sheetfeed.Sheet)
    sheet.session = session
    sheet.id = "test-sheet-id-00000000"
    sheet.tab = "products"
    sheet.sa_email = "service@example.test"
    return sheet


class SheetFeedTests(unittest.TestCase):
    def test_429_honours_retry_after_then_succeeds(self) -> None:
        session = mock.Mock()
        session.get.side_effect = [
            Response(429, headers={"Retry-After": "0"}, text="quota"),
            Response(200, {"values": [["id"], ["sku-1"]]}),
        ]
        with mock.patch.object(sheetfeed.time, "sleep") as sleep:
            result = bare_sheet(session)._get("/values/products")
        self.assertEqual(result["values"][1][0], "sku-1")
        self.assertEqual(session.get.call_count, 2)
        sleep.assert_called_once_with(0.0)

    def test_429_stops_after_bounded_retries(self) -> None:
        session = mock.Mock()
        session.get.return_value = Response(429, headers={"Retry-After": "0"}, text="quota")
        with mock.patch.object(sheetfeed.time, "sleep") as sleep:
            with self.assertRaisesRegex(sheetfeed.SheetError, "remained unavailable"):
                bare_sheet(session)._get("/values/products")
        self.assertEqual(session.get.call_count, sheetfeed.SHEETS_RATE_RETRY_ATTEMPTS)
        self.assertEqual(sleep.call_count, sheetfeed.SHEETS_RATE_RETRY_ATTEMPTS - 1)

    def test_503_uses_the_same_bounded_backoff(self) -> None:
        session = mock.Mock()
        session.get.side_effect = [
            Response(503, text="backend unavailable"),
            Response(200, {"values": [["id"], ["sku-1"]]}),
        ]
        with mock.patch.object(sheetfeed.time, "sleep") as sleep:
            result = bare_sheet(session)._get("/values/products")
        self.assertEqual(result["values"][1][0], "sku-1")
        self.assertEqual(session.get.call_count, 2)
        self.assertEqual(sleep.call_count, 1)

    def test_upsert_rejects_duplicate_input_before_a_write(self) -> None:
        sheet = bare_sheet(mock.Mock())
        sheet.write_header = mock.Mock()
        sheet._post = mock.Mock()
        with self.assertRaisesRegex(sheetfeed.SheetError, "input contains duplicate id"):
            sheet.upsert([{"id": "sku-1"}, {"id": "sku-1"}], ["id"], [])
        sheet.write_header.assert_not_called()
        sheet._post.assert_not_called()

    def test_upsert_rejects_ambiguous_existing_sheet_before_a_write(self) -> None:
        sheet = bare_sheet(mock.Mock())
        sheet.write_header = mock.Mock()
        sheet._post = mock.Mock()
        with self.assertRaisesRegex(sheetfeed.SheetError, "sheet contains duplicate id"):
            sheet.upsert([{"id": "sku-1", "title": "replacement"}], ["id", "title"], [
                ["sku-1", "first"], ["sku-1", "second"],
            ])
        sheet.write_header.assert_not_called()
        sheet._post.assert_not_called()


if __name__ == "__main__":
    unittest.main()

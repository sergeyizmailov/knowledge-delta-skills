#!/usr/bin/env python3
"""Offline contract tests for sheetfeed.py. No Google credentials or network."""

from __future__ import annotations
import os as _os, tempfile as _tempfile
_os.environ["METAOPS_PACE_DIR"] = _tempfile.mkdtemp(prefix="metaops-pace-test-")
_os.environ.setdefault("METAOPS_CREATE_GAP_HOURS", "0")

import contextlib
import io
import json
import sys
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


HEADER = sheetfeed.REQUIRED + ["gtin"]


def good_row(pid: str = "sku-1") -> list[str]:
    return [pid, "Title", "Desc", "in stock", "new", "19.99 USD", "https://example.com/p",
            "https://example.com/p.jpg", "Brand", "123"]


class SetCommandTests(unittest.TestCase):
    """`set` edits one field of an EXISTING product and validates the row it would write."""

    def test_unknown_id_is_refused_instead_of_appending_a_junk_row(self) -> None:
        with self.assertRaisesRegex(sheetfeed.SheetError, "unknown id 'sku-typo'"):
            sheetfeed.checked_set_item(HEADER, [good_row()], "sku-typo", "title", "New", "meta")

    def test_unknown_field_is_refused_instead_of_adding_a_junk_column(self) -> None:
        with self.assertRaisesRegex(sheetfeed.SheetError, "unknown field 'titel'"):
            sheetfeed.checked_set_item(HEADER, [good_row()], "sku-1", "titel", "New", "meta")

    def test_id_column_cannot_be_rewritten(self) -> None:
        with self.assertRaisesRegex(sheetfeed.SheetError, "cannot change the id"):
            sheetfeed.checked_set_item(HEADER, [good_row()], "sku-1", "id", "sku-2", "meta")

    def test_known_feed_column_missing_from_the_header_is_allowed(self) -> None:
        item = sheetfeed.checked_set_item(HEADER, [good_row()], "sku-1", "custom_label_0", "a", "meta")
        self.assertEqual(item, {"id": "sku-1", "custom_label_0": "a"})

    def test_a_write_that_breaks_the_row_is_refused(self) -> None:
        with self.assertRaisesRegex(sheetfeed.SheetError, "price must look like"):
            sheetfeed.checked_set_item(HEADER, [good_row()], "sku-1", "price", "cheap", "meta")
        with self.assertRaisesRegex(sheetfeed.SheetError, "availability"):
            sheetfeed.checked_set_item(HEADER, [good_row()], "sku-1", "availability", "maybe", "meta")

    def test_an_unrelated_existing_problem_does_not_block_a_valid_fix(self) -> None:
        broken = good_row("sku-2")
        broken[5] = "free"                       # pre-existing bad price on another row
        item = sheetfeed.checked_set_item(HEADER, [good_row(), broken], "sku-1", "title", "Fixed", "meta")
        self.assertEqual(item["title"], "Fixed")

    def test_main_never_reaches_upsert_for_an_unknown_id(self) -> None:
        sheet = mock.Mock()
        sheet.read.return_value = (HEADER, [good_row()])
        argv = ["sheetfeed", "--sheet", "x" * 30, "--json", "set", "--id", "nope", "--field", "title",
                "--value", "v"]
        out = io.StringIO()
        with (
            mock.patch.object(sheetfeed, "Sheet", return_value=sheet),
            mock.patch.object(sys, "argv", argv),
            contextlib.redirect_stdout(out),
        ):
            code = sheetfeed.main()
        self.assertEqual(code, 2)
        sheet.upsert.assert_not_called()
        self.assertIn("unknown id", json.loads(out.getvalue())["error"]["message"])

    def test_main_upserts_a_valid_set(self) -> None:
        sheet = mock.Mock()
        sheet.read.return_value = (HEADER, [good_row()])
        sheet.upsert.return_value = {"updated": 1, "appended": 0}
        argv = ["sheetfeed", "--sheet", "x" * 30, "--json", "set", "--id", "sku-1", "--field", "title",
                "--value", "New"]
        with (
            mock.patch.object(sheetfeed, "Sheet", return_value=sheet),
            mock.patch.object(sys, "argv", argv),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(sheetfeed.main(), 0)
        self.assertEqual(sheet.upsert.call_args.args[0], [{"id": "sku-1", "title": "New"}])


if __name__ == "__main__":
    unittest.main()

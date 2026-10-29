"""Offline checks: no Fabric credentials or network calls are used."""

import base64
import contextlib
import copy
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import verify_stocks_unchanged as verify

ITEM_ID = "11111111-2222-3333-4444-555555555555"


def definition(text="original"):
    return {"definition": {"parts": [
        {"path": "model.tmdl", "payload": base64.b64encode(text.encode()).decode(), "payloadType": "InlineBase64"},
        {"path": ".platform", "payload": "e30=", "payloadType": "InlineBase64"},
    ]}}


def response(payload=None, code=200, headers=None):
    return Mock(status_code=code, headers=headers or {}, json=Mock(return_value=payload))


class SelectivityTests(unittest.TestCase):
    def setUp(self):
        network = patch("requests.sessions.Session.request", side_effect=AssertionError("Network forbidden"))
        network.start()
        self.addCleanup(network.stop)
        self.before = {"SemanticModel": {"id": ITEM_ID, "displayName": "Stocks Index", "description": "", "folderId": None, "parts": verify.part_hashes(definition())}}

    def test_part_order_is_irrelevant(self):
        reordered = definition()
        reordered["definition"]["parts"].reverse()
        after = copy.deepcopy(self.before)
        after["SemanticModel"]["parts"] = verify.part_hashes(reordered)
        self.assertEqual(verify.differences(self.before, after), [])

    def test_changed_bytes_are_detected_with_same_id(self):
        after = copy.deepcopy(self.before)
        after["SemanticModel"]["parts"] = verify.part_hashes(definition("changed"))
        self.assertEqual(verify.differences(self.before, after), ["SemanticModel: definition part changed: model.tmdl"])

    def test_deleted_or_added_definition_part_is_detected(self):
        after = copy.deepcopy(self.before)
        del after["SemanticModel"]["parts"][".platform"]
        self.assertTrue(verify.differences(self.before, after))
        self.assertTrue(verify.differences(after, self.before))

    def test_recreated_item_or_metadata_change_is_detected(self):
        for field in ("id", "displayName", "description", "folderId"):
            after = copy.deepcopy(self.before)
            after["SemanticModel"][field] = "changed"
            self.assertIn(f"SemanticModel: {field} changed", verify.differences(self.before, after))

    def test_empty_duplicate_or_invalid_parts_are_rejected(self):
        empty = {"definition": {"parts": []}}
        duplicate = definition()
        duplicate["definition"]["parts"].append(duplicate["definition"]["parts"][0])
        invalid = definition()
        invalid["definition"]["parts"][0]["payload"] = "not base64!"
        for value in (empty, duplicate, invalid):
            with self.assertRaises(ValueError):
                verify.part_hashes(value)

    def test_async_export_reads_result_without_following_arbitrary_url(self):
        session = Mock()
        session.request.side_effect = [
            response(code=202, headers={"x-ms-operation-id": ITEM_ID, "Location": "https://example.invalid", "Retry-After": "1"}),
            response({"status": "Running"}),
            response({"status": "Succeeded"}),
            response(definition()),
        ]
        with patch.object(verify.time, "sleep"):
            self.assertEqual(verify.get_definition(session, verify.TEST_WORKSPACE_ID, ITEM_ID), definition())
        calls = session.request.call_args_list
        self.assertEqual([call.args[0] for call in calls], ["POST", "GET", "GET", "GET"])
        self.assertTrue(all(call.args[1].startswith(verify.API + "/") for call in calls))
        self.assertTrue(calls[-1].args[1].endswith("/result"))
        self.assertTrue(all(call.kwargs["allow_redirects"] is False for call in calls))

    def test_failed_export_is_not_success(self):
        session = Mock()
        session.request.side_effect = [response(code=202, headers={"x-ms-operation-id": ITEM_ID}), response({"status": "Failed"})]
        with patch.object(verify.time, "sleep"), self.assertRaisesRegex(ValueError, "export failed"):
            verify.get_definition(session, verify.TEST_WORKSPACE_ID, ITEM_ID)

    def test_missing_stocks_pair_prevents_baseline(self):
        session = Mock()
        session.request.return_value = response({"value": []})
        with self.assertRaisesRegex(ValueError, "Expected exactly one"):
            verify.snapshot(session, verify.TEST_WORKSPACE_ID)
        self.assertEqual(session.request.call_count, 1)

    def test_snapshot_follows_inventory_pages_and_captures_both_types(self):
        session = Mock()
        session.request.side_effect = [
            response({"value": [{"id": ITEM_ID, "displayName": "Stocks Index", "type": "Report"}], "continuationToken": "next"}),
            response({"value": [{"id": ITEM_ID, "displayName": "Stocks Index", "type": "SemanticModel"}]}),
            response(definition()), response(definition()),
        ]
        with contextlib.redirect_stdout(io.StringIO()):
            result = verify.snapshot(session, verify.TEST_WORKSPACE_ID)
        self.assertEqual(set(result), {"Report", "SemanticModel"})
        self.assertEqual(session.request.call_args_list[1].kwargs["params"]["continuationToken"], "next")


if __name__ == "__main__":
    unittest.main()

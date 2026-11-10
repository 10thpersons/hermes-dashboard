"""Offline ID-bound router regressions. Only temporary dummy state and fake child effects."""
import asyncio
import copy
import json
from pathlib import Path
import runpy
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from fastapi import HTTPException
from pydantic import ValidationError
from routers import affiliate
from draft_ids import ensure_draft_ids, pending_draft


class DraftIdentityTests(unittest.TestCase):
    def setUp(self):
        self.state = {"drafts": [
            {"text": "low A", "score": 70, "published": False},
            {"text": "high B", "score": 95, "published": False},
        ], "counts": {"dummy:post": 0}, "posts": []}
        self.patches = [
            patch.object(affiliate, "_load_state", side_effect=lambda: copy.deepcopy(self.state)),
            patch.object(affiliate, "_save_state", side_effect=self.save),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def save(self, value):
        self.state = copy.deepcopy(value)

    def listing(self):
        return asyncio.run(affiliate.list_drafts())

    def test_score_order_rejects_only_selected_stored_record(self):
        listed = self.listing()
        self.assertEqual([d["text"] for d in listed], ["high B", "low A"])
        identity = listed[0]["id"]
        self.assertEqual([d["text"] for d in self.state["drafts"]], ["low A", "high B"])
        result = asyncio.run(affiliate.reject_drafts([identity]))
        self.assertEqual(result, {"rejected": 1})
        self.assertFalse(self.state["drafts"][0]["published"])
        self.assertTrue(self.state["drafts"][1]["rejected"])

    def test_membership_changes_do_not_shift_selection(self):
        listed = self.listing()
        high, low = listed[0]["id"], listed[1]["id"]
        asyncio.run(affiliate.reject_drafts([low]))
        self.state["drafts"].insert(0, {"text": "new C", "score": 99, "published": False})
        ensure_draft_ids(self.state)
        asyncio.run(affiliate.reject_drafts([high]))
        self.assertFalse(self.state["drafts"][0]["published"])
        self.assertTrue(next(d for d in self.state["drafts"] if d["id"] == high)["rejected"])

    def test_unknown_stale_empty_duplicate_batch_fails_without_partial_mutation(self):
        listed = self.listing()
        high, low = listed[0]["id"], listed[1]["id"]
        asyncio.run(affiliate.reject_drafts([low]))
        for ids in ([high, "missing"], [high, low], [""], [], [high, high]):
            before = copy.deepcopy(self.state)
            with self.subTest(ids=ids), self.assertRaises(HTTPException):
                asyncio.run(affiliate.reject_drafts(ids))
            self.assertEqual(self.state, before)

    def test_publish_rejects_positional_or_missing_identity(self):
        for body in ({}, {"draft_index": 0}, {"draft_id": ""}, {"draft_id": 0}):
            with self.assertRaises(ValidationError):
                affiliate.PublishBody(**body)
        self.listing()
        with patch.object(affiliate.subprocess, "run") as child:
            with self.assertRaises(HTTPException):
                asyncio.run(affiliate.publish(affiliate.PublishBody(draft_id="missing")))
            child.assert_not_called()

    def test_publish_child_reselects_id_and_owns_final_mutation(self):
        selected_id = self.listing()[0]["id"]
        # Execute ONLY the extracted child script against synthetic modules, not a bot.
        def fake_child(command, **kwargs):
            self.assertEqual(command[3:], [selected_id, "false"])
            child_state = copy.deepcopy(self.state)
            child_state["drafts"].reverse()  # A positional selection would now be wrong.
            state_object = SimpleNamespace(data=child_state, save=lambda: self.save(child_state))
            captured = []

            class FakeDraft:
                def __init__(self, **fields):
                    self.__dict__.update(fields)

            class FakePipeline:
                def __init__(self, state):
                    self.state = state

                def publish(self, draft):
                    captured.append(draft.text)
                    self.state.data["counts"]["dummy:post"] += 1
                    return {"post_id": "dummy-post", "published_at": "dummy-time"}

            modules = {
                "bot": SimpleNamespace(),
                "bot.state": SimpleNamespace(State=lambda: state_object),
                "bot.draft_ids": SimpleNamespace(pending_draft=pending_draft),
                "bot.writer": SimpleNamespace(Draft=FakeDraft),
                "bot.pipeline": SimpleNamespace(Pipeline=FakePipeline),
            }
            output = []
            with patch.dict(sys.modules, modules), patch.object(sys, "argv", ["-c", *command[3:]]):
                exec(command[2], {"print": lambda text: output.append(text)})
            self.assertEqual(captured, ["high B"])
            return SimpleNamespace(returncode=0, stdout="\n".join(output), stderr="")

        with patch.object(affiliate.subprocess, "run", side_effect=fake_child):
            result = asyncio.run(affiliate.publish(affiliate.PublishBody(draft_id=selected_id)))
        self.assertEqual(result["draft_id"], selected_id)
        self.assertEqual(self.state["counts"]["dummy:post"], 1)
        self.assertTrue(next(d for d in self.state["drafts"] if d["id"] == selected_id)["published"])
        self.assertFalse(next(d for d in self.state["drafts"] if d["id"] != selected_id)["published"])

    def test_migration_deterministic_unique_persisted_and_never_reuses_counter(self):
        bot_helper = runpy.run_path(str(BACKEND.parent / "affiliate-bot/bot/draft_ids.py"))
        original = {"drafts": [{"text": "same"}, {"text": "same"}, {"id": "draft-8"}]}
        first, second = copy.deepcopy(original), copy.deepcopy(original)
        ensure_draft_ids(first)
        bot_helper["ensure_draft_ids"](second)
        self.assertEqual(first, second)
        self.assertEqual(len({d["id"] for d in first["drafts"]}), 3)
        self.assertFalse(ensure_draft_ids(first))
        previous = first["next_draft_id"]
        first["drafts"] = [{"text": "new"}]
        ensure_draft_ids(first)
        self.assertEqual(first["drafts"][0]["id"], f"draft-{previous}")
        initial_listing = self.listing()
        self.assertEqual(initial_listing, self.listing())
        self.assertTrue(all(d.get("id") for d in self.state["drafts"]))
        with self.assertRaises(ValueError):
            ensure_draft_ids({"drafts": [{"id": "duplicate"}, {"id": "duplicate"}]})


if __name__ == "__main__":
    unittest.main()

"""Stdlib staging/migration regression using a stub config and temporary dummy ledger."""
import json
from pathlib import Path
import runpy
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

BOT = Path(__file__).resolve().parents[1] / "bot"


class StagingIdentityTests(unittest.TestCase):
    def test_legacy_duplicates_staging_and_reload_keep_unique_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ledger = root / "state.json"
            ledger.write_text(json.dumps({"drafts": [{"text": "same"}, {"text": "same"}]}))
            package = types.ModuleType("fixture_bot")
            package.__path__ = [str(BOT)]
            config = types.ModuleType("fixture_bot.config")
            config.STATE = root
            helpers = types.ModuleType("fixture_bot.draft_ids")
            helpers.__dict__.update(runpy.run_path(str(BOT / "draft_ids.py")))
            modules = {"fixture_bot": package, "fixture_bot.config": config,
                       "fixture_bot.draft_ids": helpers}
            with patch.dict(sys.modules, modules):
                # Import only this source file, with no real bot configuration.
                state_source = (BOT / "state.py").read_text()
                namespace = {"__name__": "fixture_bot.state", "__package__": "fixture_bot"}
                exec(compile(state_source, str(BOT / "state.py"), "exec"), namespace)
                State = namespace["State"]
                state = State(path=ledger)
                original = [d["id"] for d in state.data["drafts"]]
                self.assertEqual(len(set(original)), 2)
                self.assertEqual(original, [d["id"] for d in json.loads(ledger.read_text())["drafts"]])
                new = {"text": "same"}
                state.add_draft(new)
                self.assertNotIn(new["id"], original)
                state.save()
                self.assertEqual([*original, new["id"]], [d["id"] for d in State(path=ledger).data["drafts"]])
                with self.assertRaises(ValueError):
                    state.add_draft({"id": original[0], "text": "must not reuse"})


if __name__ == "__main__":
    unittest.main()

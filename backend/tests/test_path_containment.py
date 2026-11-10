"""Path-containment regressions; run with stdlib unittest discovery."""
import importlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


BACKEND_DIR = Path(__file__).resolve().parents[1]


class PathContainmentTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.home = self.base / "hermes"
        self.vault = self.base / "vault"
        self.outside = self.base / "outside"
        self.output = self.home / "cron" / "output"
        for directory in (self.vault, self.outside, self.output):
            directory.mkdir(parents=True)

        # Configure dummy stores before importing config or the service. Patch
        # service constants too, so cached imports cannot point at real stores.
        environment = patch.dict(os.environ, {
            "HERMES_HOME": str(self.home),
            "OBSIDIAN_VAULT": str(self.vault),
        })
        environment.start()
        self.addCleanup(environment.stop)
        search_path = patch.object(sys, "path", [str(BACKEND_DIR), *sys.path])
        search_path.start()
        self.addCleanup(search_path.stop)
        importlib.import_module("config")
        self.data = importlib.import_module("services.hermes_data")
        stores = patch.multiple(
            self.data, OBSIDIAN_VAULT=self.vault, CRON_OUTPUT_DIR=self.output
        )
        stores.start()
        self.addCleanup(stores.stop)

        (self.outside / "secret.md").write_text("outside secret", encoding="utf-8")
        (self.output.parent / "notes.md").write_text("parent secret", encoding="utf-8")
        sibling = self.output.parent / "x"
        sibling.mkdir()
        (sibling / "secret.md").write_text("sibling secret", encoding="utf-8")

    def test_tree_root_and_subdirectory_preserve_relative_paths(self):
        (self.vault / "root.md").write_text("root", encoding="utf-8")
        subdir = self.vault / "subdir"
        subdir.mkdir()
        (subdir / "note.md").write_text("note", encoding="utf-8")
        (self.vault / ".hidden.md").write_text("hidden", encoding="utf-8")
        (self.vault / ".hidden-dir").mkdir()
        (subdir / ".hidden.md").write_text("hidden", encoding="utf-8")
        expected = [
            {"name": "root.md", "path": "root.md", "type": "file", "size": 4},
            {"name": "subdir", "path": "subdir", "type": "directory", "size": None},
        ]
        self.assertEqual(self.data.get_obsidian_tree(), expected)
        self.assertEqual(self.data.get_obsidian_tree(""), expected)
        self.assertEqual(self.data.get_obsidian_tree("subdir"), [
            {"name": "note.md", "path": "subdir/note.md", "type": "file", "size": 4},
        ])

    def test_tree_rejects_traversal_and_absolute_outside_path(self):
        for path in ("../outside", str(self.outside.resolve())):
            with self.subTest(path=path):
                self.assertEqual(self.data.get_obsidian_tree(path), [])

    def test_tree_rejects_outside_symlink_and_skips_escaped_children(self):
        (self.vault / "escape").symlink_to(self.outside, target_is_directory=True)
        (self.vault / "secret-link.md").symlink_to(self.outside / "secret.md")
        self.assertEqual(self.data.get_obsidian_tree("escape"), [])
        self.assertEqual(self.data.get_obsidian_tree(), [])

    def test_tree_paths_are_relative_to_resolved_vault_base(self):
        (self.vault / "note.md").write_text("note", encoding="utf-8")
        alias = self.base / "vault-alias"
        alias.symlink_to(self.vault, target_is_directory=True)
        with patch.object(self.data, "OBSIDIAN_VAULT", alias):
            self.assertEqual(self.data.get_obsidian_tree(), [
                {"name": "note.md", "path": "note.md", "type": "file", "size": 4},
            ])

    def test_cron_valid_per_job_directory_and_loose_file(self):
        job_id = "Job-1_test.v2"
        job_dir = self.output / job_id
        job_dir.mkdir()
        per_job = job_dir / "2026-11-10_10-00-00.md"
        loose = self.output / f"{job_id}_20261110_110000.txt"
        per_job.write_text("per-job output", encoding="utf-8")
        loose.write_text("loose output", encoding="utf-8")
        os.utime(per_job, (1000, 1000))
        os.utime(loose, (2000, 2000))
        (job_dir / ".hidden.md").write_text("hidden", encoding="utf-8")
        (job_dir / "ignored.json").write_text("{}", encoding="utf-8")
        (self.output / "other_20261110.txt").write_text("other", encoding="utf-8")

        scan = self.data._scan_cron_output(job_id)
        self.assertEqual(scan["count"], 2)
        self.assertEqual([entry["path"] for entry in scan["files"]],
                         [str(per_job), str(loose)])
        self.assertEqual(scan["latest"], scan["files"][-1])
        history = self.data.get_cron_history(job_id)
        self.assertEqual(history["count"], 2)
        self.assertEqual(history["files"], list(reversed(scan["files"])))
        self.assertEqual(self.data.get_cron_output(job_id)["content"], "loose output")
        self.assertEqual(
            self.data.read_cron_output_file(job_id, per_job.name)["content"],
            "per-job output",
        )
        self.assertEqual(
            self.data.read_cron_output_file(job_id, loose.name)["content"],
            "loose output",
        )

    def test_cron_rejects_invalid_ids_without_exposing_files(self):
        nested = self.output / "a" / "b"
        nested.mkdir(parents=True)
        (nested / "secret.md").write_text("nested secret", encoding="utf-8")
        invalid_ids = ("..", "../x", "a/b", "", ".hidden", "a..b",
                       "a\\b", "a b", "a\n", "a" * 129, str(self.outside))
        # Even matching loose files must not make invalid IDs acceptable.
        for job_id in (".hidden", "a..b", "a b", "a" * 129):
            (self.output / f"{job_id}_output.md").write_text("invalid", encoding="utf-8")
        for job_id in invalid_ids:
            with self.subTest(job_id=job_id):
                self.assertEqual(self.data._scan_cron_output(job_id), {
                    "files": [], "latest": None, "count": 0,
                })
                self.assertEqual(self.data.get_cron_history(job_id), {
                    "job_id": job_id, "count": 0, "files": [],
                })
                self.assertIsNone(self.data.get_cron_output(job_id))
                self.assertIsNone(self.data.read_cron_output_file(job_id, "notes.md"))
                self.assertIsNone(self.data.read_cron_output_file(job_id, "secret.md"))

    def test_cron_rejects_per_job_directory_symlink_outside_output(self):
        (self.output / "linked-job").symlink_to(self.outside, target_is_directory=True)
        self.assertEqual(self.data._scan_cron_output("linked-job"), {
            "files": [], "latest": None, "count": 0,
        })
        self.assertIsNone(self.data.read_cron_output_file("linked-job", "secret.md"))


if __name__ == "__main__":
    unittest.main()

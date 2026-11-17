"""Windows regression tests for ancestor escapes and exclusive destination writes."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pyquaddir_addons as addons


@unittest.skipUnless(os.name == "nt", "Windows pinned-path write backend")
class WriteSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.left, self.right, self.outside = [self.root / name for name in ("left", "right", "outside")]
        for path in (self.left, self.right, self.outside):
            path.mkdir()
        (self.left / "nested" / "child").mkdir(parents=True)
        (self.left / "nested" / "child" / "file.txt").write_bytes(b"source")
        self.entries = addons.compare_directories(str(self.left), str(self.right), addons.CompareOptions(recursive=True)).entries

    def tearDown(self):
        self.tmp.cleanup()

    def junction(self, path, target):
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(path), str(target)], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_sync_rejects_intermediate_junction_without_outside_writes(self):
        self.junction(self.right / "nested", self.outside)
        result = addons.execute_selective_sync_copy(self.entries, "left_to_right", str(self.left), str(self.right))
        self.assertEqual(result.copied_count, 0)
        self.assertTrue(result.errors or result.skipped_conflicts)
        self.assertEqual(list(self.outside.iterdir()), [])

    def test_sync_rejects_root_ancestor_junction(self):
        alias = self.root / "alias"
        self.junction(alias, self.root)
        result = addons.execute_selective_sync_copy(self.entries, "left_to_right", str(self.left), str(alias / "right"))
        self.assertEqual(result.copied_count, 0)
        self.assertTrue(result.errors)
        self.assertEqual(list(self.right.iterdir()), [])

    def test_sync_rejects_source_ancestor_junction(self):
        source = self.root / "source_alias"
        self.junction(source, self.left)
        entries = addons.compare_directories(str(source), str(self.right), addons.CompareOptions(recursive=True)).entries
        result = addons.execute_selective_sync_copy(entries, "left_to_right", str(source), str(self.right))
        self.assertEqual(result.copied_count, 0)
        self.assertEqual(list(self.right.iterdir()), [])

    def test_parent_cannot_be_renamed_during_copy(self):
        real_copy = addons.shutil.copyfileobj
        attempted = []

        def concurrent_rename(source, target, **kwargs):
            with self.assertRaises(OSError):
                os.rename(self.right / "nested", self.right / "moved")
            attempted.append(True)
            return real_copy(source, target, **kwargs)

        with mock.patch.object(addons.shutil, "copyfileobj", side_effect=concurrent_rename):
            result = addons.execute_selective_sync_copy(self.entries, "left_to_right", str(self.left), str(self.right))
        self.assertFalse(result.errors, result.errors)
        self.assertTrue(attempted)
        self.assertEqual((self.right / "nested" / "child" / "file.txt").read_bytes(), b"source")

    def test_late_destination_collision_preserves_existing_bytes(self):
        real_copy = addons._copy_file_exclusive_no_overwrite

        def create_late_collision(source, target):
            Path(target).write_bytes(b"other writer")
            return real_copy(source, target)

        with mock.patch.object(addons, "_copy_file_exclusive_no_overwrite", side_effect=create_late_collision):
            result = addons.execute_selective_sync_copy(self.entries, "left_to_right", str(self.left), str(self.right))
        self.assertTrue(result.skipped_conflicts)
        self.assertEqual((self.right / "nested" / "child" / "file.txt").read_bytes(), b"other writer")

    def test_both_export_writers_reject_ancestor_junction(self):
        self.junction(self.right / "escape", self.outside)
        (self.outside / "nested").mkdir()
        for exporter in (
            lambda p: addons.export_file_list_safe(str(self.left), p),
            lambda p: addons.export_hash_manifest([], p),
        ):
            with self.assertRaises(OSError):
                exporter(str(self.right / "escape" / "nested" / "report.txt"))
        self.assertEqual(list((self.outside / "nested").iterdir()), [])

    def test_failed_copy_deletes_only_its_exclusive_handle(self):
        preserved = self.right / "preserved.txt"
        preserved.write_bytes(b"other writer")

        def fail_copy(source, target, **kwargs):
            target.write(b"partial")
            raise OSError("injected copy failure")

        with mock.patch.object(addons.shutil, "copyfileobj", side_effect=fail_copy):
            result = addons.execute_selective_sync_copy(self.entries, "left_to_right", str(self.left), str(self.right))
        self.assertTrue(result.errors)
        self.assertFalse((self.right / "nested" / "child" / "file.txt").exists())
        self.assertEqual(preserved.read_bytes(), b"other writer")

    def test_copy_descriptor_setup_failures_remove_owned_target(self):
        import msvcrt
        source = self.left / "nested" / "child" / "file.txt"
        for module, method in ((msvcrt, "open_osfhandle"), (addons.os, "fdopen")):
            target = self.right / "setup_failure.txt"
            with mock.patch.object(module, method, side_effect=OSError("injected setup failure")):
                with self.assertRaises(OSError):
                    addons._copy_file_exclusive_no_overwrite(str(source), str(target))
            self.assertFalse(target.exists())

    def test_rename_collision_reports_exact_preserved_recovery_path(self):
        source, target = self.right / "original.txt", self.right / "renamed.txt"
        source.write_bytes(b"ORIGINAL")
        real_rename = addons.os.rename

        def race(src, dst):
            result = real_rename(src, dst)
            if Path(src) == source:
                source.write_bytes(b"OTHER_WRITER")
                target.write_bytes(b"LATE_COLLISION")
            return result

        with mock.patch.object(addons.os, "rename", side_effect=race):
            ok, errors = addons._execute_two_phase_atomic_renames([(str(source), str(target))])
        self.assertFalse(ok)
        self.assertEqual(source.read_bytes(), b"OTHER_WRITER")
        self.assertEqual(target.read_bytes(), b"LATE_COLLISION")
        temporary = list(self.right.glob(".pyqdir_ren_stage_*.tmp"))
        self.assertEqual(len(temporary), 1)
        self.assertEqual(temporary[0].read_bytes(), b"ORIGINAL")
        self.assertIn(str(temporary[0]), "\n".join(errors))
        self.assertIn("부분 롤백 0/1", errors[0])

    def test_rename_rollback_does_not_move_replaced_committed_file(self):
        first, second = self.right / "first.txt", self.right / "second.txt"
        first.write_bytes(b"FIRST")
        second.write_bytes(b"SECOND")
        first_dest, second_dest = self.right / "first_new.txt", self.right / "second_new.txt"
        rescued = self.right / "externally_moved_original.txt"
        real_rename = addons.os.rename

        def race(src, dst):
            result = real_rename(src, dst)
            if Path(dst) == first_dest:
                real_rename(first_dest, rescued)
                first_dest.write_bytes(b"OTHER_WRITER")
                second_dest.write_bytes(b"LATE_COLLISION")
            return result

        with mock.patch.object(addons.os, "rename", side_effect=race):
            ok, errors = addons._execute_two_phase_atomic_renames([
                (str(first), str(first_dest)), (str(second), str(second_dest))])
        self.assertFalse(ok)
        self.assertEqual(first_dest.read_bytes(), b"OTHER_WRITER")
        self.assertEqual(rescued.read_bytes(), b"FIRST")
        self.assertEqual(second.read_bytes(), b"SECOND")
        self.assertIn("부분 롤백 1/2", errors[0])
        self.assertTrue(any("위치 미확인" in message for message in errors))

    def test_rename_execution_rejects_ancestor_junction(self):
        self.junction(self.right / "escape", self.outside)
        sub = self.outside / "nested"
        sub.mkdir()
        source = sub / "original.txt"
        source.write_bytes(b"preserve")
        alias = self.right / "escape" / "nested"
        plan = addons.plan_multi_rename([str(alias / "original.txt")], addons.MultiRenameRule(prefix="changed_"))
        self.assertTrue(plan.has_errors)
        ok, errors = addons._execute_two_phase_atomic_renames([(str(alias / "original.txt"), str(alias / "changed.txt"))])
        self.assertFalse(ok)
        self.assertTrue(errors)
        self.assertEqual(source.read_bytes(), b"preserve")
        self.assertFalse((sub / "changed.txt").exists())


if __name__ == "__main__":
    unittest.main()

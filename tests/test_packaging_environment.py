"""Packaging must not resolve native DLLs from the desktop host's tools."""
import os
from pathlib import Path
import platform
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_exe


class PackagingEnvironment(unittest.TestCase):
    @unittest.skipUnless(platform.system() == "Windows", "Windows DLL search contract")
    def test_host_path_removed_parent_and_caller_temp_preserved(self):
        contaminated = "C:/host-tool/poppler/Library/bin;C:/other-runtime/bin"
        with mock.patch.dict(os.environ, {"PATH": contaminated}):
            before = os.environ.copy()
            env = build_exe.packaging_environment()
            self.assertEqual(dict(os.environ), before)
            for key in ("TEMP", "TMP", "TMPDIR", "HOME", "USERPROFILE", "CODEX_HOME"):
                self.assertEqual(env.get(key), before.get(key))
            self.assertNotIn("host-tool", env["PATH"])
            self.assertNotIn("other-runtime", env["PATH"])
            system32 = Path(env.get("SystemRoot") or env["WINDIR"]) / "System32"
            self.assertEqual(Path(env["PATH"].split(os.pathsep)[0]), system32)
            result = subprocess.run(
                [sys.executable, "-B", "-c", "import ctypes; assert ctypes.WinDLL('icuuc.dll').ucnv_open"],
                env=env, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_non_windows_environment_is_preserved(self):
        with mock.patch.object(build_exe.platform, "system", return_value="Linux"):
            self.assertEqual(build_exe.packaging_environment(), dict(os.environ))


if __name__ == "__main__":
    unittest.main()

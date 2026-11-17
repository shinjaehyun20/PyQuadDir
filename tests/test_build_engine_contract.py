"""The packager must select the binding imported by the application."""
import unittest
from unittest.mock import patch

import build_exe


class BuildEngineContract(unittest.TestCase):
    def test_pyside_only_is_not_a_supported_application_binding(self):
        with patch.object(build_exe.importlib.util, "find_spec",
                          side_effect=lambda name: object() if name in ("PySide6", "PyInstaller") else None), \
             patch.object(build_exe.subprocess, "check_call") as install:
            self.assertEqual(build_exe.detect_installed_qt(), "")
            build_exe.ensure_build_dependencies()
            self.assertEqual(install.call_args.args[0][-1], "PyQt6")

    def test_both_installed_selects_the_application_binding(self):
        with patch.object(build_exe.importlib.util, "find_spec", return_value=object()):
            self.assertEqual(build_exe.detect_installed_qt(), "PyQt6")

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for PyQuadDir core helpers and build script."""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import build_exe
import pyquaddir


class TestPyQuadDirCore(unittest.TestCase):
    def test_format_size(self) -> None:
        self.assertEqual(pyquaddir.format_size(0), "0 B")
        self.assertEqual(pyquaddir.format_size(512), "512 B")
        self.assertEqual(pyquaddir.format_size(2048), "2.0 KB")

    def test_unique_target_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            first = pyquaddir.get_unique_target_path(tmp_path, "sample.txt")
            self.assertEqual(first.name, "sample.txt")
            first.write_text("hello", encoding="utf-8")

            second = pyquaddir.get_unique_target_path(tmp_path, "sample.txt")
            self.assertEqual(second.name, "sample (1).txt")

    def test_match_color_hex(self) -> None:
        rules = pyquaddir.DEFAULT_COLOR_RULES
        dir_col = pyquaddir.match_color_hex(rules, dark_mode=True, color_filter_enabled=True, is_dir=True, ext="")
        self.assertEqual(dir_col, "#FBBF24")

        py_col = pyquaddir.match_color_hex(rules, dark_mode=True, color_filter_enabled=True, is_dir=False, ext=".py")
        self.assertEqual(py_col, "#A3E635")

        disabled_col = pyquaddir.match_color_hex(rules, dark_mode=True, color_filter_enabled=False, is_dir=False, ext=".py")
        self.assertIsNone(disabled_col)

    def test_icon_generator(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ico_file = Path(tmp) / "pyquaddir.ico"
            out = build_exe.generate_quaddir_ico(ico_file, size=64)
            self.assertTrue(out.exists())
            data = out.read_bytes()
            self.assertGreater(len(data), 100)
            self.assertEqual(data[:4], b"\x00\x00\x01\x00")

    def test_v22_zoom_wheel_order_and_view_modes(self) -> None:
        self.assertEqual(len(pyquaddir.ZOOM_WHEEL_ORDER), 8)
        self.assertEqual(pyquaddir.ZOOM_WHEEL_ORDER[0], "details")
        self.assertEqual(pyquaddir.ZOOM_WHEEL_ORDER[-1], "extra_large_icons")
        for mode in pyquaddir.ZOOM_WHEEL_ORDER:
            self.assertIn(mode, pyquaddir.VIEW_MODE_LABELS)


if __name__ == "__main__":
    unittest.main()

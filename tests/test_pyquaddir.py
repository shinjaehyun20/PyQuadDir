#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for PyQuadDir core helpers, v2.4 diagnostics, and build script."""

import sys
import tempfile
import unittest
import zipfile
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

    def test_v24_url_decode_and_safe_norm_path(self) -> None:
        norm = pyquaddir.safe_norm_path(r"\\?\G:\CloudDrive\Project\report.xlsx")
        self.assertFalse(norm.startswith(r"\\?\\"))
        self.assertTrue(norm.endswith(r"CloudDrive\Project\report.xlsx"))

        decoded = pyquaddir.normalize_user_input_path(
            "file:///G:/%EB%82%B4%20%EB%93%9C%EB%9D%BC%EC%9D%B4%EB%B8%8C/Docs/400.html"
        )
        self.assertIn("내 드라이브", decoded)
        self.assertTrue(decoded.endswith("400.html"))

    def test_v24_diagnose_file_health_and_xlsx_parser(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)

            # 1) Empty 0-byte file
            empty_f = tmp_p / "empty.pdf"
            empty_f.write_bytes(b"")
            res_empty = pyquaddir.diagnose_file_health(str(empty_f))
            self.assertEqual(res_empty["status"], "empty")

            # 2) OLE2 (.xls) saved with .xlsx extension
            fake_xlsx = tmp_p / "legacy.xlsx"
            fake_xlsx.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 64)
            res_xls = pyquaddir.diagnose_file_health(str(fake_xlsx))
            self.assertEqual(res_xls["status"], "ext_mismatch")
            self.assertEqual(res_xls["suggested_ext"], ".xls")

            # 3) DRM encrypted signature
            drm_f = tmp_p / "secured.xlsx"
            drm_f.write_bytes(b"FASOO DRM HEADER v5.0" + b"\x00" * 64)
            res_drm = pyquaddir.diagnose_file_health(str(drm_f))
            self.assertEqual(res_drm["status"], "drm_encrypted")

            # 4) Valid minimal .xlsx file & built-in sheet parser
            valid_xlsx = tmp_p / "valid.xlsx"
            with zipfile.ZipFile(valid_xlsx, "w") as zf:
                zf.writestr(
                    "xl/workbook.xml",
                    '<?xml version="1.0"?><workbook><sheets><sheet name="Summary" sheetId="1"/></sheets></workbook>',
                )
                zf.writestr(
                    "xl/sharedStrings.xml",
                    '<?xml version="1.0"?><sst><si><t>Item</t></si><si><t>Status</t></si></sst>',
                )
                zf.writestr(
                    "xl/worksheets/sheet1.xml",
                    '<?xml version="1.0"?><worksheet><sheetData>'
                    '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row>'
                    "</sheetData></worksheet>",
                )
            res_ok = pyquaddir.diagnose_file_health(str(valid_xlsx))
            self.assertEqual(res_ok["status"], "ok")

            sheets, err = pyquaddir.parse_xlsx_preview_sheets(str(valid_xlsx))
            self.assertEqual(err, "")
            self.assertEqual(len(sheets), 1)
            self.assertEqual(sheets[0][0], "Summary")
            self.assertEqual(sheets[0][1][0], ["Item", "Status"])

    def test_v25_resolve_restorable_dir_and_config_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            sub_dir = tmp_p / "existing_parent" / "deleted_child" / "grandchild"
            (tmp_p / "existing_parent").mkdir(parents=True, exist_ok=True)

            # Even when deleted_child/grandchild no longer exists, resolve_restorable_dir finds existing_parent
            restored = pyquaddir.resolve_restorable_dir(str(sub_dir))
            self.assertEqual(restored, pyquaddir.safe_norm_path(str(tmp_p / "existing_parent")))

            candidates = pyquaddir.get_config_candidate_paths()
            self.assertGreaterEqual(len(candidates), 2)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit & Integration Test Suite for PyQuadDir v3.1.1 Clean-Room Add-ons (test_pyquaddir_addons.py)
================================================================================================
표준 라이브러리 `unittest` 기반으로 다음 항목을 전수 검증합니다:
  1. 다크/라이트 테마 전 색상 토큰의 WCAG 2.1 명암비(본문 AAA >= 7.0:1, 배지/강조 AA >= 4.5:1) 준수
  2. 일괄 이름 바꾸기(Multi-Rename): 접두사/접미사, 정규식 찾기·바꾸기, 연번([N]), 대소문자, 확장자,
     Windows 예약어/특수문자/경로탈출 차단, 배치 내부 중복 차단, 기존 파일 덮어쓰기 차단,
     순환 이름 변경(a↔b) 및 대소문자 변경 스테이징, 직전 변경 실행 취소(Undo) 및 Undo 충돌 방어
  3. 패널 간 폴더 비교·동기화(Compare Panes): 좌/우 전용, 최신 시각 차이, 동일 크기 1바이트 변조 SHA-256 탐지,
     기존 파일 덮어쓰기 원천 차단 선택 복사 및 안전 사본(_sync_1) 저장
  4. 폴더 실제 용량 계산(Occupied Space): 다단계 중첩 합산, 심볼릭 링크 순환 루프 차단, 하드링크 중복 합산 방지,
     취소 이벤트(Cancellation) 즉시 중단
  5. 파일 해시(MD5/SHA-1/SHA-256) 단일 패스 계산·클립보드 대조 및 3단계 고속 중복 파일 찾기
     (동일 크기 → 앞·뒤 4KB 부분 해시 → 전체 SHA-256, 자동 삭제 0건 보장)
  6. 파일 목록 내보내기(CSV UTF-8 BOM + 수식 주입 방어 / Markdown / XSS 안전 HTML / TXT 비덮어쓰기),
     플랫 뷰(Ctrl+B) 수집기, 탭 복제·잠금 상태 머신 및 `install_pyquaddir_addons` 컨트롤러 통합 검증
"""

from __future__ import annotations

import ast
import hashlib
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pyquaddir_addons as addons


# ===========================================================================
# 경량 헤드리스 Qt6 호환 스텁 (PyQt6 미설치 환경에서도 컨트롤러 100% 검증)
# ===========================================================================

class _FakeSignal:
    def __init__(self) -> None:
        self._slots: List[Callable[..., Any]] = []

    def connect(self, fn: Callable[..., Any]) -> None:
        self._slots.append(fn)

    def emit(self, *args: Any, **kwargs: Any) -> None:
        for fn in list(self._slots):
            fn(*args, **kwargs)


class _FakeAction:
    def __init__(self, text: str) -> None:
        self.text = text
        self.enabled = True
        self.triggered = _FakeSignal()

    def setEnabled(self, val: bool) -> None:
        self.enabled = val


class _FakeMenu:
    def __init__(self, parent: Any = None) -> None:
        self.parent = parent
        self.actions: List[_FakeAction] = []
        self.submenus: List["_FakeMenu"] = []
        self.aboutToShow = _FakeSignal()

    def clear(self) -> None:
        self.actions.clear()
        self.submenus.clear()

    def addAction(self, text: str) -> _FakeAction:
        act = _FakeAction(text)
        self.actions.append(act)
        return act

    def addMenu(self, title: str) -> "_FakeMenu":
        sub = _FakeMenu(self)
        sub.title = title  # type: ignore[attr-defined]
        self.submenus.append(sub)
        return sub

    def addSeparator(self) -> None:
        pass

    def exec(self, *_args: Any) -> None:
        return None


class _FakeToolButton:
    class ToolButtonPopupMode:
        InstantPopup = 1

    def __init__(self) -> None:
        self._text = ""
        self._tooltip = ""
        self._menu: Any = None

    def setText(self, t: str) -> None:
        self._text = t

    def text(self) -> str:
        return self._text

    def setToolTip(self, t: str) -> None:
        self._tooltip = t

    def setPopupMode(self, _m: Any) -> None:
        pass

    def setMenu(self, m: Any) -> None:
        self._menu = m


class _FakeShortcut:
    instances: List["_FakeShortcut"] = []

    def __init__(self, seq: str, parent: Any, activated: Optional[Callable[[], None]] = None) -> None:
        self.seq = seq
        self.parent = parent
        self.activated = activated
        _FakeShortcut.instances.append(self)


def _build_fake_qt_mods() -> Dict[str, Any]:
    class Qt:
        class ContextMenuPolicy:
            CustomContextMenu = 3

        class ItemDataRole:
            UserRole = 0x0100

        class AlignmentFlag:
            AlignRight = 2

        class CheckState:
            Checked = 2
            Unchecked = 0

        class ItemFlag:
            ItemIsUserCheckable = 16
            ItemIsEnabled = 32
            ItemIsSelectable = 1

    class QtCore:
        pass

    QtCore.Qt = Qt  # type: ignore[attr-defined]

    class QtGui:
        QShortcut = _FakeShortcut
        QKeySequence = staticmethod(lambda s: s)
        QColor = staticmethod(lambda c: c)

    class QtWidgets:
        QToolButton = _FakeToolButton
        QMenu = _FakeMenu

        class QMessageBox:
            @staticmethod
            def warning(*_a: Any, **_kw: Any) -> None:
                pass

            @staticmethod
            def information(*_a: Any, **_kw: Any) -> None:
                pass

    return {"QtCore": QtCore, "QtGui": QtGui, "QtWidgets": QtWidgets}


# ===========================================================================
# 1. WCAG 2.1 다크/라이트 테마 명암 대비율 검증
# ===========================================================================

class TestWcagThemeCompliance(unittest.TestCase):
    def test_dark_and_light_palettes_meet_wcag_aa_and_aaa(self) -> None:
        for mode_name, pal in addons.ADDON_THEMES.items():
            with self.subTest(mode=mode_name):
                r_primary = addons.wcag_contrast_ratio(pal["text_primary"], pal["bg_surface"])
                r_secondary = addons.wcag_contrast_ratio(pal["text_secondary"], pal["bg_surface"])
                self.assertGreaterEqual(r_primary, 7.0, f"{mode_name} primary contrast too low: {r_primary:.2f}")
                self.assertGreaterEqual(r_secondary, 7.0, f"{mode_name} secondary contrast too low: {r_secondary:.2f}")

                pairs = [
                    ("accent", pal["accent_text"], pal["accent_bg"]),
                    ("badge_ok", pal["badge_ok_fg"], pal["badge_ok_bg"]),
                    ("badge_warn", pal["badge_warn_fg"], pal["badge_warn_bg"]),
                    ("badge_err", pal["badge_err_fg"], pal["badge_err_bg"]),
                    ("badge_left", pal["badge_left_fg"], pal["badge_left_bg"]),
                    ("badge_right", pal["badge_right_fg"], pal["badge_right_bg"]),
                ]
                for label, fg, bg in pairs:
                    ratio = addons.wcag_contrast_ratio(fg, bg)
                    self.assertGreaterEqual(
                        ratio, 4.5, f"{mode_name}:{label} ({fg} on {bg}) failed WCAG AA: {ratio:.2f}"
                    )

        qss_dark = addons.build_addon_dialog_qss(True)
        qss_light = addons.build_addon_dialog_qss(False)
        self.assertIn("#0B1120", qss_dark)
        self.assertIn("#FFFFFF", qss_light)


# ===========================================================================
# 2. 일괄 이름 바꾸기 (Multi-Rename Tool) 및 안전 가드레일 검증
# ===========================================================================

class TestMultiRenameTool(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_prefix_suffix_regex_counter_case_ext_and_undo(self) -> None:
        f1 = self.root / "IMG_2026_alpha.JPG"
        f2 = self.root / "IMG_2026_beta.JPG"
        f1.write_text("alpha-data", encoding="utf-8")
        f2.write_text("beta-data", encoding="utf-8")

        rule = addons.MultiRenameRule(
            prefix="shoot_",
            suffix="_[N]",
            find_text=r"^IMG_\d+_",
            replace_text="",
            use_regex=True,
            counter_start=10,
            counter_step=5,
            counter_padding=3,
            case_transform=addons.CaseTransform.LOWER,
            extension_mode=addons.ExtensionMode.REPLACE,
            custom_extension=".webp",
        )
        plan = addons.plan_multi_rename([str(f1), str(f2)], rule)
        self.assertFalse(plan.has_errors, plan.error_messages)
        self.assertEqual(plan.changed_count, 2)
        self.assertEqual([it.new_name for it in plan.items], ["shoot_alpha_010.webp", "shoot_beta_015.webp"])

        ok, undo_batch, errs = addons.execute_multi_rename_plan(plan)
        self.assertTrue(ok, errs)
        self.assertIsNotNone(undo_batch)
        self.assertTrue((self.root / "shoot_alpha_010.webp").exists())
        self.assertTrue((self.root / "shoot_beta_015.webp").exists())
        self.assertFalse(f1.exists())

        assert undo_batch is not None
        u_ok, u_errs = addons.undo_multi_rename_batch(undo_batch)
        self.assertTrue(u_ok, u_errs)
        self.assertEqual(f1.read_text(encoding="utf-8"), "alpha-data")
        self.assertEqual(f2.read_text(encoding="utf-8"), "beta-data")

    def test_cyclic_swap_and_case_only_rename(self) -> None:
        fa = self.root / "a.txt"
        fb = self.root / "b.txt"
        fa.write_text("content-A", encoding="utf-8")
        fb.write_text("content-B", encoding="utf-8")

        ok, errs = addons._execute_two_phase_atomic_renames(
            [(str(fa), str(fb)), (str(fb), str(fa))]
        )
        self.assertTrue(ok, errs)
        self.assertEqual(fa.read_text(encoding="utf-8"), "content-B")
        self.assertEqual(fb.read_text(encoding="utf-8"), "content-A")

        rule_upper = addons.MultiRenameRule(
            case_transform=addons.CaseTransform.UPPER,
            extension_mode=addons.ExtensionMode.UPPER,
        )
        plan = addons.plan_multi_rename([str(fa)], rule_upper)
        self.assertFalse(plan.has_errors)
        ok2, _, errs2 = addons.execute_multi_rename_plan(plan)
        self.assertTrue(ok2, errs2)
        names_now = {p.name for p in self.root.iterdir()}
        self.assertIn("A.TXT", names_now)

    def test_blocks_reserved_names_invalid_chars_duplicates_and_existing_overwrite(self) -> None:
        f1 = self.root / "doc1.txt"
        f2 = self.root / "doc2.txt"
        existing = self.root / "target_exists.txt"
        for p in (f1, f2, existing):
            p.write_text(p.name, encoding="utf-8")

        plan_res = addons.plan_multi_rename([str(f1)], addons.MultiRenameRule(name_template="NUL"))
        self.assertTrue(plan_res.has_errors)
        self.assertIn("예약", plan_res.error_messages[0])

        for bad_tpl in ("bad:ads", "sub/evil", "bad?name", "trailing. "):
            p_bad = addons.plan_multi_rename(
                [str(f1)],
                addons.MultiRenameRule(name_template=bad_tpl, extension_mode=addons.ExtensionMode.REMOVE),
            )
            self.assertTrue(p_bad.has_errors, f"Failed to block {bad_tpl!r}")

        plan_dup = addons.plan_multi_rename([str(f1), str(f2)], addons.MultiRenameRule(name_template="same_name"))
        self.assertTrue(plan_dup.has_errors)
        self.assertIn("중복", plan_dup.error_messages[0])

        plan_exist = addons.plan_multi_rename([str(f1)], addons.MultiRenameRule(name_template="TARGET_EXISTS"))
        self.assertTrue(plan_exist.has_errors)
        self.assertIn("덮어쓰기 차단", plan_exist.error_messages[0])
        ok_exec, _, _ = addons.execute_multi_rename_plan(plan_exist)
        self.assertFalse(ok_exec)
        self.assertEqual(existing.read_text(encoding="utf-8"), "target_exists.txt")

        plan_rx = addons.plan_multi_rename([str(f1)], addons.MultiRenameRule(find_text="[unclosed", use_regex=True))
        self.assertTrue(plan_rx.has_errors)

    def test_undo_blocks_overwrite_if_new_file_created_at_old_path(self) -> None:
        orig = self.root / "draft.txt"
        orig.write_text("original-body", encoding="utf-8")
        plan = addons.plan_multi_rename([str(orig)], addons.MultiRenameRule(name_template="final"))
        ok, batch, _ = addons.execute_multi_rename_plan(plan)
        self.assertTrue(ok)
        assert batch is not None

        orig.write_text("new-external-file-must-not-be-overwritten", encoding="utf-8")
        u_ok, u_errs = addons.undo_multi_rename_batch(batch)
        self.assertFalse(u_ok)
        self.assertTrue(any("보호" in e for e in u_errs))
        self.assertEqual(orig.read_text(encoding="utf-8"), "new-external-file-must-not-be-overwritten")


# ===========================================================================
# 3. 패널 간 폴더 비교 · 동기화 미리보기 (Compare Panes) 검증
# ===========================================================================

class TestComparePanes(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.left = Path(self.tmp.name) / "left"
        self.right = Path(self.tmp.name) / "right"
        self.left.mkdir()
        self.right.mkdir()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_compare_statuses_sha256_and_non_overwriting_sync(self) -> None:
        now = time.time()
        (self.left / "only_left.txt").write_bytes(b"left-exclusive")
        (self.right / "only_right.txt").write_bytes(b"right-exclusive")
        (self.left / "same.txt").write_bytes(b"identical-payload")
        (self.right / "same.txt").write_bytes(b"identical-payload")
        os.utime(self.left / "same.txt", (now, now))
        os.utime(self.right / "same.txt", (now, now))

        (self.left / "tampered.bin").write_bytes(b"AAAA1111")
        (self.right / "tampered.bin").write_bytes(b"AAAA2222")
        os.utime(self.left / "tampered.bin", (now, now))
        os.utime(self.right / "tampered.bin", (now, now))

        cmp_fast = addons.compare_directories(str(self.left), str(self.right), addons.CompareOptions(verify_sha256=False))
        by_name_fast = {e.rel_display: e.status for e in cmp_fast.entries}
        self.assertEqual(by_name_fast["only_left.txt"], addons.CompareStatus.LEFT_ONLY)
        self.assertEqual(by_name_fast["only_right.txt"], addons.CompareStatus.RIGHT_ONLY)
        self.assertEqual(by_name_fast["same.txt"], addons.CompareStatus.IDENTICAL)
        self.assertEqual(by_name_fast["tampered.bin"], addons.CompareStatus.IDENTICAL)

        cmp_sha = addons.compare_directories(str(self.left), str(self.right), addons.CompareOptions(verify_sha256=True))
        by_name_sha = {e.rel_display: e.status for e in cmp_sha.entries}
        self.assertEqual(by_name_sha["tampered.bin"], addons.CompareStatus.DIFF_CONTENT)

        res_block = addons.execute_selective_sync_copy(
            cmp_sha.entries, "left_to_right", str(self.left), str(self.right), conflict_policy="block"
        )
        self.assertEqual(res_block.copied_count, 1)
        self.assertEqual((self.right / "only_left.txt").read_bytes(), b"left-exclusive")
        self.assertEqual((self.right / "tampered.bin").read_bytes(), b"AAAA2222")
        self.assertGreaterEqual(len(res_block.skipped_conflicts), 1)

        tampered_entry = [e for e in cmp_sha.entries if e.rel_display == "tampered.bin"]
        res_ren = addons.execute_selective_sync_copy(
            tampered_entry, "left_to_right", str(self.left), str(self.right), conflict_policy="rename_copy"
        )
        self.assertEqual(res_ren.copied_count, 1)
        self.assertEqual((self.right / "tampered.bin").read_bytes(), b"AAAA2222")
        self.assertEqual((self.right / "tampered_sync_1.bin").read_bytes(), b"AAAA1111")

        right_only_entries = [e for e in cmp_sha.entries if e.status == addons.CompareStatus.RIGHT_ONLY]
        res_rl = addons.execute_selective_sync_copy(
            right_only_entries, "right_to_left", str(self.left), str(self.right), conflict_policy="block"
        )
        self.assertEqual(res_rl.copied_count, 1)
        self.assertEqual((self.left / "only_right.txt").read_bytes(), b"right-exclusive")


# ===========================================================================
# 4. 폴더 실제 용량 계산 (Occupied Space) 검증
# ===========================================================================

class TestFolderOccupiedSize(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_nested_size_symlink_loop_immunity_and_hardlink_dedup(self) -> None:
        sub_a = self.root / "alpha"
        sub_b = sub_a / "nested"
        sub_b.mkdir(parents=True)
        (sub_a / "f1.bin").write_bytes(b"x" * 1024)
        (sub_b / "f2.bin").write_bytes(b"y" * 2048)

        hardlink_path = sub_b / "f1_hardlink.bin"
        try:
            os.link(sub_a / "f1.bin", hardlink_path)
            hardlink_created = True
        except OSError:
            hardlink_created = False

        loop_link = sub_b / "loop_to_root"
        symlink_created = False
        try:
            os.symlink(self.root, loop_link, target_is_directory=True)
            symlink_created = True
        except OSError:
            pass

        summary = addons.calculate_folder_occupied_size(str(sub_a))
        self.assertFalse(summary.cancelled)
        self.assertEqual(summary.total_bytes, 3072)
        expected_files = 3 if hardlink_created else 2
        self.assertEqual(summary.file_count, expected_files)
        self.assertEqual(summary.dir_count, 1)
        if symlink_created:
            self.assertGreaterEqual(summary.skipped_links, 1)

        ev = threading.Event()
        ev.set()
        cancelled_sum = addons.calculate_folder_occupied_size(str(sub_a), cancel_event=ev)
        self.assertTrue(cancelled_sum.cancelled)


# ===========================================================================
# 5. 파일 해시 계산·검증 및 3단계 고속 중복 파일 찾기 검증
# ===========================================================================

class TestChecksumAndDuplicates(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_single_pass_hashes_verification_and_manifest_guard(self) -> None:
        payload = b"PyQuadDir Clean-Room Hash Verification Payload 2026" * 300
        f = self.root / "sample.bin"
        f.write_bytes(payload)

        rec = addons.compute_file_hashes(str(f))
        self.assertEqual(rec.md5, hashlib.md5(payload).hexdigest())
        self.assertEqual(rec.sha1, hashlib.sha1(payload).hexdigest())
        self.assertEqual(rec.sha256, hashlib.sha256(payload).hexdigest())

        v_ok = addons.verify_expected_hash(rec, f"  {rec.sha256.upper()} *sample.bin\n")
        self.assertTrue(v_ok.matched)
        self.assertEqual(v_ok.algorithm, "SHA-256")

        v_md5 = addons.verify_expected_hash(rec, rec.md5)
        self.assertTrue(v_md5.matched)
        self.assertEqual(v_md5.algorithm, "MD5")

        v_bad = addons.verify_expected_hash(rec, "0" * 64)
        self.assertFalse(v_bad.matched)

        manifest_p = self.root / "out.sha256"
        addons.export_hash_manifest([rec], str(manifest_p))
        self.assertIn(rec.sha256, manifest_p.read_text(encoding="utf-8"))
        with self.assertRaises(FileExistsError):
            addons.export_hash_manifest([rec], str(manifest_p))

    def test_3stage_duplicate_finder_separates_middle_byte_diff_and_never_deletes(self) -> None:
        head = b"H" * 4096
        mid_a = b"A" * 8192
        mid_b = b"A" * 4000 + b"Z" + b"A" * 4191
        tail = b"T" * 4096

        blob_dup = head + mid_a + tail
        blob_near = head + mid_b + tail
        blob_diff_edge = b"X" * 16384
        blob_unique_sz = b"U" * 999

        sub = self.root / "sub"
        sub.mkdir()
        (self.root / "dup_orig.bin").write_bytes(blob_dup)
        (sub / "dup_copy1.bin").write_bytes(blob_dup)
        (sub / "dup_copy2.bin").write_bytes(blob_dup)
        (self.root / "near_miss.bin").write_bytes(blob_near)
        (self.root / "diff_edge.bin").write_bytes(blob_diff_edge)
        (self.root / "unique.bin").write_bytes(blob_unique_sz)

        res = addons.find_duplicate_files_3stage(str(self.root), recursive=True)
        self.assertEqual(res.scanned_files, 6)
        self.assertEqual(res.stage1_candidate_files, 5)
        self.assertEqual(res.stage2_candidate_files, 4)
        self.assertEqual(res.stage3_hashed_files, 4)
        self.assertEqual(len(res.groups), 1)
        self.assertEqual(len(res.groups[0].files), 3)
        self.assertEqual(res.total_wasted_bytes, len(blob_dup) * 2)
        self.assertEqual(len(list(self.root.rglob("*.bin"))), 6)


# ===========================================================================
# 6. 내보내기 · 플랫 뷰(Ctrl+B) · 탭 복제/잠금 · QDirMainWindow 통합 검증
# ===========================================================================

class TestExportFlatViewAndIntegration(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_synthetic_export_record_escapes_markup(self) -> None:
        record = addons.ExportRecord("a|b_<script>.txt", "a|b_<script>.txt", "fixture", False, "TXT", 1, "1 B", "")
        md = addons.render_export_content("fixture", [record], addons.ExportOptions(fmt=addons.ExportFormat.MARKDOWN))
        html = addons.render_export_content("fixture", [record], addons.ExportOptions(fmt=addons.ExportFormat.HTML))
        self.assertIn(r"a\|b_<script>.txt", md)
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>", html)

    def test_export_csv_md_html_txt_security_and_no_overwrite(self) -> None:
        formula_file = self.root / "=SUM(1,2)_report.csv"
        xss_md_file = self.root / "markup_sample.txt"
        formula_file.write_text("1,2", encoding="utf-8")
        xss_md_file.write_text("hello", encoding="utf-8")

        out_dir = self.root / "exports"
        out_dir.mkdir()

        csv_p, cnt = addons.export_file_list_safe(
            str(self.root),
            str(out_dir / "list.csv"),
            addons.ExportOptions(fmt=addons.ExportFormat.CSV, include_sha256=True),
        )
        self.assertGreaterEqual(cnt, 2)
        raw_csv_bytes = Path(csv_p).read_bytes()
        self.assertTrue(raw_csv_bytes.startswith(b"\xef\xbb\xbf"), "CSV must include UTF-8 BOM for Excel")
        csv_txt = raw_csv_bytes.decode("utf-8-sig")
        self.assertIn("'=SUM(1,2)_report.csv", csv_txt)

        md_p, _ = addons.export_file_list_safe(
            str(self.root),
            str(out_dir / "list.md"),
            addons.ExportOptions(fmt=addons.ExportFormat.MARKDOWN),
        )
        self.assertIn("markup_sample.txt", Path(md_p).read_text(encoding="utf-8"))

        html_p, _ = addons.export_file_list_safe(
            str(self.root),
            str(out_dir / "list.html"),
            addons.ExportOptions(fmt=addons.ExportFormat.HTML, dark_html=True),
        )
        html_txt = Path(html_p).read_text(encoding="utf-8")
        self.assertIn("markup_sample.txt", html_txt)
        self.assertNotIn("<script>", html_txt)

        txt_p, _ = addons.export_file_list_safe(
            str(self.root),
            str(out_dir / "list.txt"),
            addons.ExportOptions(fmt=addons.ExportFormat.TXT),
        )
        self.assertTrue(Path(txt_p).exists())
        with self.assertRaises(FileExistsError):
            addons.export_file_list_safe(
                str(self.root),
                str(out_dir / "list.txt"),
                addons.ExportOptions(fmt=addons.ExportFormat.TXT),
            )

    def test_flat_view_max_entries_cap(self) -> None:
        for i in range(6):
            (self.root / f"f_{i:02d}.txt").write_text(str(i), encoding="utf-8")
        recs, truncated = addons.collect_flat_view_records(str(self.root), max_entries=3)
        self.assertTrue(truncated)
        self.assertEqual(len(recs), 3)

    def test_flat_view_tab_lock_context_menu_and_controller_integration(self) -> None:
        d1 = self.root / "docs"
        d2 = d1 / "2026"
        d2.mkdir(parents=True)
        (self.root / "root.txt").write_bytes(b"12345")
        (d1 / "spec.md").write_bytes(b"a" * 200)
        (d2 / "deep.pdf").write_bytes(b"b" * 500)

        flat_recs, trunc = addons.collect_flat_view_records(str(self.root))
        self.assertFalse(trunc)
        disp_names = [str(r["disp_name"]) for r in flat_recs]
        self.assertEqual(len(disp_names), 3)
        self.assertIn("docs/2026/deep.pdf", disp_names)

        _FakeShortcut.instances.clear()
        fake_qt = _build_fake_qt_mods()

        class _MockLabel:
            def __init__(self) -> None:
                self._t = ""

            def text(self) -> str:
                return self._t

            def setText(self, t: str) -> None:
                self._t = t

        class _MockTab:
            def __init__(self, path: str, win: Any) -> None:
                self.current_path = addons.safe_norm_path(path)
                self.main_window = win
                self.view_mode = "details"
                self.sort_by = "size"
                self.sort_asc = False
                self.group_by = "none"
                self.summary_label = _MockLabel()
                self.last_records: List[Dict[str, object]] = []
                self._selected: List[str] = []

            def selected_file_paths(self) -> List[str]:
                return list(self._selected)

            def set_view_mode(self, m: str) -> None:
                self.view_mode = m

            def _collect_sorted_entries(self, p: Path) -> List[Dict[str, object]]:
                recs: List[Dict[str, object]] = []
                for e in sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name)):
                    is_d = e.is_dir()
                    recs.append({
                        "name": e.name,
                        "disp_name": e.name,
                        "path": addons.safe_norm_path(str(e)),
                        "is_dir": is_d,
                        "ext": "" if is_d else e.suffix.lower(),
                        "size_b": 0 if is_d else e.stat().st_size,
                        "size_str": "<DIR>" if is_d else addons.format_bytes(e.stat().st_size),
                        "type_str": "폴더" if is_d else "파일",
                        "mtime": e.stat().st_mtime,
                        "ctime": e.stat().st_ctime,
                        "date_str": "2026-11-17 14:00",
                        "day_group": "2026-11-17",
                    })
                return recs

            def update_status_summary(self) -> None:
                self.summary_label.setText("기본 요약")

            def refresh(self) -> None:
                self.last_records = self._collect_sorted_entries(Path(self.current_path))
                self.update_status_summary()

        class _MockTabBar:
            def __init__(self) -> None:
                self.customContextMenuRequested = _FakeSignal()

            def setContextMenuPolicy(self, _p: Any) -> None:
                pass

        class _MockTabWidget:
            def __init__(self) -> None:
                self.tabs: List[Any] = []
                self.titles: List[str] = []
                self.curr = 0
                self._bar = _MockTabBar()

            def count(self) -> int:
                return len(self.tabs)

            def widget(self, i: int) -> Any:
                return self.tabs[i] if 0 <= i < len(self.tabs) else None

            def currentIndex(self) -> int:
                return self.curr

            def tabText(self, i: int) -> str:
                return self.titles[i]

            def setTabText(self, i: int, t: str) -> None:
                self.titles[i] = t

            def tabBar(self) -> _MockTabBar:
                return self._bar

        class _MockPane:
            def __init__(self, idx: int, path: str, win: Any) -> None:
                self.pane_index = idx
                self.pane_title = f"패널 {idx + 1}"
                self.win = win
                self.tab_widget = _MockTabWidget()
                self.add_new_tab(path)

            def add_new_tab(self, path_str: Optional[str] = None) -> _MockTab:
                t = _MockTab(path_str or str(self.win.root), self.win)
                self.tab_widget.tabs.append(t)
                self.tab_widget.titles.append(Path(t.current_path).name)
                self.tab_widget.curr = len(self.tab_widget.tabs) - 1
                t.refresh()
                return t

            def close_tab(self, index: int) -> None:
                if len(self.tab_widget.tabs) <= 1:
                    return
                self.tab_widget.tabs.pop(index)
                self.tab_widget.titles.pop(index)
                self.tab_widget.curr = max(0, min(self.tab_widget.curr, len(self.tab_widget.tabs) - 1))

            def current_tab(self) -> _MockTab:
                return self.tab_widget.tabs[self.tab_widget.curr]

            def current_path(self) -> str:
                return self.tab_widget.tabs[self.tab_widget.curr].current_path

            def _refresh_all_tab_titles(self) -> None:
                for i, t in enumerate(self.tab_widget.tabs):
                    self.tab_widget.titles[i] = Path(t.current_path).name

        class _MockCmdToolbar:
            def __init__(self) -> None:
                self.widgets: List[Any] = []

            def addWidget(self, w: Any) -> None:
                self.widgets.append(w)

        class _MockMainWindow:
            def __init__(self, root_p: Path) -> None:
                self.root = root_p
                self.dark_mode = True
                self.show_hidden_files = False
                self.show_file_extensions = True
                self.active_pane_index = 0
                self.cmd_tb = _MockCmdToolbar()
                self.status_messages: List[str] = []
                self.single_rename_called = 0
                self.panes = [_MockPane(i, str(root_p), self) for i in range(4)]

            def active_pane(self) -> _MockPane:
                return self.panes[self.active_pane_index]

            def show_status_message(self, msg: str, _timeout: int = 0) -> None:
                self.status_messages.append(msg)

            def refresh_all_panes(self) -> None:
                for p in self.panes:
                    for t in p.tab_widget.tabs:
                        t.refresh()

            def _set_toolbar_compact_mode(self, _tier: str) -> None:
                pass

            def _shortcut_rename(self) -> None:
                self.single_rename_called += 1

        win = _MockMainWindow(self.root)
        ctrl = addons.install_pyquaddir_addons(win, qt_mods=fake_qt)
        self.assertIs(addons.install_pyquaddir_addons(win, qt_mods=fake_qt), ctrl)

        seqs = {s.seq for s in _FakeShortcut.instances}
        self.assertGreaterEqual(len(ctrl.collect_quick_palette_entries()), 8)
        for req_seq in ("Ctrl+M", "Shift+F2", "Alt+Shift+Enter", "Ctrl+B", "Ctrl+Shift+K", "Ctrl+Shift+L", "Ctrl+P"):
            self.assertIn(req_seq, seqs)
        self.assertEqual(len(win.cmd_tb.widgets), 1)

        ctx_menu = _FakeMenu()
        active_tab = win.active_pane().current_tab()
        ctrl.populate_tab_context_menu(ctx_menu, active_tab, [])
        self.assertEqual(len(ctx_menu.submenus), 1)
        self.assertGreaterEqual(len(ctx_menu.submenus[0].actions), 8)

        active_tab._selected = [str(self.root / "root.txt")]
        win._shortcut_rename()
        self.assertEqual(win.single_rename_called, 1)

        multi_called: List[bool] = []
        ctrl.open_multi_rename = lambda: multi_called.append(True)  # type: ignore[method-assign]
        active_tab._selected = [str(self.root / "root.txt"), str(d1)]
        win._shortcut_rename()
        self.assertEqual(len(multi_called), 1)

        active_tab._selected = [str(d1)]
        computed = ctrl.calculate_active_folder_sizes()
        self.assertEqual(computed[addons.safe_norm_path(str(d1))].total_bytes, 700)
        dir_row = next(r for r in active_tab.last_records if r["is_dir"])
        self.assertEqual(dir_row["size_b"], 700)
        self.assertIn("폴더 실용량 700 B", active_tab.summary_label.text())

        self.assertTrue(ctrl.toggle_active_flat_view())
        self.assertEqual(len(active_tab.last_records), 3)
        self.assertFalse(ctrl.toggle_active_flat_view())

        pane0 = win.active_pane()
        ctrl.duplicate_active_tab()
        self.assertEqual(pane0.tab_widget.count(), 2)
        ctrl.toggle_active_tab_lock()
        pane0.close_tab(1)
        self.assertEqual(pane0.tab_widget.count(), 2)
        ctrl.toggle_active_tab_lock()
        pane0.close_tab(1)
        self.assertEqual(pane0.tab_widget.count(), 1)

    def test_surgical_merge_compatibility_with_pyquaddir_v3_1_1_copy(self) -> None:
        """원본 파일은 일절 건드리지 않고, 로컬 임시 복사본에 2줄 훅을 삽입해 AST 및 --self-test-profile 통과를 검증."""
        env_target = os.environ.get("PYQUADDIR_SOURCE_PATH", "")
        orig_candidates = [
            Path(env_target) if env_target else Path(""),
            Path(__file__).resolve().parent / "pyquaddir.py",
            Path(__file__).resolve().parent.parent / "pyquaddir.py",
            Path.cwd() / "pyquaddir.py",
            Path.cwd() / "downloads" / "pyquaddir_orig.py",
        ]
        orig_file = next((p for p in orig_candidates if p and p.is_file()), None)
        if orig_file is None:
            self.skipTest("pyquaddir.py snapshot not present in current test directory")

        src = orig_file.read_text(encoding="utf-8")
        anchor = "self._apply_responsive_viewport(self.width(), force=True)"
        self.assertIn(anchor, src)

        hook_code = (
            anchor
            + "\n            from pyquaddir_addons import install_pyquaddir_addons"
            + "\n            install_pyquaddir_addons(self)"
        )
        patched_src = src.replace(anchor, hook_code, 1)
        ast.parse(patched_src)

        patched_path = self.root / "pyquaddir_merged_check.py"
        patched_path.write_text(patched_src, encoding="utf-8")
        profile_dir = self.root / "isolated_profile"
        profile_dir.mkdir()

        proc = subprocess.run(
            [sys.executable, str(patched_path), "--self-test-profile", "--profile-dir", str(profile_dir)],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, f"Self-test failed: {proc.stderr}")


if __name__ == "__main__":
    unittest.main(verbosity=2)

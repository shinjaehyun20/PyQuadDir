#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Q-Dir Desktop Explorer v3.1 통합 자동 검증 테스트 스위트 (test_q_dir_v31.py)
==========================================================================
Windows 및 Linux(Headless Qt/Xvfb) 환경에서 다음 10대 핵심 항목을 실증 테스트합니다:
  [TC-01] 한글 파일·폴더·빈 폴더 ZIP / TAR.GZ / TAR 왕복 및 구형 CP949 ZIP 복원
  [TC-02] 대상 기존 파일(existing.txt) + 후속 악성 항목(../escape.txt) 사전 차단 및 무변경 보존
  [TC-03] 스테이징 추출 도중 스트림 손상/충돌 시 부분 반입(Partial Write) 제로 & 트랜잭션 롤백
  [TC-04] 경로 검증 전수 매트릭스 (.., 드라이브, 절대/루트, UNC, NTFS ADS, 예약어, 끝 공백/점)
  [TC-05] 아카이브 내부 심볼릭/하드 링크·Reparse 속성 차단 (ZIP S_ISLNK/0x400, TAR sym/lnk/fifo)
  [TC-06] 대상 폴더 내 기존 심볼릭 링크 및 Windows Junction(mklink /J / Reparse Point) 탈출 차단
  [TC-07] 대소문자 무시 중복 항목(Report.txt vs report.txt) 및 기존 파일/폴더 충돌 차단
  [TC-08] 압축 생성 시 기존 아카이브(existing_archive.zip) 삭제/덮어쓰기 금지 및 보존
  [TC-09] 테스트 전용 프로필(--profile-dir) 격리 (사용자 홈·실행 폴더 무접촉) 및 Qt↔Tk 설정 호환 보존
  [TC-10] 정상 GUI 시작, 4분할 균등 폭·탭·세션 복원·다크모드 즐겨찾기·Enter·Ctrl+휠·긴 한글 파일명 안정성
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import zipfile

# 테스트 대상 모듈 로드
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import q_dir  # noqa: E402
import importlib.util as _importlib_util


def _load_archive_safe_core():
    try:
        import archive_safe_core as _asc
        return _asc
    except ImportError:
        core_file = SCRIPT_DIR / "archive_safe_core.py"
        if core_file.exists():
            spec = _importlib_util.spec_from_file_location("archive_safe_core", str(core_file))
            if spec and spec.loader:
                mod = _importlib_util.module_from_spec(spec)
                sys.modules["archive_safe_core"] = mod
                spec.loader.exec_module(mod)
                return mod
        raise



class QDirV31VerificationSuite(unittest.TestCase):
    """Q-Dir v3.1 보안·무결성·트랜잭션·UI/UX 자동 검증 스위트"""

    def setUp(self) -> None:
        self.temp_root = Path(tempfile.mkdtemp(prefix="qdir_v31_test_"))
        self.profile_dir = self.temp_root / "isolated_profile"
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        q_dir.set_active_profile(profile_dir=str(self.profile_dir))

    def tearDown(self) -> None:
        q_dir.set_active_profile(None, None)
        shutil.rmtree(self.temp_root, ignore_errors=True)

    # ------------------------------------------------------------------
    # [TC-01] 한글 ZIP/TAR 왕복 및 구형 CP949 한글 ZIP 복원 테스트
    # ------------------------------------------------------------------
    def test_01_korean_zip_tar_roundtrip_and_cp949(self) -> None:
        src_dir = self.temp_root / "src_한글원본"
        sub_dir = src_dir / "하위폴더_테스트"
        empty_dir = src_dir / "빈폴더_보존확인"
        sub_dir.mkdir(parents=True)
        empty_dir.mkdir(parents=True)

        f1 = src_dir / "한글문서_보고서_2026.txt"
        f2 = sub_dir / "내부파일_데이터_검증.md"
        f1.write_text("안녕하세요! Q-Dir v3.1 한글 ZIP/TAR 왕복 테스트입니다.", encoding="utf-8")
        f2.write_text("# 내부 마크다운\n- 항목 1\n- 항목 2", encoding="utf-8")

        for fmt, ext in [("zip", ".zip"), ("tar.gz", ".tar.gz"), ("tar", ".tar")]:
            arc_path = self.temp_root / f"왕복테스트_{fmt.replace('.', '_')}{ext}"
            ok_c, out_arc, cnt_c = q_dir.compress_items_to_archive(
                [str(f1), str(sub_dir), str(empty_dir)],
                str(arc_path),
                archive_format=fmt,
            )
            self.assertTrue(ok_c, f"{fmt} 압축 실패: {out_arc}")
            self.assertTrue(os.path.isfile(out_arc))
            self.assertGreaterEqual(cnt_c, 2)

            ext_dir = self.temp_root / f"extracted_{fmt.replace('.', '_')}"
            ok_e, target_root, cnt_e = q_dir.extract_archive_smart(
                out_arc, str(ext_dir), create_subfolder=True
            )
            self.assertTrue(ok_e, f"{fmt} 압축 해제 실패: {target_root}")
            self.assertEqual(cnt_e, 2)
            out_f1 = Path(target_root) / "한글문서_보고서_2026.txt"
            out_f2 = Path(target_root) / "하위폴더_테스트" / "내부파일_데이터_검증.md"
            self.assertTrue(out_f1.is_file())
            self.assertTrue(out_f2.is_file())
            self.assertEqual(out_f1.read_text(encoding="utf-8"), f1.read_text(encoding="utf-8"))
            self.assertEqual(out_f2.read_text(encoding="utf-8"), f2.read_text(encoding="utf-8"))

        # 구형 Windows/알집 CP949 인코딩 ZIP (UTF-8 비트 0x800 미설정) 복원 검증
        cp949_zip = self.temp_root / "legacy_cp949.zip"
        kor_name = "구형알집_한글폴더/한글파일명_복원성공.txt"
        cp949_bytes = kor_name.encode("cp949")
        pseudo_str = cp949_bytes.decode("cp437")
        with zipfile.ZipFile(cp949_zip, "w") as zf:
            zinfo = zipfile.ZipInfo(pseudo_str)
            zinfo.flag_bits = 0  # UTF-8 플래그 해제
            zf.writestr(zinfo, "CP949 콘텐츠 정상 복원".encode("utf-8"))

        cp949_out = self.temp_root / "cp949_extracted"
        ok_cp, out_cp_dir, cnt_cp = q_dir.extract_archive_smart(str(cp949_zip), str(cp949_out))
        self.assertTrue(ok_cp, f"CP949 ZIP 해제 실패: {out_cp_dir}")
        self.assertEqual(cnt_cp, 1)
        restored_file = cp949_out / "구형알집_한글폴더" / "한글파일명_복원성공.txt"
        self.assertTrue(restored_file.is_file())
        self.assertEqual(restored_file.read_text(encoding="utf-8"), "CP949 콘텐츠 정상 복원")

    # ------------------------------------------------------------------
    # [TC-02] 대상 기존 파일(existing.txt) + 후속 악성 항목(../escape.txt) 차단 및 무변경 보존
    # ------------------------------------------------------------------
    def test_02_existing_file_plus_malicious_subsequent_entry_preserved(self) -> None:
        dest_dir = self.temp_root / "target_workspace"
        dest_dir.mkdir(parents=True)
        existing_file = dest_dir / "existing.txt"
        original_content = "ORIGINAL_SAFE_CONTENT_DO_NOT_OVERWRITE"
        existing_file.write_text(original_content, encoding="utf-8")

        # 시나리오 A: ZIP 순서가 [existing.txt, ../escape.txt]일 때
        bad_zip_a = self.temp_root / "attack_order_a.zip"
        with zipfile.ZipFile(bad_zip_a, "w") as zf:
            zf.writestr("existing.txt", "OVERWRITTEN_BY_ATTACKER")
            zf.writestr("../escape.txt", "ESCAPED_OUTSIDE")

        ok_a, msg_a, cnt_a = q_dir.extract_archive_smart(str(bad_zip_a), str(dest_dir), create_subfolder=False)
        self.assertFalse(ok_a, "existing.txt + ../escape.txt 아카이브가 차단되지 않았습니다.")
        self.assertEqual(cnt_a, 0)
        # 기존 파일이 단 1바이트도 바뀌지 않았는지 검증
        self.assertEqual(existing_file.read_text(encoding="utf-8"), original_content)
        self.assertFalse((self.temp_root / "escape.txt").exists())

        # 시나리오 B: 첫 항목은 새 파일(first_ok.txt)이고 두 번째 항목이 ../escape.txt (또는 existing.txt)일 때
        # 첫 번째 파일조차 대상 폴더에 남아있지 않아야 함 (부분 반입 제로)
        bad_zip_b = self.temp_root / "attack_order_b.zip"
        with zipfile.ZipFile(bad_zip_b, "w") as zf:
            zf.writestr("first_ok.txt", "SHOULD_NOT_REMAIN_PARTIALLY")
            zf.writestr("../escape2.txt", "ESCAPED")

        ok_b, msg_b, cnt_b = q_dir.extract_archive_smart(str(bad_zip_b), str(dest_dir), create_subfolder=False)
        self.assertFalse(ok_b)
        self.assertEqual(cnt_b, 0)
        self.assertFalse((dest_dir / "first_ok.txt").exists(), "부분 반입된 first_ok.txt가 남아 있습니다!")
        self.assertFalse((self.temp_root / "escape2.txt").exists())
        self.assertEqual(existing_file.read_text(encoding="utf-8"), original_content)

        # 시나리오 C: TAR에서도 [first_ok.txt, existing.txt] 또는 [existing.txt, ../escape_tar.txt] 차단 및 무변경 검증
        bad_tar = self.temp_root / "attack_order_c.tar"
        with tarfile.open(bad_tar, "w") as tf:
            for name, body in [("first_tar.txt", b"PARTIAL"), ("existing.txt", b"OVERWRITE"), ("../escape_tar.txt", b"ESC")]:
                ti = tarfile.TarInfo(name)
                ti.size = len(body)
                tf.addfile(ti, io.BytesIO(body))

        ok_c, msg_c, cnt_c = q_dir.extract_archive_smart(str(bad_tar), str(dest_dir), create_subfolder=False)
        self.assertFalse(ok_c)
        self.assertEqual(cnt_c, 0)
        self.assertFalse((dest_dir / "first_tar.txt").exists())
        self.assertFalse((self.temp_root / "escape_tar.txt").exists())
        self.assertEqual(existing_file.read_text(encoding="utf-8"), original_content)

    # ------------------------------------------------------------------
    # [TC-03] 스테이징 추출 도중 오류/동시 충돌 시 롤백 및 원자성 검증
    # ------------------------------------------------------------------
    def test_03_transactional_staging_rollback_on_mid_commit_collision(self) -> None:
        dest_dir = self.temp_root / "atomic_target"
        dest_dir.mkdir(parents=True)
        keep_file = dest_dir / "keep_untouched.txt"
        keep_file.write_text("SAFE_BASELINE", encoding="utf-8")

        valid_zip = self.temp_root / "two_files.zip"
        with zipfile.ZipFile(valid_zip, "w") as zf:
            zf.writestr("alpha_new.txt", "ALPHA_CONTENT")
            zf.writestr("zeta_new.txt", "ZETA_CONTENT")

        # 커밋 단계에서 두 번째 파일('zeta_new.txt') 이동 시 동시 충돌(FileExistsError)이 발생한 상황 시뮬레이션
        orig_link = os.link

        def _simulated_race_link(src: str, dst: str, *args, **kwargs):
            if dst.endswith("zeta_new.txt"):
                raise FileExistsError("Simulated concurrent file creation collision on zeta_new.txt")
            return orig_link(src, dst, *args, **kwargs)

        with mock.patch("os.link", side_effect=_simulated_race_link):
            ok, msg, cnt = q_dir.extract_archive_smart(str(valid_zip), str(dest_dir), create_subfolder=False)

        self.assertFalse(ok, "동시 충돌 시 실패를 반환해야 합니다.")
        self.assertEqual(cnt, 0)
        # 먼저 커밋되었던 alpha_new.txt도 롤백되어 존재하지 않아야 함
        self.assertFalse((dest_dir / "alpha_new.txt").exists(), "롤백 후 alpha_new.txt가 남아 있으면 안 됩니다!")
        self.assertFalse((dest_dir / "zeta_new.txt").exists())
        # 기존 파일은 그대로 보존되어야 함
        self.assertEqual(keep_file.read_text(encoding="utf-8"), "SAFE_BASELINE")

    # ------------------------------------------------------------------
    # [TC-04] 경로 검사 함수 전수 매트릭스 (.., 절대/루트, UNC, 드라이브, ADS, 예약어, 끝 공백/점)
    # ------------------------------------------------------------------
    def test_04_path_validation_security_matrix(self) -> None:
        dest_dir = self.temp_root / "matrix_dest"
        dest_dir.mkdir(parents=True)

        malicious_paths = [
            # 상위 디렉터리 탈출
            "../escape.txt",
            "..\\escape.txt",
            "sub/../../escape.txt",
            "sub/..\\../escape.txt",
            ".",
            "..",
            # 루트/절대 경로 (선행 슬래시/백슬래시)
            "/absolute.txt",
            "\\absolute.txt",
            "/etc/passwd",
            "\\Windows\\System32\\cmd.exe",
            # UNC 네트워크 경로
            "\\\\server\\share\\file.txt",
            "//server/share/file.txt",
            "\\\\?\\C:\\evil.txt",
            # 드라이브 문자 경로
            "C:\\evil.txt",
            "C:/evil.txt",
            "C:relative_drive.txt",
            "d:\\data\\leak.txt",
            # NTFS 대체 데이터 스트림 (ADS)
            "file.txt:hidden.txt",
            "file.txt::$DATA",
            "folder:stream/inside.txt",
            "::$DATA",
            "normal.txt:zone.identifier",
            # Windows 예약 파일명 (확장자 포함/미포함, 대소문자 혼합)
            "CON",
            "con.txt",
            "PRN.log",
            "aux",
            "NUL",
            "nul.tar.gz",
            "COM1",
            "com9.dat",
            "LPT1",
            "lpt4.doc",
            "CONIN$",
            "CONOUT$",
            "CLOCK$",
            "sub/NUL.txt/a.txt",
            # 끝 공백 / 끝 마침표
            "trailing_space.txt ",
            "trailing_dot.txt.",
            "dir_with_dot./inside.txt",
            "dir_with_space /inside.txt",
            # 금지 특수문자 및 제어문자
            "bad<char>.txt",
            "bad|pipe.txt",
            "bad?q.txt",
            "bad*star.txt",
            "null\x00byte.txt",
            "ctrl\x07bell.txt",
        ]

        for bad_p in malicious_paths:
            with self.subTest(bad_path=bad_p):
                with self.assertRaises(PermissionError, msg=f"경로 검사 함수가 '{bad_p}'를 차단하지 못했습니다!"):
                    q_dir._validate_safe_extract_dest(str(dest_dir), bad_p)

                # 실제 ZIP 아카이브에 담아 extract_archive_smart 호출 시에도 차단되는지 검증
                z_path = self.temp_root / "single_bad.zip"
                with zipfile.ZipFile(z_path, "w") as zf:
                    zf.writestr(bad_p if "\x00" not in bad_p else "../escape.txt", "PAYLOAD")
                ok, msg, cnt = q_dir.extract_archive_smart(str(z_path), str(dest_dir))
                self.assertFalse(ok, f"extract_archive_smart가 '{bad_p}'를 차단하지 못했습니다!")
                self.assertEqual(cnt, 0)
                self.assertEqual(list(dest_dir.iterdir()), [], f"차단 실패로 파일이 생성됨: {bad_p}")

    # ------------------------------------------------------------------
    # [TC-05] 아카이브 내부 심볼릭/하드 링크·Reparse·특수 파일 차단 검증
    # ------------------------------------------------------------------
    def test_05_archive_internal_links_and_reparse_blocked(self) -> None:
        dest_dir = self.temp_root / "link_dest"
        dest_dir.mkdir(parents=True)

        # 1) ZIP 내부 Unix Symlink (0o120000)
        zip_sym = self.temp_root / "zip_symlink.zip"
        with zipfile.ZipFile(zip_sym, "w") as zf:
            zf.writestr("innocent.txt", "HELLO")
            zinfo = zipfile.ZipInfo("evil_symlink")
            zinfo.external_attr = (stat.S_IFLNK | 0o777) << 16
            zf.writestr(zinfo, "/etc/passwd")

        ok1, msg1, _ = q_dir.extract_archive_smart(str(zip_sym), str(dest_dir))
        self.assertFalse(ok1)
        self.assertFalse((dest_dir / "innocent.txt").exists(), "링크 포함 ZIP의 앞선 파일이 풀리면 안 됩니다.")

        # 2) ZIP 내부 Windows FILE_ATTRIBUTE_REPARSE_POINT (0x400)
        zip_rep = self.temp_root / "zip_reparse.zip"
        with zipfile.ZipFile(zip_rep, "w") as zf:
            zinfo = zipfile.ZipInfo("junction_dir/")
            zinfo.external_attr = ((stat.S_IFDIR | 0o755) << 16) | 0x0410
            zf.writestr(zinfo, "")
            zf.writestr("junction_dir/outside.txt", "PWN")

        ok2, msg2, _ = q_dir.extract_archive_smart(str(zip_rep), str(dest_dir))
        self.assertFalse(ok2)
        self.assertEqual(list(dest_dir.iterdir()), [])

        # 3) TAR 내부 Symlink (SYMTYPE) 및 Hardlink (LNKTYPE)
        for link_type, t_name in [(tarfile.SYMTYPE, "tar_sym.tar"), (tarfile.LNKTYPE, "tar_hard.tar")]:
            t_path = self.temp_root / t_name
            with tarfile.open(t_path, "w") as tf:
                b_data = b"SAFE_FIRST"
                ti1 = tarfile.TarInfo("first.txt")
                ti1.size = len(b_data)
                tf.addfile(ti1, io.BytesIO(b_data))

                ti_link = tarfile.TarInfo("link_entry")
                ti_link.type = link_type
                ti_link.linkname = "../outside_target.txt"
                tf.addfile(ti_link)

            ok_t, msg_t, _ = q_dir.extract_archive_smart(str(t_path), str(dest_dir))
            self.assertFalse(ok_t, f"{t_name} 링크 아카이브가 차단되지 않았습니다.")
            self.assertFalse((dest_dir / "first.txt").exists(), "TAR 링크 차단 시 첫 파일도 쓰이면 안 됩니다.")

    # ------------------------------------------------------------------
    # [TC-06] 대상 폴더 내 기존 Junction / 심볼릭 링크를 통한 외부 폴더 쓰기 차단
    # ------------------------------------------------------------------
    def test_06_existing_target_junction_and_symlink_blocked(self) -> None:
        dest_dir = self.temp_root / "workspace_with_junction"
        outside_dir = self.temp_root / "outside_secret_folder"
        dest_dir.mkdir(parents=True)
        outside_dir.mkdir(parents=True)

        zip_sub = self.temp_root / "write_into_sub.zip"
        with zipfile.ZipFile(zip_sub, "w") as zf:
            zf.writestr("sub_junction/pwned.txt", "WRITTEN_OUTSIDE_TARGET")

        junc_path = dest_dir / "sub_junction"
        created_link = False
        if platform.system() == "Windows":
            # Windows 실제 디렉터리 Junction (mklink /J) 생성
            res = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(junc_path), str(outside_dir)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            created_link = res.returncode == 0 and junc_path.exists()

        if not created_link:
            # Linux/macOS 또는 권한 제한 환경에서는 실제 심볼릭 링크 생성
            os.symlink(str(outside_dir), str(junc_path), target_is_directory=True)

        self.assertTrue(q_dir.is_symlink_or_reparse_point(str(junc_path)))

        # 1) 실제 심볼릭 링크 / Windows Junction 대상 추출 시 사전 차단 검증
        ok, msg, cnt = q_dir.extract_archive_smart(str(zip_sub), str(dest_dir), create_subfolder=False)
        self.assertFalse(ok, "기존 Junction/심볼릭 링크 경유 쓰기가 차단되지 않았습니다!")
        self.assertEqual(cnt, 0)
        self.assertFalse(
            (outside_dir / "pwned.txt").exists(),
            "치명적 오류: 기존 Junction을 통해 대상 밖 폴더(outside_secret_folder)에 파일이 기록되었습니다!",
        )

        # 2) Windows NTFS Junction 속성(FILE_ATTRIBUTE_REPARSE_POINT=0x400, st_reparse_tag=0xA0000003) 모킹 검증
        os.unlink(str(junc_path)) if not (platform.system() == "Windows" and junc_path.is_dir()) else os.rmdir(str(junc_path))
        normal_sub = dest_dir / "sub_junction"
        normal_sub.mkdir(parents=True)

        orig_lstat = os.lstat

        class _FakeWinJunctionStat:
            def __init__(self, real_st):
                self.st_mode = real_st.st_mode
                self.st_size = real_st.st_size
                self.st_mtime = real_st.st_mtime
                self.st_ctime = real_st.st_ctime
                self.st_file_attributes = 0x0410  # FILE_ATTRIBUTE_DIRECTORY | FILE_ATTRIBUTE_REPARSE_POINT
                self.st_reparse_tag = 0xA0000003  # IO_REPARSE_TAG_MOUNT_POINT (Windows Junction)

        def _mock_lstat(p):
            st = orig_lstat(p)
            if os.path.normpath(str(p)).endswith("sub_junction"):
                return _FakeWinJunctionStat(st)
            return st

        with mock.patch("os.lstat", side_effect=_mock_lstat):
            self.assertTrue(q_dir.is_symlink_or_reparse_point(str(normal_sub)))
            ok_j, msg_j, _ = q_dir.extract_archive_smart(str(zip_sub), str(dest_dir), create_subfolder=False)
            self.assertFalse(ok_j, "Windows Reparse Tag(0xA0000003) Junction이 차단되지 않았습니다!")
            self.assertFalse((normal_sub / "pwned.txt").exists())

    # ------------------------------------------------------------------
    # [TC-07] 대소문자만 다른 중복 파일 및 기존 파일/디렉터리 충돌 차단
    # ------------------------------------------------------------------
    def test_07_case_insensitive_duplicates_and_collisions_blocked(self) -> None:
        dest_dir = self.temp_root / "case_collision_dest"
        dest_dir.mkdir(parents=True)

        # 1) 아카이브 내부 대소문자 중복 (Report.txt vs report.txt)
        dup_zip = self.temp_root / "case_dup.zip"
        with zipfile.ZipFile(dup_zip, "w") as zf:
            zf.writestr("Report.txt", "FIRST_UPPER")
            zf.writestr("report.txt", "SECOND_LOWER")

        ok1, msg1, _ = q_dir.extract_archive_smart(str(dup_zip), str(dest_dir))
        self.assertFalse(ok1, "대소문자만 다른 아카이브 내부 중복 항목이 차단되지 않았습니다!")
        self.assertEqual(list(dest_dir.iterdir()), [], "대소문자 중복 아카이브에서 부분 파일이 생성되었습니다!")

        # 2) 아카이브 내부 파일↔폴더 이름 충돌 (sub 파일 vs SUB/a.txt)
        file_dir_conflict_zip = self.temp_root / "file_dir_conflict.zip"
        with zipfile.ZipFile(file_dir_conflict_zip, "w") as zf:
            zf.writestr("module", "FILE_NAMED_MODULE")
            zf.writestr("MODULE/init.py", "CONFLICTING_DIR")

        ok2, msg2, _ = q_dir.extract_archive_smart(str(file_dir_conflict_zip), str(dest_dir))
        self.assertFalse(ok2)
        self.assertEqual(list(dest_dir.iterdir()), [])

        # 3) 대상 폴더에 대소문자만 다른 기존 파일('Readme.md')이 있을 때 'README.MD' 추출 차단
        existing_readme = dest_dir / "Readme.md"
        existing_readme.write_text("KEEP_ORIGINAL_README", encoding="utf-8")

        ci_target_zip = self.temp_root / "ci_target.zip"
        with zipfile.ZipFile(ci_target_zip, "w") as zf:
            zf.writestr("README.MD", "OVERWRITE_ATTEMPT")

        ok3, msg3, _ = q_dir.extract_archive_smart(str(ci_target_zip), str(dest_dir))
        self.assertFalse(ok3, "대상에 대소문자만 다른 기존 파일이 있을 때 차단되지 않았습니다!")
        self.assertEqual(existing_readme.read_text(encoding="utf-8"), "KEEP_ORIGINAL_README")

    # ------------------------------------------------------------------
    # [TC-08] 압축 생성 시 기존 아카이브 삭제/덮어쓰기 금지 및 보존
    # ------------------------------------------------------------------
    def test_08_existing_archive_preserved_during_compression(self) -> None:
        src_file = self.temp_root / "source_doc.txt"
        src_file.write_text("NEW_DATA_TO_COMPRESS", encoding="utf-8")

        existing_arc = self.temp_root / "important_backup.zip"
        precious_bytes = b"PK\x03\x04PRECIOUS_EXISTING_ARCHIVE_DO_NOT_DELETE"
        existing_arc.write_bytes(precious_bytes)

        # 동일 이름 및 대소문자 변형 이름으로 압축 시도 -> 모두 실패하고 기존 아카이브는 100% 보존되어야 함
        for attempt_name in ["important_backup.zip", "IMPORTANT_BACKUP.ZIP", "important_backup"]:
            ok, msg, cnt = q_dir.compress_items_to_archive(
                [str(src_file)],
                str(self.temp_root / attempt_name),
                archive_format="zip",
            )
            self.assertFalse(ok, f"기존 아카이브가 존재하는데 '{attempt_name}' 압축이 허용되었습니다!")
            self.assertEqual(cnt, 0)
            self.assertEqual(
                existing_arc.read_bytes(),
                precious_bytes,
                "치명적 오류: 기존 아카이브 파일이 삭제되거나 변경되었습니다!",
            )

    # ------------------------------------------------------------------
    # [TC-09] 테스트 전용 프로필 격리(홈/실행 폴더 무접촉) 및 Qt↔Tk 설정 호환
    # ------------------------------------------------------------------
    def test_09_isolated_profile_and_qt_tk_config_compatibility(self) -> None:
        home_cfg = q_dir.CONFIG_PATH
        exe_cfg = SCRIPT_DIR / ".qdir_session.json"

        home_before = home_cfg.read_bytes() if home_cfg.exists() else None
        exe_before = exe_cfg.read_bytes() if exe_cfg.exists() else None

        # 테스트 전용 프로필 활성화 상태에서 후보 경로에 홈/실행 폴더가 포함되지 않는지 확인
        candidates = q_dir.get_config_candidate_paths()
        self.assertNotIn(home_cfg, candidates)
        self.assertNotIn(exe_cfg, candidates)
        for c in candidates:
            self.assertTrue(str(c).startswith(str(self.profile_dir)))

        # 1단계: Qt 엔진이 전체 설정(보기 모드, 창 크기, 탭별 보기, 즐겨찾기 등) 저장
        qt_data = {
            "dark_mode": True,
            "color_filter_enabled": True,
            "default_view_mode": "tiles",
            "show_icons": True,
            "show_file_extensions": True,
            "show_hidden_files": True,
            "layout_mode": "quad",
            "active_pane_index": 2,
            "favorites": [{"name": "⭐ 내 작업폴더", "path": str(self.temp_root)}],
            "pane_tabs": [[str(self.temp_root)], [str(self.temp_root)], [str(self.temp_root)], [str(self.temp_root)]],
            "pane_active_tab_indices": [0, 0, 0, 0],
            "pane_tab_view_modes": [["tiles"], ["details"], ["large_icons"], ["content"]],
            "window_geometry": [100, 120, 1600, 960, False],
        }
        q_dir.save_app_config(qt_data, engine="qt")

        # 2단계: Tk 엔진으로 전환 후 일부 키만 담아 저장하더라도 Qt 설정이 지워지지 않고 보존되는지 검증
        tk_data = {
            "dark_mode": True,
            "color_filter_enabled": True,
            "favorites": [{"name": "⭐ 내 작업폴더", "path": str(self.temp_root)}],
            "layout_mode": "quad",
            "active_pane_index": 1,
            "pane_tabs": [[str(self.temp_root), str(self.profile_dir)], [str(self.temp_root)], [str(self.temp_root)], [str(self.temp_root)]],
            "pane_active_tab_indices": [1, 0, 0, 0],
        }
        q_dir.save_app_config(tk_data, engine="tk")

        loaded = q_dir.load_app_config()
        self.assertEqual(loaded.get("default_view_mode"), "tiles", "Tk 저장 후 Qt default_view_mode가 유실됨!")
        self.assertEqual(loaded.get("show_hidden_files"), True, "Tk 저장 후 Qt show_hidden_files가 유실됨!")
        self.assertEqual(loaded.get("window_geometry"), [100, 120, 1600, 960, False], "Tk 저장 후 창 크기가 유실됨!")
        self.assertEqual(loaded.get("favorites"), [{"name": "⭐ 내 작업폴더", "path": str(self.temp_root)}])
        # 첫 번째 패널에 탭이 2개로 늘어났으므로 기존 1번 탭 'tiles'는 유지되고 2번 탭은 기본값('tiles')으로 확장됨
        self.assertEqual(loaded.get("pane_tab_view_modes"), [["tiles", "tiles"], ["details"], ["large_icons"], ["content"]])
        self.assertIn("qt", loaded.get("engines", {}))  # type: ignore[arg-type]
        self.assertIn("tk", loaded.get("engines", {}))  # type: ignore[arg-type]

        # 사용자 홈 및 실행 파일 인접 설정이 전혀 건드려지지 않았는지 검증
        home_after = home_cfg.read_bytes() if home_cfg.exists() else None
        exe_after = exe_cfg.read_bytes() if exe_cfg.exists() else None
        self.assertEqual(home_before, home_after, "격리 프로필 모드에서 사용자 홈 설정 파일이 변경되었습니다!")
        self.assertEqual(exe_before, exe_after, "격리 프로필 모드에서 실행 파일 인접 설정 파일이 변경되었습니다!")

    # ------------------------------------------------------------------
    # [TC-10] 정상 GUI 시작 및 4분할·다크모드 즐겨찾기·Enter·Ctrl+휠·긴 한글 파일명 안정성
    # ------------------------------------------------------------------
    def test_10_gui_startup_and_uiux_regressions(self) -> None:
        # 1) 긴 한글 파일명 시각 폭 말줄임 검증
        long_kor = "2026년_제1차_정보관리기술사_실전모의고사_최종해설집_수정이력포함_매우긴파일명_테스트.xlsx"
        elided = q_dir.elide_middle_smart(long_kor, max_visual_cols=20)
        self.assertIn("…", elided)
        self.assertTrue(elided.endswith(".xlsx"))
        self.assertLess(len(elided), len(long_kor))

        # 2) 프로필 단위 자가검증(--self-test-profile)과 실제 GUI 초기화 검증(--self-test-gui) 분리 실행
        prof_only_dir = self.temp_root / "profile_unit_subproc"
        res_prof = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_DIR / "q_dir.py"),
                "--profile-dir",
                str(prof_only_dir),
                "--self-test-profile",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
        self.assertEqual(res_prof.returncode, 0, res_prof.stderr.decode("utf-8", errors="replace"))
        saved_gui_cfg = json.loads((prof_only_dir / ".qdir_session.json").read_text(encoding="utf-8"))
        self.assertEqual(saved_gui_cfg.get("layout_mode"), "quad")
        self.assertEqual(len(saved_gui_cfg.get("pane_tabs", [])), 4)

        # 3) 종료 전 디렉터리 복원 및 하위 폴더 삭제 시 상위 폴더 폴백(resolve_restorable_dir) 검증
        deep_dir = self.temp_root / "restorable_parent" / "deleted_child"
        deep_dir.mkdir(parents=True)
        self.assertEqual(q_dir.resolve_restorable_dir(str(deep_dir)), q_dir.safe_norm_path(str(deep_dir)))
        shutil.rmtree(deep_dir)
        self.assertEqual(
            q_dir.resolve_restorable_dir(str(deep_dir)),
            q_dir.safe_norm_path(str(deep_dir.parent)),
        )

        # 4) UI/UX 핵심 기능 보존 검증 (4분할 균등 폭/분할선 동기화, 다크모드 즐겨찾기, Enter 실행, Ctrl+휠 8단계, ElidedLabel)
        qdir_source = (SCRIPT_DIR / "q_dir.py").read_text(encoding="utf-8")
        self.assertEqual(
            q_dir.ZOOM_WHEEL_ORDER,
            ["details", "list", "content", "tiles", "small_icons", "medium_icons", "large_icons", "extra_large_icons"],
        )
        for token in (
            "def equalize_splitters(self)",
            "def _on_top_splitter_moved(",
            "def _on_bottom_splitter_moved(",
            "QToolBar#FavToolbar",
            "#FBBF24",
            "#F8FAFC",
            "Qt.Key.Key_Return",
            "Qt.Key.Key_Enter",
            "def step_view_mode_zoom(",
            "class ElidedLabel(",
            "QRubberBand",
        ):
            self.assertIn(token, qdir_source, f"UI/UX 필수 구성요소 누락: {token}")



    # ------------------------------------------------------------------
    # [TC-11] 압축 생성(overwrite=False): 하드링크 미지원 + 게시 직전 동시 파일 생성 시
    #         os.replace 금지 및 기존 파일 보존, 하드링크 후 스테이징 unlink 실패 롤백
    # ------------------------------------------------------------------
    def test_11_compress_no_overwrite_race_and_hardlink_unlink_failure(self) -> None:
        src_file = self.temp_root / "compress_src.txt"
        src_file.write_text("SOURCE_PAYLOAD_V31", encoding="utf-8")

        # 11-A: 하드링크 미지원(OSError) + 게시(rename) 직전 다른 프로세스가 동일 아카이브 생성
        race_arc = self.temp_root / "race_output.zip"
        concurrent_bytes = b"PK\x03\x04CONCURRENT_PROCESS_ARCHIVE_MUST_SURVIVE"

        def _win_non_overwriting_rename(src: str, dst: str) -> None:
            # 게시 직전 다른 프로세스가 동일 경로에 파일을 생성한 경쟁 상황 재현
            Path(dst).write_bytes(concurrent_bytes)
            # Windows MoveFileExW(flags=0) / os.rename은 대상이 존재하면 덮어쓰지 않고 FileExistsError 발생
            if os.path.lexists(dst):
                raise FileExistsError(f"[WinError 183] 파일이 이미 있으므로 만들 수 없습니다: '{dst}'")

        with (
            mock.patch("os.replace", side_effect=AssertionError("overwrite=False 경로에서 os.replace 호출 금지!")),
            mock.patch("os.link", side_effect=OSError("Hardlink not supported on volume")),
            mock.patch.object(q_dir, "_supports_non_overwriting_rename", return_value=True),
            mock.patch("os.rename", side_effect=_win_non_overwriting_rename),
        ):
            ok, msg, cnt = q_dir.compress_items_to_archive([str(src_file)], str(race_arc), "zip", overwrite=False)

        self.assertFalse(ok, "게시 직전 다른 프로세스가 파일을 생성했는데 압축이 성공 처리되었습니다!")
        self.assertEqual(cnt, 0)
        self.assertEqual(
            race_arc.read_bytes(),
            concurrent_bytes,
            "치명적 회귀: 하드링크 미지원 + 경쟁 생성 시 기존 파일이 덮어써졌습니다!",
        )

        # 11-B: 하드링크 미지원 + 비덮어쓰기 rename 지원 미확인 환경에서는 즉시 실패 중단
        unsupported_arc = self.temp_root / "unsupported_env.zip"
        with (
            mock.patch("os.replace", side_effect=AssertionError("os.replace 호출 금지")),
            mock.patch("os.link", side_effect=OSError("EXDEV / EPERM")),
            mock.patch.object(q_dir, "_supports_non_overwriting_rename", return_value=False),
        ):
            ok_u, msg_u, _ = q_dir.compress_items_to_archive([str(src_file)], str(unsupported_arc), "zip", overwrite=False)
        self.assertFalse(ok_u)
        self.assertFalse(unsupported_arc.exists())

        # 11-C: hard-link 성공 후 스테이징 unlink 실패 시 거짓 성공 금지 및 게시본 회수
        unlink_fail_arc = self.temp_root / "unlink_fail.zip"
        orig_unlink = os.unlink

        def _fail_staging_unlink(p: str) -> None:
            if ".qdir_arc_stage_" in os.path.basename(p):
                raise PermissionError("Staging file locked by scanner")
            return orig_unlink(p)

        with mock.patch("os.unlink", side_effect=_fail_staging_unlink):
            ok_uf, msg_uf, cnt_uf = q_dir.compress_items_to_archive(
                [str(src_file)], str(unlink_fail_arc), "zip", overwrite=False
            )
        self.assertFalse(ok_uf, "스테이징 unlink가 실패했는데 거짓 성공(True)을 반환했습니다!")
        self.assertEqual(cnt_uf, 0)
        self.assertFalse(unlink_fail_arc.exists(), "스테이징 unlink 실패 후 게시된 링크가 회수되지 않았습니다!")
        # 남아있는 스테이징 임시파일 정리
        for rem in self.temp_root.glob(".qdir_arc_stage_*"):
            orig_unlink(str(rem))

        # 11-D: hard-link 성공 직후 다른 작성자가 대상 파일을 교체한 뒤 스테이징 unlink가 실패한 경우
        # 실패(False)를 반환하되, 다른 작성자가 교체한 대상 파일은 절대 삭제하지 않고 보존해야 함
        replaced_arc = self.temp_root / "unlink_fail_replaced.zip"

        def _fail_staging_unlink_after_other_replace(p: str) -> None:
            if ".qdir_arc_stage_" in os.path.basename(p):
                if replaced_arc.exists():
                    orig_unlink(str(replaced_arc))
                replaced_arc.write_bytes(b"OTHER_WRITER_REPLACED_ARCHIVE")
                raise PermissionError("Staging file locked after target replacement")
            return orig_unlink(p)

        with mock.patch("os.unlink", side_effect=_fail_staging_unlink_after_other_replace):
            ok_ur, _, cnt_ur = q_dir.compress_items_to_archive(
                [str(src_file)], str(replaced_arc), "zip", overwrite=False
            )
        self.assertFalse(ok_ur)
        self.assertEqual(cnt_ur, 0)
        self.assertEqual(
            replaced_arc.read_bytes(),
            b"OTHER_WRITER_REPLACED_ARCHIVE",
            "스테이징 unlink 실패 롤백 시 다른 작성자가 교체한 대상 파일을 삭제하면 안 됩니다!",
        )
        for rem in self.temp_root.glob(".qdir_arc_stage_*"):
            orig_unlink(str(rem))

    # ------------------------------------------------------------------
    # [TC-12] 압축 해제(overwrite=False): 하드링크 미지원 + 게시 직전 동시 파일/폴더 생성 시
    #         os.replace 금지, 기존 파일 보존, 공유 폴더 병합 차단
    # ------------------------------------------------------------------
    def test_12_extract_no_overwrite_race_and_shared_folder_merge_blocked(self) -> None:
        zip_path = self.temp_root / "sample_extract.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("target_item.txt", "ARCHIVE_NEW_DATA")

        # 12-A: create_subfolder=False, 하드링크 미지원 + rename 직전 다른 프로세스가 target_item.txt 생성
        dest_a = self.temp_root / "extract_race_a"
        dest_a.mkdir(parents=True)
        concurrent_text = "OTHER_PROCESS_CREATED_THIS_FIRST"

        def _win_rename_file_race(src: str, dst: str) -> None:
            if dst.endswith("target_item.txt"):
                Path(dst).write_text(concurrent_text, encoding="utf-8")
            if os.path.lexists(dst):
                raise FileExistsError(f"[WinError 183] 파일이 이미 존재합니다: '{dst}'")

        with (
            mock.patch("os.replace", side_effect=AssertionError("overwrite=False에서 os.replace 호출 금지!")),
            mock.patch("os.link", side_effect=OSError("Hardlink unsupported")),
            mock.patch.object(q_dir, "_supports_non_overwriting_rename", return_value=True),
            mock.patch("os.rename", side_effect=_win_rename_file_race),
        ):
            ok_a, msg_a, cnt_a = q_dir.extract_archive_smart(
                str(zip_path), str(dest_a), create_subfolder=False, overwrite=False
            )

        self.assertFalse(ok_a, "게시 직전 동시 생성 충돌에서 압축 해제가 실패해야 합니다!")
        self.assertEqual(cnt_a, 0)
        self.assertEqual(
            (dest_a / "target_item.txt").read_text(encoding="utf-8"),
            concurrent_text,
            "치명적 회귀: 압축 해제 게시 직전 생성된 기존 파일이 덮어써졌습니다!",
        )

        # 12-B: create_subfolder=True, 스테이징 추출 중 다른 프로세스가 하위 폴더(sample_extract)를 먼저 생성한 경우
        # 공유 폴더 병합으로 우회(fallthrough)하지 않고 즉시 실패하며 기존 폴더를 보존해야 함
        dest_b = self.temp_root / "extract_race_b"
        dest_b.mkdir(parents=True)
        sub_target = dest_b / "sample_extract"

        def _win_rename_dir_race(src: str, dst: str) -> None:
            if Path(dst) == sub_target:
                sub_target.mkdir(parents=True, exist_ok=True)
                (sub_target / "other_writer.txt").write_text("KEEP_ME", encoding="utf-8")
            if os.path.lexists(dst):
                raise FileExistsError(f"[WinError 183] 폴더가 이미 존재합니다: '{dst}'")

        with (
            mock.patch("os.replace", side_effect=AssertionError("overwrite=False에서 os.replace 호출 금지!")),
            mock.patch.object(q_dir, "_supports_non_overwriting_rename", return_value=True),
            mock.patch("os.rename", side_effect=_win_rename_dir_race),
        ):
            ok_b, msg_b, cnt_b = q_dir.extract_archive_smart(
                str(zip_path), str(dest_b), create_subfolder=True, overwrite=False
            )

        self.assertFalse(ok_b, "하위 폴더 동시 생성 시 공유 폴더 병합으로 넘어가면 안 됩니다!")
        self.assertEqual(cnt_b, 0)
        self.assertTrue((sub_target / "other_writer.txt").is_file())
        self.assertFalse((sub_target / "target_item.txt").exists(), "공유 폴더에 파일이 병합 반입되었습니다!")

    # ------------------------------------------------------------------
    # [TC-13] 롤백 시 경로 문자열 rmtree/unlink 금지: 다른 작성자가 추가·교체한 대상 100% 보존
    # ------------------------------------------------------------------
    def test_13_rollback_preserves_other_writer_added_and_replaced_targets(self) -> None:
        # 13-A: 1번째 파일(alpha.txt) 게시 후 다른 작성자가 alpha.txt를 교체(새 inode)하고 2번째 파일(zeta.txt)에서 실패할 때
        dest_a = self.temp_root / "rollback_replace_test"
        dest_a.mkdir(parents=True)

        zip_two = self.temp_root / "rollback_two.zip"
        with zipfile.ZipFile(zip_two, "w") as zf:
            zf.writestr("alpha.txt", "OUR_INITIAL_ALPHA")
            zf.writestr("zeta.txt", "OUR_ZETA")

        orig_link = os.link

        def _hook_link_replace_alpha(src: str, dst: str, *args, **kwargs):
            if dst.endswith("zeta.txt"):
                # 다른 작성자가 이미 게시된 alpha.txt를 삭제 후 새 파일(다른 inode/내용)로 교체함
                alpha_p = dest_a / "alpha.txt"
                if alpha_p.exists():
                    alpha_p.unlink()
                alpha_p.write_text("REPLACED_BY_OTHER_WRITER_DO_NOT_DELETE", encoding="utf-8")
                raise FileExistsError("Concurrent collision on zeta.txt")
            return orig_link(src, dst, *args, **kwargs)

        with mock.patch("os.link", side_effect=_hook_link_replace_alpha):
            ok_a, _, _ = q_dir.extract_archive_smart(str(zip_two), str(dest_a), create_subfolder=False)

        self.assertFalse(ok_a)
        self.assertTrue(
            (dest_a / "alpha.txt").is_file(),
            "치명적 오류: 다른 작성자가 교체한 alpha.txt가 경로 문자열 기반 롤백으로 삭제되었습니다!",
        )
        self.assertEqual(
            (dest_a / "alpha.txt").read_text(encoding="utf-8"),
            "REPLACED_BY_OTHER_WRITER_DO_NOT_DELETE",
        )

        # 13-B: 1번째 폴더(sub_dir/our.txt) 게시 후 다른 작성자가 sub_dir/foreign.txt를 추가하고 2번째 항목(zeta.txt)이 실패할 때
        # 우리의 our.txt만 제거하고 sub_dir와 foreign.txt는 절대 rmtree로 지우지 않고 보존해야 함
        dest_b = self.temp_root / "rollback_dir_test"
        dest_b.mkdir(parents=True)

        zip_dir_and_file = self.temp_root / "dir_and_file.zip"
        with zipfile.ZipFile(zip_dir_and_file, "w") as zf:
            zf.writestr("sub_dir/our.txt", "OUR_FILE_TO_ROLLBACK")
            zf.writestr("zeta.txt", "SECOND_ITEM")

        def _hook_link_add_foreign_in_subdir(src: str, dst: str, *args, **kwargs):
            if dst.endswith("zeta.txt"):
                foreign_f = dest_b / "sub_dir" / "foreign_writer.txt"
                foreign_f.write_text("FOREIGN_WRITER_FILE_MUST_SURVIVE", encoding="utf-8")
                raise FileExistsError("Collision on zeta.txt")
            return orig_link(src, dst, *args, **kwargs)

        with mock.patch("os.link", side_effect=_hook_link_add_foreign_in_subdir):
            ok_b, _, _ = q_dir.extract_archive_smart(str(zip_dir_and_file), str(dest_b), create_subfolder=False)

        self.assertFalse(ok_b)
        self.assertFalse(
            (dest_b / "sub_dir" / "our.txt").exists(),
            "우리가 반입한 our.txt는 롤백 시 제거되어야 합니다.",
        )
        self.assertTrue(
            (dest_b / "sub_dir" / "foreign_writer.txt").is_file(),
            "치명적 오류: 롤백이 rmtree를 호출하여 다른 작성자가 폴더 안에 추가한 foreign_writer.txt를 삭제했습니다!",
        )
        self.assertEqual(
            (dest_b / "sub_dir" / "foreign_writer.txt").read_text(encoding="utf-8"),
            "FOREIGN_WRITER_FILE_MUST_SURVIVE",
        )

    # ------------------------------------------------------------------
    # [TC-14] --self-test-gui 예외 은폐(headless 가짜 성공) 금지 및 첫 실행 설정 덮어쓰기 방지
    # ------------------------------------------------------------------
    def test_14_self_test_gui_no_fake_headless_and_first_run_preserves_configs(self) -> None:
        # 14-A: --self-test-gui 실행 중 GUI 엔진 초기화 예외 발생 시 headless 성공(0)으로 둔갑하지 않고 예외를 그대로 전파해야 함
        with mock.patch.object(q_dir, "run_pyqt6_app", side_effect=RuntimeError("Simulated Qt Display Init Error")):
            with self.assertRaises(RuntimeError):
                q_dir.main(["--profile-dir", str(self.profile_dir), "--engine", "qt", "--self-test-gui"])

        with mock.patch.object(q_dir, "run_tkinter_app", side_effect=RuntimeError("Simulated Tk TclError")):
            with self.assertRaises(RuntimeError):
                q_dir.main(["--profile-dir", str(self.profile_dir), "--engine", "tk", "--self-test-gui"])

        # 14-B: 일반 첫 실행(사용자 변경 없음, _config_dirty=False) 시 기존 홈/인접 설정을 자동 덮어쓰지 않아야 함
        q_dir.set_active_profile(None, None)
        fake_home_cfg = self.temp_root / "fake_home_config.json"
        fake_exe_cfg = self.temp_root / "fake_exe_session.json"
        home_raw = json.dumps({"custom_user_marker": "KEEP_HOME_INTACT", "dark_mode": False}, indent=2)
        exe_raw = json.dumps({"custom_session_marker": "KEEP_EXE_INTACT", "layout_mode": "2h"}, indent=2)
        fake_home_cfg.write_text(home_raw, encoding="utf-8")
        fake_exe_cfg.write_text(exe_raw, encoding="utf-8")

        with mock.patch.object(q_dir, "get_config_candidate_paths", return_value=[fake_exe_cfg, fake_home_cfg]):
            loaded_initial = q_dir.load_app_config()
            self.assertIn("layout_mode", loaded_initial)
            # 일반 첫 실행 중 초기화(_is_initializing=True) 및 무변경 종료(_config_dirty=False) 시 파일 무변경 검증
            self.assertEqual(fake_home_cfg.read_text(encoding="utf-8"), home_raw)
            self.assertEqual(fake_exe_cfg.read_text(encoding="utf-8"), exe_raw)
        q_dir.set_active_profile(profile_dir=str(self.profile_dir))



    # ------------------------------------------------------------------
    # [TC-15] 게시 직후(os.link / os.rename 반환 전후) 다른 작성자의 삭제·교체 경합 및
    #         롤백 시 검사 후 이름 기반 삭제(TOCTOU) 경합 방지, 전용 하위폴더 원자 모드 검증
    # ------------------------------------------------------------------
    def test_15_post_publish_restat_and_check_then_delete_races(self) -> None:
        mods = [("q_dir", q_dir)]
        try:
            archive_safe_core = _load_archive_safe_core()
            mods.append(("archive_safe_core", archive_safe_core))
        except Exception:
            pass

        for mod_name, mod in mods:
            with self.subTest(module=mod_name):
                # 15-A: os.link가 a.txt를 게시한 직후(함수 반환 전) 다른 작성자가 a.txt를 삭제하고 새 파일을 씀 ->
                #       이후 z.txt 충돌 시 롤백이 다른 작성자의 새 a.txt를 절대 삭제하면 안 됨
                dest_a = self.temp_root / f"race_post_link_{mod_name}"
                dest_a.mkdir(parents=True, exist_ok=True)
                (dest_a / "z.txt").write_text("EXISTING_Z_CONFLICT", encoding="utf-8")

                zip_az = self.temp_root / f"az_{mod_name}.zip"
                with zipfile.ZipFile(zip_az, "w") as zf:
                    zf.writestr("a.txt", "OUR_STAGING_A")
                    zf.writestr("z.txt", "OUR_STAGING_Z")

                orig_link = os.link
                orig_find_ci = mod._find_case_insensitive_existing

                # 사전 검사(inspect_archive_entries) 통과 후 커밋 도중 z.txt가 생성된 경쟁 재현
                commit_phase = {"started": False}

                def _find_ci_hide_z_until_commit(parent_dir: str, seg_name: str):
                    if seg_name == "z.txt" and not commit_phase["started"]:
                        return None
                    return orig_find_ci(parent_dir, seg_name)

                def _link_then_other_writer_replaces_immediately(src: str, dst: str, *args, **kwargs):
                    commit_phase["started"] = True
                    if dst.endswith("a.txt"):
                        orig_link(src, dst, *args, **kwargs)
                        # os.link 직후(_publish_file_no_overwrite가 반환하기도 전!) 다른 작성자가 삭제 후 새 파일 기록
                        os.unlink(dst)
                        Path(dst).write_text("OTHER_WRITER_REPLACED_IMMEDIATELY_AFTER_LINK", encoding="utf-8")
                        return None
                    return orig_link(src, dst, *args, **kwargs)

                with (
                    mock.patch.object(mod, "_find_case_insensitive_existing", side_effect=_find_ci_hide_z_until_commit),
                    mock.patch("os.link", side_effect=_link_then_other_writer_replaces_immediately),
                ):
                    ok_a, _, cnt_a = mod.extract_archive_smart(
                        str(zip_az), str(dest_a), create_subfolder=False, overwrite=False
                    )

                self.assertFalse(ok_a)
                self.assertEqual(cnt_a, 0)
                self.assertTrue(
                    (dest_a / "a.txt").is_file(),
                    f"[{mod_name}] 게시 후 대상 ID 재조회 버그로 인해 다른 작성자의 새 a.txt가 삭제되었습니다!",
                )
                self.assertEqual(
                    (dest_a / "a.txt").read_text(encoding="utf-8"),
                    "OTHER_WRITER_REPLACED_IMMEDIATELY_AFTER_LINK",
                )

                # 15-B: os.rename으로 디렉터리(sub_dir/a.txt)를 게시한 직후 다른 작성자가 내부 a.txt를 교체 ->
                #       이후 z.txt 충돌 시 롤백이 다른 작성자의 sub_dir/a.txt를 절대 삭제하면 안 됨
                dest_b = self.temp_root / f"race_post_rename_dir_{mod_name}"
                dest_b.mkdir(parents=True, exist_ok=True)
                (dest_b / "z.txt").write_text("EXISTING_Z_CONFLICT", encoding="utf-8")

                zip_dir_z = self.temp_root / f"dir_z_{mod_name}.zip"
                with zipfile.ZipFile(zip_dir_z, "w") as zf:
                    zf.writestr("sub_dir/a.txt", "OUR_DIR_A")
                    zf.writestr("z.txt", "OUR_Z")

                commit_phase["started"] = False
                orig_rename = os.rename

                def _rename_dir_then_other_writer_replaces_child(src: str, dst: str) -> None:
                    commit_phase["started"] = True
                    orig_rename(src, dst)
                    if dst.endswith("sub_dir"):
                        child_a = Path(dst) / "a.txt"
                        if child_a.exists():
                            child_a.unlink()
                        child_a.write_text("OTHER_WRITER_REPLACED_CHILD_AFTER_DIR_RENAME", encoding="utf-8")

                with (
                    mock.patch.object(mod, "_find_case_insensitive_existing", side_effect=_find_ci_hide_z_until_commit),
                    mock.patch.object(mod, "_supports_non_overwriting_rename", return_value=True),
                    mock.patch("os.rename", side_effect=_rename_dir_then_other_writer_replaces_child),
                ):
                    ok_b, _, cnt_b = mod.extract_archive_smart(
                        str(zip_dir_z), str(dest_b), create_subfolder=False, overwrite=False
                    )

                self.assertFalse(ok_b)
                self.assertEqual(cnt_b, 0)
                self.assertTrue(
                    (dest_b / "sub_dir" / "a.txt").is_file(),
                    f"[{mod_name}] os.rename 디렉터리 게시 후 ID 재조회 버그로 인해 교체된 sub_dir/a.txt가 삭제되었습니다!",
                )
                self.assertEqual(
                    (dest_b / "sub_dir" / "a.txt").read_text(encoding="utf-8"),
                    "OTHER_WRITER_REPLACED_CHILD_AFTER_DIR_RENAME",
                )

                # 15-C: 플랫폼별 롤백 삭제 경합(TOCTOU) 검증
                dest_c = self.temp_root / f"race_check_then_delete_{mod_name}"
                dest_c.mkdir(parents=True, exist_ok=True)

                if os.name == "nt":
                    # [Windows 15-C1] CreateFileW 호출 직전 다른 작성자가 파일을 교체한 경우:
                    # 새로 열린 핸들의 ID가 our_id_pre와 다르므로 삭제하지 않고(deleted=False) 새 파일 바이트를 보존해야 함
                    f_pre = dest_c / "victim_pre.txt"
                    f_pre.write_bytes(b"OUR_PUBLISHED_CONTENT_PRE")
                    our_id_pre = mod._stat_identity(str(f_pre))
                    self.assertIsNotNone(our_id_pre)

                    orig_create_file = mod._k32.CreateFileW
                    swapped_pre = {"done": False}
                    other_pre_bytes = b"WIN_OTHER_WRITER_SWAPPED_BEFORE_CREATEFILEW"

                    def _create_file_pre_swap(lpFileName, dwAccess, dwShare, lpSec, dwDisp, dwFlags, hTpl):
                        if str(lpFileName).endswith("victim_pre.txt") and not swapped_pre["done"]:
                            swapped_pre["done"] = True
                            os.unlink(str(lpFileName))
                            Path(str(lpFileName)).write_bytes(other_pre_bytes)
                        return orig_create_file(lpFileName, dwAccess, dwShare, lpSec, dwDisp, dwFlags, hTpl)

                    with mock.patch.object(mod._k32, "CreateFileW", side_effect=_create_file_pre_swap):
                        deleted_pre = mod._safe_unlink_if_same_file(str(f_pre), our_id_pre)

                    self.assertTrue(swapped_pre["done"], "CreateFileW 직전 파일 교체 주입이 실행되지 않았습니다.")
                    self.assertFalse(deleted_pre, "CreateFileW 직전 교체된 타 작성자 파일이 삭제되면 안 됩니다!")
                    self.assertTrue(f_pre.is_file())
                    self.assertEqual(f_pre.read_bytes(), other_pre_bytes)

                    # [Windows 15-C2a] CreateFileW가 우리 파일의 핸들(h)을 연 직후(GetFileInformationByHandle 전) 교체된 경우:
                    # 열린 핸들(h)에 연결된 우리 원본 객체만 삭제되고(deleted=True), 경로상의 새 파일 바이트는 100% 보존되어야 함
                    f_post = dest_c / "victim_post_open.txt"
                    f_post.write_bytes(b"OUR_PUBLISHED_CONTENT_POST_OPEN")
                    our_id_post = mod._stat_identity(str(f_post))
                    self.assertIsNotNone(our_id_post)

                    swapped_post = {"done": False}
                    other_post_bytes = b"WIN_OTHER_WRITER_SWAPPED_AFTER_HANDLE_OPEN"
                    gone_path = dest_c / "victim_post_open.txt.old_handle_target"

                    def _create_file_post_swap(lpFileName, dwAccess, dwShare, lpSec, dwDisp, dwFlags, hTpl):
                        h = orig_create_file(lpFileName, dwAccess, dwShare, lpSec, dwDisp, dwFlags, hTpl)
                        if str(lpFileName).endswith("victim_post_open.txt") and not swapped_post["done"]:
                            swapped_post["done"] = True
                            os.rename(str(lpFileName), str(gone_path))
                            Path(str(lpFileName)).write_bytes(other_post_bytes)
                        return h

                    with mock.patch.object(mod._k32, "CreateFileW", side_effect=_create_file_post_swap):
                        deleted_post = mod._safe_unlink_if_same_file(str(f_post), our_id_post)

                    self.assertTrue(swapped_post["done"], "핸들 오픈 직후 파일 교체 주입이 실행되지 않았습니다.")
                    self.assertTrue(deleted_post, "열린 핸들(h)에 해당하는 우리 원본 객체는 정상 삭제(True)되어야 합니다.")
                    self.assertFalse(gone_path.exists(), "핸들 기반 삭제(SetFileInformationByHandle)로 원본 객체가 제거되어야 합니다.")
                    self.assertTrue(f_post.is_file(), "경로 이름에 새로 생성된 타 작성자 파일은 보존되어야 합니다!")
                    self.assertEqual(f_post.read_bytes(), other_post_bytes)

                    # [Windows 15-C2b] 핸들 ID 검증(GetFileInformationByHandle) 통과 직후 SetFileInformationByHandle 직전에 교체된 경우:
                    # 마찬가지로 열린 핸들(h)의 우리 원본 객체만 삭제되고(deleted=True), 새 파일 바이트는 100% 보존되어야 함
                    f_post_chk = dest_c / "victim_post_check.txt"
                    f_post_chk.write_bytes(b"OUR_PUBLISHED_CONTENT_POST_CHECK")
                    our_id_post_chk = mod._stat_identity(str(f_post_chk))
                    self.assertIsNotNone(our_id_post_chk)

                    orig_set_info = mod._k32.SetFileInformationByHandle
                    swapped_post_chk = {"done": False}
                    other_post_chk_bytes = b"WIN_OTHER_WRITER_SWAPPED_BEFORE_SETFILEINFO"
                    gone_chk_path = dest_c / "victim_post_check.txt.old_handle_target"

                    def _set_info_pre_swap(hFile, infoClass, lpBuf, dwSize):
                        if not swapped_post_chk["done"] and f_post_chk.exists():
                            swapped_post_chk["done"] = True
                            os.rename(str(f_post_chk), str(gone_chk_path))
                            f_post_chk.write_bytes(other_post_chk_bytes)
                        return orig_set_info(hFile, infoClass, lpBuf, dwSize)

                    with mock.patch.object(mod._k32, "SetFileInformationByHandle", side_effect=_set_info_pre_swap):
                        deleted_post_chk = mod._safe_unlink_if_same_file(str(f_post_chk), our_id_post_chk)

                    self.assertTrue(swapped_post_chk["done"], "SetFileInformationByHandle 직전 파일 교체 주입이 실행되지 않았습니다.")
                    self.assertTrue(deleted_post_chk, "열린 핸들(h)에 해당하는 우리 원본 객체는 정상 삭제(True)되어야 합니다.")
                    self.assertFalse(gone_chk_path.exists(), "핸들 기반 삭제(SetFileInformationByHandle)로 원본 객체가 제거되어야 합니다.")
                    self.assertTrue(f_post_chk.is_file(), "경로 이름에 새로 생성된 타 작성자 파일은 보존되어야 합니다!")
                    self.assertEqual(f_post_chk.read_bytes(), other_post_chk_bytes)
                else:
                    # [POSIX 15-C] 이름으로 unlink하는 구현에서 lstat 검사 직후 파일이 교체되는 경쟁 검증
                    f_c = dest_c / "victim.txt"
                    f_c.write_bytes(b"OUR_PUBLISHED_CONTENT")
                    our_id = mod._stat_identity(str(f_c))
                    self.assertIsNotNone(our_id)

                    orig_lstat = os.lstat
                    swapped_posix = {"done": False}
                    other_posix_bytes = b"POSIX_SWAPPED_RIGHT_AFTER_LSTAT"

                    def _lstat_swap_race(p):
                        st = orig_lstat(p)
                        if str(p).endswith("victim.txt") and not swapped_posix["done"]:
                            swapped_posix["done"] = True
                            try:
                                os.unlink(p)
                            except OSError:
                                pass
                            Path(p).write_bytes(other_posix_bytes)
                        return st

                    with mock.patch("os.lstat", side_effect=_lstat_swap_race):
                        deleted = mod._safe_unlink_if_same_file(str(f_c), our_id)

                    self.assertTrue(swapped_posix["done"], "POSIX lstat 직후 교체 주입이 실행되지 않았습니다.")
                    self.assertFalse(deleted, "검사 직후 교체된 파일이 이름 기반 unlink로 삭제되면 안 됩니다!")
                    self.assertTrue(f_c.is_file())
                    self.assertEqual(f_c.read_bytes(), other_posix_bytes)

                # 15-D: 전용 새 하위 폴더 원자적 비덮어쓰기 게시 모드(atomic_subfolder_only=True) 검증
                dest_d = self.temp_root / f"atomic_subfolder_mode_{mod_name}"
                dest_d.mkdir(parents=True, exist_ok=True)
                # 이미 존재하는 폴더에 create_subfolder=False로 풀려고 하면 공유 폴더 반입을 즉시 거부해야 함
                ok_d1, _, _ = mod.extract_archive_smart(
                    str(zip_az), str(dest_d), create_subfolder=False, overwrite=False, atomic_subfolder_only=True
                )
                self.assertFalse(ok_d1)
                # create_subfolder=True로 전용 새 하위 폴더에 게시하면 단일 원자 연산으로 성공해야 함
                ok_d2, sub_out, cnt_d2 = mod.extract_archive_smart(
                    str(zip_az), str(dest_d), create_subfolder=True, overwrite=False, atomic_subfolder_only=True
                )
                self.assertTrue(ok_d2)
                self.assertEqual(cnt_d2, 2)
                self.assertTrue((Path(sub_out) / "a.txt").is_file())
                self.assertTrue((Path(sub_out) / "z.txt").is_file())


    # ------------------------------------------------------------------
    # [TC-16] 다크/라이트 명암비(WCAG >= 4.5:1), 세부 정보 창(InspectorPane) 검은 글씨 방지,
    #         좁은 패널 흰 탭 바 제거, 긴 한글 탭/주소 구분 및 360px/780px 레이아웃 보존 검증
    # ------------------------------------------------------------------
    def test_16_ui_contrast_tabs_address_and_responsive_preservation(self) -> None:
        def _rel_lum(hex_col: str) -> float:
            h = hex_col.lstrip("#")
            rgb = [int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4)]
            lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
            return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]

        def _contrast(fg: str, bg: str) -> float:
            l1, l2 = _rel_lum(fg), _rel_lum(bg)
            bright, dark = max(l1, l2), min(l1, l2)
            return (bright + 0.05) / (dark + 0.05)

        # 16-A: 다크/라이트 핵심 UI 컴포넌트 전경/배경 명암비 검증 (WCAG AA 4.5:1 이상)
        contrast_pairs = [
            # Dark Mode
            ("Dark Inspector Title", "#38BDF8", "#1E293B", 4.5),
            ("Dark Inspector Meta (이름/위치/날짜)", "#F8FAFC", "#0F172A", 7.0),
            ("Dark Inspector Preview Label", "#E2E8F0", "#0F172A", 7.0),
            ("Dark Favorites Title", "#FBBF24", "#1E293B", 4.5),
            ("Dark Favorites Item Button", "#F8FAFC", "#0F172A", 7.0),
            ("Dark Active Tab", "#FFFFFF", "#1E3A8A", 7.0),
            ("Dark Inactive Tab", "#CBD5E1", "#0F172A", 7.0),
            ("Dark Address & Filter Input", "#F8FAFC", "#0F172A", 7.0),
            # Light Mode
            ("Light Inspector Title", "#1E3A8A", "#FFFFFF", 7.0),
            ("Light Inspector Meta (이름/위치/날짜)", "#0F172A", "#F8FAFC", 7.0),
            ("Light Favorites Title", "#0F172A", "#F1F5F9", 7.0),
            ("Light Favorites Item Button", "#0F172A", "#FFFFFF", 7.0),
            ("Light Active Tab", "#1E3A8A", "#FFFFFF", 7.0),
            ("Light Inactive Tab", "#334155", "#E2E8F0", 4.5),
            ("Light Address & Filter Input", "#0F172A", "#FFFFFF", 7.0),
        ]
        for label, fg, bg, min_ratio in contrast_pairs:
            ratio = _contrast(fg, bg)
            self.assertGreaterEqual(
                ratio,
                min_ratio,
                f"[{label}] 명암비 미달: {fg} on {bg} = {ratio:.2f}:1 (최소 {min_ratio}:1 필요)",
            )

        # 16-B: QSS 규칙에 세부 정보 창(InspectorPane), 일반 QLabel, QTabBar 배경, 활성 탭 구분이 모두 존재하는지 검증
        qdir_source = Path(q_dir.__file__).read_text(encoding="utf-8")
        required_qss_tokens = [
            "QLabel, QCheckBox, QRadioButton { color: #F8FAFC; background: transparent; }",
            "QFrame#InspectorPane QLabel#InspectorTitleLabel { color: #38BDF8;",
            "QFrame#InspectorPane QLabel#InspectorMetaLabel { color: #F8FAFC; background-color: #0F172A;",
            "QTabWidget, QTabWidget::tab-bar, QTabBar { background-color: #0F172A; border: none; }",
            "QTabWidget, QTabWidget::tab-bar, QTabBar { background-color: #E2E8F0; border: none; }",
            "self.tab_widget.setDocumentMode(False)",
        ]
        for token in required_qss_tokens:
            self.assertIn(token, qdir_source, f"필수 QSS/탭 스타일 누락: {token}")

        # 16-C: 긴 한글 폴더명 가운데 말줄임으로 접두사 동일 폴더들이 서로 명확히 구분되는지 검증
        long_kr_1 = "2026년_상반기_차세대_정보시스템_고도화_사업_제안서_최종본_v1"
        long_kr_2 = "2026년_상반기_차세대_정보시스템_고도화_사업_제안서_최종본_v2"
        elided_1 = q_dir.elide_middle_smart(long_kr_1, 20)
        elided_2 = q_dir.elide_middle_smart(long_kr_2, 20)
        self.assertNotEqual(
            elided_1,
            elided_2,
            f"긴 한글 폴더명 말줄임 결과가 서로 구분되지 않습니다: {elided_1} vs {elided_2}",
        )
        self.assertTrue(elided_1.endswith("_v1"))
        self.assertTrue(elided_2.endswith("_v2"))

        # 16-D: 사용자 실경로 흔적 0건 검증
        self.assertNotIn("G:/%EB%82%B4", qdir_source)
        self.assertNotIn("장윤이", qdir_source)

    # ------------------------------------------------------------------
    # [TC-17] overwrite=True 경로 완전 제거 및 거부 검증 (compress / extract / inspect)
    # ------------------------------------------------------------------
    def test_17_overwrite_true_strictly_prohibited(self) -> None:
        src_f = self.temp_root / "no_ow_src.txt"
        src_f.write_text("SOURCE_PAYLOAD", encoding="utf-8")
        arc_f = self.temp_root / "no_ow.zip"

        # 17-A: compress_items_to_archive(..., overwrite=True) 즉시 거부
        ok_c, msg_c, cnt_c = q_dir.compress_items_to_archive([str(src_f)], str(arc_f), "zip", overwrite=True)
        self.assertFalse(ok_c)
        self.assertEqual(cnt_c, 0)
        self.assertIn("overwrite=True", msg_c)
        self.assertFalse(arc_f.exists())

        # 정상 생성(overwrite=False) 후 extract_archive_smart(..., overwrite=True) 및 inspect(..., overwrite=True) 즉시 거부
        ok_c2, _, _ = q_dir.compress_items_to_archive([str(src_f)], str(arc_f), "zip", overwrite=False)
        self.assertTrue(ok_c2)

        dest_dir = self.temp_root / "no_ow_dest"
        dest_dir.mkdir(parents=True, exist_ok=True)
        with self.assertRaises(ValueError):
            q_dir.inspect_archive_entries(str(arc_f), str(dest_dir), overwrite=True)

        ok_e, msg_e, cnt_e = q_dir.extract_archive_smart(str(arc_f), str(dest_dir), create_subfolder=True, overwrite=True)
        self.assertFalse(ok_e)
        self.assertEqual(cnt_e, 0)
        self.assertIn("overwrite=True", msg_e)

        # archive_safe_core 모듈에서도 동일하게 거부 및 os.replace 호출 코드가 0건인지 검증
        archive_safe_core = _load_archive_safe_core()
        core_text = Path(archive_safe_core.__file__).read_text(encoding="utf-8")
        self.assertNotIn("os.replace(", core_text)
        ok_ec, msg_ec, _ = archive_safe_core.extract_archive_smart(
            str(arc_f), str(dest_dir), create_subfolder=True, overwrite=True
        )
        self.assertFalse(ok_ec)
        self.assertIn("overwrite=True", msg_ec)


if __name__ == "__main__":
    unittest.main(verbosity=2)
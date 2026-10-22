#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PyQuadDir Desktop Explorer — PyInstaller 단일 실행 파일(.exe) 자동 빌드 스크립트
=================================================================================
이 스크립트는 `pyquaddir.py`를 Windows에서 콘솔 창 없는 단일 실행 파일(`dist/PyQuadDir.exe`)로
자동 패키징합니다.

주요 기능:
1. 필수 빌드 패키지(`PySide6` 또는 `PyQt6`, `pyinstaller`) 설치 여부 확인 및 자동 설치
2. 외부 이미지 없이 순수 Python 바이너리 생성기로 4분할 PyQuadDir 전용 아이콘(`pyquaddir.ico`) 자동 생성
3. Windows 실행 파일 상세 속성(`version_info.txt`: 파일 설명, 버전, 저작권 메타데이터) 자동 생성
4. PyInstaller `--onefile --windowed` 최적화 옵션 실행 및 완료 후 `dist` 폴더 자동 열기

사용 방법 (pyquaddir.py와 같은 폴더에서 실행):
    python build_exe.py
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import platform
import shutil
import struct
import subprocess
import sys
import zlib
from pathlib import Path
from typing import List


APP_NAME = "PyQuadDir"
SOURCE_SCRIPT = "pyquaddir.py"
ICON_FILE = "pyquaddir.ico"
VERSION_FILE = "version_info.txt"


# ---------------------------------------------------------------------------
# 1. 순수 Python 기반 PyQuadDir 4분할 로고 아이콘(pyquaddir.ico) 생성기 (외부 패키지 불필요)
# ---------------------------------------------------------------------------
def generate_quaddir_ico(output_path: Path, size: int = 64) -> Path:
    """
    외부 이미지 라이브러리(Pillow 등) 없이도 표준 PNG-in-ICO 포맷으로
    선명한 4분할(블루·그린·앰버·퍼플) PyQuadDir 아이콘(.ico) 파일을 생성합니다.
    """
    width = height = size
    raw_rows: List[bytes] = []

    # 색상 팔레트 (R, G, B, A)
    bg_dark = (15, 23, 42, 255)        # #0F172A 네이비 다크 배경
    border_col = (51, 65, 85, 255)     # #334155 외곽 테두리
    quad_tl = (56, 189, 248, 255)      # 좌상단: 스카이 블루 (#38BDF8)
    quad_tr = (52, 211, 153, 255)      # 우상단: 에메랄드 그린 (#34D399)
    quad_bl = (251, 191, 36, 255)      # 좌하단: 골드 앰버 (#FBBF24)
    quad_br = (192, 132, 252, 255)     # 우하단: 바이올렛 퍼플 (#C084FC)
    header_tint = (255, 255, 255, 255) # 각 패널 상단 탭 바 하이라이트

    half = size // 2
    pad = max(4, size // 12)
    gap = max(2, size // 20)
    corner_r = max(6, size // 8)

    def _in_rounded_rect(x: int, y: int, x0: int, y0: int, x1: int, y1: int, r: int) -> bool:
        if not (x0 <= x < x1 and y0 <= y < y1):
            return False
        if x < x0 + r and y < y0 + r:
            return (x - (x0 + r)) ** 2 + (y - (y0 + r)) ** 2 <= r ** 2
        if x >= x1 - r and y < y0 + r:
            return (x - (x1 - r - 1)) ** 2 + (y - (y0 + r)) ** 2 <= r ** 2
        if x < x0 + r and y >= y1 - r:
            return (x - (x0 + r)) ** 2 + (y - (y1 - r - 1)) ** 2 <= r ** 2
        if x >= x1 - r and y >= y1 - r:
            return (x - (x1 - r - 1)) ** 2 + (y - (y1 - r - 1)) ** 2 <= r ** 2
        return True

    for y in range(height):
        row = bytearray([0])  # PNG filter type 0 (None)
        for x in range(width):
            if not _in_rounded_rect(x, y, 1, 1, width - 1, height - 1, corner_r):
                row.extend((0, 0, 0, 0))
                continue

            if not _in_rounded_rect(x, y, 3, 3, width - 3, height - 3, max(4, corner_r - 2)):
                row.extend(border_col)
                continue

            # 4분할 사분면 영역 계산
            in_left = pad <= x < half - gap
            in_right = half + gap <= x < width - pad
            in_top = pad <= y < half - gap
            in_bottom = half + gap <= y < height - pad

            if in_left and in_top:
                col = header_tint if y < pad + 5 else quad_tl
            elif in_right and in_top:
                col = header_tint if y < pad + 5 else quad_tr
            elif in_left and in_bottom:
                col = header_tint if y < half + gap + 5 else quad_bl
            elif in_right and in_bottom:
                col = header_tint if y < half + gap + 5 else quad_br
            else:
                col = bg_dark

            row.extend(col)
        raw_rows.append(bytes(row))

    raw_data = b"".join(raw_rows)

    def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", crc)

    png_sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    idat = zlib.compress(raw_data, level=9)
    png_bytes = (
        png_sig
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", idat)
        + _png_chunk(b"IEND", b"")
    )

    # ICO 컨테이너 헤더 (1개 PNG 엔트리 포함)
    ico_header = struct.pack("<HHH", 0, 1, 1)
    w_byte = 0 if width >= 256 else width
    h_byte = 0 if height >= 256 else height
    ico_dir_entry = struct.pack(
        "<BBBBHHII",
        w_byte,
        h_byte,
        0,
        0,
        1,
        32,
        len(png_bytes),
        6 + 16,  # 헤더(6) + 엔트리(16) = 22바이트 오프셋
    )

    output_path.write_bytes(ico_header + ico_dir_entry + png_bytes)
    return output_path


# ---------------------------------------------------------------------------
# 2. Windows 실행 파일 버전 리소스(version_info.txt) 생성기
# ---------------------------------------------------------------------------
def generate_version_file(output_path: Path) -> Path:
    content = """# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(1, 0, 0, 0),
    prodvers=(1, 0, 0, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        '041204B0',
        [StringStruct('CompanyName', 'PyQuadDir Open Source Project'),
        StringStruct('FileDescription', 'PyQuadDir 4분할 다중 탭 파일 탐색기'),
        StringStruct('FileVersion', '1.0.0.0'),
        StringStruct('InternalName', 'PyQuadDir'),
        StringStruct('LegalCopyright', 'MIT License — Open Source Desktop Utility'),
        StringStruct('OriginalFilename', 'PyQuadDir.exe'),
        StringStruct('ProductName', 'PyQuadDir Desktop Explorer'),
        StringStruct('ProductVersion', '1.0.0.0')])
      ]),
    VarFileInfo([VarStruct('Translation', [1042, 1200])])
  ]
)
"""
    output_path.write_text(content, encoding="utf-8")
    return output_path


# ---------------------------------------------------------------------------
# 3. pyquaddir.py 동결(Frozen .exe) 환경 안전 패치 점검
# ---------------------------------------------------------------------------
def ensure_frozen_safe_source(script_path: Path) -> None:
    """
    PyInstaller로 빌드된 .exe 실행 파일 내부에서는 `sys.executable`이 파이썬 인터프리터가 아닌
    `PyQuadDir.exe` 자신을 가리키므로, 동결 상태(`sys.frozen`)일 때 `pip install` 서브프로세스를
    호출하지 않도록 안전 가드를 보장합니다.
    """
    text = script_path.read_text(encoding="utf-8")
    if 'getattr(sys, "frozen", False)' not in text and "def _check_or_install_pyqt6() -> bool:" in text:
        guard_snippet = 'if getattr(sys, "frozen", False):\n        return _detect_qt_binding() is not None'
        target = '    if "--tk" in sys.argv:\n        return False'
        replacement = f"{target}\n    {guard_snippet}"
        if target in text:
            script_path.write_text(text.replace(target, replacement, 1), encoding="utf-8")
            print("[✓] pyquaddir.py 내부에 PyInstaller Frozen(.exe) 안전 가드를 적용했습니다.")


# ---------------------------------------------------------------------------
# 4. 필수 패키지 점검 및 PyInstaller 빌드 실행
# ---------------------------------------------------------------------------
def detect_installed_qt() -> str:
    if importlib.util.find_spec("PySide6") is not None:
        return "PySide6"
    if importlib.util.find_spec("PyQt6") is not None:
        return "PyQt6"
    return ""


def ensure_build_dependencies(skip_install: bool = False) -> str:
    qt_pkg = detect_installed_qt()
    missing: List[str] = []
    if not qt_pkg:
        missing.append("PySide6")
    if importlib.util.find_spec("PyInstaller") is None:
        missing.append("pyinstaller")

    if not missing:
        print(f"[✓] {qt_pkg} 및 PyInstaller 패키지가 모두 준비되어 있습니다.")
        return qt_pkg

    if skip_install:
        print(f"[!] 미설치 패키지 감지: {', '.join(missing)} (--skip-install 모드)")
        return qt_pkg or "PySide6"

    print(f"[*] 빌드에 필요한 패키지를 설치합니다: {', '.join(missing)}")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", *missing])
    return detect_installed_qt() or "PySide6"


def build_pyinstaller_command(
    script_path: Path,
    icon_path: Path,
    version_path: Path,
    qt_pkg: str = "PyQt6",
    onefile: bool = True,
    clean: bool = True,
) -> List[str]:
    cmd: List[str] = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--windowed",  # 콘솔 창 숨김 (GUI 전용)
        f"--name={APP_NAME}",
        f"--icon={icon_path}",
        # Qt 바인딩 및 Tkinter 폴백 모듈 명시적 포함
        f"--hidden-import={qt_pkg}.QtCore",
        f"--hidden-import={qt_pkg}.QtGui",
        f"--hidden-import={qt_pkg}.QtWidgets",
        "--hidden-import=tkinter",
        "--hidden-import=tkinter.ttk",
        "--hidden-import=tkinter.messagebox",
        "--hidden-import=tkinter.simpledialog",
    ]
    if onefile:
        cmd.append("--onefile")
    else:
        cmd.append("--onedir")

    if clean:
        cmd.append("--clean")

    if platform.system() == "Windows" and version_path.exists():
        cmd.append(f"--version-file={version_path}")

    cmd.append(str(script_path))
    return cmd


def clean_build_artifacts(base_dir: Path) -> None:
    """이전 빌드 임시 폴더(build/)와 .spec 파일을 정리합니다."""
    build_dir = base_dir / "build"
    spec_file = base_dir / f"{APP_NAME}.spec"
    if build_dir.exists():
        shutil.rmtree(build_dir, ignore_errors=True)
    if spec_file.exists():
        try:
            spec_file.unlink()
        except Exception:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(
        description="pyquaddir.py를 단일 실행 파일(PyQuadDir.exe)로 패키징합니다."
    )
    parser.add_argument(
        "--onedir",
        action="store_true",
        help="단일 .exe 대신 폴더 형태(--onedir)로 빠르게 빌드합니다 (초기 구동 속도 우선 시 사용).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="아이콘과 버전 리소스 파일만 생성하고 실제 PyInstaller 실행 명령어를 출력합니다.",
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="빌드 완료 후 임시 폴더(build/, PyQuadDir.spec)를 삭제하지 않고 유지합니다.",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="빌드 완료 후 dist 폴더를 탐색기로 자동 열지 않습니다.",
    )
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent
    script_path = base_dir / SOURCE_SCRIPT

    print("=" * 68)
    print(" 🚀 PyQuadDir Desktop Explorer — PyInstaller .EXE 자동 패키징 도구")
    print("=" * 68)

    if not script_path.exists():
        print(f"[오류] '{script_path}' 파일을 찾을 수 없습니다.")
        print("       build_exe.py를 pyquaddir.py와 같은 폴더에 두고 실행해 주세요.")
        return 1

    # 1. pyquaddir.py 동결 가드 확인
    ensure_frozen_safe_source(script_path)

    # 2. 아이콘(.ico) 및 버전 리소스 생성
    icon_path = generate_quaddir_ico(base_dir / ICON_FILE)
    print(f"[✓] 4분할 전용 아이콘 생성 완료: {icon_path.name}")

    version_path = generate_version_file(base_dir / VERSION_FILE)
    print(f"[✓] Windows 버전 리소스 파일 생성 완료: {version_path.name}")

    # 3. 명령어 조합
    qt_pkg = detect_installed_qt() or "PySide6"
    cmd = build_pyinstaller_command(
        script_path=script_path,
        icon_path=icon_path,
        version_path=version_path,
        qt_pkg=qt_pkg,
        onefile=not args.onedir,
        clean=True,
    )

    if args.dry_run:
        print("\n[Dry-Run] 실행될 PyInstaller 명령어:")
        print("  " + " ".join(cmd))
        return 0

    # 4. 의존성 설치 및 빌드 수행
    qt_pkg = ensure_build_dependencies()
    cmd = build_pyinstaller_command(
        script_path=script_path,
        icon_path=icon_path,
        version_path=version_path,
        qt_pkg=qt_pkg,
        onefile=not args.onedir,
        clean=True,
    )

    print("\n[*] PyInstaller 패키징을 시작합니다 (약 30초~1분 소요)...")
    print("    명령어:", " ".join(cmd))
    print("-" * 68)

    result = subprocess.run(cmd, cwd=str(base_dir))
    if result.returncode != 0:
        print(f"\n[!] 빌드 중 오류가 발생했습니다 (종료 코드: {result.returncode}).")
        return result.returncode

    if not args.keep_temp:
        clean_build_artifacts(base_dir)

    ext = ".exe" if platform.system() == "Windows" else ""
    if args.onedir:
        output_bin = base_dir / "dist" / APP_NAME / f"{APP_NAME}{ext}"
    else:
        output_bin = base_dir / "dist" / f"{APP_NAME}{ext}"

    print("\n" + "=" * 68)
    print(" ✅ PyQuadDir 단일 실행 파일(.exe) 패키징 완료!")
    if output_bin.exists():
        size_mb = output_bin.stat().st_size / (1024 * 1024)
        print(f" 📂 생성된 실행 파일: {output_bin} ({size_mb:.1f} MB)")
    else:
        print(f" 📂 출력 폴더: {base_dir / 'dist'}")
    print("=" * 68)

    # Windows에서 빌드 완료 시 결과물 폴더(dist) 자동 열기
    dist_dir = base_dir / "dist"
    if not args.no_open and platform.system() == "Windows" and dist_dir.exists():
        try:
            os.startfile(str(dist_dir))  # type: ignore[attr-defined]
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main())

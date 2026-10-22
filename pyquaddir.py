#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
PyQuadDir Desktop Explorer v2.2 (Quad-View Multi-Tab File Manager for Windows)
==============================================================================
실제 Windows 로컬 드라이브(C:\, D:\ 등)와 파일 시스템을 직접 제어하는
데스크톱 4분할(Quad) 다중 탭 파일 탐색기입니다.
(Inspired by the quad-pane file manager concept of Q-Dir)

[트리플 엔진 지원 — MIT 라이선스 호환]
- 기본 Qt 엔진 (PySide6 / PyQt6 자동 감지): OS 네이티브 파일 아이콘, 실시간 이미지 썸네일,
  고시인성 Windows 11 벡터 아이콘(QPainter), Ctrl+마우스 휠 8단계 뷰/썸네일 줌 전환
- 내장 폴백 엔진 (Tkinter ttk): 외부 패키지 설치 없이 Python 표준 라이브러리만으로도 즉시 구동

[v2.2 주요 업데이트]
1. 고시인성 벡터 아이콘(QPainter QIcon) 렌더링 & 아이콘 크기 확대:
   - 작아서 보이지 않던 특수문자(⊕, ⇅, ⊞, ◧, ◨, ◀, ▶, ▲, ⟳)를 Windows 11 스타일의
     선명한 컬러 벡터 그래픽 아이콘(20x20px)으로 전면 교체하고 목록 기본 아이콘 크기 확대
2. Ctrl + 마우스 휠 스크롤 보기 모드(썸네일 크기) 실시간 전환:
   - 패널 위에서 [Ctrl + 마우스 휠 위로] 스크롤 시:
     자세히 → 목록 → 내용 → 타일 → 작은 아이콘 → 보통 아이콘 → 큰 아이콘 → 아주 큰 아이콘(최대 220px) 순으로 확대 전환
   - [Ctrl + 마우스 휠 아래로] 스크롤 시 역순으로 축소/상세 보기로 즉시 전환
3. 파일/폴더 선택 후 Enter 키 즉시 실행 및 진입:
   - 메인 Enter 및 숫자패드 Enter로 폴더 진입 / 파일 실행, Backspace로 상위 폴더 이동
4. 상단 레이아웃·드라이브 드롭다운 메뉴화 & 즐겨찾기 전용 바 확장
5. 전체 선택(Ctrl+A) 시 상위 폴더('..') 선택 자동 제외
"""

from __future__ import annotations

import ctypes
import datetime
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# 공통 설정 및 확장자 색상 필터 프리셋
# ---------------------------------------------------------------------------
CONFIG_PATH = Path.home() / ".pyquaddir_config.json"
LEGACY_CONFIG_PATH = Path.home() / ".qdir_py_config.json"

IMAGE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico", ".svg", ".tif", ".tiff"
}

TEXT_PREVIEW_EXTENSIONS = {
    ".txt", ".md", ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".htm", ".css",
    ".json", ".xml", ".yaml", ".yml", ".ini", ".cfg", ".conf", ".log", ".bat",
    ".cmd", ".ps1", ".sh", ".csv", ".tsv", ".sql", ".c", ".cpp", ".h", ".java",
    ".cs", ".go", ".rs", ".toml", ".env",
}

DEFAULT_COLOR_RULES: Dict[str, Dict[str, object]] = {
    "폴더 (Directory)": {
        "extensions": ["<DIR>"],
        "color_dark": "#FBBF24",   # 골드 앰버
        "color_light": "#B45309",
        "enabled": True,
    },
    "실행 및 스크립트 (Executable)": {
        "extensions": [".exe", ".msi", ".bat", ".cmd", ".ps1", ".vbs", ".com", ".sh"],
        "color_dark": "#34D399",   # 에메랄드 그린
        "color_light": "#047857",
        "enabled": True,
    },
    "압축 아카이브 (Archive)": {
        "extensions": [".zip", ".7z", ".rar", ".tar", ".gz", ".bz2", ".xz", ".iso", ".alz", ".egg"],
        "color_dark": "#C084FC",   # 퍼플
        "color_light": "#7E22CE",
        "enabled": True,
    },
    "이미지 및 그래픽 (Image)": {
        "extensions": [".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".ico", ".psd", ".ai", ".tif"],
        "color_dark": "#38BDF8",   # 스카이 블루
        "color_light": "#0369A1",
        "enabled": True,
    },
    "문서 및 오피스 (Document)": {
        "extensions": [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".hwp", ".hwpx", ".txt", ".md", ".csv", ".rtf"],
        "color_dark": "#FB923C",   # 코랄 오렌지
        "color_light": "#C2410C",
        "enabled": True,
    },
    "소스 코드 및 설정 (Code)": {
        "extensions": [".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".json", ".xml", ".yaml", ".yml", ".c", ".cpp", ".h", ".java", ".cs", ".go", ".rs", ".sql"],
        "color_dark": "#A3E635",   # 라임 그린
        "color_light": "#3F6212",
        "enabled": True,
    },
    "오디오 및 비디오 (Media)": {
        "extensions": [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm", ".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"],
        "color_dark": "#F472B6",   # 핑크 로즈
        "color_light": "#BE185D",
        "enabled": True,
    },
    "시스템 및 로그 (System)": {
        "extensions": [".dll", ".sys", ".ini", ".cfg", ".log", ".tmp", ".bak", ".dat", ".lnk"],
        "color_dark": "#94A3B8",   # 슬레이트 그레이
        "color_light": "#64748B",
        "enabled": True,
    },
}

VIEW_MODES_META: List[Tuple[str, str, int]] = [
    ("extra_large_icons", "아주 큰 아이콘", 148),
    ("large_icons", "큰 아이콘", 92),
    ("medium_icons", "보통 아이콘", 60),
    ("small_icons", "작은 아이콘", 32),
    ("list", "목록", 24),
    ("details", "자세히", 24),
    ("tiles", "타일", 52),
    ("content", "내용", 40),
]

# Ctrl + 마우스 휠 확대/축소 순서 (아래로 스크롤 <-> 위로 스크롤)
ZOOM_WHEEL_ORDER: List[str] = [
    "details",            # 1단계: 자세히 (테이블)
    "list",               # 2단계: 목록
    "content",            # 3단계: 내용
    "tiles",              # 4단계: 타일
    "small_icons",        # 5단계: 작은 아이콘 (32px)
    "medium_icons",       # 6단계: 보통 아이콘 (60px)
    "large_icons",        # 7단계: 큰 아이콘 (92px)
    "extra_large_icons",  # 8단계: 아주 큰 아이콘 (148px~220px)
]

VIEW_MODE_LABELS: Dict[str, str] = {k: v for k, v, _ in VIEW_MODES_META}


def load_app_config() -> Dict[str, object]:
    for candidate in (CONFIG_PATH, LEGACY_CONFIG_PATH):
        if candidate.exists():
            try:
                return json.loads(candidate.read_text(encoding="utf-8"))
            except Exception:
                continue
    return {}


def save_app_config(data: Dict[str, object]) -> None:
    try:
        CONFIG_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


def get_default_favorites() -> List[Dict[str, str]]:
    """Windows 및 OS 표준 주요 사용자 폴더를 기본 즐겨찾기로 구성합니다."""
    home = Path.home()
    candidates = [
        ("🏠 홈 폴더", home),
        ("🖥️ 바탕화면", home / "Desktop"),
        ("📥 다운로드", home / "Downloads"),
        ("📄 문서", home / "Documents"),
        ("🖼️ 사진", home / "Pictures"),
    ]
    favs: List[Dict[str, str]] = []
    for name, path in candidates:
        if path.exists() and path.is_dir():
            favs.append({"name": name, "path": str(path)})
    return favs


def get_mounted_drives() -> List[Dict[str, object]]:
    """현재 PC에 연결된 모든 드라이브(C:\\, D:\\ 등)와 용량 정보를 반환합니다."""
    drives: List[Dict[str, object]] = []
    if platform.system() == "Windows":
        try:
            bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        except Exception:
            bitmask = 0
        for i in range(26):
            if bitmask & (1 << i):
                letter = f"{chr(65 + i)}:\\"
                if os.path.exists(letter):
                    label = _get_windows_volume_label(letter)
                    free_b, total_b = _safe_disk_usage(letter)
                    drives.append({
                        "root": letter,
                        "label": label,
                        "free": free_b,
                        "total": total_b,
                    })
    else:
        for root_candidate in ("/", str(Path.home())):
            if os.path.exists(root_candidate):
                free_b, total_b = _safe_disk_usage(root_candidate)
                drives.append({
                    "root": root_candidate,
                    "label": "루트" if root_candidate == "/" else "홈",
                    "free": free_b,
                    "total": total_b,
                })
    return drives


def _get_windows_volume_label(drive_root: str) -> str:
    if platform.system() != "Windows":
        return ""
    try:
        vol_buf = ctypes.create_unicode_buffer(261)
        fs_buf = ctypes.create_unicode_buffer(261)
        ctypes.windll.kernel32.GetVolumeInformationW(
            ctypes.c_wchar_p(drive_root),
            vol_buf,
            ctypes.sizeof(vol_buf),
            None,
            None,
            None,
            fs_buf,
            ctypes.sizeof(fs_buf),
        )
        return vol_buf.value or "로컬 디스크"
    except Exception:
        return "로컬 디스크"


def _safe_disk_usage(path: str) -> Tuple[int, int]:
    try:
        usage = shutil.disk_usage(path)
        return usage.free, usage.total
    except Exception:
        return 0, 0


def format_size(size_bytes: int) -> str:
    """바이트 단위를 읽기 쉬운 단위로 변환합니다."""
    if size_bytes < 0:
        return ""
    if size_bytes < 1024:
        return f"{size_bytes:,} B"
    units = ["KB", "MB", "GB", "TB", "PB"]
    val = float(size_bytes)
    for unit in units:
        val /= 1024.0
        if val < 1024.0 or unit == units[-1]:
            return f"{val:,.1f} {unit}" if val < 100 else f"{val:,.0f} {unit}"
    return f"{size_bytes:,} B"


def classify_size_bucket(size_b: int, is_dir: bool) -> str:
    if is_dir:
        return "0. 폴더"
    if size_b == 0:
        return "1. 빈 파일 (0 B)"
    if size_b < 100 * 1024:
        return "2. 아주 작음 (< 100 KB)"
    if size_b < 5 * 1024 * 1024:
        return "3. 보통 (100 KB ~ 5 MB)"
    if size_b < 100 * 1024 * 1024:
        return "4. 큼 (5 MB ~ 100 MB)"
    return "5. 아주 큼 (> 100 MB)"


def get_unique_target_path(dest_dir: Path, name: str) -> Path:
    """동일한 이름이 있을 때 '파일명 (1).ext' 형태로 고유 경로를 생성합니다."""
    candidate = dest_dir / name
    if not candidate.exists():
        return candidate
    stem = Path(name).stem
    suffix = Path(name).suffix
    counter = 1
    while True:
        new_name = f"{stem} ({counter}){suffix}"
        candidate = dest_dir / new_name
        if not candidate.exists():
            return candidate
        counter += 1


def match_color_hex(
    color_rules: Dict[str, Dict[str, object]],
    dark_mode: bool,
    color_filter_enabled: bool,
    is_dir: bool,
    ext: str,
) -> Optional[str]:
    """파일 확장자 또는 폴더 여부에 따라 적용할 HEX 색상 코드를 반환합니다."""
    if not color_filter_enabled:
        return None
    color_key = "color_dark" if dark_mode else "color_light"
    if is_dir:
        dir_rule = color_rules.get("폴더 (Directory)")
        if dir_rule and dir_rule.get("enabled", True):
            return str(dir_rule.get(color_key, "#FBBF24"))
        return None
    if not ext:
        return None
    ext_lower = ext.lower()
    for cat_name, rule in color_rules.items():
        if cat_name.startswith("폴더") or not rule.get("enabled", True):
            continue
        exts = rule.get("extensions", [])
        if isinstance(exts, list) and ext_lower in exts:
            return str(rule.get(color_key, "#38BDF8"))
    return None


def get_initial_4_paths() -> List[str]:
    home = Path.home()
    drives = get_mounted_drives()
    first_drive = str(drives[0]["root"]) if drives else str(home)
    return [
        first_drive,
        str(home / "Desktop") if (home / "Desktop").is_dir() else str(home),
        str(home / "Downloads") if (home / "Downloads").is_dir() else str(home),
        str(home / "Documents") if (home / "Documents").is_dir() else str(home),
    ]


def open_path_with_os(target_path: str) -> None:
    if platform.system() == "Windows":
        os.startfile(target_path)  # type: ignore[attr-defined]
    elif platform.system() == "Darwin":
        subprocess.Popen(["open", target_path])
    else:
        subprocess.Popen(["xdg-open", target_path])


# ---------------------------------------------------------------------------
# 엔진 선택 및 PyQt6 부트스트랩
# ---------------------------------------------------------------------------
def _detect_qt_binding() -> Optional[str]:
    """설치된 Qt 바인딩(PySide6 또는 PyQt6)을 감지하여 반환합니다."""
    if "--pyqt6" in sys.argv:
        order = ("PyQt6", "PySide6")
    else:
        order = ("PySide6", "PyQt6")
    for pkg in order:
        try:
            __import__(pkg)
            return pkg
        except ImportError:
            continue
    return None


def _check_or_install_pyqt6() -> bool:
    if "--tk" in sys.argv:
        return False
    if getattr(sys, "frozen", False):
        return _detect_qt_binding() is not None
    if _detect_qt_binding() is not None:
        return True

    msg = (
        "고해상도 썸네일 및 탐색기 기능을 지원하는 Qt 엔진(PySide6 / PyQt6)이 아직 설치되어 있지 않습니다.\n\n"
        "• [예(Y)] 클릭: Qt 엔진을 자동 설치(pip install PySide6) 후 실행\n"
        "• [아니오(N)] 클릭: 별도 설치 없이 내장 Tkinter 엔진으로 즉시 실행"
    )
    install = False
    if platform.system() == "Windows":
        try:
            res = ctypes.windll.user32.MessageBoxW(0, msg, "PyQuadDir 실행 엔진 선택", 0x24)
            install = (res == 6)
        except Exception:
            install = False
    else:
        if sys.stdin and sys.stdin.isatty():
            print(msg)
            ans = input("Qt 엔진(PySide6) 자동 설치 진행 [Y/n]: ").strip().lower()
            install = ans in ("", "y", "yes")

    if install:
        for candidate_pkg in ("PySide6", "PyQt6"):
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", candidate_pkg])
                if _detect_qt_binding() is not None:
                    return True
            except Exception:
                continue
        print("Qt 엔진 설치 실패 -> 내장 Tkinter 엔진으로 구동합니다.")
        return False
    return False


# ===========================================================================
# 1. Qt (PySide6 / PyQt6) 기반 메인 PyQuadDir 엔진
# ===========================================================================
def run_pyqt6_app() -> None:
    binding = _detect_qt_binding()
    if binding == "PySide6":
        from PySide6.QtCore import (  # type: ignore[import-not-found]
            QFileInfo,
            QItemSelection,
            QItemSelectionModel,
            QMimeData,
            QPoint,
            QPointF,
            QRectF,
            QSize,
            Qt,
            QUrl,
            Signal as pyqtSignal,
        )
        from PySide6.QtGui import (  # type: ignore[import-not-found]
            QAction,
            QActionGroup,
            QColor,
            QDrag,
            QFont,
            QIcon,
            QImageReader,
            QKeySequence,
            QPainter,
            QPainterPath,
            QPen,
            QPixmap,
            QPolygonF,
            QShortcut,
        )
        from PySide6.QtWidgets import (  # type: ignore[import-not-found]
            QAbstractItemView,
            QApplication,
            QCheckBox,
            QColorDialog,
            QDialog,
            QDialogButtonBox,
            QFileIconProvider,
            QFormLayout,
            QFrame,
            QHBoxLayout,
            QHeaderView,
            QInputDialog,
            QLabel,
            QLineEdit,
            QListView,
            QListWidget,
            QListWidgetItem,
            QMainWindow,
            QMenu,
            QMessageBox,
            QPlainTextEdit,
            QPushButton,
            QSplitter,
            QStackedWidget,
            QStatusBar,
            QTableWidget,
            QTableWidgetItem,
            QTabWidget,
            QToolBar,
            QToolButton,
            QVBoxLayout,
            QWidget,
        )
    else:
        from PyQt6.QtCore import (
            QFileInfo,
            QItemSelection,
            QItemSelectionModel,
            QMimeData,
            QPoint,
            QPointF,
            QRectF,
            QSize,
            Qt,
            QUrl,
            pyqtSignal,
        )
        from PyQt6.QtGui import (
            QAction,
            QActionGroup,
            QColor,
            QDrag,
            QFont,
            QIcon,
            QImageReader,
            QKeySequence,
            QPainter,
            QPainterPath,
            QPen,
            QPixmap,
            QPolygonF,
            QShortcut,
        )
        from PyQt6.QtWidgets import (
            QAbstractItemView,
            QApplication,
            QCheckBox,
            QColorDialog,
            QDialog,
            QDialogButtonBox,
            QFileIconProvider,
            QFormLayout,
            QFrame,
            QHBoxLayout,
            QHeaderView,
            QInputDialog,
            QLabel,
            QLineEdit,
            QListView,
            QListWidget,
            QListWidgetItem,
            QMainWindow,
            QMenu,
            QMessageBox,
            QPlainTextEdit,
            QPushButton,
            QSplitter,
            QStackedWidget,
            QStatusBar,
            QTableWidget,
            QTableWidgetItem,
            QTabWidget,
            QToolBar,
            QToolButton,
            QVBoxLayout,
            QWidget,
        )

    # -----------------------------------------------------------------------
    # 고시인성 벡터 UI 아이콘 생성기 (작아서 안 보이던 유니코드 기호를 선명한 그래픽으로 대체)
    # -----------------------------------------------------------------------
    def create_ui_icon(kind: str, dark_mode: bool = True, size: int = 20) -> QIcon:
        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        fg_main = QColor("#E2E8F0" if dark_mode else "#334155")
        accent_blue = QColor("#38BDF8" if dark_mode else "#2563EB")
        accent_green = QColor("#34D399" if dark_mode else "#059669")
        accent_amber = QColor("#FBBF24" if dark_mode else "#D97706")
        accent_purple = QColor("#C084FC" if dark_mode else "#7C3AED")
        accent_red = QColor("#F87171" if dark_mode else "#DC2626")

        if kind == "new":
            # Windows 11 스타일: 파란 원 + 선명한 십자(+)
            pen = QPen(accent_blue, 1.8)
            p.setPen(pen)
            p.setBrush(QColor(37, 99, 235, 45))
            p.drawEllipse(QRectF(2.0, 2.0, size - 4.0, size - 4.0))
            pen_plus = QPen(accent_blue, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            p.setPen(pen_plus)
            mid = size / 2.0
            p.drawLine(QPointF(mid, 5.5), QPointF(mid, size - 5.5))
            p.drawLine(QPointF(5.5, mid), QPointF(size - 5.5, mid))

        elif kind == "sort":
            # 상하 교차 화살표 (좌측 파란 상향 화살표, 우측 슬레이트 하향 화살표)
            pen_up = QPen(accent_blue, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen_up)
            p.drawLine(QPointF(6.0, 16.0), QPointF(6.0, 4.0))
            p.drawLine(QPointF(3.0, 7.5), QPointF(6.0, 4.0))
            p.drawLine(QPointF(9.0, 7.5), QPointF(6.0, 4.0))

            pen_dn = QPen(fg_main, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen_dn)
            p.drawLine(QPointF(14.0, 4.0), QPointF(14.0, 16.0))
            p.drawLine(QPointF(11.0, 12.5), QPointF(14.0, 16.0))
            p.drawLine(QPointF(17.0, 12.5), QPointF(14.0, 16.0))

        elif kind == "view":
            # 2x2 그리드 카드 아이콘
            pen = QPen(accent_blue, 1.8)
            p.setPen(pen)
            p.setBrush(QColor(56, 189, 248, 55))
            p.drawRoundedRect(QRectF(2.5, 2.5, 6.5, 6.5), 1.5, 1.5)
            p.drawRoundedRect(QRectF(11.0, 2.5, 6.5, 6.5), 1.5, 1.5)
            p.setPen(QPen(fg_main, 1.8))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(QRectF(2.5, 11.0, 6.5, 6.5), 1.5, 1.5)
            p.drawRoundedRect(QRectF(11.0, 11.0, 6.5, 6.5), 1.5, 1.5)

        elif kind == "preview":
            # Windows 11 미리보기 창 아이콘 (좌측 흰/투명, 우측 파란 강조 분할 사각형)
            p.setPen(QPen(fg_main, 1.8))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(QRectF(2.0, 3.5, 16.0, 13.0), 2.5, 2.5)
            p.setPen(QPen(accent_blue, 2.0))
            p.setBrush(QColor(37, 99, 235, 95))
            p.drawRoundedRect(QRectF(10.5, 3.5, 7.5, 13.0), 2.0, 2.0)

        elif kind == "details":
            # Windows 11 세부정보 창 아이콘 (우측에 파란 줄무늬 표시)
            p.setPen(QPen(fg_main, 1.8))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(QRectF(2.0, 3.5, 16.0, 13.0), 2.5, 2.5)
            p.setPen(QPen(accent_blue, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(QPointF(10.0, 4.0), QPointF(10.0, 16.0))
            for y_pos in (7.0, 10.0, 13.0):
                p.drawLine(QPointF(12.2, y_pos), QPointF(15.8, y_pos))

        elif kind == "layout":
            # PyQuadDir 4분할 컬러 블록 아이콘
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(accent_blue)
            p.drawRoundedRect(QRectF(2.0, 2.0, 7.2, 7.2), 1.8, 1.8)
            p.setBrush(accent_green)
            p.drawRoundedRect(QRectF(10.8, 2.0, 7.2, 7.2), 1.8, 1.8)
            p.setBrush(accent_amber)
            p.drawRoundedRect(QRectF(2.0, 10.8, 7.2, 7.2), 1.8, 1.8)
            p.setBrush(accent_purple)
            p.drawRoundedRect(QRectF(10.8, 10.8, 7.2, 7.2), 1.8, 1.8)

        elif kind == "back":
            pen = QPen(fg_main, 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            p.drawLine(QPointF(15.5, 10.0), QPointF(4.5, 10.0))
            p.drawLine(QPointF(9.5, 5.0), QPointF(4.5, 10.0))
            p.drawLine(QPointF(9.5, 15.0), QPointF(4.5, 10.0))

        elif kind == "forward":
            pen = QPen(fg_main, 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            p.drawLine(QPointF(4.5, 10.0), QPointF(15.5, 10.0))
            p.drawLine(QPointF(10.5, 5.0), QPointF(15.5, 10.0))
            p.drawLine(QPointF(10.5, 15.0), QPointF(15.5, 10.0))

        elif kind == "up":
            pen = QPen(accent_blue, 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            p.drawLine(QPointF(10.0, 15.5), QPointF(10.0, 4.5))
            p.drawLine(QPointF(5.0, 9.5), QPointF(10.0, 4.5))
            p.drawLine(QPointF(15.0, 9.5), QPointF(10.0, 4.5))

        elif kind == "refresh":
            pen = QPen(accent_green, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            p.drawArc(QRectF(3.5, 3.5, 13.0, 13.0), 45 * 16, 270 * 16)
            p.drawLine(QPointF(14.5, 3.0), QPointF(16.5, 6.8))
            p.drawLine(QPointF(12.2, 6.8), QPointF(16.5, 6.8))

        elif kind == "delete":
            pen = QPen(accent_red, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.drawLine(QPointF(4.0, 5.5), QPointF(16.0, 5.5))
            p.drawLine(QPointF(8.0, 3.5), QPointF(12.0, 3.5))
            p.drawRoundedRect(QRectF(5.5, 5.5, 9.0, 11.5), 1.5, 1.5)
            p.drawLine(QPointF(8.5, 8.5), QPointF(8.5, 14.0))
            p.drawLine(QPointF(11.5, 8.5), QPointF(11.5, 14.0))

        p.end()
        return QIcon(pix)

    # 썸네일 아이콘 인메모리 캐시: (path, mtime_ns, size) -> QIcon
    THUMBNAIL_CACHE: Dict[Tuple[str, int, int], QIcon] = {}

    def get_entry_icon_or_thumbnail(
        icon_provider: QFileIconProvider,
        path_str: str,
        is_dir: bool,
        ext: str,
        mtime: float,
        icon_px: int,
        show_icons: bool = True,
    ) -> QIcon:
        if not show_icons:
            return QIcon()
        if not is_dir and ext in IMAGE_EXTENSIONS and icon_px >= 20:
            key = (path_str, int(mtime * 1000), icon_px)
            cached = THUMBNAIL_CACHE.get(key)
            if cached is not None:
                return cached
            try:
                reader = QImageReader(path_str)
                reader.setAutoTransform(True)
                orig_size = reader.size()
                if orig_size.isValid() and (orig_size.width() > icon_px or orig_size.height() > icon_px):
                    scaled_size = orig_size.scaled(
                        QSize(icon_px, icon_px), Qt.AspectRatioMode.KeepAspectRatio
                    )
                    reader.setScaledSize(scaled_size)
                img = reader.read()
                if not img.isNull():
                    canvas = QPixmap(icon_px, icon_px)
                    canvas.fill(Qt.GlobalColor.transparent)
                    pix = QPixmap.fromImage(img).scaled(
                        icon_px,
                        icon_px,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    painter = QPainter(canvas)
                    x_off = (icon_px - pix.width()) // 2
                    y_off = (icon_px - pix.height()) // 2
                    painter.drawPixmap(x_off, y_off, pix)
                    painter.end()
                    ic = QIcon(canvas)
                    if len(THUMBNAIL_CACHE) > 1500:
                        THUMBNAIL_CACHE.clear()
                    THUMBNAIL_CACHE[key] = ic
                    return ic
            except Exception:
                pass
        return icon_provider.icon(QFileInfo(path_str))

    class SortableTableWidgetItem(QTableWidgetItem):
        def __init__(
            self,
            text: str,
            sort_key: object,
            is_dir: bool = False,
            is_parent: bool = False,
        ):
            super().__init__(text)
            self.sort_key = sort_key
            self.is_dir = is_dir
            self.is_parent = is_parent

        def __lt__(self, other: "QTableWidgetItem") -> bool:
            if isinstance(other, SortableTableWidgetItem):
                header = self.tableWidget().horizontalHeader() if self.tableWidget() else None
                order = header.sortIndicatorOrder() if header else Qt.SortOrder.AscendingOrder
                if self.is_parent != other.is_parent:
                    return self.is_parent if order == Qt.SortOrder.AscendingOrder else not self.is_parent
                if self.is_dir != other.is_dir:
                    return self.is_dir if order == Qt.SortOrder.AscendingOrder else not self.is_dir
                try:
                    return self.sort_key < other.sort_key  # type: ignore[operator]
                except TypeError:
                    return str(self.sort_key) < str(other.sort_key)
            return super().__lt__(other)

    def perform_file_transfer_qt(
        parent_widget: QWidget,
        src_paths: List[str],
        dest_dir_str: str,
        mode: str = "copy",
    ) -> Tuple[int, List[str]]:
        dest_dir = Path(dest_dir_str)
        if not dest_dir.exists() or not dest_dir.is_dir():
            return 0, [f"대상 폴더가 존재하지 않습니다: {dest_dir_str}"]

        success_count = 0
        errors: List[str] = []
        apply_all_choice: Optional[str] = None

        for src_str in src_paths:
            src = Path(src_str)
            if not src.exists():
                continue

            try:
                if src.is_dir() and dest_dir.resolve().is_relative_to(src.resolve()):
                    errors.append(
                        f"폴더를 자기 자신의 하위 폴더로 {('이동' if mode == 'move' else '복사')}할 수 없습니다: {src.name}"
                    )
                    continue
            except Exception:
                pass

            target = dest_dir / src.name

            if src.resolve() == target.resolve():
                if mode == "move":
                    continue
                target = get_unique_target_path(dest_dir, f"{src.stem} - 복사본{src.suffix}")

            elif target.exists():
                choice = apply_all_choice
                if choice is None:
                    msg_box = QMessageBox(parent_widget)
                    msg_box.setWindowTitle("파일/폴더 이름 충돌")
                    msg_box.setText(
                        f"대상 폴더에 이미 '{src.name}' 항목이 존재합니다.\n어떻게 처리할까요?"
                    )
                    btn_rename = msg_box.addButton("자동 번호 붙이기 (권장)", QMessageBox.ButtonRole.AcceptRole)
                    btn_overwrite = msg_box.addButton("덮어쓰기", QMessageBox.ButtonRole.DestructiveRole)
                    btn_skip = msg_box.addButton("건너뛰기", QMessageBox.ButtonRole.RejectRole)
                    chk_all = QCheckBox("다음 충돌 항목에도 모두 동일하게 적용")
                    msg_box.setCheckBox(chk_all)
                    msg_box.exec()

                    clicked = msg_box.clickedButton()
                    if clicked == btn_rename:
                        choice = "rename"
                    elif clicked == btn_overwrite:
                        choice = "overwrite"
                    else:
                        choice = "skip"

                    if chk_all.isChecked():
                        apply_all_choice = choice

                if choice == "skip":
                    continue
                elif choice == "rename":
                    target = get_unique_target_path(dest_dir, src.name)
                elif choice == "overwrite":
                    try:
                        if target.is_dir() and not target.is_symlink():
                            shutil.rmtree(target)
                        else:
                            target.unlink()
                    except Exception as exc:
                        errors.append(f"{target.name} 덮어쓰기 실패: {exc}")
                        continue

            try:
                if mode == "move":
                    shutil.move(str(src), str(target))
                else:
                    if src.is_dir():
                        shutil.copytree(str(src), str(target))
                    else:
                        shutil.copy2(str(src), str(target))
                success_count += 1
            except Exception as exc:
                action_kr = "이동" if mode == "move" else "복사"
                errors.append(f"'{src.name}' {action_kr} 실패: {exc}")

        return success_count, errors

    # -----------------------------------------------------------------------
    # 1-A. 자세히(Details) 및 내용(Content) 보기용 테이블 뷰
    # -----------------------------------------------------------------------
    class FileTableView(QTableWidget):
        filesDropped = pyqtSignal(list, str, Qt.KeyboardModifier)
        middleClickedFolder = pyqtSignal(str)
        paneFocused = pyqtSignal()

        def __init__(self, tab_widget: "DirectoryTab", parent: Optional[QWidget] = None):
            super().__init__(parent)
            self.dir_tab = tab_widget

            self.setColumnCount(4)
            self.setHorizontalHeaderLabels(["이름", "크기", "유형", "수정한 날짜"])
            self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
            self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            self.setAlternatingRowColors(True)
            self.setShowGrid(False)
            self.verticalHeader().setVisible(False)
            self.verticalHeader().setDefaultSectionSize(28)
            self.setIconSize(QSize(24, 24))

            header = self.horizontalHeader()
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
            self.setColumnWidth(1, 95)
            self.setColumnWidth(2, 100)
            self.setColumnWidth(3, 140)
            header.setSortIndicatorShown(True)

            self.setDragEnabled(True)
            self.setAcceptDrops(True)
            self.viewport().setAcceptDrops(True)
            self.setDropIndicatorShown(True)
            self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)

        def selectAll(self) -> None:
            """Ctrl+A 전체 선택 시 '📁 .. (상위 폴더)'나 분류 헤더 행은 절대 선택되지 않도록 제외합니다."""
            self.clearSelection()
            sel_model = self.selectionModel()
            if sel_model is None:
                return
            selection = QItemSelection()
            max_col = self.columnCount() - 1
            for row in range(self.rowCount()):
                if self.isRowHidden(row):
                    continue
                first_item = self.item(row, 0)
                if first_item is None:
                    continue
                is_parent_or_header = bool(first_item.data(Qt.ItemDataRole.UserRole + 1))
                if is_parent_or_header:
                    continue
                left_idx = self.model().index(row, 0)
                right_idx = self.model().index(row, max_col)
                selection.select(left_idx, right_idx)
            sel_model.select(selection, QItemSelectionModel.SelectionFlag.Select)

        def focusInEvent(self, event) -> None:
            super().focusInEvent(event)
            self.paneFocused.emit()

        def keyPressEvent(self, event) -> None:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.paneFocused.emit()
                self.dir_tab.activate_selected_or_current()
                event.accept()
                return
            if event.key() == Qt.Key.Key_Backspace:
                self.paneFocused.emit()
                self.dir_tab.go_up()
                event.accept()
                return
            super().keyPressEvent(event)

        def wheelEvent(self, event) -> None:
            """Ctrl + 마우스 휠 스크롤 시 보기 모드 및 썸네일 크기를 전환합니다."""
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                self.paneFocused.emit()
                delta = event.angleDelta().y()
                if delta == 0:
                    delta = event.angleDelta().x()
                if delta > 0:
                    self.dir_tab.step_view_mode_zoom(1)
                elif delta < 0:
                    self.dir_tab.step_view_mode_zoom(-1)
                event.accept()
                return
            super().wheelEvent(event)

        def mousePressEvent(self, event) -> None:
            self.paneFocused.emit()
            if event.button() == Qt.MouseButton.MiddleButton:
                idx = self.indexAt(event.pos())
                if idx.isValid():
                    item = self.item(idx.row(), 0)
                    if item is not None:
                        full_path = item.data(Qt.ItemDataRole.UserRole)
                        if full_path and os.path.isdir(full_path):
                            self.middleClickedFolder.emit(full_path)
                            return
            super().mousePressEvent(event)

        def selected_file_paths(self) -> List[str]:
            paths: List[str] = []
            seen_rows = set()
            for item in self.selectedItems():
                row = item.row()
                if row in seen_rows:
                    continue
                seen_rows.add(row)
                name_item = self.item(row, 0)
                if name_item is not None:
                    is_parent = name_item.data(Qt.ItemDataRole.UserRole + 1)
                    path = name_item.data(Qt.ItemDataRole.UserRole)
                    if path and not is_parent:
                        paths.append(str(path))
            return paths

        def startDrag(self, supportedActions) -> None:
            paths = self.selected_file_paths()
            if not paths:
                return
            mime = QMimeData()
            urls = [QUrl.fromLocalFile(p) for p in paths]
            mime.setUrls(urls)

            drag = QDrag(self)
            drag.setMimeData(mime)
            drag.exec(Qt.DropAction.CopyAction | Qt.DropAction.MoveAction)

        def dragEnterEvent(self, event) -> None:
            if event.mimeData().hasUrls():
                event.acceptProposedAction()
            else:
                super().dragEnterEvent(event)

        def dragMoveEvent(self, event) -> None:
            if event.mimeData().hasUrls():
                event.acceptProposedAction()
            else:
                super().dragMoveEvent(event)

        def dropEvent(self, event) -> None:
            if not event.mimeData().hasUrls():
                return
            src_paths: List[str] = []
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    local_p = url.toLocalFile()
                    if os.path.exists(local_p):
                        src_paths.append(os.path.normpath(local_p))
            if not src_paths:
                return

            target_dir = self.dir_tab.current_path
            pos = event.position().toPoint()
            idx = self.indexAt(pos)
            if idx.isValid():
                row_item = self.item(idx.row(), 0)
                if row_item is not None:
                    candidate_path = row_item.data(Qt.ItemDataRole.UserRole)
                    if candidate_path and os.path.isdir(candidate_path):
                        target_dir = str(candidate_path)

            modifiers = event.modifiers()
            event.acceptProposedAction()
            self.filesDropped.emit(src_paths, target_dir, modifiers)

    # -----------------------------------------------------------------------
    # 1-B. 썸네일/아이콘/목록/타일 보기용 리스트 뷰
    # -----------------------------------------------------------------------
    class FileIconListView(QListWidget):
        filesDropped = pyqtSignal(list, str, Qt.KeyboardModifier)
        middleClickedFolder = pyqtSignal(str)
        paneFocused = pyqtSignal()

        def __init__(self, tab_widget: "DirectoryTab", parent: Optional[QWidget] = None):
            super().__init__(parent)
            self.dir_tab = tab_widget
            self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
            self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            self.setResizeMode(QListView.ResizeMode.Adjust)
            self.setWrapping(True)
            self.setWordWrap(True)
            self.setUniformItemSizes(False)

            self.setDragEnabled(True)
            self.setAcceptDrops(True)
            self.viewport().setAcceptDrops(True)
            self.setDropIndicatorShown(True)
            self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)

        def selectAll(self) -> None:
            """Ctrl+A 전체 선택 시 '📁 .. (상위 폴더)' 항목은 제외하고 선택합니다."""
            self.clearSelection()
            for i in range(self.count()):
                item = self.item(i)
                if item is None or item.isHidden():
                    continue
                if bool(item.data(Qt.ItemDataRole.UserRole + 1)):
                    continue
                item.setSelected(True)

        def focusInEvent(self, event) -> None:
            super().focusInEvent(event)
            self.paneFocused.emit()

        def keyPressEvent(self, event) -> None:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.paneFocused.emit()
                self.dir_tab.activate_selected_or_current()
                event.accept()
                return
            if event.key() == Qt.Key.Key_Backspace:
                self.paneFocused.emit()
                self.dir_tab.go_up()
                event.accept()
                return
            super().keyPressEvent(event)

        def wheelEvent(self, event) -> None:
            """Ctrl + 마우스 휠 스크롤 시 보기 모드 및 썸네일 크기를 전환합니다."""
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                self.paneFocused.emit()
                delta = event.angleDelta().y()
                if delta == 0:
                    delta = event.angleDelta().x()
                if delta > 0:
                    self.dir_tab.step_view_mode_zoom(1)
                elif delta < 0:
                    self.dir_tab.step_view_mode_zoom(-1)
                event.accept()
                return
            super().wheelEvent(event)

        def mousePressEvent(self, event) -> None:
            self.paneFocused.emit()
            if event.button() == Qt.MouseButton.MiddleButton:
                item = self.itemAt(event.pos())
                if item is not None:
                    full_path = item.data(Qt.ItemDataRole.UserRole)
                    if full_path and os.path.isdir(full_path):
                        self.middleClickedFolder.emit(full_path)
                        return
            super().mousePressEvent(event)

        def selected_file_paths(self) -> List[str]:
            paths: List[str] = []
            for item in self.selectedItems():
                is_parent = item.data(Qt.ItemDataRole.UserRole + 1)
                p = item.data(Qt.ItemDataRole.UserRole)
                if p and not is_parent:
                    paths.append(str(p))
            return paths

        def startDrag(self, supportedActions) -> None:
            paths = self.selected_file_paths()
            if not paths:
                return
            mime = QMimeData()
            urls = [QUrl.fromLocalFile(p) for p in paths]
            mime.setUrls(urls)

            drag = QDrag(self)
            drag.setMimeData(mime)
            drag.exec(Qt.DropAction.CopyAction | Qt.DropAction.MoveAction)

        def dragEnterEvent(self, event) -> None:
            if event.mimeData().hasUrls():
                event.acceptProposedAction()
            else:
                super().dragEnterEvent(event)

        def dragMoveEvent(self, event) -> None:
            if event.mimeData().hasUrls():
                event.acceptProposedAction()
            else:
                super().dragMoveEvent(event)

        def dropEvent(self, event) -> None:
            if not event.mimeData().hasUrls():
                return
            src_paths: List[str] = []
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    local_p = url.toLocalFile()
                    if os.path.exists(local_p):
                        src_paths.append(os.path.normpath(local_p))
            if not src_paths:
                return

            target_dir = self.dir_tab.current_path
            pos = event.position().toPoint()
            item = self.itemAt(pos)
            if item is not None:
                candidate_path = item.data(Qt.ItemDataRole.UserRole)
                if candidate_path and os.path.isdir(candidate_path):
                    target_dir = str(candidate_path)

            modifiers = event.modifiers()
            event.acceptProposedAction()
            self.filesDropped.emit(src_paths, target_dir, modifiers)

    # -----------------------------------------------------------------------
    # 2. 개별 탭 위젯 (테이블 뷰 + 아이콘/썸네일 뷰 + Ctrl+휠 줌 전환)
    # -----------------------------------------------------------------------
    class DirectoryTab(QWidget):
        pathChanged = pyqtSignal(str)
        statusUpdated = pyqtSignal(str)
        selectionChangedSignal = pyqtSignal(str)
        openInNewTabRequested = pyqtSignal(str)
        paneActivated = pyqtSignal()

        def __init__(
            self,
            initial_path: str,
            main_window: "QDirMainWindow",
            pane: "ExplorerPane",
            parent: Optional[QWidget] = None,
        ):
            super().__init__(parent)
            self.main_window = main_window
            self.pane = pane
            self.icon_provider = QFileIconProvider()

            self.history: List[str] = []
            self.history_index: int = -1
            self.current_path: str = ""

            self.view_mode: str = self.main_window.default_view_mode
            self.extra_zoom_px: int = 148  # 아주 큰 아이콘 상태에서 추가 휠 확대 지원 (148 ~ 220px)
            self.sort_by: str = "name"
            self.sort_asc: bool = True
            self.group_by: str = "none"

            self._build_ui()
            self.refresh_nav_icons()
            self.navigate_to(initial_path, record_history=True)

        def _build_ui(self) -> None:
            layout = QVBoxLayout(self)
            layout.setContentsMargins(4, 4, 4, 4)
            layout.setSpacing(4)

            nav_layout = QHBoxLayout()
            nav_layout.setContentsMargins(0, 0, 0, 0)
            nav_layout.setSpacing(3)

            self.btn_back = QToolButton()
            self.btn_back.setToolTip("뒤로 가기 (Alt+Left)")
            self.btn_back.clicked.connect(self.go_back)

            self.btn_forward = QToolButton()
            self.btn_forward.setToolTip("앞으로 가기 (Alt+Right)")
            self.btn_forward.clicked.connect(self.go_forward)

            self.btn_up = QToolButton()
            self.btn_up.setToolTip("상위 폴더로 이동 (Backspace / Alt+Up)")
            self.btn_up.clicked.connect(self.go_up)

            self.btn_refresh = QToolButton()
            self.btn_refresh.setToolTip("새로고침 (F5)")
            self.btn_refresh.clicked.connect(self.refresh)

            self.address_edit = QLineEdit()
            self.address_edit.setPlaceholderText("경로 입력 후 Enter (예: C:\\Users)")
            self.address_edit.returnPressed.connect(self._on_address_entered)

            self.btn_star = QToolButton()
            self.btn_star.setText("⭐")
            self.btn_star.setToolTip("현재 폴더를 즐겨찾기 바에 추가")
            self.btn_star.clicked.connect(self._add_current_to_favorites)

            self.filter_edit = QLineEdit()
            self.filter_edit.setPlaceholderText("🔍 이름/확장자 필터...")
            self.filter_edit.setFixedWidth(135)
            self.filter_edit.setClearButtonEnabled(True)
            self.filter_edit.textChanged.connect(self.apply_filter)

            for w in (self.btn_back, self.btn_forward, self.btn_up, self.btn_refresh):
                w.setFixedSize(28, 28)
                w.setIconSize(QSize(18, 18))
                nav_layout.addWidget(w)

            self.btn_star.setFixedSize(28, 28)
            nav_layout.addWidget(self.address_edit, stretch=1)
            nav_layout.addWidget(self.btn_star)
            nav_layout.addWidget(self.filter_edit)
            layout.addLayout(nav_layout)

            self.stack = QStackedWidget()

            self.table = FileTableView(self)
            self.table.doubleClicked.connect(self._on_table_double_clicked)
            self.table.itemSelectionChanged.connect(self._on_selection_changed)
            self.table.filesDropped.connect(self._on_files_dropped)
            self.table.middleClickedFolder.connect(self.openInNewTabRequested.emit)
            self.table.paneFocused.connect(self.paneActivated.emit)
            self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self.table.customContextMenuRequested.connect(self._show_context_menu)

            self.icon_list = FileIconListView(self)
            self.icon_list.itemDoubleClicked.connect(self._on_icon_double_clicked)
            self.icon_list.itemSelectionChanged.connect(self._on_selection_changed)
            self.icon_list.filesDropped.connect(self._on_files_dropped)
            self.icon_list.middleClickedFolder.connect(self.openInNewTabRequested.emit)
            self.icon_list.paneFocused.connect(self.paneActivated.emit)
            self.icon_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self.icon_list.customContextMenuRequested.connect(self._show_context_menu)

            self.stack.addWidget(self.table)
            self.stack.addWidget(self.icon_list)
            layout.addWidget(self.stack, stretch=1)

            self.summary_label = QLabel("")
            self.summary_label.setObjectName("PaneSummaryLabel")
            layout.addWidget(self.summary_label)

        def refresh_nav_icons(self) -> None:
            dm = self.main_window.dark_mode
            self.btn_back.setIcon(create_ui_icon("back", dm, 18))
            self.btn_forward.setIcon(create_ui_icon("forward", dm, 18))
            self.btn_up.setIcon(create_ui_icon("up", dm, 18))
            self.btn_refresh.setIcon(create_ui_icon("refresh", dm, 18))

        def selected_file_paths(self) -> List[str]:
            if self.stack.currentWidget() == self.icon_list:
                return self.icon_list.selected_file_paths()
            return self.table.selected_file_paths()

        def set_view_mode(self, mode: str) -> None:
            self.view_mode = mode
            if mode == "extra_large_icons" and self.extra_zoom_px < 148:
                self.extra_zoom_px = 148
            self.refresh()
            # 전환 후에도 현재 활성 뷰 위젯에 포커스를 유지해 연속 Ctrl+휠 및 키보드 조작 보장
            self.stack.currentWidget().setFocus()

        def step_view_mode_zoom(self, step: int) -> None:
            """
            Ctrl + 마우스 휠 스크롤로 보기 모드를 단계별로 확대(step > 0)하거나 축소(step < 0)합니다.
            순서: 자세히 <-> 목록 <-> 내용 <-> 타일 <-> 작은 아이콘 <-> 보통 아이콘 <-> 큰 아이콘 <-> 아주 큰 아이콘(148~220px)
            """
            curr_idx = (
                ZOOM_WHEEL_ORDER.index(self.view_mode)
                if self.view_mode in ZOOM_WHEEL_ORDER
                else 0
            )

            # 이미 '아주 큰 아이콘'인 상태에서 휠을 더 올리면 220px까지 썸네일을 한층 더 크게 확대
            if self.view_mode == "extra_large_icons" and step > 0:
                if self.extra_zoom_px < 220:
                    self.extra_zoom_px = min(220, self.extra_zoom_px + 24)
                    self.refresh()
                    self.main_window.statusBar().showMessage(
                        f"🔍 [Ctrl+마우스 휠] 보기 확대: 아주 큰 아이콘 ({self.extra_zoom_px}px)", 2500
                    )
                return

            if self.view_mode == "extra_large_icons" and step < 0 and self.extra_zoom_px > 148:
                self.extra_zoom_px = max(148, self.extra_zoom_px - 24)
                self.refresh()
                self.main_window.statusBar().showMessage(
                    f"🔍 [Ctrl+마우스 휠] 보기 축소: 아주 큰 아이콘 ({self.extra_zoom_px}px)", 2500
                )
                return

            new_idx = max(0, min(len(ZOOM_WHEEL_ORDER) - 1, curr_idx + (1 if step > 0 else -1)))
            if new_idx != curr_idx:
                new_mode = ZOOM_WHEEL_ORDER[new_idx]
                self.extra_zoom_px = 148
                self.set_view_mode(new_mode)
                mode_kr = VIEW_MODE_LABELS.get(new_mode, new_mode)
                self.main_window.statusBar().showMessage(
                    f"🔍 [Ctrl+마우스 휠] 보기 모드 전환: {mode_kr}", 2500
                )

        def set_sort(self, sort_by: Optional[str] = None, ascending: Optional[bool] = None) -> None:
            if sort_by is not None:
                self.sort_by = sort_by
            if ascending is not None:
                self.sort_asc = ascending
            self.refresh()

        def set_group_by(self, group_by: str) -> None:
            self.group_by = group_by
            self.refresh()

        def navigate_to(self, path_str: str, record_history: bool = True) -> bool:
            expanded = os.path.expandvars(os.path.expanduser(path_str.strip()))
            target = Path(expanded)
            if not target.exists() or not target.is_dir():
                QMessageBox.warning(self, "경로 오류", f"폴더를 찾을 수 없거나 접근할 수 없습니다:\n{path_str}")
                self.address_edit.setText(self.current_path)
                return False

            norm_path = str(target.resolve())
            self.current_path = norm_path
            self.address_edit.setText(norm_path)

            if record_history:
                if self.history_index < len(self.history) - 1:
                    self.history = self.history[: self.history_index + 1]
                if not self.history or self.history[-1] != norm_path:
                    self.history.append(norm_path)
                    self.history_index = len(self.history) - 1

            self.btn_back.setEnabled(self.history_index > 0)
            self.btn_forward.setEnabled(self.history_index < len(self.history) - 1)

            self.refresh()
            self.pathChanged.emit(norm_path)
            return True

        def _on_address_entered(self) -> None:
            self.paneActivated.emit()
            text = self.address_edit.text().strip()
            if text:
                if self.navigate_to(text, record_history=True):
                    self.stack.currentWidget().setFocus()

        def go_back(self) -> None:
            self.paneActivated.emit()
            if self.history_index > 0:
                self.history_index -= 1
                self.navigate_to(self.history[self.history_index], record_history=False)

        def go_forward(self) -> None:
            self.paneActivated.emit()
            if self.history_index < len(self.history) - 1:
                self.history_index += 1
                self.navigate_to(self.history[self.history_index], record_history=False)

        def go_up(self) -> None:
            self.paneActivated.emit()
            if not self.current_path:
                return
            parent = Path(self.current_path).parent
            if str(parent) != self.current_path:
                self.navigate_to(str(parent), record_history=True)

        def _collect_sorted_entries(self, p: Path) -> List[Dict[str, object]]:
            raw_entries: List[os.DirEntry] = []
            with os.scandir(p) as it:
                for entry in it:
                    if not self.main_window.show_hidden_files and entry.name.startswith("."):
                        continue
                    raw_entries.append(entry)

            records: List[Dict[str, object]] = []
            for entry in raw_entries:
                try:
                    is_dir = entry.is_dir(follow_symlinks=False)
                except Exception:
                    is_dir = False

                try:
                    stat = entry.stat(follow_symlinks=False)
                    size_b = 0 if is_dir else stat.st_size
                    mtime = stat.st_mtime
                    ctime = stat.st_ctime
                    date_str = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
                    day_group = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
                except Exception:
                    size_b = 0
                    mtime = 0.0
                    ctime = 0.0
                    date_str = "-"
                    day_group = "날짜 미상"

                ext = "" if is_dir else Path(entry.name).suffix.lower()
                if is_dir:
                    disp_name = entry.name
                    type_str = "폴더"
                    size_str = "<DIR>"
                else:
                    if self.main_window.show_file_extensions or not ext:
                        disp_name = entry.name
                    else:
                        disp_name = Path(entry.name).stem
                    type_str = f"{ext[1:].upper()} 파일" if ext else "파일"
                    size_str = format_size(size_b)

                records.append({
                    "name": entry.name,
                    "disp_name": disp_name,
                    "path": entry.path,
                    "is_dir": is_dir,
                    "ext": ext,
                    "size_b": size_b,
                    "size_str": size_str,
                    "type_str": type_str,
                    "mtime": mtime,
                    "ctime": ctime,
                    "date_str": date_str,
                    "day_group": day_group,
                })

            def _key_fn(r: Dict[str, object]) -> object:
                if self.sort_by == "modified":
                    return r["mtime"]
                if self.sort_by == "created":
                    return r["ctime"]
                if self.sort_by == "size":
                    return r["size_b"]
                if self.sort_by == "type":
                    return str(r["type_str"]).lower()
                if self.sort_by == "ext":
                    return str(r["ext"]).lower()
                return str(r["name"]).lower()

            dirs = [r for r in records if r["is_dir"]]
            files = [r for r in records if not r["is_dir"]]
            dirs.sort(key=_key_fn, reverse=not self.sort_asc)
            files.sort(key=_key_fn, reverse=not self.sort_asc)
            return dirs + files

        def refresh(self) -> None:
            if not self.current_path:
                return

            p = Path(self.current_path)
            try:
                records = self._collect_sorted_entries(p)
            except PermissionError:
                self.summary_label.setText("🔒 접근 권한이 없는 폴더입니다.")
                return
            except Exception as exc:
                self.summary_label.setText(f"⚠️ 읽기 오류: {exc}")
                return

            dir_count = sum(1 for r in records if r["is_dir"])
            file_count = sum(1 for r in records if not r["is_dir"])
            total_bytes = sum(int(r["size_b"]) for r in records if not r["is_dir"])  # type: ignore[arg-type]

            self._dir_count = dir_count
            self._file_count = file_count
            self._total_bytes = total_bytes

            has_parent = p.parent != p

            if self.view_mode in ("details", "content"):
                self.stack.setCurrentWidget(self.table)
                self._populate_table_view(p, records, has_parent)
            else:
                self.stack.setCurrentWidget(self.icon_list)
                self._populate_icon_view(p, records, has_parent)

            self.apply_filter(self.filter_edit.text())
            self.update_status_summary()

        def _populate_table_view(
            self, p: Path, records: List[Dict[str, object]], has_parent: bool
        ) -> None:
            self.table.setSortingEnabled(False)
            self.table.setRowCount(0)

            icon_px = 40 if self.view_mode == "content" else 24
            row_h = 46 if self.view_mode == "content" else 28
            self.table.setIconSize(QSize(icon_px, icon_px))
            self.table.verticalHeader().setDefaultSectionSize(row_h)

            grouped_rows: List[Tuple[str, Optional[Dict[str, object]]]] = []
            if self.group_by == "none":
                for r in records:
                    grouped_rows.append(("item", r))
            else:
                groups: Dict[str, List[Dict[str, object]]] = {}
                for r in records:
                    if self.group_by == "type":
                        g_key = "📁 폴더" if r["is_dir"] else str(r["type_str"])
                    elif self.group_by == "modified":
                        g_key = f"📅 {r['day_group']}"
                    elif self.group_by == "size":
                        g_key = classify_size_bucket(int(r["size_b"]), bool(r["is_dir"]))  # type: ignore[arg-type]
                    else:
                        g_key = "기타"
                    groups.setdefault(g_key, []).append(r)

                for g_title in sorted(groups.keys()):
                    grouped_rows.append((f"group:{g_title} ({len(groups[g_title])}개)", None))
                    for r in groups[g_title]:
                        grouped_rows.append(("item", r))

            total_rows = len(grouped_rows) + (1 if has_parent else 0)
            self.table.setRowCount(total_rows)

            row_idx = 0
            if has_parent:
                parent_str = str(p.parent)
                item_name = SortableTableWidgetItem("📁 .. (상위 폴더)", "", is_dir=True, is_parent=True)
                item_name.setData(Qt.ItemDataRole.UserRole, parent_str)
                item_name.setData(Qt.ItemDataRole.UserRole + 1, True)
                item_name.setFlags(Qt.ItemFlag.ItemIsEnabled)
                font = item_name.font()
                font.setBold(True)
                item_name.setFont(font)

                item_size = SortableTableWidgetItem("", -1, is_dir=True, is_parent=True)
                item_size.setFlags(Qt.ItemFlag.ItemIsEnabled)
                item_type = SortableTableWidgetItem("상위 폴더", "", is_dir=True, is_parent=True)
                item_type.setFlags(Qt.ItemFlag.ItemIsEnabled)
                item_date = SortableTableWidgetItem("", 0, is_dir=True, is_parent=True)
                item_date.setFlags(Qt.ItemFlag.ItemIsEnabled)

                self.table.setItem(0, 0, item_name)
                self.table.setItem(0, 1, item_size)
                self.table.setItem(0, 2, item_type)
                self.table.setItem(0, 3, item_date)
                row_idx = 1

            for kind, rec in grouped_rows:
                if kind.startswith("group:") and rec is None:
                    g_label = kind.split("group:", 1)[1]
                    hdr_item = SortableTableWidgetItem(f"▾ {g_label}", g_label, is_dir=True, is_parent=True)
                    hdr_item.setData(Qt.ItemDataRole.UserRole, "")
                    hdr_item.setData(Qt.ItemDataRole.UserRole + 1, True)
                    hdr_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                    f = hdr_item.font()
                    f.setBold(True)
                    hdr_item.setFont(f)
                    hdr_item.setForeground(QColor("#38BDF8" if self.main_window.dark_mode else "#2563EB"))

                    for c_i in range(4):
                        cell = hdr_item if c_i == 0 else SortableTableWidgetItem("", 0, is_dir=True, is_parent=True)
                        cell.setFlags(Qt.ItemFlag.ItemIsEnabled)
                        self.table.setItem(row_idx, c_i, cell)
                    row_idx += 1
                    continue

                assert rec is not None
                is_dir = bool(rec["is_dir"])
                ext = str(rec["ext"])
                size_b = int(rec["size_b"])  # type: ignore[arg-type]
                mtime = float(rec["mtime"])  # type: ignore[arg-type]
                disp_name = str(rec["disp_name"])
                full_path = str(rec["path"])
                size_str = str(rec["size_str"])
                type_str = str(rec["type_str"])
                date_str = str(rec["date_str"])

                item_name = SortableTableWidgetItem(disp_name, disp_name.lower(), is_dir=is_dir)
                item_name.setData(Qt.ItemDataRole.UserRole, full_path)
                item_name.setData(Qt.ItemDataRole.UserRole + 1, False)

                icon = get_entry_icon_or_thumbnail(
                    self.icon_provider,
                    full_path,
                    is_dir,
                    ext,
                    mtime,
                    icon_px,
                    show_icons=self.main_window.show_icons,
                )
                if not icon.isNull():
                    item_name.setIcon(icon)

                item_size = SortableTableWidgetItem(size_str, size_b, is_dir=is_dir)
                item_size.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                item_type = SortableTableWidgetItem(type_str, type_str.lower(), is_dir=is_dir)
                item_date = SortableTableWidgetItem(date_str, mtime, is_dir=is_dir)

                color = self.main_window.get_color_for_entry(is_dir=is_dir, ext=ext)
                if color is not None:
                    for col_item in (item_name, item_size, item_type, item_date):
                        col_item.setForeground(color)
                if is_dir:
                    f = item_name.font()
                    f.setBold(True)
                    item_name.setFont(f)

                self.table.setItem(row_idx, 0, item_name)
                self.table.setItem(row_idx, 1, item_size)
                self.table.setItem(row_idx, 2, item_type)
                self.table.setItem(row_idx, 3, item_date)
                row_idx += 1

            if self.group_by == "none":
                self.table.setSortingEnabled(True)

        def _populate_icon_view(
            self, p: Path, records: List[Dict[str, object]], has_parent: bool
        ) -> None:
            self.icon_list.clear()

            xl_px = self.extra_zoom_px
            mode_px_map = {
                "extra_large_icons": (xl_px, QSize(xl_px + 28, xl_px + 46), QListView.ViewMode.IconMode),
                "large_icons": (92, QSize(124, 140), QListView.ViewMode.IconMode),
                "medium_icons": (60, QSize(98, 108), QListView.ViewMode.IconMode),
                "small_icons": (32, QSize(160, 42), QListView.ViewMode.ListMode),
                "list": (24, QSize(190, 32), QListView.ViewMode.ListMode),
                "tiles": (52, QSize(240, 68), QListView.ViewMode.ListMode),
            }
            icon_px, grid_sz, lv_mode = mode_px_map.get(
                self.view_mode, (60, QSize(98, 108), QListView.ViewMode.IconMode)
            )
            self.icon_list.setViewMode(lv_mode)
            self.icon_list.setIconSize(QSize(icon_px, icon_px))
            self.icon_list.setGridSize(grid_sz)
            self.icon_list.setWrapping(True)
            if lv_mode == QListView.ViewMode.ListMode:
                self.icon_list.setFlow(QListView.Flow.TopToBottom)
            else:
                self.icon_list.setFlow(QListView.Flow.LeftToRight)

            if has_parent:
                parent_str = str(p.parent)
                p_item = QListWidgetItem("📁 .. (상위 폴더)")
                p_item.setData(Qt.ItemDataRole.UserRole, parent_str)
                p_item.setData(Qt.ItemDataRole.UserRole + 1, True)
                p_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                f = p_item.font()
                f.setBold(True)
                p_item.setFont(f)
                self.icon_list.addItem(p_item)

            for rec in records:
                is_dir = bool(rec["is_dir"])
                ext = str(rec["ext"])
                mtime = float(rec["mtime"])  # type: ignore[arg-type]
                disp_name = str(rec["disp_name"])
                full_path = str(rec["path"])
                size_str = str(rec["size_str"])
                type_str = str(rec["type_str"])

                if self.view_mode == "tiles":
                    label_text = f"{disp_name}\n{type_str} · {size_str}"
                else:
                    label_text = disp_name

                item = QListWidgetItem(label_text)
                item.setData(Qt.ItemDataRole.UserRole, full_path)
                item.setData(Qt.ItemDataRole.UserRole + 1, False)
                item.setToolTip(f"{disp_name}\n유형: {type_str}\n크기: {size_str}\n수정한 날짜: {rec['date_str']}")

                icon = get_entry_icon_or_thumbnail(
                    self.icon_provider,
                    full_path,
                    is_dir,
                    ext,
                    mtime,
                    icon_px,
                    show_icons=self.main_window.show_icons,
                )
                if not icon.isNull():
                    item.setIcon(icon)

                color = self.main_window.get_color_for_entry(is_dir=is_dir, ext=ext)
                if color is not None:
                    item.setForeground(color)
                if is_dir:
                    f = item.font()
                    f.setBold(True)
                    item.setFont(f)

                self.icon_list.addItem(item)

        def apply_filter(self, keyword: str) -> None:
            kw = keyword.strip().lower()
            for row in range(self.table.rowCount()):
                name_item = self.table.item(row, 0)
                if name_item is None:
                    continue
                if name_item.data(Qt.ItemDataRole.UserRole + 1):
                    self.table.setRowHidden(row, False)
                    continue
                text = name_item.text().lower()
                self.table.setRowHidden(row, bool(kw and kw not in text))

            for i in range(self.icon_list.count()):
                l_item = self.icon_list.item(i)
                if l_item is None:
                    continue
                if l_item.data(Qt.ItemDataRole.UserRole + 1):
                    l_item.setHidden(False)
                    continue
                text = l_item.text().lower()
                l_item.setHidden(bool(kw and kw not in text))

        def _on_selection_changed(self) -> None:
            self.update_status_summary()
            sel = self.selected_file_paths()
            if sel:
                self.selectionChangedSignal.emit(sel[0])
            else:
                self.selectionChangedSignal.emit("")

        def update_status_summary(self) -> None:
            selected_paths = self.selected_file_paths()
            free_b, total_b = _safe_disk_usage(self.current_path)
            free_str = f"여유 {format_size(free_b)}" if total_b > 0 else ""
            mode_kr = VIEW_MODE_LABELS.get(self.view_mode, self.view_mode)

            if selected_paths:
                sel_bytes = 0
                for p in selected_paths:
                    try:
                        if os.path.isfile(p):
                            sel_bytes += os.path.getsize(p)
                    except Exception:
                        pass
                msg = (
                    f"[{mode_kr}] 선택: {len(selected_paths)}개 ({format_size(sel_bytes)})  |  "
                    f"폴더 {getattr(self, '_dir_count', 0)}개, 파일 {getattr(self, '_file_count', 0)}개 "
                    f"({format_size(getattr(self, '_total_bytes', 0))})"
                )
            else:
                msg = (
                    f"[{mode_kr}] 폴더 {getattr(self, '_dir_count', 0)}개, 파일 {getattr(self, '_file_count', 0)}개 "
                    f"({format_size(getattr(self, '_total_bytes', 0))})"
                )
            if free_str:
                msg += f"  |  💾 {free_str}"

            self.summary_label.setText(msg)
            self.statusUpdated.emit(f"[{self.pane.pane_title}] {self.current_path}  —  {msg}")

        def activate_selected_or_current(self) -> None:
            """선택된 파일/폴더(또는 현재 포커스 행)에서 Enter 키를 눌렀을 때 폴더 진입 또는 파일 실행을 수행합니다."""
            self.paneActivated.emit()
            selected_paths = self.selected_file_paths()
            if selected_paths:
                dirs = [p for p in selected_paths if os.path.isdir(p)]
                files = [p for p in selected_paths if os.path.isfile(p)]
                if len(selected_paths) == 1 and dirs:
                    self.navigate_to(dirs[0], record_history=True)
                    return
                if dirs and not files:
                    self.navigate_to(dirs[0], record_history=True)
                    for extra_d in dirs[1:]:
                        self.openInNewTabRequested.emit(extra_d)
                    return
                for f_path in files:
                    self._activate_path(f_path)
                return

            if self.stack.currentWidget() == self.icon_list:
                curr_item = self.icon_list.currentItem()
                if curr_item is not None:
                    full_path = curr_item.data(Qt.ItemDataRole.UserRole)
                    if full_path:
                        self._activate_path(str(full_path))
            else:
                row = self.table.currentRow()
                if row >= 0:
                    name_item = self.table.item(row, 0)
                    if name_item is not None:
                        full_path = name_item.data(Qt.ItemDataRole.UserRole)
                        if full_path:
                            self._activate_path(str(full_path))

        def _on_table_double_clicked(self, index) -> None:
            self.paneActivated.emit()
            row = index.row()
            name_item = self.table.item(row, 0)
            if name_item is None:
                return
            full_path = name_item.data(Qt.ItemDataRole.UserRole)
            if not full_path:
                return
            self._activate_path(str(full_path))

        def _on_icon_double_clicked(self, item: QListWidgetItem) -> None:
            self.paneActivated.emit()
            full_path = item.data(Qt.ItemDataRole.UserRole)
            if not full_path:
                return
            self._activate_path(str(full_path))

        def _activate_path(self, full_path: str) -> None:
            if os.path.isdir(full_path):
                self.navigate_to(full_path, record_history=True)
            else:
                try:
                    open_path_with_os(full_path)
                except Exception as exc:
                    QMessageBox.warning(self, "실행 오류", f"파일을 열 수 없습니다:\n{full_path}\n\n오류: {exc}")

        def _on_files_dropped(
            self, src_paths: List[str], target_dir: str, modifiers: Qt.KeyboardModifier
        ) -> None:
            self.paneActivated.emit()
            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                mode = "move"
            elif modifiers & Qt.KeyboardModifier.ControlModifier:
                mode = "copy"
            else:
                menu = QMenu(self)
                act_copy = menu.addAction(f"📄 여기에 복사 ({len(src_paths)}개 항목)")
                act_move = menu.addAction(f"✂️ 여기에 이동 ({len(src_paths)}개 항목)")
                menu.addSeparator()
                menu.addAction("❌ 취소")
                chosen = menu.exec(self.cursor().pos())
                if chosen == act_copy:
                    mode = "copy"
                elif chosen == act_move:
                    mode = "move"
                else:
                    return

            count, errors = perform_file_transfer_qt(self, src_paths, target_dir, mode=mode)
            self.main_window.refresh_all_panes()
            if errors:
                QMessageBox.warning(self, "작업 중 오류 발생", "\n".join(errors[:10]))
            else:
                action_kr = "이동" if mode == "move" else "복사"
                self.main_window.statusBar().showMessage(
                    f"✅ {count}개 항목을 '{target_dir}'(으)로 {action_kr}했습니다.", 4000
                )

        def _add_current_to_favorites(self) -> None:
            self.paneActivated.emit()
            if self.current_path:
                self.main_window.add_favorite(self.current_path)

        def _show_context_menu(self, pos: QPoint) -> None:
            self.paneActivated.emit()
            selected_paths = self.selected_file_paths()
            menu = QMenu(self)

            if len(selected_paths) == 1 and os.path.isdir(selected_paths[0]):
                target_folder = selected_paths[0]
                act_open = menu.addAction("📂 열기 (Enter)")
                act_open_tab = menu.addAction("➕ 새 탭에서 폴더 열기 (휠 클릭)")
                act_open.triggered.connect(lambda: self.navigate_to(target_folder))
                act_open_tab.triggered.connect(lambda: self.openInNewTabRequested.emit(target_folder))
                menu.addSeparator()
            elif len(selected_paths) == 1 and os.path.isfile(selected_paths[0]):
                target_file = selected_paths[0]
                act_run = menu.addAction("▶️ 기본 프로그램으로 실행 (Enter)")
                act_run.triggered.connect(lambda: open_path_with_os(target_file))
                menu.addSeparator()

            view_sub = menu.addMenu("🖼️ 보기 모드 변경 (Ctrl+휠)")
            for v_key, v_label, _ in VIEW_MODES_META:
                act_v = view_sub.addAction(f"{'• ' if self.view_mode == v_key else '   '}{v_label}")
                act_v.triggered.connect(lambda checked=False, k=v_key: self.set_view_mode(k))

            if selected_paths:
                copy_to_menu = menu.addMenu("📑 다른 패널로 즉시 복사")
                move_to_menu = menu.addMenu("📦 다른 패널로 즉시 이동")
                for idx, other_pane in enumerate(self.main_window.panes):
                    dest_path = other_pane.current_path()
                    if not dest_path:
                        continue
                    label = f"[{idx + 1}번 창] {Path(dest_path).name or dest_path} ({dest_path})"
                    c_act = copy_to_menu.addAction(label)
                    c_act.triggered.connect(
                        lambda checked=False, d=dest_path: self._transfer_to_pane(selected_paths, d, "copy")
                    )
                    m_act = move_to_menu.addAction(label)
                    m_act.triggered.connect(
                        lambda checked=False, d=dest_path: self._transfer_to_pane(selected_paths, d, "move")
                    )
                menu.addSeparator()

                act_copy = menu.addAction("📋 복사 (Ctrl+C)")
                act_cut = menu.addAction("✂️ 잘라내기 (Ctrl+X)")
                act_copy.triggered.connect(lambda: self.main_window.set_clipboard_files(selected_paths, "copy"))
                act_cut.triggered.connect(lambda: self.main_window.set_clipboard_files(selected_paths, "move"))

            if self.main_window.clipboard_paths:
                mode_kr = "이동" if self.main_window.clipboard_mode == "move" else "복사"
                act_paste = menu.addAction(
                    f"📥 여기에 붙여넣기 ({len(self.main_window.clipboard_paths)}개 {mode_kr}, Ctrl+V)"
                )
                act_paste.triggered.connect(self.paste_files_here)

            menu.addSeparator()
            act_new_folder = menu.addAction("📁 새 폴더 만들기 (Ctrl+Shift+N)")
            act_new_file = menu.addAction("📝 새 텍스트 파일 만들기")
            act_new_folder.triggered.connect(self.create_new_folder)
            act_new_file.triggered.connect(self.create_new_text_file)

            if len(selected_paths) == 1:
                menu.addSeparator()
                act_rename = menu.addAction("✏️ 이름 바꾸기 (F2)")
                act_rename.triggered.connect(self.rename_selected_item)

            if selected_paths:
                act_delete = menu.addAction("🗑️ 삭제 (Delete)")
                act_delete.triggered.connect(self.delete_selected_items)

            menu.addSeparator()
            act_copy_path = menu.addAction("🔗 현재/선택 경로 클립보드 복사")
            act_copy_path.triggered.connect(
                lambda: QApplication.clipboard().setText(
                    selected_paths[0] if selected_paths else self.current_path
                )
            )
            act_open_os = menu.addAction("🪟 Windows 기본 탐색기에서 열기")
            act_open_os.triggered.connect(lambda: open_path_with_os(self.current_path))
            act_open_term = menu.addAction("💻 여기서 터미널(CMD/PowerShell) 열기")
            act_open_term.triggered.connect(self._open_terminal_here)

            if len(selected_paths) == 1:
                act_prop = menu.addAction("ℹ️ 상세 속성 보기")
                act_prop.triggered.connect(lambda: self._show_properties(selected_paths[0]))

            active_viewport = (
                self.icon_list.viewport()
                if self.stack.currentWidget() == self.icon_list
                else self.table.viewport()
            )
            menu.exec(active_viewport.mapToGlobal(pos))

        def _transfer_to_pane(self, src_paths: List[str], dest_dir: str, mode: str) -> None:
            count, errors = perform_file_transfer_qt(self, src_paths, dest_dir, mode=mode)
            self.main_window.refresh_all_panes()
            if errors:
                QMessageBox.warning(self, "오류", "\n".join(errors[:10]))
            else:
                action_kr = "이동" if mode == "move" else "복사"
                self.main_window.statusBar().showMessage(
                    f"✅ {count}개 항목을 '{dest_dir}'(으)로 {action_kr} 완료!", 4000
                )

        def paste_files_here(self) -> None:
            if not self.main_window.clipboard_paths:
                return
            count, errors = perform_file_transfer_qt(
                self,
                self.main_window.clipboard_paths,
                self.current_path,
                mode=self.main_window.clipboard_mode,
            )
            if self.main_window.clipboard_mode == "move" and count > 0:
                self.main_window.clipboard_paths.clear()
            self.main_window.refresh_all_panes()
            if errors:
                QMessageBox.warning(self, "붙여넣기 오류", "\n".join(errors[:10]))

        def create_new_folder(self) -> None:
            name, ok = QInputDialog.getText(self, "새 폴더 만들기", "새 폴더 이름을 입력하세요:", text="새 폴더")
            if ok and name.strip():
                target = Path(self.current_path) / name.strip()
                try:
                    target.mkdir(parents=False, exist_ok=False)
                    self.refresh()
                except Exception as exc:
                    QMessageBox.warning(self, "폴더 생성 실패", f"폴더를 만들 수 없습니다:\n{exc}")

        def create_new_text_file(self, default_filename: str = "새 문서.txt") -> None:
            name, ok = QInputDialog.getText(
                self, "새 파일 만들기", "새 파일 이름을 입력하세요:", text=default_filename
            )
            if ok and name.strip():
                target = Path(self.current_path) / name.strip()
                if target.exists():
                    QMessageBox.warning(self, "파일 존재", "동일한 이름의 파일이 이미 존재합니다.")
                    return
                try:
                    target.write_text("", encoding="utf-8")
                    self.refresh()
                except Exception as exc:
                    QMessageBox.warning(self, "파일 생성 실패", f"파일을 만들 수 없습니다:\n{exc}")

        def rename_selected_item(self) -> None:
            paths = self.selected_file_paths()
            if len(paths) != 1:
                return
            src = Path(paths[0])
            new_name, ok = QInputDialog.getText(
                self, "이름 바꾸기", "새 이름을 입력하세요:", text=src.name
            )
            if ok and new_name.strip() and new_name.strip() != src.name:
                target = src.parent / new_name.strip()
                if target.exists():
                    QMessageBox.warning(self, "이름 중복", "해당 이름의 파일이나 폴더가 이미 존재합니다.")
                    return
                try:
                    src.rename(target)
                    self.main_window.refresh_all_panes()
                except Exception as exc:
                    QMessageBox.warning(self, "이름 변경 실패", f"이름을 변경할 수 없습니다:\n{exc}")

        def delete_selected_items(self) -> None:
            paths = self.selected_file_paths()
            if not paths:
                return
            sample_names = "\n".join(f"• {Path(p).name}" for p in paths[:6])
            if len(paths) > 6:
                sample_names += f"\n... 외 {len(paths) - 6}개"

            ans = QMessageBox.question(
                self,
                "삭제 확인",
                f"선택한 {len(paths)}개 항목을 삭제하시겠습니까?\n\n{sample_names}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if ans != QMessageBox.StandardButton.Yes:
                return

            errors: List[str] = []
            for p_str in paths:
                p = Path(p_str)
                try:
                    if p.is_dir() and not p.is_symlink():
                        shutil.rmtree(p)
                    else:
                        p.unlink()
                except Exception as exc:
                    errors.append(f"{p.name}: {exc}")

            self.main_window.refresh_all_panes()
            if errors:
                QMessageBox.warning(self, "삭제 중 오류", "\n".join(errors[:10]))

        def _open_terminal_here(self) -> None:
            try:
                if platform.system() == "Windows":
                    subprocess.Popen("start cmd", cwd=self.current_path, shell=True)
                elif platform.system() == "Darwin":
                    subprocess.Popen(["open", "-a", "Terminal", self.current_path])
                else:
                    subprocess.Popen(["x-terminal-emulator"], cwd=self.current_path)
            except Exception as exc:
                QMessageBox.warning(self, "터미널 실행 실패", f"터미널을 열 수 없습니다:\n{exc}")

        def _show_properties(self, target_path: str) -> None:
            p = Path(target_path)
            try:
                st = p.stat()
                created = datetime.datetime.fromtimestamp(st.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
                modified = datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                size_info = format_size(st.st_size) if p.is_file() else "폴더 (Directory)"
            except Exception as exc:
                QMessageBox.information(self, "속성", f"경로: {target_path}\n상태 조회 오류: {exc}")
                return

            info_text = (
                f"이름: {p.name}\n"
                f"전체 경로: {p.resolve()}\n"
                f"유형: {'폴더' if p.is_dir() else (p.suffix or '파일')}\n"
                f"크기: {size_info}\n"
                f"생성 일시: {created}\n"
                f"수정 일시: {modified}"
            )
            QMessageBox.information(self, f"'{p.name}' 속성", info_text)

    # -----------------------------------------------------------------------
    # 3. 우측 미리 보기 창 (Preview Pane) & 세부 정보 창 (Details Pane)
    # -----------------------------------------------------------------------
    class InspectorPane(QFrame):
        def __init__(self, main_window: "QDirMainWindow", parent: Optional[QWidget] = None):
            super().__init__(parent)
            self.main_window = main_window
            self.setObjectName("InspectorPane")
            self.mode: str = "preview"
            self.current_target_path: str = ""
            self.setMinimumWidth(260)
            self.setMaximumWidth(460)
            self._build_ui()

        def _build_ui(self) -> None:
            layout = QVBoxLayout(self)
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setSpacing(6)

            hdr = QHBoxLayout()
            self.title_lbl = QLabel("🖼️ 미리 보기 창")
            self.title_lbl.setStyleSheet("font-weight: bold; font-size: 13px;")
            hdr.addWidget(self.title_lbl, stretch=1)

            btn_close = QToolButton()
            btn_close.setText("✕")
            btn_close.setToolTip("창 닫기")
            btn_close.clicked.connect(self.main_window.close_inspector_pane)
            hdr.addWidget(btn_close)
            layout.addLayout(hdr)

            self.img_label = QLabel()
            self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.img_label.setMinimumHeight(180)
            self.img_label.setWordWrap(True)
            layout.addWidget(self.img_label)

            self.text_preview = QPlainTextEdit()
            self.text_preview.setReadOnly(True)
            self.text_preview.hide()
            layout.addWidget(self.text_preview, stretch=1)

            self.meta_label = QLabel("파일이나 폴더를 선택하면 여기에 정보가 표시됩니다.")
            self.meta_label.setWordWrap(True)
            self.meta_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            layout.addWidget(self.meta_label, stretch=1)

        def set_mode(self, mode: str) -> None:
            self.mode = mode
            self.title_lbl.setText("🖼️ 미리 보기 창" if mode == "preview" else "📋 세부 정보 창")
            self.inspect_path(self.current_target_path)

        def inspect_path(self, path_str: str) -> None:
            self.current_target_path = path_str
            if not path_str or not os.path.exists(path_str):
                self.img_label.show()
                self.img_label.setPixmap(QPixmap())
                self.img_label.setText("항목을 선택해 미리 보거나\n세부 정보를 확인하세요.")
                self.text_preview.hide()
                self.meta_label.setText("")
                return

            p = Path(path_str)
            is_dir = p.is_dir()
            ext = "" if is_dir else p.suffix.lower()

            try:
                st = p.stat()
                size_b = 0 if is_dir else st.st_size
                ctime_str = datetime.datetime.fromtimestamp(st.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
                mtime_str = datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                atime_str = datetime.datetime.fromtimestamp(st.st_atime).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                size_b = 0
                ctime_str = mtime_str = atime_str = "-"

            img_dims = ""
            if not is_dir and ext in IMAGE_EXTENSIONS:
                self.text_preview.hide()
                self.img_label.show()
                reader = QImageReader(str(p))
                reader.setAutoTransform(True)
                orig_sz = reader.size()
                if orig_sz.isValid():
                    img_dims = f"{orig_sz.width()} × {orig_sz.height()} px"
                img = reader.read()
                if not img.isNull():
                    pix = QPixmap.fromImage(img).scaled(
                        QSize(300, 260),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    self.img_label.setPixmap(pix)
                else:
                    self.img_label.setPixmap(QPixmap())
                    self.img_label.setText("🖼️ 이미지를 불러올 수 없습니다.")

            elif self.mode == "preview" and not is_dir and ext in TEXT_PREVIEW_EXTENSIONS:
                self.img_label.hide()
                self.text_preview.show()
                try:
                    raw_bytes = p.read_bytes()[:32768]
                    try:
                        content = raw_bytes.decode("utf-8")
                    except UnicodeDecodeError:
                        content = raw_bytes.decode("cp949", errors="replace")
                    self.text_preview.setPlainText(content)
                except Exception as exc:
                    self.text_preview.setPlainText(f"텍스트 미리 보기 실패: {exc}")
            else:
                self.text_preview.hide()
                self.img_label.show()
                ic = QFileIconProvider().icon(QFileInfo(str(p)))
                self.img_label.setPixmap(ic.pixmap(QSize(72, 72)))

            if self.mode == "details":
                lines = [
                    f"📌 이름: {p.name}",
                    f"📂 유형: {'폴더' if is_dir else (ext.upper()[1:] + ' 파일' if ext else '파일')}",
                    f"📍 위치: {p.parent}",
                ]
                if not is_dir:
                    lines.append(f"📦 크기: {format_size(size_b)} ({size_b:,} 바이트)")
                if img_dims:
                    lines.append(f"🖼️ 해상도: {img_dims}")
                lines.extend([
                    f"🕒 수정한 날짜: {mtime_str}",
                    f"📅 만든 날짜: {ctime_str}",
                    f"👁️ 액세스한 날짜: {atime_str}",
                ])
                self.meta_label.setText("\n".join(lines))
                self.meta_label.show()
            else:
                short_info = f"📄 {p.name}"
                if img_dims:
                    short_info += f"  ({img_dims}, {format_size(size_b)})"
                elif not is_dir:
                    short_info += f"  ({format_size(size_b)})"
                self.meta_label.setText(short_info)
                self.meta_label.show()

    # -----------------------------------------------------------------------
    # 4. 개별 탐색 패널 (1~4번 창)
    # -----------------------------------------------------------------------
    class ExplorerPane(QFrame):
        paneActivated = pyqtSignal(int)

        def __init__(
            self,
            pane_index: int,
            main_window: "QDirMainWindow",
            initial_tabs: Optional[List[str]] = None,
            parent: Optional[QWidget] = None,
        ):
            super().__init__(parent)
            self.pane_index = pane_index
            self.pane_title = f"패널 {pane_index + 1}"
            self.main_window = main_window
            self.setFrameShape(QFrame.Shape.StyledPanel)
            self.setObjectName("ExplorerPane")

            self._build_ui()

            tabs_to_open = initial_tabs or [str(Path.home())]
            for t_path in tabs_to_open:
                if os.path.isdir(t_path):
                    self.add_new_tab(t_path)
            if self.tab_widget.count() == 0:
                self.add_new_tab(str(Path.home()))

        def _build_ui(self) -> None:
            layout = QVBoxLayout(self)
            layout.setContentsMargins(3, 3, 3, 3)
            layout.setSpacing(2)

            header_bar = QHBoxLayout()
            header_bar.setContentsMargins(4, 2, 4, 2)
            header_bar.setSpacing(4)

            self.badge_label = QLabel(f" #{self.pane_index + 1} ")
            self.badge_label.setObjectName("PaneBadge")
            header_bar.addWidget(self.badge_label)

            self.path_title_label = QLabel("")
            self.path_title_label.setObjectName("PaneTitlePath")
            header_bar.addWidget(self.path_title_label, stretch=1)

            self.btn_new_tab = QToolButton()
            self.btn_new_tab.setText("새 탭")
            self.btn_new_tab.setIcon(create_ui_icon("new", self.main_window.dark_mode, 16))
            self.btn_new_tab.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            self.btn_new_tab.setToolTip("현재 패널에 새 탭 추가 (Ctrl+T)")
            self.btn_new_tab.clicked.connect(lambda: self.add_new_tab(self.current_path()))
            header_bar.addWidget(self.btn_new_tab)

            layout.addLayout(header_bar)

            self.tab_widget = QTabWidget()
            self.tab_widget.setTabsClosable(True)
            self.tab_widget.setMovable(True)
            self.tab_widget.setDocumentMode(True)
            self.tab_widget.tabCloseRequested.connect(self.close_tab)
            self.tab_widget.currentChanged.connect(self._on_tab_changed)
            layout.addWidget(self.tab_widget, stretch=1)

        def set_active_visual(self, is_active: bool) -> None:
            self.setProperty("activePane", "true" if is_active else "false")
            self.style().unpolish(self)
            self.style().polish(self)

        def add_new_tab(self, path_str: Optional[str] = None) -> DirectoryTab:
            target = path_str if (path_str and os.path.isdir(path_str)) else str(Path.home())
            tab = DirectoryTab(target, self.main_window, self)
            tab.pathChanged.connect(lambda new_p, t=tab: self._update_tab_title(t, new_p))
            tab.statusUpdated.connect(self.main_window.statusBar().showMessage)
            tab.selectionChangedSignal.connect(self.main_window.on_active_selection_changed)
            tab.openInNewTabRequested.connect(self.add_new_tab)
            tab.paneActivated.connect(lambda: self.paneActivated.emit(self.pane_index))

            idx = self.tab_widget.addTab(tab, self._short_tab_name(target))
            self.tab_widget.setTabToolTip(idx, target)
            self.tab_widget.setCurrentIndex(idx)
            self._update_tab_title(tab, target)
            return tab

        def close_tab(self, index: int) -> None:
            if self.tab_widget.count() <= 1:
                return
            w = self.tab_widget.widget(index)
            self.tab_widget.removeTab(index)
            if w is not None:
                w.deleteLater()

        def current_tab(self) -> Optional[DirectoryTab]:
            w = self.tab_widget.currentWidget()
            return w if isinstance(w, DirectoryTab) else None

        def current_path(self) -> str:
            t = self.current_tab()
            return t.current_path if t else str(Path.home())

        def navigate_current_tab(self, path_str: str) -> None:
            t = self.current_tab()
            if t:
                t.navigate_to(path_str, record_history=True)

        def refresh_all_tabs(self) -> None:
            self.btn_new_tab.setIcon(create_ui_icon("new", self.main_window.dark_mode, 16))
            for i in range(self.tab_widget.count()):
                w = self.tab_widget.widget(i)
                if isinstance(w, DirectoryTab):
                    w.refresh_nav_icons()
                    w.refresh()

        def get_all_tab_paths(self) -> List[str]:
            paths: List[str] = []
            for i in range(self.tab_widget.count()):
                w = self.tab_widget.widget(i)
                if isinstance(w, DirectoryTab) and w.current_path:
                    paths.append(w.current_path)
            return paths

        def _on_tab_changed(self, index: int) -> None:
            t = self.current_tab()
            if t:
                self.path_title_label.setText(t.current_path)
                t.update_status_summary()

        def _update_tab_title(self, tab: DirectoryTab, new_path: str) -> None:
            idx = self.tab_widget.indexOf(tab)
            if idx >= 0:
                self.tab_widget.setTabText(idx, self._short_tab_name(new_path))
                self.tab_widget.setTabToolTip(idx, new_path)
            if tab == self.current_tab():
                self.path_title_label.setText(new_path)

        @staticmethod
        def _short_tab_name(path_str: str) -> str:
            p = Path(path_str)
            name = p.name or path_str
            return name if len(name) <= 18 else name[:16] + "…"

    # -----------------------------------------------------------------------
    # 5. 설정 다이얼로그 (색상 규칙 & 즐겨찾기 관리)
    # -----------------------------------------------------------------------
    class ColorRulesDialog(QDialog):
        def __init__(
            self,
            color_rules: Dict[str, Dict[str, object]],
            dark_mode: bool,
            parent: Optional[QWidget] = None,
        ):
            super().__init__(parent)
            self.setWindowTitle("🎨 Q-Dir 확장자별 색상 필터 설정")
            self.resize(620, 420)
            self.dark_mode = dark_mode
            self.rules: Dict[str, Dict[str, object]] = json.loads(json.dumps(color_rules))
            self._build_ui()

        def _build_ui(self) -> None:
            layout = QVBoxLayout(self)
            desc = QLabel(
                "카테고리별 확장자 목록(쉼표로 구분)과 표시 색상을 자유롭게 변경할 수 있습니다."
            )
            layout.addWidget(desc)

            self.form_layout = QFormLayout()
            self.row_widgets: Dict[str, Tuple[QCheckBox, QLineEdit, QPushButton]] = {}

            for cat_name, rule in self.rules.items():
                row_w = QWidget()
                row_h = QHBoxLayout(row_w)
                row_h.setContentsMargins(0, 0, 0, 0)

                chk = QCheckBox(cat_name)
                chk.setChecked(bool(rule.get("enabled", True)))
                chk.setFixedWidth(185)

                exts = rule.get("extensions", [])
                ext_str = ", ".join(exts) if isinstance(exts, list) else str(exts)
                ext_edit = QLineEdit(ext_str)
                if cat_name.startswith("폴더"):
                    ext_edit.setReadOnly(True)

                color_key = "color_dark" if self.dark_mode else "color_light"
                hex_color = str(rule.get(color_key, "#38BDF8"))
                btn_color = QPushButton(hex_color)
                btn_color.setFixedWidth(90)
                btn_color.setStyleSheet(
                    f"background-color: {hex_color}; color: #111827; font-weight: bold; border-radius: 4px;"
                )
                btn_color.clicked.connect(
                    lambda checked=False, c=cat_name, b=btn_color: self._pick_color(c, b)
                )

                row_h.addWidget(chk)
                row_h.addWidget(ext_edit, stretch=1)
                row_h.addWidget(btn_color)

                self.form_layout.addRow(row_w)
                self.row_widgets[cat_name] = (chk, ext_edit, btn_color)

            layout.addLayout(self.form_layout)

            btn_reset = QPushButton("기본 색상 규칙으로 초기화")
            btn_reset.clicked.connect(self._reset_defaults)
            layout.addWidget(btn_reset)

            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.accepted.connect(self._on_accept)
            buttons.rejected.connect(self.reject)
            layout.addWidget(buttons)

        def _pick_color(self, cat_name: str, btn: QPushButton) -> None:
            color_key = "color_dark" if self.dark_mode else "color_light"
            current_hex = str(self.rules[cat_name].get(color_key, "#38BDF8"))
            chosen = QColorDialog.getColor(QColor(current_hex), self, f"{cat_name} 색상 선택")
            if chosen.isValid():
                hex_val = chosen.name().upper()
                self.rules[cat_name][color_key] = hex_val
                btn.setText(hex_val)
                btn.setStyleSheet(
                    f"background-color: {hex_val}; color: #111827; font-weight: bold; border-radius: 4px;"
                )

        def _reset_defaults(self) -> None:
            self.rules = json.loads(json.dumps(DEFAULT_COLOR_RULES))
            color_key = "color_dark" if self.dark_mode else "color_light"
            for cat_name, (chk, ext_edit, btn) in self.row_widgets.items():
                rule = self.rules[cat_name]
                chk.setChecked(True)
                ext_edit.setText(", ".join(rule["extensions"]))  # type: ignore[arg-type]
                hex_val = str(rule[color_key])
                btn.setText(hex_val)
                btn.setStyleSheet(
                    f"background-color: {hex_val}; color: #111827; font-weight: bold; border-radius: 4px;"
                )

        def _on_accept(self) -> None:
            for cat_name, (chk, ext_edit, _) in self.row_widgets.items():
                self.rules[cat_name]["enabled"] = chk.isChecked()
                if not cat_name.startswith("폴더"):
                    raw_exts = [e.strip().lower() for e in ext_edit.text().split(",") if e.strip()]
                    norm_exts = [e if e.startswith(".") else f".{e}" for e in raw_exts]
                    self.rules[cat_name]["extensions"] = norm_exts
            self.accept()

    class FavoritesDialog(QDialog):
        def __init__(self, favorites: List[Dict[str, str]], parent: Optional[QWidget] = None):
            super().__init__(parent)
            self.setWindowTitle("⭐ 자주 쓰는 폴더 즐겨찾기 관리")
            self.resize(540, 380)
            self.favorites: List[Dict[str, str]] = [dict(item) for item in favorites]
            self._build_ui()

        def _build_ui(self) -> None:
            layout = QVBoxLayout(self)

            self.list_widget = QListWidget()
            self._refresh_list()
            layout.addWidget(self.list_widget, stretch=1)

            btn_row = QHBoxLayout()
            btn_add = QPushButton("➕ 경로 직접 추가")
            btn_rename = QPushButton("✏️ 이름 수정")
            btn_del = QPushButton("🗑️ 선택 삭제")
            btn_up = QPushButton("▲ 위로")
            btn_down = QPushButton("▼ 아래로")

            btn_add.clicked.connect(self._add_item)
            btn_rename.clicked.connect(self._rename_item)
            btn_del.clicked.connect(self._del_item)
            btn_up.clicked.connect(lambda: self._move_item(-1))
            btn_down.clicked.connect(lambda: self._move_item(1))

            for b in (btn_add, btn_rename, btn_del, btn_up, btn_down):
                btn_row.addWidget(b)
            layout.addLayout(btn_row)

            box = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
            box.accepted.connect(self.accept)
            box.rejected.connect(self.reject)
            layout.addWidget(box)

        def _refresh_list(self) -> None:
            self.list_widget.clear()
            for fav in self.favorites:
                item = QListWidgetItem(f"{fav.get('name', '폴더')}   —   {fav.get('path', '')}")
                self.list_widget.addItem(item)

        def _add_item(self) -> None:
            path_str, ok1 = QInputDialog.getText(self, "즐겨찾기 추가", "폴더 전체 경로를 입력하세요:")
            if not (ok1 and path_str.strip()):
                return
            p = Path(path_str.strip())
            if not p.is_dir():
                QMessageBox.warning(self, "경로 오류", "유효한 폴더 경로가 아닙니다.")
                return
            default_name = f"⭐ {p.name or str(p)}"
            name_str, ok2 = QInputDialog.getText(
                self, "즐겨찾기 이름", "표시할 이름을 입력하세요:", text=default_name
            )
            if ok2 and name_str.strip():
                self.favorites.append({"name": name_str.strip(), "path": str(p.resolve())})
                self._refresh_list()

        def _rename_item(self) -> None:
            idx = self.list_widget.currentRow()
            if 0 <= idx < len(self.favorites):
                curr_name = self.favorites[idx].get("name", "")
                new_name, ok = QInputDialog.getText(self, "이름 수정", "새 표시 이름:", text=curr_name)
                if ok and new_name.strip():
                    self.favorites[idx]["name"] = new_name.strip()
                    self._refresh_list()

        def _del_item(self) -> None:
            idx = self.list_widget.currentRow()
            if 0 <= idx < len(self.favorites):
                self.favorites.pop(idx)
                self._refresh_list()

        def _move_item(self, delta: int) -> None:
            idx = self.list_widget.currentRow()
            new_idx = idx + delta
            if 0 <= idx < len(self.favorites) and 0 <= new_idx < len(self.favorites):
                self.favorites[idx], self.favorites[new_idx] = (
                    self.favorites[new_idx],
                    self.favorites[idx],
                )
                self._refresh_list()
                self.list_widget.setCurrentRow(new_idx)

    # -----------------------------------------------------------------------
    # 6. 메인 Q-Dir 윈도우 (고시인성 벡터 아이콘 명령 바 + 즐겨찾기 바)
    # -----------------------------------------------------------------------
    class QDirMainWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("PyQuadDir Desktop Explorer — 4분할 다중 탭 파일 탐색기")
            self.resize(1520, 940)

            self.config = load_app_config()
            self.dark_mode: bool = bool(self.config.get("dark_mode", True))
            self.color_filter_enabled: bool = bool(self.config.get("color_filter_enabled", True))
            self.color_rules: Dict[str, Dict[str, object]] = self.config.get(  # type: ignore[assignment]
                "color_rules", json.loads(json.dumps(DEFAULT_COLOR_RULES))
            )
            self.favorites: List[Dict[str, str]] = self.config.get(  # type: ignore[assignment]
                "favorites", get_default_favorites()
            )
            self.current_layout_mode: str = str(self.config.get("layout_mode", "quad"))
            self.default_view_mode: str = str(self.config.get("default_view_mode", "details"))
            self.show_icons: bool = bool(self.config.get("show_icons", True))
            self.show_file_extensions: bool = bool(self.config.get("show_file_extensions", True))
            self.show_hidden_files: bool = bool(self.config.get("show_hidden_files", False))

            self.active_pane_index: int = 0
            self.clipboard_paths: List[str] = []
            self.clipboard_mode: str = "copy"

            self._build_ui()
            self._apply_theme()
            self._refresh_toolbar_icons()
            self.set_layout_mode(self.current_layout_mode)
            self._set_active_pane(0)

        def save_config(self) -> None:
            pane_tabs = [pane.get_all_tab_paths() for pane in self.panes]
            save_app_config({
                "dark_mode": self.dark_mode,
                "color_filter_enabled": self.color_filter_enabled,
                "color_rules": self.color_rules,
                "favorites": self.favorites,
                "layout_mode": self.current_layout_mode,
                "default_view_mode": self.default_view_mode,
                "show_icons": self.show_icons,
                "show_file_extensions": self.show_file_extensions,
                "show_hidden_files": self.show_hidden_files,
                "pane_tabs": pane_tabs,
            })

        def closeEvent(self, event) -> None:
            self.save_config()
            super().closeEvent(event)

        def _build_ui(self) -> None:
            # ===============================================================
            # 1층: Windows 11 탐색기 스타일 통합 명령 바 (20x20 선명한 벡터 아이콘 적용)
            # ===============================================================
            cmd_tb = QToolBar("탐색기 명령 바")
            cmd_tb.setMovable(False)
            cmd_tb.setIconSize(QSize(20, 20))
            self.addToolBar(Qt.ToolBarArea.TopToolBarArea, cmd_tb)

            # (1) [새로 만들기 ▾]
            self.btn_new = QToolButton()
            self.btn_new.setText("새로 만들기 ▼")
            self.btn_new.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            self.btn_new.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            menu_new = QMenu(self.btn_new)
            menu_new.addAction("📁 폴더 (Ctrl+Shift+N)").triggered.connect(self._shortcut_new_folder)
            menu_new.addSeparator()
            menu_new.addAction("📝 텍스트 문서 (.txt)").triggered.connect(
                lambda: self._create_file_in_active("새 텍스트 문서.txt")
            )
            menu_new.addAction("📘 마크다운 문서 (.md)").triggered.connect(
                lambda: self._create_file_in_active("노트.md")
            )
            menu_new.addAction("🐍 Python 스크립트 (.py)").triggered.connect(
                lambda: self._create_file_in_active("script.py")
            )
            menu_new.addAction("⚙️ 배치 스크립트 (.bat)").triggered.connect(
                lambda: self._create_file_in_active("run.bat")
            )
            self.btn_new.setMenu(menu_new)
            cmd_tb.addWidget(self.btn_new)

            cmd_tb.addSeparator()

            # (2) 파일 편집 버튼들
            act_cut = QToolButton()
            act_cut.setText("✂️ 잘라내기")
            act_cut.setToolTip("선택 항목 잘라내기 (Ctrl+X)")
            act_cut.clicked.connect(self._shortcut_cut)
            cmd_tb.addWidget(act_cut)

            act_copy = QToolButton()
            act_copy.setText("📋 복사")
            act_copy.setToolTip("선택 항목 복사 (Ctrl+C)")
            act_copy.clicked.connect(self._shortcut_copy)
            cmd_tb.addWidget(act_copy)

            act_paste = QToolButton()
            act_paste.setText("📥 붙여넣기")
            act_paste.setToolTip("현재 활성 탭에 붙여넣기 (Ctrl+V)")
            act_paste.clicked.connect(self._shortcut_paste)
            cmd_tb.addWidget(act_paste)

            act_rename = QToolButton()
            act_rename.setText("✏️ 이름 바꾸기")
            act_rename.setToolTip("선택 항목 이름 바꾸기 (F2)")
            act_rename.clicked.connect(self._shortcut_rename)
            cmd_tb.addWidget(act_rename)

            btn_send = QToolButton()
            btn_send.setText("📤 다른 패널로 전송 ▼")
            btn_send.setToolTip("선택한 항목을 다른 패널(1~4번 창)로 즉시 복사하거나 이동합니다")
            btn_send.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            self.send_menu = QMenu(btn_send)
            self.send_menu.aboutToShow.connect(self._populate_send_menu)
            btn_send.setMenu(self.send_menu)
            cmd_tb.addWidget(btn_send)

            self.btn_del = QToolButton()
            self.btn_del.setText("삭제")
            self.btn_del.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            self.btn_del.setToolTip("선택 항목 삭제 (Delete)")
            self.btn_del.clicked.connect(self._shortcut_delete)
            cmd_tb.addWidget(self.btn_del)

            cmd_tb.addSeparator()

            # (3) [정렬 ▾] (선명한 상하 화살표 벡터 아이콘)
            self.btn_sort = QToolButton()
            self.btn_sort.setText("정렬 ▼")
            self.btn_sort.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            self.btn_sort.setToolTip("현재 활성 탭의 정렬 기준·방향 및 분류(그룹화) 방법을 설정합니다")
            self.btn_sort.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            self.sort_menu = QMenu(self.btn_sort)
            self.sort_menu.aboutToShow.connect(self._populate_sort_menu)
            self.btn_sort.setMenu(self.sort_menu)
            cmd_tb.addWidget(self.btn_sort)

            # (4) [보기 ▾] (선명한 2x2 그리드 벡터 아이콘)
            self.btn_view = QToolButton()
            self.btn_view.setText("보기 ▼")
            self.btn_view.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            self.btn_view.setToolTip("아이콘/썸네일 크기 전환 (Ctrl + 마우스 휠 스크롤로도 전환 가능)")
            self.btn_view.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            self.view_menu = QMenu(self.btn_view)
            self.view_menu.aboutToShow.connect(self._populate_view_menu)
            self.btn_view.setMenu(self.view_menu)
            cmd_tb.addWidget(self.btn_view)

            cmd_tb.addSeparator()

            # (5) [레이아웃 ▾] (4분할 컬러 로고 아이콘)
            self.btn_layout_menu = QToolButton()
            self.btn_layout_menu.setText("레이아웃: 4분할 ▼")
            self.btn_layout_menu.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            self.btn_layout_menu.setToolTip("화면 분할 레이아웃 전환 및 창 비율 균등화")
            self.btn_layout_menu.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            self.layout_menu = QMenu(self.btn_layout_menu)
            self._populate_layout_menu()
            self.btn_layout_menu.setMenu(self.layout_menu)
            cmd_tb.addWidget(self.btn_layout_menu)

            # (6) [💽 드라이브 ▾]
            self.btn_drive_menu = QToolButton()
            self.btn_drive_menu.setText("💽 드라이브 ▼")
            self.btn_drive_menu.setToolTip("연결된 모든 드라이브(C:, D: 등) 목록과 남은 용량을 보고 이동합니다")
            self.btn_drive_menu.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            self.drive_menu = QMenu(self.btn_drive_menu)
            self.drive_menu.aboutToShow.connect(self._populate_drive_menu)
            self.btn_drive_menu.setMenu(self.drive_menu)
            cmd_tb.addWidget(self.btn_drive_menu)

            cmd_tb.addSeparator()

            # (7) 우측: [미리 보기] & [세부 정보] (선명한 분할 창 벡터 아이콘) & [테마]
            self.btn_preview_toggle = QToolButton()
            self.btn_preview_toggle.setText("미리 보기")
            self.btn_preview_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            self.btn_preview_toggle.setToolTip("우측 미리 보기 창 켜기/끄기 (이미지 및 문서 내용 실시간 미리보기)")
            self.btn_preview_toggle.setCheckable(True)
            self.btn_preview_toggle.clicked.connect(lambda checked: self.toggle_inspector_pane("preview", checked))
            cmd_tb.addWidget(self.btn_preview_toggle)

            self.btn_details_toggle = QToolButton()
            self.btn_details_toggle.setText("세부 정보")
            self.btn_details_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            self.btn_details_toggle.setToolTip("우측 세부 정보 창 켜기/끄기 (파일 상세 메타데이터 및 해상도 표시)")
            self.btn_details_toggle.setCheckable(True)
            self.btn_details_toggle.clicked.connect(lambda checked: self.toggle_inspector_pane("details", checked))
            cmd_tb.addWidget(self.btn_details_toggle)

            self.btn_theme = QToolButton()
            self.btn_theme.setText("🌙 다크" if self.dark_mode else "☀️ 라이트")
            self.btn_theme.setToolTip("다크 / 라이트 테마 전환")
            self.btn_theme.clicked.connect(self._toggle_theme)
            cmd_tb.addWidget(self.btn_theme)

            # ===============================================================
            # 2층: 즐겨찾기(⭐) 전용 바 — 가로 전체 폭을 즐겨찾기에 온전히 할당!
            # ===============================================================
            self.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea)
            self.fav_tb = QToolBar("즐겨찾기 전용 바")
            self.fav_tb.setMovable(False)
            self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.fav_tb)
            self._rebuild_favorites_bar()

            # ===============================================================
            # 중앙 영역: 좌측 4분할 스플리터 + 우측 미리보기/세부정보 사이드 창
            # ===============================================================
            central = QWidget()
            central_layout = QHBoxLayout(central)
            central_layout.setContentsMargins(6, 6, 6, 6)
            central_layout.setSpacing(6)
            self.setCentralWidget(central)

            self.main_splitter = QSplitter(Qt.Orientation.Vertical)
            self.top_splitter = QSplitter(Qt.Orientation.Horizontal)
            self.bottom_splitter = QSplitter(Qt.Orientation.Horizontal)
            central_layout.addWidget(self.main_splitter, stretch=1)

            self.inspector_pane = InspectorPane(self)
            self.inspector_pane.hide()
            central_layout.addWidget(self.inspector_pane)

            saved_pane_tabs = self.config.get("pane_tabs", [])
            default_starts = get_initial_4_paths()

            self.panes: List[ExplorerPane] = []
            for i in range(4):
                init_tabs: List[str] = []
                if isinstance(saved_pane_tabs, list) and i < len(saved_pane_tabs):
                    candidate_list = saved_pane_tabs[i]
                    if isinstance(candidate_list, list):
                        init_tabs = [str(p) for p in candidate_list if os.path.isdir(str(p))]
                if not init_tabs:
                    init_tabs = [default_starts[i]]

                pane = ExplorerPane(i, self, initial_tabs=init_tabs)
                pane.paneActivated.connect(self._set_active_pane)
                self.panes.append(pane)

            self.setStatusBar(QStatusBar())
            self.statusBar().showMessage(
                "준비 완료 — 패널 위에서 [Ctrl + 마우스 휠]을 굴리면 보기 모드(자세히 ↔ 썸네일 아이콘)가 즉시 전환됩니다."
            )
            self._register_shortcuts()

        def _refresh_toolbar_icons(self) -> None:
            dm = self.dark_mode
            self.btn_new.setIcon(create_ui_icon("new", dm, 20))
            self.btn_del.setIcon(create_ui_icon("delete", dm, 20))
            self.btn_sort.setIcon(create_ui_icon("sort", dm, 20))
            self.btn_view.setIcon(create_ui_icon("view", dm, 20))
            self.btn_layout_menu.setIcon(create_ui_icon("layout", dm, 20))
            self.btn_preview_toggle.setIcon(create_ui_icon("preview", dm, 20))
            self.btn_details_toggle.setIcon(create_ui_icon("details", dm, 20))

        # -------------------------------------------------------------------
        # 상단 드롭다운 메뉴 동적 생성기
        # -------------------------------------------------------------------
        def _populate_send_menu(self) -> None:
            self.send_menu.clear()
            t = self.active_pane().current_tab()
            sel = t.selected_file_paths() if t else []
            if not sel:
                act_empty = self.send_menu.addAction("⚠️ 먼저 전송할 파일이나 폴더를 선택하세요")
                act_empty.setEnabled(False)
                return

            self.send_menu.addSection(f"📑 선택 항목 ({len(sel)}개) 다른 창으로 복사")
            for idx, pane in enumerate(self.panes):
                dest = pane.current_path()
                act_c = self.send_menu.addAction(f"📄 [{idx + 1}번 창]으로 복사 ({Path(dest).name or dest})")
                act_c.triggered.connect(lambda checked=False, d=dest: t._transfer_to_pane(sel, d, "copy"))  # type: ignore[union-attr]

            self.send_menu.addSeparator()
            self.send_menu.addSection(f"📦 선택 항목 ({len(sel)}개) 다른 창으로 이동")
            for idx, pane in enumerate(self.panes):
                dest = pane.current_path()
                act_m = self.send_menu.addAction(f"✂️ [{idx + 1}번 창]으로 이동 ({Path(dest).name or dest})")
                act_m.triggered.connect(lambda checked=False, d=dest: t._transfer_to_pane(sel, d, "move"))  # type: ignore[union-attr]

        def _populate_sort_menu(self) -> None:
            self.sort_menu.clear()
            t = self.active_pane().current_tab()
            curr_sort = t.sort_by if t else "name"
            curr_asc = t.sort_asc if t else True
            curr_group = t.group_by if t else "none"

            main_sorts = [
                ("name", "이름"),
                ("modified", "수정한 날짜"),
                ("type", "유형"),
                ("size", "크기"),
            ]
            for s_key, s_label in main_sorts:
                prefix = "● " if curr_sort == s_key else "    "
                act = self.sort_menu.addAction(f"{prefix}{s_label}")
                act.triggered.connect(lambda checked=False, k=s_key: self._set_active_sort(sort_by=k))

            more_menu = self.sort_menu.addMenu("    기타")
            for s_key, s_label in [("ext", "확장자"), ("created", "만든 날짜")]:
                prefix = "● " if curr_sort == s_key else "    "
                act = more_menu.addAction(f"{prefix}{s_label}")
                act.triggered.connect(lambda checked=False, k=s_key: self._set_active_sort(sort_by=k))

            self.sort_menu.addSeparator()
            act_asc = self.sort_menu.addAction(f"{'● ' if curr_asc else '    '}오름차순")
            act_desc = self.sort_menu.addAction(f"{'● ' if not curr_asc else '    '}내림차순")
            act_asc.triggered.connect(lambda: self._set_active_sort(ascending=True))
            act_desc.triggered.connect(lambda: self._set_active_sort(ascending=False))

            self.sort_menu.addSeparator()
            grp_menu = self.sort_menu.addMenu("    분류 방법")
            for g_key, g_label in [
                ("none", "없음 (기본)"),
                ("type", "유형별 그룹화"),
                ("modified", "수정한 날짜별 그룹화"),
                ("size", "크기별 그룹화"),
            ]:
                prefix = "● " if curr_group == g_key else "    "
                act_g = grp_menu.addAction(f"{prefix}{g_label}")
                act_g.triggered.connect(lambda checked=False, gk=g_key: self._set_active_group(gk))

        def _populate_view_menu(self) -> None:
            self.view_menu.clear()
            t = self.active_pane().current_tab()
            curr_mode = t.view_mode if t else self.default_view_mode

            for v_key, v_label, _ in VIEW_MODES_META:
                prefix = "● " if curr_mode == v_key else "    "
                act = self.view_menu.addAction(f"{prefix}{v_label}")
                act.triggered.connect(lambda checked=False, k=v_key: self._set_view_mode_From_menu(k))

            act_apply_all = self.view_menu.addAction("    ↳ 현재 보기 모드를 4개 패널 전체에 적용")
            act_apply_all.triggered.connect(lambda: self._apply_view_mode_all_panes(curr_mode))

            self.view_menu.addSeparator()
            is_det = self.inspector_pane.isVisible() and self.inspector_pane.mode == "details"
            is_prv = self.inspector_pane.isVisible() and self.inspector_pane.mode == "preview"

            act_det_pane = self.view_menu.addAction(f"{'● ' if is_det else '    '}📋 세부 정보 창")
            act_prv_pane = self.view_menu.addAction(f"{'● ' if is_prv else '    '}🖼️ 미리 보기 창")
            act_det_pane.triggered.connect(lambda: self.toggle_inspector_pane("details", not is_det))
            act_prv_pane.triggered.connect(lambda: self.toggle_inspector_pane("preview", not is_prv))

            self.view_menu.addSeparator()
            show_sub = self.view_menu.addMenu("    표시")

            act_icons = show_sub.addAction(f"{'✓ ' if self.show_icons else '    '}아이콘 및 썸네일 표시")
            act_icons.triggered.connect(self._toggle_show_icons)

            act_exts = show_sub.addAction(f"{'✓ ' if self.show_file_extensions else '    '}파일 확장명 표시")
            act_exts.triggered.connect(self._toggle_show_extensions)

            act_hidden = show_sub.addAction(f"{'✓ ' if self.show_hidden_files else '    '}숨긴 항목 표시")
            act_hidden.triggered.connect(self._toggle_hidden_files)

            show_sub.addSeparator()
            act_color = show_sub.addAction(f"{'✓ ' if self.color_filter_enabled else '    '}🎨 확장자별 색상 필터 켜기")
            act_color.triggered.connect(self._toggle_color_filter)

            act_color_cfg = show_sub.addAction("    ⚙️ 확장자 색상 규칙 편집...")
            act_color_cfg.triggered.connect(self._open_color_rules_dialog)

        def _populate_layout_menu(self) -> None:
            self.layout_menu.clear()
            layouts_meta = [
                ("quad", "4분할 (2×2 격자)", "Ctrl+1"),
                ("2h", "2분할 (좌/우)", "Ctrl+2"),
                ("2v", "2분할 (상/하)", "Ctrl+3"),
                ("3_left", "3분할 (좌1·우2)", "Ctrl+4"),
                ("3_top", "3분할 (상1·하2)", "Ctrl+5"),
                ("single", "1분할 (단일 최대화)", "Ctrl+6"),
            ]
            for mode_key, text, shortcut_str in layouts_meta:
                prefix = "● " if getattr(self, "current_layout_mode", "quad") == mode_key else "    "
                act = self.layout_menu.addAction(f"{prefix}{text}\t{shortcut_str}")
                act.triggered.connect(lambda checked=False, m=mode_key: self.set_layout_mode(m))

            self.layout_menu.addSeparator()
            act_eq = self.layout_menu.addAction("⚖️ 분할 창 비율 균등 정렬")
            act_eq.triggered.connect(self.equalize_splitters)

        def _populate_drive_menu(self) -> None:
            self.drive_menu.clear()
            drives = get_mounted_drives()
            if not drives:
                act = self.drive_menu.addAction("감지된 드라이브 없음")
                act.setEnabled(False)
                return

            for drv in drives:
                root = str(drv["root"])
                label = str(drv["label"])
                free_b = int(drv["free"])  # type: ignore[arg-type]
                total_b = int(drv["total"])  # type: ignore[arg-type]

                if total_b > 0:
                    pct_used = int(((total_b - free_b) / total_b) * 100)
                    text = f"💾 {root} ({label})  —  여유 {format_size(free_b)} / {format_size(total_b)} ({pct_used}%)"
                else:
                    text = f"💾 {root} ({label})"

                act = self.drive_menu.addAction(text)
                act.triggered.connect(lambda checked=False, r=root: self.active_pane().navigate_current_tab(r))

            self.drive_menu.addSeparator()
            new_tab_sub = self.drive_menu.addMenu("➕ 새 탭에서 드라이브 열기")
            for drv in drives:
                root = str(drv["root"])
                label = str(drv["label"])
                act_nt = new_tab_sub.addAction(f"💾 {root} ({label})")
                act_nt.triggered.connect(lambda checked=False, r=root: self.active_pane().add_new_tab(r))

        # -------------------------------------------------------------------
        # 즐겨찾기 바 (가로 1줄 전체 활용)
        # -------------------------------------------------------------------
        def _rebuild_favorites_bar(self) -> None:
            self.fav_tb.clear()

            lbl_fav = QLabel("  ⭐ 즐겨찾기: ")
            lbl_fav.setStyleSheet("font-weight: bold;")
            self.fav_tb.addWidget(lbl_fav)

            for idx, fav in enumerate(self.favorites):
                name = fav.get("name", "폴더")
                path = fav.get("path", "")
                btn = QToolButton()
                btn.setText(name)
                btn.setToolTip(
                    f"{path}\n• 좌클릭: 현재 활성 탭에서 이동\n• 우클릭: 새 탭으로 열기 또는 즐겨찾기 삭제"
                )
                btn.clicked.connect(lambda checked=False, p=path: self.active_pane().navigate_current_tab(p))
                btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                btn.customContextMenuRequested.connect(
                    lambda pos, i=idx, p=path, b=btn: self._show_fav_button_menu(b.mapToGlobal(pos), i, p)
                )
                self.fav_tb.addWidget(btn)

            self.fav_tb.addSeparator()
            btn_add_curr = QToolButton()
            btn_add_curr.setText("➕ 현재 폴더 추가")
            btn_add_curr.setToolTip("현재 활성 패널의 폴더를 즐겨찾기 바에 즉시 추가합니다")
            btn_add_curr.clicked.connect(lambda: self.add_favorite(self.active_pane().current_path()))
            self.fav_tb.addWidget(btn_add_curr)

            btn_manage_fav = QToolButton()
            btn_manage_fav.setText("⚙️ 즐겨찾기 편집")
            btn_manage_fav.setToolTip("즐겨찾기 폴더 목록을 추가·이름변경·순서조정·삭제합니다")
            btn_manage_fav.clicked.connect(self._open_favorites_dialog)
            self.fav_tb.addWidget(btn_manage_fav)

        def _show_fav_button_menu(self, global_pos: QPoint, fav_idx: int, path_str: str) -> None:
            menu = QMenu(self)
            act_open = menu.addAction("📂 현재 활성 탭에서 열기")
            act_new_tab = menu.addAction("➕ 활성 패널의 새 탭으로 열기")
            menu.addSeparator()
            act_remove = menu.addAction("🗑️ 이 즐겨찾기 삭제")

            chosen = menu.exec(global_pos)
            if chosen == act_open:
                self.active_pane().navigate_current_tab(path_str)
            elif chosen == act_new_tab:
                self.active_pane().add_new_tab(path_str)
            elif chosen == act_remove and 0 <= fav_idx < len(self.favorites):
                self.favorites.pop(fav_idx)
                self._rebuild_favorites_bar()
                self.save_config()

        # -------------------------------------------------------------------
        # 미리 보기 창 / 세부 정보 창 제어
        # -------------------------------------------------------------------
        def toggle_inspector_pane(self, mode: str, show: bool) -> None:
            if show:
                self.inspector_pane.set_mode(mode)
                self.inspector_pane.show()
                self.btn_preview_toggle.setChecked(mode == "preview")
                self.btn_details_toggle.setChecked(mode == "details")
                t = self.active_pane().current_tab()
                sel = t.selected_file_paths() if t else []
                self.inspector_pane.inspect_path(sel[0] if sel else (t.current_path if t else ""))
            else:
                self.close_inspector_pane()

        def close_inspector_pane(self) -> None:
            self.inspector_pane.hide()
            self.btn_preview_toggle.setChecked(False)
            self.btn_details_toggle.setChecked(False)

        def on_active_selection_changed(self, first_selected_path: str) -> None:
            if self.inspector_pane.isVisible():
                target = first_selected_path or self.active_pane().current_path()
                self.inspector_pane.inspect_path(target)

        # -------------------------------------------------------------------
        # 보기 / 정렬 / 표시 옵션 핸들러
        # -------------------------------------------------------------------
        def _set_active_sort(
            self, sort_by: Optional[str] = None, ascending: Optional[bool] = None
        ) -> None:
            t = self.active_pane().current_tab()
            if t:
                t.set_sort(sort_by=sort_by, ascending=ascending)

        def _set_active_group(self, group_by: str) -> None:
            t = self.active_pane().current_tab()
            if t:
                t.set_group_by(group_by)

        def _set_view_mode_From_menu(self, mode: str) -> None:
            self.default_view_mode = mode
            t = self.active_pane().current_tab()
            if t:
                t.set_view_mode(mode)
            self.save_config()

        def _apply_view_mode_all_panes(self, mode: str) -> None:
            self.default_view_mode = mode
            for pane in self.panes:
                for i in range(pane.tab_widget.count()):
                    w = pane.tab_widget.widget(i)
                    if isinstance(w, DirectoryTab):
                        w.set_view_mode(mode)
            self.save_config()

        def _toggle_show_icons(self) -> None:
            self.show_icons = not self.show_icons
            self.refresh_all_panes()
            self.save_config()

        def _toggle_show_extensions(self) -> None:
            self.show_file_extensions = not self.show_file_extensions
            self.refresh_all_panes()
            self.save_config()

        def _toggle_hidden_files(self) -> None:
            self.show_hidden_files = not self.show_hidden_files
            self.refresh_all_panes()
            self.save_config()

        def _toggle_color_filter(self) -> None:
            self.color_filter_enabled = not self.color_filter_enabled
            self.refresh_all_panes()
            self.save_config()

        def _create_file_in_active(self, default_name: str) -> None:
            t = self.active_pane().current_tab()
            if t:
                t.create_new_text_file(default_name)

        # -------------------------------------------------------------------
        # 레이아웃 및 기본 동작
        # -------------------------------------------------------------------
        def _register_shortcuts(self) -> None:
            QShortcut(QKeySequence("Ctrl+1"), self, activated=lambda: self.set_layout_mode("quad"))
            QShortcut(QKeySequence("Ctrl+2"), self, activated=lambda: self.set_layout_mode("2h"))
            QShortcut(QKeySequence("Ctrl+3"), self, activated=lambda: self.set_layout_mode("2v"))
            QShortcut(QKeySequence("Ctrl+4"), self, activated=lambda: self.set_layout_mode("3_left"))
            QShortcut(QKeySequence("Ctrl+5"), self, activated=lambda: self.set_layout_mode("3_top"))
            QShortcut(QKeySequence("Ctrl+6"), self, activated=lambda: self.set_layout_mode("single"))

            QShortcut(QKeySequence("Ctrl+T"), self, activated=self._shortcut_new_tab)
            QShortcut(QKeySequence("Ctrl+W"), self, activated=self._shortcut_close_tab)
            QShortcut(QKeySequence("F5"), self, activated=self.refresh_all_panes)
            QShortcut(QKeySequence("F2"), self, activated=self._shortcut_rename)
            QShortcut(QKeySequence("Delete"), self, activated=self._shortcut_delete)
            QShortcut(QKeySequence("Ctrl+Shift+N"), self, activated=self._shortcut_new_folder)
            QShortcut(QKeySequence("Ctrl+C"), self, activated=self._shortcut_copy)
            QShortcut(QKeySequence("Ctrl+X"), self, activated=self._shortcut_cut)
            QShortcut(QKeySequence("Ctrl+V"), self, activated=self._shortcut_paste)
            QShortcut(QKeySequence("Backspace"), self, activated=self._shortcut_up)
            QShortcut(QKeySequence("Alt+Left"), self, activated=self._shortcut_back)
            QShortcut(QKeySequence("Alt+Right"), self, activated=self._shortcut_forward)
            QShortcut(QKeySequence("Alt+Up"), self, activated=self._shortcut_up)

        def active_pane(self) -> ExplorerPane:
            return self.panes[self.active_pane_index]

        def _set_active_pane(self, index: int) -> None:
            if 0 <= index < len(self.panes):
                self.active_pane_index = index
                for i, p in enumerate(self.panes):
                    p.set_active_visual(i == index)
                t = self.panes[index].current_tab()
                if t and self.inspector_pane.isVisible():
                    sel = t.selected_file_paths()
                    self.inspector_pane.inspect_path(sel[0] if sel else t.current_path)

        def set_layout_mode(self, mode: str) -> None:
            self.current_layout_mode = mode
            short_names = {
                "quad": "4분할(2×2)",
                "2h": "2분할(좌/우)",
                "2v": "2분할(상/하)",
                "3_left": "3분할(좌1·우2)",
                "3_top": "3분할(상1·하2)",
                "single": "1분할(단일)",
            }
            self.btn_layout_menu.setText(f"레이아웃: {short_names.get(mode, '4분할')} ▼")
            self._populate_layout_menu()

            for p in self.panes:
                p.setParent(None)
                p.hide()
            self.top_splitter.setParent(None)
            self.bottom_splitter.setParent(None)

            if mode == "quad":
                self.main_splitter.setOrientation(Qt.Orientation.Vertical)
                self.top_splitter.setOrientation(Qt.Orientation.Horizontal)
                self.bottom_splitter.setOrientation(Qt.Orientation.Horizontal)

                self.top_splitter.addWidget(self.panes[0])
                self.top_splitter.addWidget(self.panes[1])
                self.bottom_splitter.addWidget(self.panes[2])
                self.bottom_splitter.addWidget(self.panes[3])

                self.main_splitter.addWidget(self.top_splitter)
                self.main_splitter.addWidget(self.bottom_splitter)
                self.top_splitter.show()
                self.bottom_splitter.show()
                for p in self.panes:
                    p.show()

            elif mode == "2h":
                self.main_splitter.setOrientation(Qt.Orientation.Horizontal)
                self.main_splitter.addWidget(self.panes[0])
                self.main_splitter.addWidget(self.panes[1])
                self.panes[0].show()
                self.panes[1].show()

            elif mode == "2v":
                self.main_splitter.setOrientation(Qt.Orientation.Vertical)
                self.main_splitter.addWidget(self.panes[0])
                self.main_splitter.addWidget(self.panes[1])
                self.panes[0].show()
                self.panes[1].show()

            elif mode == "3_left":
                self.main_splitter.setOrientation(Qt.Orientation.Horizontal)
                self.bottom_splitter.setOrientation(Qt.Orientation.Vertical)
                self.bottom_splitter.addWidget(self.panes[1])
                self.bottom_splitter.addWidget(self.panes[2])
                self.main_splitter.addWidget(self.panes[0])
                self.main_splitter.addWidget(self.bottom_splitter)
                self.bottom_splitter.show()
                for i in (0, 1, 2):
                    self.panes[i].show()

            elif mode == "3_top":
                self.main_splitter.setOrientation(Qt.Orientation.Vertical)
                self.bottom_splitter.setOrientation(Qt.Orientation.Horizontal)
                self.bottom_splitter.addWidget(self.panes[1])
                self.bottom_splitter.addWidget(self.panes[2])
                self.main_splitter.addWidget(self.panes[0])
                self.main_splitter.addWidget(self.bottom_splitter)
                self.bottom_splitter.show()
                for i in (0, 1, 2):
                    self.panes[i].show()

            elif mode == "single":
                self.main_splitter.setOrientation(Qt.Orientation.Horizontal)
                target_pane = self.panes[self.active_pane_index]
                self.main_splitter.addWidget(target_pane)
                target_pane.show()

            self.equalize_splitters()

        def equalize_splitters(self) -> None:
            if self.main_splitter.count() == 2:
                self.main_splitter.setSizes([500, 500])
            if self.top_splitter.count() == 2:
                self.top_splitter.setSizes([500, 500])
            if self.bottom_splitter.count() == 2:
                self.bottom_splitter.setSizes([500, 500])

        def add_favorite(self, path_str: str) -> None:
            norm = str(Path(path_str).resolve())
            for fav in self.favorites:
                if fav.get("path") == norm:
                    QMessageBox.information(self, "즐겨찾기", "이미 즐겨찾기에 등록된 폴더입니다.")
                    return
            default_name = f"⭐ {Path(norm).name or norm}"
            name, ok = QInputDialog.getText(
                self, "즐겨찾기 추가", "상단 즐겨찾기 바에 표시할 이름:", text=default_name
            )
            if ok and name.strip():
                self.favorites.append({"name": name.strip(), "path": norm})
                self._rebuild_favorites_bar()
                self.save_config()

        def _open_favorites_dialog(self) -> None:
            dlg = FavoritesDialog(self.favorites, self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self.favorites = dlg.favorites
                self._rebuild_favorites_bar()
                self.save_config()

        def get_color_for_entry(self, is_dir: bool, ext: str) -> Optional[QColor]:
            hex_c = match_color_hex(
                self.color_rules, self.dark_mode, self.color_filter_enabled, is_dir, ext
            )
            return QColor(hex_c) if hex_c else None

        def _open_color_rules_dialog(self) -> None:
            dlg = ColorRulesDialog(self.color_rules, self.dark_mode, self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self.color_rules = dlg.rules
                self.refresh_all_panes()
                self.save_config()

        def set_clipboard_files(self, paths: List[str], mode: str) -> None:
            self.clipboard_paths = list(paths)
            self.clipboard_mode = mode
            action_kr = "잘라내기(이동 대기)" if mode == "move" else "복사 대기"
            self.statusBar().showMessage(f"📋 {len(paths)}개 항목 {action_kr} 설정됨 (Ctrl+V로 붙여넣기)", 4000)

        def refresh_all_panes(self) -> None:
            self._rebuild_favorites_bar()
            for pane in self.panes:
                pane.refresh_all_tabs()

        def _toggle_theme(self) -> None:
            self.dark_mode = not self.dark_mode
            self.btn_theme.setText("🌙 다크" if self.dark_mode else "☀️ 라이트")
            self._apply_theme()
            self._refresh_toolbar_icons()
            self.refresh_all_panes()
            self.save_config()

        def _shortcut_new_tab(self) -> None:
            p = self.active_pane()
            p.add_new_tab(p.current_path())

        def _shortcut_close_tab(self) -> None:
            p = self.active_pane()
            p.close_tab(p.tab_widget.currentIndex())

        def _shortcut_rename(self) -> None:
            t = self.active_pane().current_tab()
            if t:
                t.rename_selected_item()

        def _shortcut_delete(self) -> None:
            t = self.active_pane().current_tab()
            if t:
                t.delete_selected_items()

        def _shortcut_new_folder(self) -> None:
            t = self.active_pane().current_tab()
            if t:
                t.create_new_folder()

        def _shortcut_copy(self) -> None:
            t = self.active_pane().current_tab()
            if t:
                sel = t.selected_file_paths()
                if sel:
                    self.set_clipboard_files(sel, "copy")

        def _shortcut_cut(self) -> None:
            t = self.active_pane().current_tab()
            if t:
                sel = t.selected_file_paths()
                if sel:
                    self.set_clipboard_files(sel, "move")

        def _shortcut_paste(self) -> None:
            t = self.active_pane().current_tab()
            if t:
                t.paste_files_here()

        def _shortcut_up(self) -> None:
            t = self.active_pane().current_tab()
            if t and not t.address_edit.hasFocus() and not t.filter_edit.hasFocus():
                t.go_up()

        def _shortcut_back(self) -> None:
            t = self.active_pane().current_tab()
            if t:
                t.go_back()

        def _shortcut_forward(self) -> None:
            t = self.active_pane().current_tab()
            if t:
                t.go_forward()

        def keyPressEvent(self, event) -> None:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                t = self.active_pane().current_tab()
                if t and not t.address_edit.hasFocus() and not t.filter_edit.hasFocus():
                    t.activate_selected_or_current()
                    event.accept()
                    return
            super().keyPressEvent(event)

        def _apply_theme(self) -> None:
            if self.dark_mode:
                qss = """
                QMainWindow, QDialog { background-color: #0F172A; color: #E2E8F0; }
                QToolBar { background-color: #1E293B; border-bottom: 1px solid #334155; spacing: 5px; padding: 4px; }
                QToolButton { background-color: transparent; color: #E2E8F0; border: 1px solid transparent; border-radius: 5px; padding: 5px 9px; font-size: 13px; }
                QToolButton:hover { background-color: #334155; border: 1px solid #475569; }
                QToolButton:checked { background-color: #2563EB; color: #FFFFFF; font-weight: bold; }
                QToolButton::menu-indicator { image: none; width: 0px; }
                QFrame#ExplorerPane, QFrame#InspectorPane { background-color: #1E293B; border: 2px solid #334155; border-radius: 7px; }
                QFrame#ExplorerPane[activePane="true"] { border: 2px solid #38BDF8; }
                QLabel#PaneBadge { background-color: #2563EB; color: #FFFFFF; font-weight: bold; border-radius: 4px; padding: 1px 5px; }
                QLabel#PaneTitlePath, QLabel#PaneSummaryLabel { color: #94A3B8; font-size: 11px; padding: 2px 4px; }
                QLineEdit, QPlainTextEdit { background-color: #0F172A; color: #F8FAFC; border: 1px solid #475569; border-radius: 4px; padding: 4px 6px; selection-background-color: #2563EB; font-size: 12px; }
                QLineEdit:focus { border: 1px solid #38BDF8; }
                QTabWidget::pane { border: 1px solid #334155; background-color: #0F172A; }
                QTabBar::tab { background-color: #1E293B; color: #94A3B8; border: 1px solid #334155; border-bottom: none; border-top-left-radius: 5px; border-top-right-radius: 5px; padding: 5px 10px; margin-right: 2px; font-size: 12px; }
                QTabBar::tab:selected { background-color: #0F172A; color: #38BDF8; font-weight: bold; }
                QTableWidget, QListWidget { background-color: #0F172A; alternate-background-color: #131D31; color: #E2E8F0; border: none; selection-background-color: #1D4ED8; selection-color: #FFFFFF; font-size: 12px; }
                QHeaderView::section { background-color: #1E293B; color: #CBD5E1; border: none; border-right: 1px solid #334155; border-bottom: 1px solid #334155; padding: 4px 6px; font-weight: bold; }
                QSplitter::handle { background-color: #334155; }
                QSplitter::handle:hover { background-color: #38BDF8; }
                QStatusBar { background-color: #1E293B; color: #CBD5E1; border-top: 1px solid #334155; }
                QMenu { background-color: #1E293B; color: #F8FAFC; border: 1px solid #475569; padding: 4px; font-size: 12px; }
                QMenu::item { padding: 5px 22px 5px 12px; border-radius: 4px; }
                QMenu::item:selected { background-color: #2563EB; color: #FFFFFF; }
                """
            else:
                qss = """
                QMainWindow, QDialog { background-color: #F1F5F9; color: #0F172A; }
                QToolBar { background-color: #FFFFFF; border-bottom: 1px solid #CBD5E1; spacing: 5px; padding: 4px; }
                QToolButton { background-color: transparent; color: #1E293B; border: 1px solid transparent; border-radius: 5px; padding: 5px 9px; font-size: 13px; }
                QToolButton:hover { background-color: #E2E8F0; border: 1px solid #CBD5E1; }
                QToolButton:checked { background-color: #2563EB; color: #FFFFFF; font-weight: bold; }
                QToolButton::menu-indicator { image: none; width: 0px; }
                QFrame#ExplorerPane, QFrame#InspectorPane { background-color: #FFFFFF; border: 2px solid #CBD5E1; border-radius: 7px; }
                QFrame#ExplorerPane[activePane="true"] { border: 2px solid #2563EB; }
                QLabel#PaneBadge { background-color: #2563EB; color: #FFFFFF; font-weight: bold; border-radius: 4px; padding: 1px 5px; }
                QLabel#PaneTitlePath, QLabel#PaneSummaryLabel { color: #475569; font-size: 11px; padding: 2px 4px; }
                QLineEdit, QPlainTextEdit { background-color: #F8FAFC; color: #0F172A; border: 1px solid #CBD5E1; border-radius: 4px; padding: 4px 6px; font-size: 12px; }
                QLineEdit:focus { border: 1px solid #2563EB; }
                QTabWidget::pane { border: 1px solid #CBD5E1; background-color: #FFFFFF; }
                QTabBar::tab { background-color: #E2E8F0; color: #475569; border: 1px solid #CBD5E1; border-bottom: none; border-top-left-radius: 5px; border-top-right-radius: 5px; padding: 5px 10px; margin-right: 2px; font-size: 12px; }
                QTabBar::tab:selected { background-color: #FFFFFF; color: #1D4ED8; font-weight: bold; }
                QTableWidget, QListWidget { background-color: #FFFFFF; alternate-background-color: #F8FAFC; color: #0F172A; border: none; selection-background-color: #2563EB; selection-color: #FFFFFF; font-size: 12px; }
                QHeaderView::section { background-color: #F1F5F9; color: #334155; border: none; border-right: 1px solid #CBD5E1; border-bottom: 1px solid #CBD5E1; padding: 4px 6px; font-weight: bold; }
                QSplitter::handle { background-color: #CBD5E1; }
                QSplitter::handle:hover { background-color: #2563EB; }
                QStatusBar { background-color: #FFFFFF; color: #334155; border-top: 1px solid #CBD5E1; }
                QMenu { background-color: #FFFFFF; color: #0F172A; border: 1px solid #CBD5E1; padding: 4px; font-size: 12px; }
                QMenu::item { padding: 5px 22px 5px 12px; border-radius: 4px; }
                QMenu::item:selected { background-color: #2563EB; color: #FFFFFF; }
                """
            self.setStyleSheet(qss)

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("PyQuadDir Desktop Explorer")
    font = QFont("Malgun Gothic", 9) if platform.system() == "Windows" else QFont("Sans Serif", 10)
    app.setFont(font)

    win = QDirMainWindow()
    win.show()
    sys.exit(app.exec())


# ===========================================================================
# 2. 내장 Tkinter (ttk) 폴백 엔진 (Ctrl+마우스 휠 행 높이 확대/축소 지원)
# ===========================================================================
def run_tkinter_app() -> None:
    import tkinter as tk
    from tkinter import messagebox, simpledialog, ttk

    class TkDirectoryTab(ttk.Frame):
        def __init__(self, parent_notebook: ttk.Notebook, app: "TkQDirApp", pane_idx: int, initial_path: str):
            super().__init__(parent_notebook)
            self.app = app
            self.pane_idx = pane_idx
            self.current_path = str(Path(initial_path).resolve()) if os.path.isdir(initial_path) else str(Path.home())
            self.history: List[str] = [self.current_path]
            self.history_idx: int = 0

            self._build_ui()
            self.refresh()

        def _build_ui(self) -> None:
            nav = ttk.Frame(self)
            nav.pack(fill=tk.X, padx=3, pady=3)

            ttk.Button(nav, text="⬅️", width=3, command=self.go_back).pack(side=tk.LEFT, padx=1)
            ttk.Button(nav, text="➡️", width=3, command=self.go_forward).pack(side=tk.LEFT, padx=1)
            ttk.Button(nav, text="⬆️", width=3, command=self.go_up).pack(side=tk.LEFT, padx=1)
            ttk.Button(nav, text="🔄", width=3, command=self.refresh).pack(side=tk.LEFT, padx=1)

            self.addr_var = tk.StringVar(value=self.current_path)
            addr_entry = ttk.Entry(nav, textvariable=self.addr_var)
            addr_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)
            addr_entry.bind("<Return>", lambda e: self.navigate_to(self.addr_var.get()))

            ttk.Button(nav, text="⭐", width=3, command=lambda: self.app.add_favorite(self.current_path)).pack(side=tk.LEFT, padx=1)

            self.filter_var = tk.StringVar()
            self.filter_var.trace_add("write", lambda *_: self.refresh())
            filter_entry = ttk.Entry(nav, textvariable=self.filter_var, width=14)
            filter_entry.pack(side=tk.LEFT, padx=2)

            tree_frame = ttk.Frame(self)
            tree_frame.pack(fill=tk.BOTH, expand=True, padx=3, pady=1)

            cols = ("name", "size", "type", "modified")
            self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="extended")
            self.tree.heading("name", text="이름")
            self.tree.heading("size", text="크기")
            self.tree.heading("type", text="유형")
            self.tree.heading("modified", text="수정한 날짜")

            self.tree.column("name", width=220, stretch=True)
            self.tree.column("size", width=85, anchor=tk.E, stretch=False)
            self.tree.column("type", width=90, stretch=False)
            self.tree.column("modified", width=130, stretch=False)

            vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
            self.tree.configure(yscrollcommand=vsb.set)
            self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            vsb.pack(side=tk.RIGHT, fill=tk.Y)

            self.summary_var = tk.StringVar(value="")
            ttk.Label(self, textvariable=self.summary_var).pack(fill=tk.X, padx=4, pady=2)

            self.tree.bind("<FocusIn>", lambda e: self.app.set_active_pane(self.pane_idx))
            self.tree.bind("<Double-1>", self._on_double_click)
            self.tree.bind("<Return>", self._on_enter_key)
            self.tree.bind("<KP_Enter>", self._on_enter_key)
            self.tree.bind("<BackSpace>", lambda e: self.go_up())
            self.tree.bind("<ButtonPress-1>", self._on_drag_start)
            self.tree.bind("<ButtonRelease-1>", self._on_drag_drop)
            self.tree.bind("<Button-3>", self._on_right_click)
            self.tree.bind("<Control-a>", self._on_select_all)
            self.tree.bind("<Control-A>", self._on_select_all)
            self.tree.bind("<Control-MouseWheel>", self._on_ctrl_wheel)
            self.tree.bind("<<TreeviewSelect>>", self._unselect_parent_if_multi)

        def _on_ctrl_wheel(self, event) -> str:
            step = 1 if event.delta > 0 else -1
            self.app.step_font_zoom(step)
            return "break"

        def _on_select_all(self, event) -> str:
            items = [i for i in self.tree.get_children() if i != "..parent.."]
            self.tree.selection_set(items)
            return "break"

        def _unselect_parent_if_multi(self, event) -> None:
            sel = list(self.tree.selection())
            if len(sel) > 1 and "..parent.." in sel:
                sel.remove("..parent..")
                self.tree.selection_set(sel)

        def navigate_to(self, path_str: str, record: bool = True) -> None:
            p = Path(os.path.expandvars(os.path.expanduser(path_str.strip())))
            if not p.is_dir():
                messagebox.showwarning("경로 오류", f"폴더를 찾을 수 없습니다:\n{path_str}")
                self.addr_var.set(self.current_path)
                return
            self.current_path = str(p.resolve())
            self.addr_var.set(self.current_path)
            if record:
                self.history = self.history[: self.history_idx + 1]
                self.history.append(self.current_path)
                self.history_idx = len(self.history) - 1
            self.refresh()
            self.app.update_tab_title(self.pane_idx, self)

        def go_back(self) -> None:
            if self.history_idx > 0:
                self.history_idx -= 1
                self.navigate_to(self.history[self.history_idx], record=False)

        def go_forward(self) -> None:
            if self.history_idx < len(self.history) - 1:
                self.history_idx += 1
                self.navigate_to(self.history[self.history_idx], record=False)

        def go_up(self) -> None:
            p = Path(self.current_path)
            if p.parent != p:
                self.navigate_to(str(p.parent))

        def refresh(self) -> None:
            for item in self.tree.get_children():
                self.tree.delete(item)

            p = Path(self.current_path)
            kw = self.filter_var.get().strip().lower()

            if p.parent != p:
                self.tree.insert("", tk.END, iid="..parent..", values=("📁 .. (상위 폴더)", "", "상위 폴더", ""), tags=("parent",))

            entries: List[os.DirEntry] = []
            try:
                with os.scandir(p) as it:
                    for e in it:
                        if kw and kw not in e.name.lower():
                            continue
                        entries.append(e)
            except Exception as exc:
                self.summary_var.set(f"⚠️ 접근 불가: {exc}")
                return

            entries.sort(key=lambda x: (not x.is_dir(follow_symlinks=False), x.name.lower()))
            dir_cnt, file_cnt, total_b = 0, 0, 0

            for e in entries:
                is_dir = e.is_dir(follow_symlinks=False)
                ext = "" if is_dir else Path(e.name).suffix.lower()
                try:
                    st = e.stat(follow_symlinks=False)
                    sz = 0 if is_dir else st.st_size
                    dt = datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")
                except Exception:
                    sz, dt = 0, "-"

                if is_dir:
                    dir_cnt += 1
                    disp_name = f"📁 {e.name}"
                    sz_str, tp_str = "<DIR>", "폴더"
                else:
                    file_cnt += 1
                    total_b += sz
                    disp_name = f"📄 {e.name}"
                    sz_str = format_size(sz)
                    tp_str = f"{ext[1:].upper()} 파일" if ext else "파일"

                hex_c = match_color_hex(
                    self.app.color_rules,
                    self.app.dark_mode,
                    self.app.color_filter_enabled,
                    is_dir,
                    ext,
                )
                tag_name = f"color_{hex_c}" if hex_c else ""
                if hex_c:
                    self.tree.tag_configure(tag_name, foreground=hex_c)

                self.tree.insert(
                    "",
                    tk.END,
                    iid=e.path,
                    values=(disp_name, sz_str, tp_str, dt),
                    tags=(tag_name,) if tag_name else (),
                )

            free_b, _ = _safe_disk_usage(self.current_path)
            self.summary_var.set(
                f"폴더 {dir_cnt}개, 파일 {file_cnt}개 ({format_size(total_b)}) | 여유 {format_size(free_b)}"
            )

        def selected_paths(self) -> List[str]:
            return [iid for iid in self.tree.selection() if iid != "..parent.." and os.path.exists(iid)]

        def _on_enter_key(self, event) -> str:
            sel = self.tree.selection()
            if not sel:
                focus_id = self.tree.focus()
                if focus_id:
                    sel = (focus_id,)
            if not sel:
                return "break"
            first = sel[0]
            if first == "..parent..":
                self.go_up()
            elif os.path.isdir(first):
                self.navigate_to(first)
            else:
                for iid in sel:
                    if iid != "..parent.." and os.path.isfile(iid):
                        open_path_with_os(iid)
            return "break"

        def _on_double_click(self, event) -> None:
            item_id = self.tree.identify_row(event.y)
            if item_id == "..parent..":
                self.go_up()
                return
            sel = self.tree.selection()
            if not sel:
                return
            iid = sel[0]
            if iid == "..parent..":
                self.go_up()
            elif os.path.isdir(iid):
                self.navigate_to(iid)
            elif os.path.exists(iid):
                open_path_with_os(iid)

        def _on_drag_start(self, event) -> None:
            self.app.set_active_pane(self.pane_idx)
            self.app.drag_source_tab = self

        def _on_drag_drop(self, event) -> None:
            src_tab = self.app.drag_source_tab
            self.app.drag_source_tab = None
            if not src_tab:
                return
            w = self.winfo_containing(event.x_root, event.y_root)
            if w is None:
                return
            target_tab: Optional[TkDirectoryTab] = None
            curr = w
            while curr is not None:
                if isinstance(curr, TkDirectoryTab):
                    target_tab = curr
                    break
                curr = getattr(curr, "master", None)

            if target_tab is not None and target_tab is not src_tab:
                paths = src_tab.selected_paths()
                if paths:
                    self.app.transfer_files_tk(paths, target_tab.current_path)

        def _on_right_click(self, event) -> None:
            self.app.set_active_pane(self.pane_idx)
            paths = self.selected_paths()
            menu = tk.Menu(self, tearoff=0)
            if len(paths) == 1 and os.path.isdir(paths[0]):
                menu.add_command(label="➕ 새 탭에서 폴더 열기", command=lambda: self.app.add_tab(self.pane_idx, paths[0]))
            if paths:
                for i in range(4):
                    dest = self.app.get_pane_current_path(i)
                    menu.add_command(
                        label=f"📑 [{i+1}번 창]으로 복사 ({Path(dest).name or dest})",
                        command=lambda d=dest: self.app.transfer_files_tk(paths, d, "copy"),
                    )
                    menu.add_command(
                        label=f"📦 [{i+1}번 창]으로 이동 ({Path(dest).name or dest})",
                        command=lambda d=dest: self.app.transfer_files_tk(paths, d, "move"),
                    )
                menu.add_separator()
                menu.add_command(label="🗑️ 선택 항목 삭제", command=lambda: self._delete_paths(paths))
            menu.add_separator()
            menu.add_command(label="📁 새 폴더 만들기", command=self._new_folder)
            menu.tk_popup(event.x_root, event.y_root)

        def _new_folder(self) -> None:
            name = simpledialog.askstring("새 폴더", "새 폴더 이름:", initialvalue="새 폴더")
            if name and name.strip():
                try:
                    (Path(self.current_path) / name.strip()).mkdir()
                    self.refresh()
                except Exception as exc:
                    messagebox.showwarning("오류", str(exc))

        def _delete_paths(self, paths: List[str]) -> None:
            if not messagebox.askyesno("삭제 확인", f"{len(paths)}개 항목을 삭제하시겠습니까?"):
                return
            for p_str in paths:
                p = Path(p_str)
                try:
                    if p.is_dir():
                        shutil.rmtree(p)
                    else:
                        p.unlink()
                except Exception as exc:
                    messagebox.showwarning("삭제 오류", str(exc))
            self.app.refresh_all()

    class TkQDirApp:
        def __init__(self) -> None:
            self.root = tk.Tk()
            self.root.title("PyQuadDir Desktop Explorer (Tkinter Engine)")
            self.root.geometry("1440x880")

            self.config = load_app_config()
            self.dark_mode = bool(self.config.get("dark_mode", False))
            self.color_filter_enabled = bool(self.config.get("color_filter_enabled", True))
            self.color_rules: Dict[str, Dict[str, object]] = self.config.get(  # type: ignore[assignment]
                "color_rules", json.loads(json.dumps(DEFAULT_COLOR_RULES))
            )
            self.favorites: List[Dict[str, str]] = self.config.get(  # type: ignore[assignment]
                "favorites", get_default_favorites()
            )
            self.active_pane_idx = 0
            self.drag_source_tab: Optional[TkDirectoryTab] = None
            self.font_size = 10
            self.style = ttk.Style(self.root)

            self._build_ui()

        def step_font_zoom(self, step: int) -> None:
            self.font_size = max(9, min(18, self.font_size + step))
            self.style.configure("Treeview", font=("Malgun Gothic", self.font_size), rowheight=self.font_size * 2 + 8)

        def _build_ui(self) -> None:
            top_bar = ttk.Frame(self.root)
            top_bar.pack(fill=tk.X, padx=4, pady=3)

            mb_layout = ttk.Menubutton(top_bar, text="📐 레이아웃 ▼")
            m_layout = tk.Menu(mb_layout, tearoff=0)
            for key, label in [
                ("quad", "4분할 (2×2)"),
                ("2h", "2분할 (좌/우)"),
                ("2v", "2분할 (상/하)"),
                ("single", "1분할 (단일)"),
            ]:
                m_layout.add_command(label=label, command=lambda m=key: self.set_layout(m))
            mb_layout["menu"] = m_layout
            mb_layout.pack(side=tk.LEFT, padx=3)

            mb_drive = ttk.Menubutton(top_bar, text="💽 드라이브 ▼")
            m_drive = tk.Menu(mb_drive, tearoff=0)
            for d in get_mounted_drives():
                r = str(d["root"])
                lbl = str(d["label"])
                free_b = int(d["free"])  # type: ignore[arg-type]
                m_drive.add_command(
                    label=f"💾 {r} ({lbl}) — 여유 {format_size(free_b)}",
                    command=lambda p=r: self.navigate_active(p),
                )
            mb_drive["menu"] = m_drive
            mb_drive.pack(side=tk.LEFT, padx=3)

            ttk.Button(top_bar, text="🎨 색상 필터 토글", command=self._toggle_color).pack(side=tk.LEFT, padx=6)

            self.fav_bar = ttk.Frame(self.root)
            self.fav_bar.pack(fill=tk.X, padx=4, pady=2)
            self._rebuild_fav_bar()

            self.grid_frame = ttk.Frame(self.root)
            self.grid_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
            for r in range(2):
                self.grid_frame.rowconfigure(r, weight=1)
            for c in range(2):
                self.grid_frame.columnconfigure(c, weight=1)

            self.pane_frames: List[ttk.LabelFrame] = []
            self.notebooks: List[ttk.Notebook] = []
            starts = get_initial_4_paths()

            for i in range(4):
                lf = ttk.LabelFrame(self.grid_frame, text=f" 패널 #{i+1} ")
                hdr = ttk.Frame(lf)
                hdr.pack(fill=tk.X, padx=2, pady=1)
                ttk.Button(hdr, text="➕ 새 탭", command=lambda idx=i: self.add_tab(idx, self.get_pane_current_path(idx))).pack(side=tk.RIGHT)

                nb = ttk.Notebook(lf)
                nb.pack(fill=tk.BOTH, expand=True)
                self.pane_frames.append(lf)
                self.notebooks.append(nb)
                self.add_tab(i, starts[i])

            self.set_layout("quad")

        def _rebuild_fav_bar(self) -> None:
            for w in self.fav_bar.winfo_children():
                w.destroy()
            ttk.Label(self.fav_bar, text="⭐ 즐겨찾기:").pack(side=tk.LEFT, padx=4)
            for f in self.favorites:
                ttk.Button(
                    self.fav_bar,
                    text=f.get("name", "폴더"),
                    command=lambda p=f.get("path", ""): self.navigate_active(p),
                ).pack(side=tk.LEFT, padx=2)

        def set_layout(self, mode: str) -> None:
            for lf in self.pane_frames:
                lf.grid_forget()
            if mode == "quad":
                self.pane_frames[0].grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
                self.pane_frames[1].grid(row=0, column=1, sticky="nsew", padx=2, pady=2)
                self.pane_frames[2].grid(row=1, column=0, sticky="nsew", padx=2, pady=2)
                self.pane_frames[3].grid(row=1, column=1, sticky="nsew", padx=2, pady=2)
            elif mode == "2h":
                self.pane_frames[0].grid(row=0, column=0, rowspan=2, sticky="nsew", padx=2, pady=2)
                self.pane_frames[1].grid(row=0, column=1, rowspan=2, sticky="nsew", padx=2, pady=2)
            elif mode == "2v":
                self.pane_frames[0].grid(row=0, column=0, columnspan=2, sticky="nsew", padx=2, pady=2)
                self.pane_frames[1].grid(row=1, column=0, columnspan=2, sticky="nsew", padx=2, pady=2)
            elif mode == "single":
                self.pane_frames[self.active_pane_idx].grid(row=0, column=0, rowspan=2, columnspan=2, sticky="nsew", padx=2, pady=2)

        def set_active_pane(self, idx: int) -> None:
            self.active_pane_idx = idx

        def add_tab(self, pane_idx: int, path_str: str) -> None:
            nb = self.notebooks[pane_idx]
            tab = TkDirectoryTab(nb, self, pane_idx, path_str)
            short = Path(tab.current_path).name or tab.current_path
            nb.add(tab, text=short[:16])
            nb.select(tab)

        def update_tab_title(self, pane_idx: int, tab: TkDirectoryTab) -> None:
            nb = self.notebooks[pane_idx]
            short = Path(tab.current_path).name or tab.current_path
            nb.tab(tab, text=short[:16])

        def get_pane_current_path(self, pane_idx: int) -> str:
            nb = self.notebooks[pane_idx]
            sel = nb.select()
            if sel:
                w = nb.nametowidget(sel)
                if isinstance(w, TkDirectoryTab):
                    return w.current_path
            return str(Path.home())

        def navigate_active(self, path_str: str) -> None:
            nb = self.notebooks[self.active_pane_idx]
            sel = nb.select()
            if sel:
                w = nb.nametowidget(sel)
                if isinstance(w, TkDirectoryTab):
                    w.navigate_to(path_str)

        def add_favorite(self, path_str: str) -> None:
            name = simpledialog.askstring("즐겨찾기 추가", "즐겨찾기 표시 이름:", initialvalue=f"⭐ {Path(path_str).name or path_str}")
            if name:
                self.favorites.append({"name": name, "path": path_str})
                self._rebuild_fav_bar()

        def _toggle_color(self) -> None:
            self.color_filter_enabled = not self.color_filter_enabled
            self.refresh_all()

        def refresh_all(self) -> None:
            for nb in self.notebooks:
                for tab_id in nb.tabs():
                    w = nb.nametowidget(tab_id)
                    if isinstance(w, TkDirectoryTab):
                        w.refresh()

        def transfer_files_tk(self, src_paths: List[str], dest_dir: str, mode: Optional[str] = None) -> None:
            if mode is None:
                ans = messagebox.askyesnocancel(
                    "드래그 앤 드롭 파일 작업",
                    f"선택한 {len(src_paths)}개 항목을 '{dest_dir}'(으)로:\n\n"
                    "• [예(Yes)]: 복사(Copy)\n"
                    "• [아니오(No)]: 이동(Move)\n"
                    "• [취소(Cancel)]: 작업 취소",
                )
                if ans is None:
                    return
                mode = "copy" if ans else "move"

            dest = Path(dest_dir)
            for s in src_paths:
                src = Path(s)
                if not src.exists():
                    continue
                target = get_unique_target_path(dest, src.name)
                try:
                    if mode == "move":
                        shutil.move(str(src), str(target))
                    else:
                        if src.is_dir():
                            shutil.copytree(str(src), str(target))
                        else:
                            shutil.copy2(str(src), str(target))
                except Exception as exc:
                    messagebox.showwarning("파일 작업 오류", str(exc))
            self.refresh_all()

        def run(self) -> None:
            self.root.mainloop()

    TkQDirApp().run()


def main() -> None:
    if _check_or_install_pyqt6():
        run_pyqt6_app()
    else:
        run_tkinter_app()


if __name__ == "__main__":
    main()
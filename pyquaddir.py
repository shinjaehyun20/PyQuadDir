#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PyQuadDir Desktop Explorer (Quad-View Multi-Tab File Manager for Windows)
=========================================================================
실제 Windows 로컬 드라이브(C:\, D:\ 등)와 파일 시스템을 직접 제어하는
데스크톱 4분할(Quad) 다중 탭 파일 탐색기입니다.
(Inspired by the quad-pane file manager concept of Q-Dir)

[트리플 엔진 지원 — MIT 라이선스 호환]
- 기본 Qt 엔진 (PySide6 / PyQt6 자동 감지): OS 네이티브 파일 아이콘, 외부 Windows 탐색기
  양방향 드래그 앤 드롭, 고해상도 다크/라이트 테마 스타일시트 지원 (미설치 시 자동 설치 팝업 제공)
- 내장 폴백 엔진 (Tkinter ttk): 외부 패키지 설치 없이 Python 표준 라이브러리만으로도
  즉시 구동되는 4분할·다중 탭·창 간 드래그 앤 드롭·확장자 색상 필터·즐겨찾기 완비

주요 기능:
1. 4분할(Quad) 화면 및 6가지 레이아웃 실시간 전환 (1~4분할, Ctrl+1~6)
2. 창 간 드래그 앤 드롭 파일 복사·이동 및 이름 충돌 해결 (덮어쓰기 / 자동 번호 붙이기 / 건너뛰기)
3. 패널별 독립 다중 탭(Tab) 탐색 (새 탭 Ctrl+T, 탭 닫기 Ctrl+W, 마우스 휠 클릭으로 새 탭 열기)
4. 확장자별 색상 필터 하이라이트 및 사용자 지정 색상 규칙 편집기
5. 자주 쓰는 폴더 즐겨찾기(북마크 바 & 관리자) 및 실시간 드라이브(C:\, D:\ 등) 용량 표시
6. 마지막 열린 탭 경로, 레이아웃, 색상 규칙, 다크/라이트 테마 자동 저장 (~/.pyquaddir_config.json)

실행 방법:
    python pyquaddir.py
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
        "extensions": [".dll", ".sys", ".ini", ".cfg", ".log", ".tmp", ".bak", ".dat"],
        "color_dark": "#94A3B8",   # 슬레이트 그레이
        "color_light": "#64748B",
        "enabled": True,
    },
}


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
# 엔진 선택 및 Qt (PySide6 / PyQt6) 부트스트랩
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
    """Qt(PySide6/PyQt6) 설치 여부를 확인하고, 미설치 시 자동 설치 여부를 묻습니다. 실패/거절 시 False를 반환하여 Tkinter 폴백으로 전환합니다."""
    if "--tk" in sys.argv:
        return False
    if getattr(sys, "frozen", False):
        return _detect_qt_binding() is not None
    if _detect_qt_binding() is not None:
        return True

    msg = (
        "고해상도 아이콘 및 외부 탐색기 드래그 앤 드롭을 지원하는 Qt 엔진(PySide6 / PyQt6)이 아직 설치되어 있지 않습니다.\n\n"
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
            QMimeData,
            QPoint,
            QSize,
            Qt,
            QUrl,
            Signal as pyqtSignal,
        )
        from PySide6.QtGui import (  # type: ignore[import-not-found]
            QColor,
            QDrag,
            QFont,
            QKeySequence,
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
            QListWidget,
            QListWidgetItem,
            QMainWindow,
            QMenu,
            QMessageBox,
            QPushButton,
            QSplitter,
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
            QMimeData,
            QPoint,
            QSize,
            Qt,
            QUrl,
            pyqtSignal,
        )
        from PyQt6.QtGui import (
            QColor,
            QDrag,
            QFont,
            QKeySequence,
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
            QListWidget,
            QListWidgetItem,
            QMainWindow,
            QMenu,
            QMessageBox,
            QPushButton,
            QSplitter,
            QStatusBar,
            QTableWidget,
            QTableWidgetItem,
            QTabWidget,
            QToolBar,
            QToolButton,
            QVBoxLayout,
            QWidget,
        )

    class SortableTableWidgetItem(QTableWidgetItem):
        def __init__(self, text: str, sort_key: object, is_dir: bool = False, is_parent: bool = False):
            super().__init__(text)
            self.sort_key = sort_key
            self.is_dir = is_dir
            self.is_parent = is_parent

        def __lt__(self, other: "QTableWidgetItem") -> bool:
            if isinstance(other, SortableTableWidgetItem):
                if self.is_parent != other.is_parent:
                    return self.is_parent
                if self.is_dir != other.is_dir:
                    return self.is_dir
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
            self.verticalHeader().setDefaultSectionSize(26)

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

        def focusInEvent(self, event) -> None:
            super().focusInEvent(event)
            self.paneFocused.emit()

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

    class DirectoryTab(QWidget):
        pathChanged = pyqtSignal(str)
        statusUpdated = pyqtSignal(str)
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
            self.show_hidden: bool = False

            self._build_ui()
            self.navigate_to(initial_path, record_history=True)

        def _build_ui(self) -> None:
            layout = QVBoxLayout(self)
            layout.setContentsMargins(4, 4, 4, 4)
            layout.setSpacing(4)

            nav_layout = QHBoxLayout()
            nav_layout.setContentsMargins(0, 0, 0, 0)
            nav_layout.setSpacing(3)

            self.btn_back = QToolButton()
            self.btn_back.setText("◀")
            self.btn_back.setToolTip("뒤로 가기 (Alt+Left)")
            self.btn_back.clicked.connect(self.go_back)

            self.btn_forward = QToolButton()
            self.btn_forward.setText("▶")
            self.btn_forward.setToolTip("앞으로 가기 (Alt+Right)")
            self.btn_forward.clicked.connect(self.go_forward)

            self.btn_up = QToolButton()
            self.btn_up.setText("▲")
            self.btn_up.setToolTip("상위 폴더로 이동 (Backspace / Alt+Up)")
            self.btn_up.clicked.connect(self.go_up)

            self.btn_refresh = QToolButton()
            self.btn_refresh.setText("⟳")
            self.btn_refresh.setToolTip("새로고침 (F5)")
            self.btn_refresh.clicked.connect(self.refresh)

            self.address_edit = QLineEdit()
            self.address_edit.setPlaceholderText("경로 입력 후 Enter (예: C:\\Users)")
            self.address_edit.returnPressed.connect(self._on_address_entered)

            self.btn_star = QToolButton()
            self.btn_star.setText("⭐")
            self.btn_star.setToolTip("현재 폴더를 즐겨찾기에 추가")
            self.btn_star.clicked.connect(self._add_current_to_favorites)

            self.filter_edit = QLineEdit()
            self.filter_edit.setPlaceholderText("🔍 이름/확장자 필터...")
            self.filter_edit.setFixedWidth(135)
            self.filter_edit.setClearButtonEnabled(True)
            self.filter_edit.textChanged.connect(self.apply_filter)

            for w in (self.btn_back, self.btn_forward, self.btn_up, self.btn_refresh):
                w.setFixedSize(26, 26)
                nav_layout.addWidget(w)

            nav_layout.addWidget(self.address_edit, stretch=1)
            nav_layout.addWidget(self.btn_star)
            nav_layout.addWidget(self.filter_edit)
            layout.addLayout(nav_layout)

            self.table = FileTableView(self)
            self.table.doubleClicked.connect(self._on_item_double_clicked)
            self.table.itemSelectionChanged.connect(self.update_status_summary)
            self.table.filesDropped.connect(self._on_files_dropped)
            self.table.middleClickedFolder.connect(self.openInNewTabRequested.emit)
            self.table.paneFocused.connect(self.paneActivated.emit)
            self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self.table.customContextMenuRequested.connect(self._show_context_menu)
            layout.addWidget(self.table, stretch=1)

            self.summary_label = QLabel("")
            self.summary_label.setObjectName("PaneSummaryLabel")
            layout.addWidget(self.summary_label)

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
                self.navigate_to(text, record_history=True)

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

        def refresh(self) -> None:
            if not self.current_path:
                return

            self.table.setSortingEnabled(False)
            self.table.setRowCount(0)

            p = Path(self.current_path)
            entries: List[os.DirEntry] = []
            try:
                with os.scandir(p) as it:
                    for entry in it:
                        if not self.show_hidden and entry.name.startswith("."):
                            continue
                        entries.append(entry)
            except PermissionError:
                self.summary_label.setText("🔒 접근 권한이 없는 폴더입니다.")
                return
            except Exception as exc:
                self.summary_label.setText(f"⚠️ 읽기 오류: {exc}")
                return

            has_parent = p.parent != p
            total_rows = len(entries) + (1 if has_parent else 0)
            self.table.setRowCount(total_rows)

            row_idx = 0
            if has_parent:
                parent_str = str(p.parent)
                item_name = SortableTableWidgetItem("📁 .. (상위 폴더)", "", is_dir=True, is_parent=True)
                item_name.setData(Qt.ItemDataRole.UserRole, parent_str)
                item_name.setData(Qt.ItemDataRole.UserRole + 1, True)
                font = item_name.font()
                font.setBold(True)
                item_name.setFont(font)

                item_size = SortableTableWidgetItem("", -1, is_dir=True, is_parent=True)
                item_type = SortableTableWidgetItem("상위 폴더", "", is_dir=True, is_parent=True)
                item_date = SortableTableWidgetItem("", 0, is_dir=True, is_parent=True)

                self.table.setItem(0, 0, item_name)
                self.table.setItem(0, 1, item_size)
                self.table.setItem(0, 2, item_type)
                self.table.setItem(0, 3, item_date)
                row_idx = 1

            dir_count = 0
            file_count = 0
            total_bytes = 0

            for entry in entries:
                try:
                    is_dir = entry.is_dir(follow_symlinks=False)
                except Exception:
                    is_dir = False

                try:
                    stat = entry.stat(follow_symlinks=False)
                    size_b = 0 if is_dir else stat.st_size
                    mtime = stat.st_mtime
                    date_str = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
                except Exception:
                    size_b = 0
                    mtime = 0.0
                    date_str = "-"

                ext = "" if is_dir else Path(entry.name).suffix.lower()
                if is_dir:
                    dir_count += 1
                    type_str = "폴더"
                    size_str = "<DIR>"
                else:
                    file_count += 1
                    total_bytes += size_b
                    type_str = f"{ext[1:].upper()} 파일" if ext else "파일"
                    size_str = format_size(size_b)

                item_name = SortableTableWidgetItem(entry.name, entry.name.lower(), is_dir=is_dir)
                item_name.setData(Qt.ItemDataRole.UserRole, entry.path)
                item_name.setData(Qt.ItemDataRole.UserRole + 1, False)

                qfile_info = QFileInfo(entry.path)
                icon = self.icon_provider.icon(qfile_info)
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

            self.table.setSortingEnabled(True)
            self.table.sortItems(0, Qt.SortOrder.AscendingOrder)

            self._dir_count = dir_count
            self._file_count = file_count
            self._total_bytes = total_bytes

            self.apply_filter(self.filter_edit.text())
            self.update_status_summary()

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

        def update_status_summary(self) -> None:
            selected_paths = self.table.selected_file_paths()
            free_b, total_b = _safe_disk_usage(self.current_path)
            free_str = f"여유 {format_size(free_b)}" if total_b > 0 else ""

            if selected_paths:
                sel_bytes = 0
                for p in selected_paths:
                    try:
                        if os.path.isfile(p):
                            sel_bytes += os.path.getsize(p)
                    except Exception:
                        pass
                msg = (
                    f"선택: {len(selected_paths)}개 ({format_size(sel_bytes)})  |  "
                    f"전체: 폴더 {getattr(self, '_dir_count', 0)}개, 파일 {getattr(self, '_file_count', 0)}개 "
                    f"({format_size(getattr(self, '_total_bytes', 0))})"
                )
            else:
                msg = (
                    f"폴더 {getattr(self, '_dir_count', 0)}개, 파일 {getattr(self, '_file_count', 0)}개 "
                    f"({format_size(getattr(self, '_total_bytes', 0))})"
                )
            if free_str:
                msg += f"  |  💾 {free_str}"

            self.summary_label.setText(msg)
            self.statusUpdated.emit(f"[{self.pane.pane_title}] {self.current_path}  —  {msg}")

        def _on_item_double_clicked(self, index) -> None:
            self.paneActivated.emit()
            row = index.row()
            name_item = self.table.item(row, 0)
            if name_item is None:
                return
            full_path = name_item.data(Qt.ItemDataRole.UserRole)
            if not full_path:
                return

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
            selected_paths = self.table.selected_file_paths()
            menu = QMenu(self)

            if len(selected_paths) == 1 and os.path.isdir(selected_paths[0]):
                target_folder = selected_paths[0]
                act_open = menu.addAction("📂 열기")
                act_open_tab = menu.addAction("➕ 새 탭에서 폴더 열기 (휠 클릭)")
                act_open.triggered.connect(lambda: self.navigate_to(target_folder))
                act_open_tab.triggered.connect(lambda: self.openInNewTabRequested.emit(target_folder))
                menu.addSeparator()
            elif len(selected_paths) == 1 and os.path.isfile(selected_paths[0]):
                target_file = selected_paths[0]
                act_run = menu.addAction("▶️ 기본 프로그램으로 실행")
                act_run.triggered.connect(lambda: open_path_with_os(target_file))
                menu.addSeparator()

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

            menu.exec(self.table.viewport().mapToGlobal(pos))

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

        def create_new_text_file(self) -> None:
            name, ok = QInputDialog.getText(
                self, "새 텍스트 파일", "새 파일 이름을 입력하세요:", text="새 문서.txt"
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
            paths = self.table.selected_file_paths()
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
            paths = self.table.selected_file_paths()
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

            btn_new_tab = QToolButton()
            btn_new_tab.setText("➕ 새 탭")
            btn_new_tab.setToolTip("현재 패널에 새 탭 추가 (Ctrl+T)")
            btn_new_tab.clicked.connect(lambda: self.add_new_tab(self.current_path()))
            header_bar.addWidget(btn_new_tab)

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
            for i in range(self.tab_widget.count()):
                w = self.tab_widget.widget(i)
                if isinstance(w, DirectoryTab):
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

    class ColorRulesDialog(QDialog):
        def __init__(
            self,
            color_rules: Dict[str, Dict[str, object]],
            dark_mode: bool,
            parent: Optional[QWidget] = None,
        ):
            super().__init__(parent)
            self.setWindowTitle("🎨 PyQuadDir 확장자별 색상 필터 설정")
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
            self.resize(520, 360)
            self.favorites: List[Dict[str, str]] = [dict(item) for item in favorites]
            self._build_ui()

        def _build_ui(self) -> None:
            layout = QVBoxLayout(self)

            self.list_widget = QListWidget()
            self._refresh_list()
            layout.addWidget(self.list_widget, stretch=1)

            btn_row = QHBoxLayout()
            btn_add = QPushButton("➕ 경로 직접 추가")
            btn_del = QPushButton("🗑️ 선택 항목 삭제")
            btn_up = QPushButton("▲ 위로")
            btn_down = QPushButton("▼ 아래로")

            btn_add.clicked.connect(self._add_item)
            btn_del.clicked.connect(self._del_item)
            btn_up.clicked.connect(lambda: self._move_item(-1))
            btn_down.clicked.connect(lambda: self._move_item(1))

            for b in (btn_add, btn_del, btn_up, btn_down):
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

    class QDirMainWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("PyQuadDir Desktop Explorer — 4분할 다중 탭 파일 탐색기")
            self.resize(1480, 920)

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
            self.active_pane_index: int = 0

            self.clipboard_paths: List[str] = []
            self.clipboard_mode: str = "copy"

            self._build_ui()
            self._apply_theme()
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
                "pane_tabs": pane_tabs,
            })

        def closeEvent(self, event) -> None:
            self.save_config()
            super().closeEvent(event)

        def _build_ui(self) -> None:
            main_tb = QToolBar("메인 도구 모음")
            main_tb.setMovable(False)
            main_tb.setIconSize(QSize(18, 18))
            self.addToolBar(Qt.ToolBarArea.TopToolBarArea, main_tb)

            lbl_layout = QLabel("  📐 레이아웃: ")
            main_tb.addWidget(lbl_layout)

            self.layout_buttons: Dict[str, QToolButton] = {}
            layouts_meta = [
                ("quad", "⊞ 4분할 (2×2)", "4분할 격자 보기 (Ctrl+1)"),
                ("2h", "◫ 2분할 (좌/우)", "좌/우 2분할 보기 (Ctrl+2)"),
                ("2v", "⊟ 2분할 (상/하)", "상/하 2분할 보기 (Ctrl+3)"),
                ("3_left", "◧ 3분할 (좌1·우2)", "좌1 + 우2 3분할 보기 (Ctrl+4)"),
                ("3_top", "⬒ 3분할 (상1·하2)", "상1 + 하2 3분할 보기 (Ctrl+5)"),
                ("single", "⬜ 1분할 (단일)", "현재 활성 패널 최대화 (Ctrl+6)"),
            ]
            for mode_key, text, tip in layouts_meta:
                btn = QToolButton()
                btn.setText(text)
                btn.setToolTip(tip)
                btn.setCheckable(True)
                btn.clicked.connect(lambda checked=False, m=mode_key: self.set_layout_mode(m))
                main_tb.addWidget(btn)
                self.layout_buttons[mode_key] = btn

            btn_equalize = QToolButton()
            btn_equalize.setText("⚖️ 창 비율 균등화")
            btn_equalize.setToolTip("분할된 모든 패널의 크기를 동일한 비율로 정렬합니다")
            btn_equalize.clicked.connect(self.equalize_splitters)
            main_tb.addWidget(btn_equalize)

            main_tb.addSeparator()

            self.btn_color_toggle = QToolButton()
            self.btn_color_toggle.setCheckable(True)
            self.btn_color_toggle.setChecked(self.color_filter_enabled)
            self._update_color_toggle_text()
            self.btn_color_toggle.clicked.connect(self._toggle_color_filter)
            main_tb.addWidget(self.btn_color_toggle)

            btn_color_cfg = QToolButton()
            btn_color_cfg.setText("⚙️ 색상 규칙 편집")
            btn_color_cfg.setToolTip("확장자별 색상 하이라이트 규칙을 추가하거나 변경합니다")
            btn_color_cfg.clicked.connect(self._open_color_rules_dialog)
            main_tb.addWidget(btn_color_cfg)

            main_tb.addSeparator()

            self.btn_hidden = QToolButton()
            self.btn_hidden.setText("👁️ 숨김 항목 표시")
            self.btn_hidden.setCheckable(True)
            self.btn_hidden.clicked.connect(self._toggle_hidden_files)
            main_tb.addWidget(self.btn_hidden)

            self.btn_theme = QToolButton()
            self.btn_theme.setText("🌙 다크 테마" if self.dark_mode else "☀️ 라이트 테마")
            self.btn_theme.clicked.connect(self._toggle_theme)
            main_tb.addWidget(self.btn_theme)

            self.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea)
            self.fav_tb = QToolBar("드라이브 및 즐겨찾기 바")
            self.fav_tb.setMovable(False)
            self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.fav_tb)
            self._rebuild_drives_and_favorites_bar()

            central = QWidget()
            central_layout = QVBoxLayout(central)
            central_layout.setContentsMargins(6, 6, 6, 6)
            self.setCentralWidget(central)

            self.main_splitter = QSplitter(Qt.Orientation.Vertical)
            self.top_splitter = QSplitter(Qt.Orientation.Horizontal)
            self.bottom_splitter = QSplitter(Qt.Orientation.Horizontal)
            central_layout.addWidget(self.main_splitter)

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
                "준비 완료 — 패널 간 파일을 마우스로 드래그 앤 드롭하여 복사/이동할 수 있습니다."
            )
            self._register_shortcuts()

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

        def set_layout_mode(self, mode: str) -> None:
            self.current_layout_mode = mode
            for k, btn in self.layout_buttons.items():
                btn.setChecked(k == mode)

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

        def _rebuild_drives_and_favorites_bar(self) -> None:
            self.fav_tb.clear()

            lbl_drv = QLabel("  💽 드라이브: ")
            self.fav_tb.addWidget(lbl_drv)

            for drv in get_mounted_drives():
                root = str(drv["root"])
                label = str(drv["label"])
                free_b = int(drv["free"])  # type: ignore[arg-type]
                total_b = int(drv["total"])  # type: ignore[arg-type]

                btn = QToolButton()
                short_root = root.rstrip("\\") if len(root) <= 3 else root
                btn.setText(f"💾 {short_root}")
                if total_b > 0:
                    pct_used = int(((total_b - free_b) / total_b) * 100)
                    btn.setToolTip(
                        f"{label} ({root})\n"
                        f"여유 공간: {format_size(free_b)} / 전체: {format_size(total_b)} (사용률 {pct_used}%)\n"
                        f"클릭: 현재 활성 패널 이동 | 우클릭: 새 탭에서 열기"
                    )
                else:
                    btn.setToolTip(f"{label} ({root})")

                btn.clicked.connect(lambda checked=False, r=root: self.active_pane().navigate_current_tab(r))
                btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                btn.customContextMenuRequested.connect(
                    lambda pos, r=root: self.active_pane().add_new_tab(r)
                )
                self.fav_tb.addWidget(btn)

            self.fav_tb.addSeparator()
            lbl_fav = QLabel(" ⭐ 즐겨찾기: ")
            self.fav_tb.addWidget(lbl_fav)

            for fav in self.favorites:
                name = fav.get("name", "폴더")
                path = fav.get("path", "")
                btn = QToolButton()
                btn.setText(name)
                btn.setToolTip(f"{path}\n(클릭: 활성 패널에서 이동 | 우클릭: 활성 패널 새 탭으로 열기)")
                btn.clicked.connect(lambda checked=False, p=path: self.active_pane().navigate_current_tab(p))
                btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                btn.customContextMenuRequested.connect(
                    lambda pos, p=path: self.active_pane().add_new_tab(p)
                )
                self.fav_tb.addWidget(btn)

            btn_manage_fav = QToolButton()
            btn_manage_fav.setText("⚙️ 즐겨찾기 편집")
            btn_manage_fav.setToolTip("즐겨찾기 폴더 목록을 추가·삭제·정렬합니다")
            btn_manage_fav.clicked.connect(self._open_favorites_dialog)
            self.fav_tb.addWidget(btn_manage_fav)

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
                self._rebuild_drives_and_favorites_bar()
                self.save_config()

        def _open_favorites_dialog(self) -> None:
            dlg = FavoritesDialog(self.favorites, self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self.favorites = dlg.favorites
                self._rebuild_drives_and_favorites_bar()
                self.save_config()

        def get_color_for_entry(self, is_dir: bool, ext: str) -> Optional[QColor]:
            hex_c = match_color_hex(
                self.color_rules, self.dark_mode, self.color_filter_enabled, is_dir, ext
            )
            return QColor(hex_c) if hex_c else None

        def _update_color_toggle_text(self) -> None:
            state_str = "ON" if self.color_filter_enabled else "OFF"
            self.btn_color_toggle.setText(f"🎨 확장자 색상 필터: {state_str}")

        def _toggle_color_filter(self) -> None:
            self.color_filter_enabled = self.btn_color_toggle.isChecked()
            self._update_color_toggle_text()
            self.refresh_all_panes()
            self.save_config()

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
            self._rebuild_drives_and_favorites_bar()
            for pane in self.panes:
                pane.refresh_all_tabs()

        def _toggle_hidden_files(self) -> None:
            show = self.btn_hidden.isChecked()
            for pane in self.panes:
                for i in range(pane.tab_widget.count()):
                    w = pane.tab_widget.widget(i)
                    if isinstance(w, DirectoryTab):
                        w.show_hidden = show
                        w.refresh()

        def _toggle_theme(self) -> None:
            self.dark_mode = not self.dark_mode
            self.btn_theme.setText("🌙 다크 테마" if self.dark_mode else "☀️ 라이트 테마")
            self._apply_theme()
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
                sel = t.table.selected_file_paths()
                if sel:
                    self.set_clipboard_files(sel, "copy")

        def _shortcut_cut(self) -> None:
            t = self.active_pane().current_tab()
            if t:
                sel = t.table.selected_file_paths()
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

        def _apply_theme(self) -> None:
            if self.dark_mode:
                qss = """
                QMainWindow, QDialog { background-color: #0F172A; color: #E2E8F0; }
                QToolBar { background-color: #1E293B; border-bottom: 1px solid #334155; spacing: 4px; padding: 3px; }
                QToolButton { background-color: transparent; color: #E2E8F0; border: 1px solid transparent; border-radius: 5px; padding: 4px 8px; font-size: 12px; }
                QToolButton:hover { background-color: #334155; border: 1px solid #475569; }
                QToolButton:checked { background-color: #2563EB; color: #FFFFFF; font-weight: bold; }
                QFrame#ExplorerPane { background-color: #1E293B; border: 2px solid #334155; border-radius: 7px; }
                QFrame#ExplorerPane[activePane="true"] { border: 2px solid #38BDF8; }
                QLabel#PaneBadge { background-color: #2563EB; color: #FFFFFF; font-weight: bold; border-radius: 4px; padding: 1px 5px; }
                QLabel#PaneTitlePath, QLabel#PaneSummaryLabel { color: #94A3B8; font-size: 11px; padding: 2px 4px; }
                QLineEdit { background-color: #0F172A; color: #F8FAFC; border: 1px solid #475569; border-radius: 4px; padding: 3px 6px; selection-background-color: #2563EB; }
                QLineEdit:focus { border: 1px solid #38BDF8; }
                QTabWidget::pane { border: 1px solid #334155; background-color: #0F172A; }
                QTabBar::tab { background-color: #1E293B; color: #94A3B8; border: 1px solid #334155; border-bottom: none; border-top-left-radius: 5px; border-top-right-radius: 5px; padding: 5px 10px; margin-right: 2px; font-size: 12px; }
                QTabBar::tab:selected { background-color: #0F172A; color: #38BDF8; font-weight: bold; }
                QTableWidget { background-color: #0F172A; alternate-background-color: #131D31; color: #E2E8F0; border: none; selection-background-color: #1D4ED8; selection-color: #FFFFFF; font-size: 12px; }
                QHeaderView::section { background-color: #1E293B; color: #CBD5E1; border: none; border-right: 1px solid #334155; border-bottom: 1px solid #334155; padding: 4px 6px; font-weight: bold; }
                QSplitter::handle { background-color: #334155; }
                QSplitter::handle:hover { background-color: #38BDF8; }
                QStatusBar { background-color: #1E293B; color: #CBD5E1; border-top: 1px solid #334155; }
                QMenu { background-color: #1E293B; color: #F8FAFC; border: 1px solid #475569; }
                QMenu::item:selected { background-color: #2563EB; }
                """
            else:
                qss = """
                QMainWindow, QDialog { background-color: #F1F5F9; color: #0F172A; }
                QToolBar { background-color: #FFFFFF; border-bottom: 1px solid #CBD5E1; spacing: 4px; padding: 3px; }
                QToolButton { background-color: transparent; color: #1E293B; border: 1px solid transparent; border-radius: 5px; padding: 4px 8px; font-size: 12px; }
                QToolButton:hover { background-color: #E2E8F0; border: 1px solid #CBD5E1; }
                QToolButton:checked { background-color: #2563EB; color: #FFFFFF; font-weight: bold; }
                QFrame#ExplorerPane { background-color: #FFFFFF; border: 2px solid #CBD5E1; border-radius: 7px; }
                QFrame#ExplorerPane[activePane="true"] { border: 2px solid #2563EB; }
                QLabel#PaneBadge { background-color: #2563EB; color: #FFFFFF; font-weight: bold; border-radius: 4px; padding: 1px 5px; }
                QLabel#PaneTitlePath, QLabel#PaneSummaryLabel { color: #475569; font-size: 11px; padding: 2px 4px; }
                QLineEdit { background-color: #F8FAFC; color: #0F172A; border: 1px solid #CBD5E1; border-radius: 4px; padding: 3px 6px; }
                QLineEdit:focus { border: 1px solid #2563EB; }
                QTabWidget::pane { border: 1px solid #CBD5E1; background-color: #FFFFFF; }
                QTabBar::tab { background-color: #E2E8F0; color: #475569; border: 1px solid #CBD5E1; border-bottom: none; border-top-left-radius: 5px; border-top-right-radius: 5px; padding: 5px 10px; margin-right: 2px; font-size: 12px; }
                QTabBar::tab:selected { background-color: #FFFFFF; color: #1D4ED8; font-weight: bold; }
                QTableWidget { background-color: #FFFFFF; alternate-background-color: #F8FAFC; color: #0F172A; border: none; selection-background-color: #2563EB; selection-color: #FFFFFF; font-size: 12px; }
                QHeaderView::section { background-color: #F1F5F9; color: #334155; border: none; border-right: 1px solid #CBD5E1; border-bottom: 1px solid #CBD5E1; padding: 4px 6px; font-weight: bold; }
                QSplitter::handle { background-color: #CBD5E1; }
                QSplitter::handle:hover { background-color: #2563EB; }
                QStatusBar { background-color: #FFFFFF; color: #334155; border-top: 1px solid #CBD5E1; }
                """
            self.setStyleSheet(qss)

    app = QApplication(sys.argv)
    app.setApplicationName("PyQuadDir Desktop Explorer")
    font = QFont("Malgun Gothic", 9) if platform.system() == "Windows" else QFont("Sans Serif", 10)
    app.setFont(font)

    win = QDirMainWindow()
    win.show()
    sys.exit(app.exec())


# ===========================================================================
# 2. 내장 Tkinter (ttk) 폴백 엔진 (외부 라이브러리 없이 100% 표준 라이브러리 구동)
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

            ttk.Button(nav, text="◀", width=3, command=self.go_back).pack(side=tk.LEFT, padx=1)
            ttk.Button(nav, text="▶", width=3, command=self.go_forward).pack(side=tk.LEFT, padx=1)
            ttk.Button(nav, text="▲", width=3, command=self.go_up).pack(side=tk.LEFT, padx=1)
            ttk.Button(nav, text="⟳", width=3, command=self.refresh).pack(side=tk.LEFT, padx=1)

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

            # 이벤트 바인딩 (더블클릭, 드래그 앤 드롭, 우클릭)
            self.tree.bind("<FocusIn>", lambda e: self.app.set_active_pane(self.pane_idx))
            self.tree.bind("<Double-1>", self._on_double_click)
            self.tree.bind("<ButtonPress-1>", self._on_drag_start)
            self.tree.bind("<ButtonRelease-1>", self._on_drag_drop)
            self.tree.bind("<Button-3>", self._on_right_click)

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

        def _on_double_click(self, event) -> None:
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

            self._build_ui()

        def _build_ui(self) -> None:
            top_bar = ttk.Frame(self.root)
            top_bar.pack(fill=tk.X, padx=4, pady=3)

            ttk.Label(top_bar, text="📐 레이아웃:").pack(side=tk.LEFT, padx=3)
            for key, label in [
                ("quad", "⊞ 4분할"),
                ("2h", "◫ 2분할(좌/우)"),
                ("2v", "⊟ 2분할(상/하)"),
                ("single", "⬜ 1분할"),
            ]:
                ttk.Button(top_bar, text=label, command=lambda m=key: self.set_layout(m)).pack(side=tk.LEFT, padx=2)

            ttk.Button(top_bar, text="🎨 색상 필터 토글", command=self._toggle_color).pack(side=tk.LEFT, padx=8)

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
            ttk.Label(self.fav_bar, text="💽 드라이브:").pack(side=tk.LEFT, padx=2)
            for d in get_mounted_drives():
                r = str(d["root"])
                ttk.Button(self.fav_bar, text=f"💾 {r}", command=lambda p=r: self.navigate_active(p)).pack(side=tk.LEFT, padx=1)
            ttk.Label(self.fav_bar, text="  ⭐ 즐겨찾기:").pack(side=tk.LEFT, padx=4)
            for f in self.favorites:
                ttk.Button(
                    self.fav_bar,
                    text=f.get("name", "폴더"),
                    command=lambda p=f.get("path", ""): self.navigate_active(p),
                ).pack(side=tk.LEFT, padx=1)

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
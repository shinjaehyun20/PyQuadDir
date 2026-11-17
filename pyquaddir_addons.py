#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PyQuadDir v3.2.0 Clean-Room Power Add-ons Module (pyquaddir_addons.py)
======================================================================
순수 Python 3 표준 라이브러리 + PyQt6 기반 데스크톱 파일 탐색기 핵심 부가기능 5종 모듈.
외부 서드파티 패키지 의존성 없이 PyQuadDir v3.1.1 (`pyquaddir.py`)의 `QDirMainWindow`에
단 2줄 호출(`install_pyquaddir_addons(self)`)로 즉시 통합됩니다.

[탑재 기능 5종 및 단축키]
1. 일괄 이름 바꾸기 (Multi-Rename Tool, `Ctrl+M` / 다중 선택 `F2` / 실행 취소 `Ctrl+Shift+Z`)
   - 접두사/접미사, 일반 문자열 및 정규식(Regex) 찾기·바꾸기, 연번 패턴(`[N]`, 시작값·증가치·자릿수 패딩),
     대소문자 변환, 확장자 변경, 변경 전→후 실시간 미리보기 및 변경 구간 하이라이트,
     중복·예약어·특수문자·기존 파일 충돌 사전 차단, 2단계 UUID 임시 스테이징 및 Undo 지원.
2. 패널 간 폴더 비교·동기화 미리보기 (Compare Panes, `Shift+F2`)
   - 활성 패널과 대상 패널(1~4번 창 선택)의 파일 목록을 이름(대소문자 무시 매칭)·크기·수정시각(허용 오차 설정)
     및 선택적 SHA-256 해시로 비교하여 [좌측 전용 / 우측 전용 / 크기·날짜·해시 상이 / 동일] 분류 및
     기존 파일 덮어쓰기 원천 차단 기반 차이 항목 선택 복사 지원.
3. 폴더 실제 용량 계산 (Calculate Occupied Space, `Alt+Shift+Enter`)
   - 선택 폴더 또는 현재 폴더 전체 하위 폴더의 하위 파일 총용량과 파일·폴더 수를 심볼릭 링크/Junction 루프 없이
     고속 합산하여 테이블 크기 열(`<DIR>` → 실제 용량, 바이트 기준 정렬 키 연동)과 상태 표시줄에 즉시 반영.
4. 파일 해시(MD5 / SHA-1 / SHA-256) 계산·검증 및 3단계 고속 중복 파일 찾기 (`Ctrl+Shift+H`)
   - 단일 스트리밍 패스 다중 해시(MD5/SHA-1/SHA-256) 계산, 클립보드 해시값 자동 판별·대조,
     [1단계 동일 크기 → 2단계 앞·뒤 4KB 부분 해시 → 3단계 전체 SHA-256 + 하드링크(inode) 제외] 고속 중복 탐지
     (자동 삭제 0건 보장, 탐색기 내 안전 선택 및 리포트 내보내기 지원).
5. 파일 목록 내보내기 (`CSV / Markdown / HTML / TXT`, `Ctrl+Shift+E`), 플랫 뷰 토글 (`Ctrl+B`),
   탭 복제 (`Ctrl+Shift+K`) 및 탭 잠금 (`Ctrl+Shift+L`)
   - UTF-8 BOM CSV(수식 주입 방어 포함), Markdown 파이프 표, XSS 안전 WCAG HTML 리포트, 정렬 TXT 비덮어쓰기 저장,
     하위 폴더 파일 모아보기(플랫 뷰) 토글, 탭 복제 및 닫기/경로 보호 탭 잠금 지원.

License: MIT / Clean-Room Implementation for PyQuadDir v3.1.1
"""

from __future__ import annotations

import csv
import ctypes
import contextlib
import datetime
import difflib
import enum
import hashlib
import html
import io
import os
import platform
import re
import shutil
import stat
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

__all__ = [
    "ADDON_VERSION",
    "ADDON_THEMES",
    "CaseTransform",
    "ExtensionMode",
    "MultiRenameRule",
    "RenamePlanItem",
    "RenamePlanResult",
    "RenameUndoEntry",
    "RenameUndoBatch",
    "CompareStatus",
    "CompareOptions",
    "CompareEntry",
    "CompareSummary",
    "SyncCopyResult",
    "FolderSizeSummary",
    "FileHashRecord",
    "HashVerificationResult",
    "DuplicateFileEntry",
    "DuplicateGroup",
    "DuplicateScanResult",
    "ExportFormat",
    "ExportOptions",
    "ExportRecord",
    "TabLockState",
    "TabLockManager",
    "wcag_relative_luminance",
    "wcag_contrast_ratio",
    "build_addon_dialog_qss",
    "safe_norm_path",
    "format_bytes",
    "is_symlink_or_reparse_point",
    "validate_safe_filename_segment",
    "plan_multi_rename",
    "execute_multi_rename_plan",
    "undo_multi_rename_batch",
    "compare_directories",
    "execute_selective_sync_copy",
    "calculate_folder_occupied_size",
    "calculate_immediate_subfolders_sizes",
    "compute_file_hashes",
    "verify_expected_hash",
    "export_hash_manifest",
    "find_duplicate_files_3stage",
    "collect_export_records",
    "render_export_content",
    "export_file_list_safe",
    "collect_flat_view_records",
    "PyQuadDirAddonController",
    "install_pyquaddir_addons",
]

ADDON_VERSION = "3.2.0"

FILE_ATTRIBUTE_REPARSE_POINT = 0x0400

WINDOWS_RESERVED_NAMES: Set[str] = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "CONIN$",
    "CONOUT$",
    "CLOCK$",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
    "COM¹",
    "COM²",
    "COM³",
    "LPT¹",
    "LPT²",
    "LPT³",
}

WINDOWS_INVALID_CHARS: Set[str] = set('<>:"|?*')

CSV_DANGEROUS_PREFIXES: Tuple[str, ...] = ("=", "+", "-", "@", "\t", "\r")


# ===========================================================================
# 0. WCAG 2.1 대비율 검증기 & 다크/라이트 테마 토큰 (AA >= 4.5:1 / AAA >= 7.0:1)
# ===========================================================================

ADDON_THEMES: Dict[str, Dict[str, str]] = {
    "dark": {
        "bg_window": "#0B1120",
        "bg_surface": "#0F172A",
        "bg_elevated": "#1E293B",
        "bg_alt_row": "#131C31",
        "border": "#334155",
        "border_focus": "#38BDF8",
        "text_primary": "#F8FAFC",     # vs #0F172A -> 17.4:1 (AAA)
        "text_secondary": "#CBD5E1",   # vs #0F172A -> 11.9:1 (AAA)
        "accent_bg": "#1D4ED8",        # vs #FFFFFF -> 6.7:1 (AA+)
        "accent_hover": "#2563EB",
        "accent_text": "#FFFFFF",
        "badge_ok_bg": "#064E3B",
        "badge_ok_fg": "#A7F3D0",      # vs #064E3B -> 8.3:1 (AAA)
        "badge_warn_bg": "#78350F",
        "badge_warn_fg": "#FDE68A",    # vs #78350F -> 8.7:1 (AAA)
        "badge_err_bg": "#7F1D1D",
        "badge_err_fg": "#FECACA",     # vs #7F1D1D -> 7.6:1 (AAA)
        "badge_left_bg": "#1E3A8A",
        "badge_left_fg": "#DBEAFE",    # vs #1E3A8A -> 8.5:1 (AAA)
        "badge_right_bg": "#065F46",
        "badge_right_fg": "#D1FAE5",   # vs #065F46 -> 7.8:1 (AAA)
    },
    "light": {
        "bg_window": "#F1F5F9",
        "bg_surface": "#FFFFFF",
        "bg_elevated": "#F8FAFC",
        "bg_alt_row": "#F8FAFC",
        "border": "#CBD5E1",
        "border_focus": "#1D4ED8",
        "text_primary": "#0F172A",     # vs #FFFFFF -> 17.8:1 (AAA)
        "text_secondary": "#334155",   # vs #FFFFFF -> 10.4:1 (AAA)
        "accent_bg": "#1D4ED8",        # vs #FFFFFF -> 6.7:1 (AA+)
        "accent_hover": "#1E40AF",
        "accent_text": "#FFFFFF",
        "badge_ok_bg": "#DCFCE7",
        "badge_ok_fg": "#065F46",      # vs #DCFCE7 -> 6.9:1 (AA+)
        "badge_warn_bg": "#FEF3C7",
        "badge_warn_fg": "#92400E",    # vs #FEF3C7 -> 6.5:1 (AA+)
        "badge_err_bg": "#FEE2E2",
        "badge_err_fg": "#991B1B",     # vs #FEE2E2 -> 6.8:1 (AA+)
        "badge_left_bg": "#DBEAFE",
        "badge_left_fg": "#1E3A8A",    # vs #DBEAFE -> 8.5:1 (AAA)
        "badge_right_bg": "#D1FAE5",
        "badge_right_fg": "#065F46",   # vs #D1FAE5 -> 6.6:1 (AA+)
    },
}


def _parse_hex_rgb(hex_color: str) -> Tuple[int, int, int]:
    cleaned = hex_color.strip().lstrip("#")
    if len(cleaned) == 3:
        cleaned = "".join(ch * 2 for ch in cleaned)
    if len(cleaned) != 6:
        raise ValueError(f"유효하지 않은 16진수 색상 코드입니다: {hex_color!r}")
    return int(cleaned[0:2], 16), int(cleaned[2:4], 16), int(cleaned[4:6], 16)


def wcag_relative_luminance(hex_color: str) -> float:
    """WCAG 2.1 표준 상대 휘도(Relative Luminance)를 계산합니다."""
    r8, g8, b8 = _parse_hex_rgb(hex_color)
    channels: List[float] = []
    for v in (r8, g8, b8):
        srgb = v / 255.0
        lin = srgb / 12.92 if srgb <= 0.04045 else ((srgb + 0.055) / 1.055) ** 2.4
        channels.append(lin)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def wcag_contrast_ratio(fg_hex: str, bg_hex: str) -> float:
    """두 16진수 색상 간의 WCAG 2.1 명암 대비율(1.0 ~ 21.0)을 반환합니다."""
    lum1 = wcag_relative_luminance(fg_hex)
    lum2 = wcag_relative_luminance(bg_hex)
    lighter = max(lum1, lum2)
    darker = min(lum1, lum2)
    return (lighter + 0.05) / (darker + 0.05)


def build_addon_dialog_qss(dark_mode: bool) -> str:
    """부가기능 다이얼로그에 일관되게 적용되는 WCAG 준수 QSS 스타일시트를 반환합니다."""
    t = ADDON_THEMES["dark" if dark_mode else "light"]
    return f"""
    QDialog {{
        background-color: {t['bg_window']};
        color: {t['text_primary']};
    }}
    QGroupBox {{
        background-color: {t['bg_surface']};
        color: {t['text_primary']};
        border: 1px solid {t['border']};
        border-radius: 6px;
        margin-top: 10px;
        padding: 10px 8px 8px 8px;
        font-weight: 700;
        font-size: 12px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 4px;
        color: {t['text_primary']};
    }}
    QLabel, QCheckBox, QRadioButton {{
        color: {t['text_primary']};
        background: transparent;
        font-size: 12px;
    }}
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit {{
        background-color: {t['bg_surface']};
        color: {t['text_primary']};
        border: 1px solid {t['border']};
        border-radius: 5px;
        padding: 4px 8px;
        font-size: 12px;
        selection-background-color: {t['accent_bg']};
        selection-color: {t['accent_text']};
    }}
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
        border: 1px solid {t['border_focus']};
    }}
    QPushButton {{
        background-color: {t['bg_elevated']};
        color: {t['text_primary']};
        border: 1px solid {t['border']};
        border-radius: 6px;
        padding: 6px 12px;
        font-weight: 600;
        font-size: 12px;
    }}
    QPushButton:hover {{
        background-color: {t['accent_hover']};
        color: {t['accent_text']};
        border: 1px solid {t['border_focus']};
    }}
    QPushButton#PrimaryActionBtn {{
        background-color: {t['accent_bg']};
        color: {t['accent_text']};
        border: 1px solid {t['border_focus']};
        font-weight: 700;
    }}
    QPushButton#PrimaryActionBtn:hover {{
        background-color: {t['accent_hover']};
    }}
    QPushButton:disabled {{
        color: {t['text_secondary']};
        background-color: {t['bg_window']};
        border: 1px solid {t['border']};
    }}
    QTableWidget {{
        background-color: {t['bg_surface']};
        alternate-background-color: {t['bg_alt_row']};
        color: {t['text_primary']};
        border: 1px solid {t['border']};
        border-radius: 6px;
        gridline-color: {t['border']};
        selection-background-color: {t['accent_bg']};
        selection-color: {t['accent_text']};
        font-size: 12px;
    }}
    QHeaderView::section {{
        background-color: {t['bg_elevated']};
        color: {t['text_primary']};
        border: none;
        border-right: 1px solid {t['border']};
        border-bottom: 1px solid {t['border']};
        padding: 6px 8px;
        font-weight: 700;
        font-size: 12px;
    }}
    QTabWidget::pane {{
        border: 1px solid {t['border']};
        background-color: {t['bg_surface']};
        border-radius: 6px;
    }}
    QTabBar::tab {{
        background-color: {t['bg_elevated']};
        color: {t['text_secondary']};
        border: 1px solid {t['border']};
        border-bottom: none;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        padding: 6px 12px;
        margin-right: 2px;
        font-weight: 600;
        font-size: 12px;
    }}
    QTabBar::tab:selected {{
        background-color: {t['accent_bg']};
        color: {t['accent_text']};
        font-weight: 700;
    }}
    """


# ===========================================================================
# 1. 공통 경로·보안·포맷 헬퍼 (가상 드라이브 보호 & 심볼릭 링크/Reparse 차단)
# ===========================================================================

def safe_norm_path(path_str: str) -> str:
    """Path.resolve()의 가상 드라이브(G: 등) 경로 왜곡을 방지하는 안전한 경로 정규화."""
    if not path_str:
        return ""
    cleaned = str(path_str).strip().strip('"')
    if not cleaned:
        return ""
    norm = os.path.normpath(os.path.abspath(cleaned))
    if platform.system() == "Windows" and len(norm) == 2 and norm[1] == ":":
        return norm + "\\"
    return norm


def format_bytes(size_bytes: int) -> str:
    """바이트 단위를 사람이 읽기 쉬운 단위(B / KB / MB / GB / TB / PB)로 포맷팅합니다."""
    if size_bytes < 0:
        return ""
    if size_bytes < 1024:
        return f"{size_bytes:,} B"
    units = ["KB", "MB", "GB", "TB", "PB"]
    val = float(size_bytes)
    for unit in units:
        val /= 1024.0
        if val < 1024.0 or unit == units[-1]:
            return f"{val:,.1f} {unit}" if val < 100.0 else f"{val:,.0f} {unit}"
    return f"{size_bytes:,} B"


def is_symlink_or_reparse_point(path_str: str) -> bool:
    """심볼릭 링크, Windows Junction(mklink /J), 마운트 포인트, Reparse Point 여부를 판별합니다."""
    if not path_str:
        return False
    try:
        if os.path.islink(path_str):
            return True
    except OSError:
        pass
    try:
        st = os.lstat(path_str)
        if stat.S_ISLNK(st.st_mode):
            return True
        file_attrs = getattr(st, "st_file_attributes", 0)
        if isinstance(file_attrs, int) and (file_attrs & FILE_ATTRIBUTE_REPARSE_POINT):
            return True
        reparse_tag = getattr(st, "st_reparse_tag", 0)
        if isinstance(reparse_tag, int) and reparse_tag != 0:
            return True
    except FileNotFoundError:
        return False
    except OSError:
        pass
    if platform.system() == "Windows":
        try:
            attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path_str))
            if attrs != 0xFFFFFFFF and (attrs & FILE_ATTRIBUTE_REPARSE_POINT):
                return True
        except Exception:
            pass
    return False


def validate_safe_filename_segment(name: str) -> Optional[str]:
    """
    단일 파일/폴더 이름이 OS 및 파일시스템 보안 규칙을 준수하는지 검사합니다.
    유효하면 None을 반환하고, 위반 시 구체적인 한국어 차단 사유 문자열을 반환합니다.
    """
    if not isinstance(name, str) or not name:
        return "파일 이름이 비어 있습니다."
    if name in (".", ".."):
        return f"상대 경로 세그먼트('{name}')는 파일명으로 사용할 수 없습니다."
    if "/" in name or "\\" in name:
        return "파일명에 경로 구분자('/' 또는 '\\')를 포함할 수 없습니다."
    if ":" in name:
        return "파일명에 드라이브 콜론 또는 NTFS 대체 데이터 스트림(':')을 포함할 수 없습니다."
    if name.endswith(" ") or name.endswith("."):
        return "파일명 끝에 공백이나 마침표('.')를 사용할 수 없습니다."
    for ch in name:
        if ord(ch) < 32:
            return "파일명에 제어 문자(0x00~0x1F)를 포함할 수 없습니다."
        if ch in WINDOWS_INVALID_CHARS:
            return f"파일명에 금지된 특수문자('{ch}')가 포함되어 있습니다."
    if len(name) > 255:
        return "파일명 길이가 최대 허용치(255자)를 초과했습니다."
    stem_check = name.rstrip(" .").split(".")[0].upper()
    if stem_check in WINDOWS_RESERVED_NAMES:
        return f"Windows 예약 장치명('{name}')은 파일명으로 사용할 수 없습니다."
    return None


def _find_case_insensitive_entry(parent_dir: str, target_name: str) -> Optional[str]:
    """parent_dir 안에서 target_name과 대소문자 무시(casefold) 기준으로 일치하는 실제 경로를 반환합니다."""
    if not parent_dir or not target_name:
        return None
    try:
        if not os.path.isdir(parent_dir) or is_symlink_or_reparse_point(parent_dir):
            return None
        target_cf = target_name.casefold()
        with os.scandir(parent_dir) as it:
            for entry in it:
                if entry.name.casefold() == target_cf:
                    return safe_norm_path(entry.path)
    except OSError:
        return None
    return None


def _split_name_and_ext(filename: str, is_dir: bool = False) -> Tuple[str, str]:
    """폴더 또는 숨김 도트 파일(.gitignore 등)을 안전하게 (stem, ext)로 분리합니다."""
    if is_dir:
        return filename, ""
    p = Path(filename)
    if filename.startswith(".") and filename.count(".") == 1:
        return filename, ""
    return p.stem, p.suffix


# ===========================================================================
# 2. 기능 1: 일괄 이름 바꾸기 (Multi-Rename Tool, Ctrl+M) + 원자적 스테이징 + Undo
# ===========================================================================

class CaseTransform(str, enum.Enum):
    KEEP = "keep"
    LOWER = "lower"
    UPPER = "upper"
    TITLE = "title"
    SENTENCE = "sentence"


class ExtensionMode(str, enum.Enum):
    KEEP = "keep"
    REPLACE = "replace"
    LOWER = "lower"
    UPPER = "upper"
    REMOVE = "remove"


@dataclass(frozen=True)
class MultiRenameRule:
    """일괄 이름 바꾸기 규칙 데이터 계약 (Input Contract)."""
    name_template: str = "[NAME]"
    prefix: str = ""
    suffix: str = ""
    find_text: str = ""
    replace_text: str = ""
    use_regex: bool = False
    case_sensitive: bool = False
    counter_start: int = 1
    counter_step: int = 1
    counter_padding: int = 2
    append_counter_if_no_token: bool = False
    counter_separator: str = "_"
    case_transform: CaseTransform = CaseTransform.KEEP
    extension_mode: ExtensionMode = ExtensionMode.KEEP
    custom_extension: str = ""


@dataclass
class RenamePlanItem:
    """개별 항목의 이름 변경 미리보기 및 검증 상태."""
    index: int
    src_path: str
    old_name: str
    new_name: str
    dst_path: str
    is_dir: bool
    changed: bool
    conflict_reason: Optional[str] = None
    diff_summary: str = ""


@dataclass
class RenamePlanResult:
    """일괄 이름 바꾸기 사전 계획 및 전수 검증 결과 (Output Contract)."""
    items: List[RenamePlanItem]
    has_errors: bool
    error_messages: List[str]
    changed_count: int


@dataclass(frozen=True)
class RenameUndoEntry:
    """단일 항목의 변경 전↔후 경로 쌍."""
    old_path: str
    new_path: str


@dataclass
class RenameUndoBatch:
    """직전 일괄 이름 변경 실행 취소(Undo) 트랜잭션 묶음."""
    batch_id: str
    created_at: str
    entries: List[RenameUndoEntry] = field(default_factory=list)


_COUNTER_TOKEN_RE = re.compile(r"\[N(?::(\d+)(?::(\d+))?(?::(\d+))?)?\]", re.IGNORECASE)


def _apply_counter_tokens(text: str, zero_based_idx: int, rule: MultiRenameRule) -> Tuple[str, bool]:
    """문자열 내 [N] 또는 [N:start:step:pad] 토큰을 치환하고 토큰 존재 여부를 함께 반환합니다."""
    found = False

    def _repl(match: re.Match[str]) -> str:
        nonlocal found
        found = True
        start = int(match.group(1)) if match.group(1) is not None else rule.counter_start
        step = int(match.group(2)) if match.group(2) is not None else rule.counter_step
        pad = int(match.group(3)) if match.group(3) is not None else rule.counter_padding
        val = start + zero_based_idx * step
        return f"{val:0{max(1, pad)}d}"

    return _COUNTER_TOKEN_RE.sub(_repl, text), found


def _apply_case_transform(stem: str, mode: CaseTransform) -> str:
    if mode == CaseTransform.LOWER:
        return stem.lower()
    if mode == CaseTransform.UPPER:
        return stem.upper()
    if mode == CaseTransform.TITLE:
        return stem.title()
    if mode == CaseTransform.SENTENCE:
        return stem[:1].upper() + stem[1:].lower() if stem else stem
    return stem


def _compute_diff_summary(old_name: str, new_name: str) -> str:
    if old_name == new_name:
        return "변경 없음"
    matcher = difflib.SequenceMatcher(None, old_name, new_name)
    parts: List[str] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            parts.append(old_name[i1:i2])
        elif tag == "delete":
            parts.append(f"[-{old_name[i1:i2]}]")
        elif tag == "insert":
            parts.append(f"[+{new_name[j1:j2]}]")
        elif tag == "replace":
            parts.append(f"[{old_name[i1:i2]}→{new_name[j1:j2]}]")
    return "".join(parts)


def plan_multi_rename(source_paths: Sequence[str], rule: MultiRenameRule) -> RenamePlanResult:
    """
    실제 파일시스템을 전혀 수정하지 않고 일괄 이름 바꾸기 결과를 계산하고,
    금지 문자·예약어·배치 내부 중복·기존 디스크 파일 덮어쓰기 충돌을 100% 사전 검증합니다.
    """
    normalized_sources: List[str] = []
    seen_src_cf: Set[str] = set()
    for raw_p in source_paths:
        norm_p = safe_norm_path(raw_p)
        if not norm_p:
            continue
        key_cf = norm_p.casefold()
        if key_cf not in seen_src_cf:
            seen_src_cf.add(key_cf)
            normalized_sources.append(norm_p)

    errors: List[str] = []
    compiled_regex: Optional[re.Pattern[str]] = None
    if rule.find_text and rule.use_regex:
        flags = 0 if rule.case_sensitive else re.IGNORECASE
        try:
            compiled_regex = re.compile(rule.find_text, flags)
        except re.error as exc:
            errors.append(f"정규식 구문 오류: {exc}")
            return RenamePlanResult(items=[], has_errors=True, error_messages=errors, changed_count=0)

    dir_existing_map: Dict[str, Dict[str, str]] = {}
    for norm_p in normalized_sources:
        parent = os.path.dirname(norm_p)
        parent_cf = parent.casefold()
        if parent_cf not in dir_existing_map:
            entries_map: Dict[str, str] = {}
            if os.path.isdir(parent) and not is_symlink_or_reparse_point(parent):
                try:
                    with os.scandir(parent) as it:
                        for entry in it:
                            entries_map[entry.name.casefold()] = safe_norm_path(entry.path)
                except OSError:
                    pass
            dir_existing_map[parent_cf] = entries_map

    batch_source_cf_set: Set[str] = {p.casefold() for p in normalized_sources}
    plan_items: List[RenamePlanItem] = []

    for idx, src_path in enumerate(normalized_sources):
        old_name = os.path.basename(src_path)
        parent_dir = os.path.dirname(src_path)

        item_err: Optional[str] = None
        is_dir = False
        mtime_dt = datetime.datetime.now()

        unsafe_ancestor = next(
            (str(p) for p in [Path(os.path.abspath(src_path)), *Path(os.path.abspath(src_path)).parents]
             if is_symlink_or_reparse_point(str(p))), None
        )
        if unsafe_ancestor:
            item_err = f"경로의 심볼릭 링크/Junction/Reparse 보호: {unsafe_ancestor}"
        elif not os.path.lexists(src_path):
            item_err = "원본 항목이 존재하지 않습니다."
        elif is_symlink_or_reparse_point(src_path):
            item_err = "심볼릭 링크 또는 Reparse Point는 안전을 위해 이름 변경이 차단됩니다."
        elif is_symlink_or_reparse_point(parent_dir):
            item_err = "부모 폴더가 심볼릭 링크 또는 Junction입니다."
        else:
            try:
                st = os.lstat(src_path)
                is_dir = stat.S_ISDIR(st.st_mode)
                mtime_dt = datetime.datetime.fromtimestamp(st.st_mtime)
            except OSError as exc:
                item_err = f"파일 상태 조회 실패: {exc}"

        orig_stem, orig_ext = _split_name_and_ext(old_name, is_dir=is_dir)
        ymd_str = mtime_dt.strftime("%Y%m%d")

        tmpl = rule.name_template if rule.name_template else "[NAME]"
        working_stem = (
            tmpl.replace("[NAME]", orig_stem)
            .replace("[name]", orig_stem)
            .replace("[EXT]", orig_ext.lstrip("."))
            .replace("[ext]", orig_ext.lstrip("."))
            .replace("[YMD]", ymd_str)
            .replace("[ymd]", ymd_str)
        )

        if rule.find_text:
            if compiled_regex is not None:
                try:
                    working_stem = compiled_regex.sub(rule.replace_text, working_stem)
                except re.error as exc:
                    item_err = item_err or f"정규식 치환 오류: {exc}"
            elif rule.case_sensitive:
                working_stem = working_stem.replace(rule.find_text, rule.replace_text)
            else:
                pattern_ci = re.compile(re.escape(rule.find_text), re.IGNORECASE)
                working_stem = pattern_ci.sub(lambda _: rule.replace_text, working_stem)

        combined_stem = f"{rule.prefix}{working_stem}{rule.suffix}"
        combined_stem, token_used = _apply_counter_tokens(combined_stem, idx, rule)
        if rule.append_counter_if_no_token and not token_used:
            num_val = rule.counter_start + idx * rule.counter_step
            pad_w = max(1, rule.counter_padding)
            combined_stem = f"{combined_stem}{rule.counter_separator}{num_val:0{pad_w}d}"

        combined_stem = _apply_case_transform(combined_stem, rule.case_transform)

        if is_dir:
            final_ext = ""
        else:
            if rule.extension_mode == ExtensionMode.KEEP:
                final_ext = orig_ext
            elif rule.extension_mode == ExtensionMode.LOWER:
                final_ext = orig_ext.lower()
            elif rule.extension_mode == ExtensionMode.UPPER:
                final_ext = orig_ext.upper()
            elif rule.extension_mode == ExtensionMode.REMOVE:
                final_ext = ""
            elif rule.extension_mode == ExtensionMode.REPLACE:
                clean_custom = rule.custom_extension.strip().lstrip(".")
                final_ext = f".{clean_custom}" if clean_custom else ""
            else:
                final_ext = orig_ext

        new_name = f"{combined_stem}{final_ext}"
        dst_path = safe_norm_path(os.path.join(parent_dir, new_name))

        if item_err is None:
            seg_err = validate_safe_filename_segment(new_name)
            if seg_err is not None:
                item_err = seg_err

        changed = old_name != new_name
        plan_items.append(
            RenamePlanItem(
                index=idx,
                src_path=src_path,
                old_name=old_name,
                new_name=new_name,
                dst_path=dst_path,
                is_dir=is_dir,
                changed=changed,
                conflict_reason=item_err,
                diff_summary=_compute_diff_summary(old_name, new_name),
            )
        )

    dst_cf_counts: Dict[str, List[RenamePlanItem]] = {}
    for item in plan_items:
        dst_cf_counts.setdefault(item.dst_path.casefold(), []).append(item)

    for _, colliding_group in dst_cf_counts.items():
        if len(colliding_group) > 1:
            names_preview = ", ".join(f"'{it.old_name}'" for it in colliding_group[:3])
            for it in colliding_group:
                if it.conflict_reason is None:
                    it.conflict_reason = (
                        f"배치 내 새 파일명 중복 충돌: {names_preview} 항목이 동일한 이름('{it.new_name}')으로 겹칩니다."
                    )

    for item in plan_items:
        if item.conflict_reason is not None or not item.changed:
            continue
        parent_cf = os.path.dirname(item.src_path).casefold()
        existing_map = dir_existing_map.get(parent_cf, {})
        existing_real = existing_map.get(item.new_name.casefold())
        if existing_real is not None and existing_real.casefold() not in batch_source_cf_set:
            item.conflict_reason = (
                f"기존 파일 덮어쓰기 차단: 폴더 내에 이미 '{os.path.basename(existing_real)}' 항목이 존재합니다."
            )

    for item in plan_items:
        if item.conflict_reason is not None:
            errors.append(f"[{item.old_name} → {item.new_name}] {item.conflict_reason}")

    changed_cnt = sum(1 for it in plan_items if it.changed and it.conflict_reason is None)
    return RenamePlanResult(
        items=plan_items,
        has_errors=bool(errors),
        error_messages=errors,
        changed_count=changed_cnt,
    )


def _rollback_rename_records(staged, committed, original_ids, phase, failure):
    """Restore only matching original identities; preserve conflicts and report recovery paths."""
    messages = []

    def owned(path, original):
        try:
            details = os.lstat(path)
            return (details.st_dev, details.st_ino) == original_ids[original]
        except OSError:
            return False

    for original, temporary, destination in reversed(committed):
        if not owned(destination, original):
            messages.append(f"반영 경로의 파일이 교체/소실되어 이동하지 않았습니다: {destination}")
            continue
        if os.path.lexists(temporary):
            messages.append(f"복구 임시 경로 충돌로 기존 항목을 보존했습니다: {temporary}")
            continue
        try:
            os.rename(destination, temporary)
        except OSError as exc:
            messages.append(f"복구 준비 실패: {destination} → {temporary} ({exc})")

    restored = 0
    for original, temporary, destination in reversed(staged):
        if owned(original, original):
            restored += 1
            continue
        if owned(temporary, original) and not os.path.lexists(original):
            try:
                os.rename(temporary, original)
            except OSError as exc:
                messages.append(f"원래 경로 복구 실패: {original} ({exc})")
        if owned(original, original):
            restored += 1
        else:
            recovery = [path for path in (temporary, destination) if owned(path, original)]
            if recovery:
                messages.append(f"수동 복구 필요: 원래 경로 '{original}'; 원본 보관 경로: {', '.join(recovery)}")
            else:
                messages.append(f"수동 확인 필요: 원본 식별자 위치 미확인; 원래 '{original}', 임시 '{temporary}', 반영 '{destination}'")

    if restored == len(staged):
        headline = f"{phase} 실패 후 원본 {restored}/{len(staged)}개 복원을 확인했습니다: {failure}"
    else:
        headline = f"{phase} 실패; 부분 롤백 {restored}/{len(staged)}개 복원, 충돌 항목은 덮어쓰지 않았습니다: {failure}"
    return [headline, *messages]


def _execute_two_phase_atomic_renames(pairs: Sequence[Tuple[str, str]]) -> Tuple[bool, List[str]]:
    # Pin parent chains for the complete transaction, including rollback/undo.
    # Do not pin source leaf handles: the operation must rename those entries.
    try:
        with contextlib.ExitStack() as locks:
            for parent in sorted({os.path.dirname(os.path.abspath(p)) for pair in pairs for p in pair}):
                locks.enter_context(_locked_sync_paths(parent, parent, parent, parent))
            return _execute_two_phase_atomic_renames_locked(pairs)
    except OSError as exc:
        return False, [f"이름 변경 안전 경로 검증 실패: {exc}"]


def _execute_two_phase_atomic_renames_locked(pairs: Sequence[Tuple[str, str]]) -> Tuple[bool, List[str]]:
    """
    (src_path, dst_path) 목록을 2단계 UUID 임시 스테이징으로 이름 변경합니다.
    - 순환 이름 변경(a.txt ↔ b.txt), 연쇄 변경(1→2, 2→3), 대소문자 단독 변경(a.txt → A.TXT)을 지원합니다.
    - 오류 시 확인된 원본만 복원을 시도하고, 충돌로 복구하지 못한 항목의 보관 경로를 보고합니다.
    """
    active_pairs = [(safe_norm_path(s), safe_norm_path(d)) for s, d in pairs if s != d]
    if not active_pairs:
        return True, []

    batch_src_cf: Set[str] = {s.casefold() for s, _ in active_pairs}
    dst_seen_cf: Set[str] = set()

    for src, dst in active_pairs:
        if not os.path.lexists(src):
            return False, [f"원본 항목을 찾을 수 없습니다: {src}"]
        if is_symlink_or_reparse_point(src):
            return False, [f"심볼릭 링크/Reparse 항목은 변경할 수 없습니다: {src}"]
        seg_err = validate_safe_filename_segment(os.path.basename(dst))
        if seg_err:
            return False, [f"안전하지 않은 대상 이름('{os.path.basename(dst)}'): {seg_err}"]
        dst_cf = dst.casefold()
        if dst_cf in dst_seen_cf:
            return False, [f"대상 경로 중복 충돌: {dst}"]
        dst_seen_cf.add(dst_cf)

        existing_ci = _find_case_insensitive_entry(os.path.dirname(dst), os.path.basename(dst))
        if existing_ci is not None and existing_ci.casefold() not in batch_src_cf:
            return False, [f"기존 파일 보호(덮어쓰기 차단): '{existing_ci}' 항목이 이미 존재합니다."]

    token = uuid.uuid4().hex[:12]
    staged_records: List[Tuple[str, str, str]] = []
    original_ids = {}

    try:
        for idx, (src, dst) in enumerate(active_pairs):
            parent = os.path.dirname(src)
            temp_name = f".pyqdir_ren_stage_{token}_{idx:04d}.tmp"
            temp_path = safe_norm_path(os.path.join(parent, temp_name))
            if os.path.lexists(temp_path) or _find_case_insensitive_entry(parent, temp_name) is not None:
                raise FileExistsError(f"스테이징 임시 경로 충돌: {temp_path}")
            original_stat = os.lstat(src)
            original_ids[src] = (original_stat.st_dev, original_stat.st_ino)
            if not original_stat.st_ino:
                raise PermissionError(f"원본 파일 식별자를 확인할 수 없습니다: {src}")
            os.rename(src, temp_path)
            staged_records.append((src, temp_path, dst))
    except OSError as exc:
        return False, _rollback_rename_records(staged_records, [], original_ids, "1단계 스테이징", exc)

    committed: List[Tuple[str, str, str]] = []
    try:
        for orig_src, temp_path, dst in staged_records:
            parent = os.path.dirname(dst)
            existing_ci = _find_case_insensitive_entry(parent, os.path.basename(dst))
            if existing_ci is not None or os.path.lexists(dst):
                raise FileExistsError(f"동시 생성된 기존 파일 보호 차단: '{existing_ci or dst}'")
            os.rename(temp_path, dst)
            committed.append((orig_src, temp_path, dst))
    except OSError as exc:
        return False, _rollback_rename_records(staged_records, committed, original_ids, "2단계 반영", exc)

    return True, []


def execute_multi_rename_plan(plan: RenamePlanResult) -> Tuple[bool, Optional[RenameUndoBatch], List[str]]:
    """검증 통과한 RenamePlanResult를 실행하고 Undo 배치를 반환합니다."""
    if plan.has_errors:
        return False, None, list(plan.error_messages)

    pairs: List[Tuple[str, str]] = [
        (it.src_path, it.dst_path) for it in plan.items if it.changed and it.conflict_reason is None
    ]
    if not pairs:
        return True, RenameUndoBatch(
            batch_id=uuid.uuid4().hex[:8],
            created_at=datetime.datetime.now().isoformat(timespec="seconds"),
            entries=[],
        ), []

    ok, errs = _execute_two_phase_atomic_renames(pairs)
    if not ok:
        return False, None, errs

    undo_batch = RenameUndoBatch(
        batch_id=uuid.uuid4().hex[:8],
        created_at=datetime.datetime.now().isoformat(timespec="seconds"),
        entries=[RenameUndoEntry(old_path=s, new_path=d) for s, d in pairs],
    )
    return True, undo_batch, []


def undo_multi_rename_batch(batch: RenameUndoBatch) -> Tuple[bool, List[str]]:
    """직전 일괄 이름 변경 배치를 안전하게 실행 취소(원복)합니다 (기존 파일 덮어쓰기 원천 차단)."""
    if not batch.entries:
        return True, []
    reverse_pairs = [(entry.new_path, entry.old_path) for entry in reversed(batch.entries)]
    return _execute_two_phase_atomic_renames(reverse_pairs)


# ===========================================================================
# 3. 기능 2: 패널 간 폴더 비교·동기화 미리보기 (Compare Panes, Shift+F2)
# ===========================================================================

class CompareStatus(str, enum.Enum):
    LEFT_ONLY = "left_only"
    RIGHT_ONLY = "right_only"
    DIFF_LEFT_NEWER = "diff_left_newer"
    DIFF_RIGHT_NEWER = "diff_right_newer"
    DIFF_CONTENT = "diff_content"
    IDENTICAL = "identical"
    SKIPPED_LINK = "skipped_link"


COMPARE_STATUS_LABELS: Dict[CompareStatus, str] = {
    CompareStatus.LEFT_ONLY: "좌측 전용 (→ 복사 후보)",
    CompareStatus.RIGHT_ONLY: "우측 전용 (← 복사 후보)",
    CompareStatus.DIFF_LEFT_NEWER: "상이 (좌측 최신)",
    CompareStatus.DIFF_RIGHT_NEWER: "상이 (우측 최신)",
    CompareStatus.DIFF_CONTENT: "상이 (크기/해시 다름)",
    CompareStatus.IDENTICAL: "동일",
    CompareStatus.SKIPPED_LINK: "링크 제외(보호)",
}


@dataclass(frozen=True)
class CompareOptions:
    """폴더 비교 옵션 데이터 계약."""
    recursive: bool = False
    verify_sha256: bool = False
    mtime_tolerance_sec: float = 2.0
    include_hidden: bool = False


@dataclass
class CompareEntry:
    """패널 간 비교 개별 항목."""
    rel_key_cf: str
    rel_display: str
    is_dir: bool
    status: CompareStatus
    left_path: Optional[str] = None
    right_path: Optional[str] = None
    left_size: Optional[int] = None
    right_size: Optional[int] = None
    left_mtime: Optional[float] = None
    right_mtime: Optional[float] = None
    left_sha256: Optional[str] = None
    right_sha256: Optional[str] = None


@dataclass
class CompareSummary:
    """패널 간 비교 종합 결과."""
    left_root: str
    right_root: str
    entries: List[CompareEntry]
    left_only_count: int = 0
    right_only_count: int = 0
    diff_count: int = 0
    identical_count: int = 0
    skipped_link_count: int = 0


@dataclass
class SyncCopyResult:
    """선택 동기화 복사 결과."""
    copied_count: int
    skipped_conflicts: List[str]
    errors: List[str]
    created_paths: List[str]


def _scan_compare_side(
    root_dir: str,
    recursive: bool,
    include_hidden: bool,
) -> Dict[str, Dict[str, Any]]:
    norm_root = safe_norm_path(root_dir)
    result: Dict[str, Dict[str, Any]] = {}
    if not norm_root or not os.path.isdir(norm_root) or is_symlink_or_reparse_point(norm_root):
        return result

    visited_dirs: Set[Tuple[int, int]] = set()
    try:
        st_root = os.lstat(norm_root)
        if st_root.st_ino:
            visited_dirs.add((st_root.st_dev, st_root.st_ino))
    except OSError:
        pass

    def _walk(curr_dir: str, rel_prefix: str) -> None:
        try:
            scandir_it = os.scandir(curr_dir)
        except OSError:
            return
        with scandir_it as it:
            for entry in it:
                if not include_hidden and entry.name.startswith("."):
                    continue
                rel_disp = f"{rel_prefix}/{entry.name}" if rel_prefix else entry.name
                rel_cf = rel_disp.casefold()
                entry_path = safe_norm_path(entry.path)

                if is_symlink_or_reparse_point(entry_path):
                    result[rel_cf] = {
                        "rel_disp": rel_disp,
                        "path": entry_path,
                        "is_dir": False,
                        "is_link": True,
                        "size": 0,
                        "mtime": 0.0,
                    }
                    continue

                try:
                    st = os.lstat(entry.path)
                except OSError:
                    continue

                is_d = stat.S_ISDIR(st.st_mode)
                if is_d:
                    if recursive:
                        ident = (st.st_dev, st.st_ino)
                        if st.st_ino and ident in visited_dirs:
                            continue
                        if st.st_ino:
                            visited_dirs.add(ident)
                        _walk(entry_path, rel_disp)
                    else:
                        result[rel_cf] = {
                            "rel_disp": rel_disp,
                            "path": entry_path,
                            "is_dir": True,
                            "is_link": False,
                            "size": 0,
                            "mtime": st.st_mtime,
                        }
                elif stat.S_ISREG(st.st_mode):
                    result[rel_cf] = {
                        "rel_disp": rel_disp,
                        "path": entry_path,
                        "is_dir": False,
                        "is_link": False,
                        "size": st.st_size,
                        "mtime": st.st_mtime,
                    }

    _walk(norm_root, "")
    return result


def _sha256_file_quick(path_str: str, chunk_size: int = 262144) -> str:
    h = hashlib.sha256()
    with open(path_str, "rb") as fp:
        while True:
            buf = fp.read(chunk_size)
            if not buf:
                break
            h.update(buf)
    return h.hexdigest()


def compare_directories(
    left_dir: str,
    right_dir: str,
    options: Optional[CompareOptions] = None,
) -> CompareSummary:
    """좌·우 패널 디렉터리의 항목을 정밀 대조하여 CompareSummary를 반환합니다."""
    opts = options or CompareOptions()
    norm_left = safe_norm_path(left_dir)
    norm_right = safe_norm_path(right_dir)

    left_map = _scan_compare_side(norm_left, opts.recursive, opts.include_hidden)
    right_map = _scan_compare_side(norm_right, opts.recursive, opts.include_hidden)

    all_keys = sorted(set(left_map.keys()) | set(right_map.keys()))
    entries: List[CompareEntry] = []
    c_left = c_right = c_diff = c_ident = c_link = 0

    for k in all_keys:
        l_rec = left_map.get(k)
        r_rec = right_map.get(k)

        if (l_rec and l_rec["is_link"]) or (r_rec and r_rec["is_link"]):
            disp = (l_rec or r_rec)["rel_disp"]  # type: ignore[index]
            entries.append(
                CompareEntry(
                    rel_key_cf=k,
                    rel_display=disp,
                    is_dir=False,
                    status=CompareStatus.SKIPPED_LINK,
                    left_path=l_rec["path"] if l_rec else None,
                    right_path=r_rec["path"] if r_rec else None,
                )
            )
            c_link += 1
            continue

        if l_rec is not None and r_rec is None:
            entries.append(
                CompareEntry(
                    rel_key_cf=k,
                    rel_display=l_rec["rel_disp"],
                    is_dir=bool(l_rec["is_dir"]),
                    status=CompareStatus.LEFT_ONLY,
                    left_path=l_rec["path"],
                    left_size=int(l_rec["size"]),
                    left_mtime=float(l_rec["mtime"]),
                )
            )
            c_left += 1
            continue

        if r_rec is not None and l_rec is None:
            entries.append(
                CompareEntry(
                    rel_key_cf=k,
                    rel_display=r_rec["rel_disp"],
                    is_dir=bool(r_rec["is_dir"]),
                    status=CompareStatus.RIGHT_ONLY,
                    right_path=r_rec["path"],
                    right_size=int(r_rec["size"]),
                    right_mtime=float(r_rec["mtime"]),
                )
            )
            c_right += 1
            continue

        assert l_rec is not None and r_rec is not None
        l_dir = bool(l_rec["is_dir"])
        r_dir = bool(r_rec["is_dir"])
        if l_dir != r_dir:
            entries.append(
                CompareEntry(
                    rel_key_cf=k,
                    rel_display=l_rec["rel_disp"],
                    is_dir=l_dir,
                    status=CompareStatus.DIFF_CONTENT,
                    left_path=l_rec["path"],
                    right_path=r_rec["path"],
                    left_size=int(l_rec["size"]),
                    right_size=int(r_rec["size"]),
                    left_mtime=float(l_rec["mtime"]),
                    right_mtime=float(r_rec["mtime"]),
                )
            )
            c_diff += 1
            continue

        if l_dir and r_dir:
            entries.append(
                CompareEntry(
                    rel_key_cf=k,
                    rel_display=l_rec["rel_disp"],
                    is_dir=True,
                    status=CompareStatus.IDENTICAL,
                    left_path=l_rec["path"],
                    right_path=r_rec["path"],
                    left_size=0,
                    right_size=0,
                    left_mtime=float(l_rec["mtime"]),
                    right_mtime=float(r_rec["mtime"]),
                )
            )
            c_ident += 1
            continue

        l_sz = int(l_rec["size"])
        r_sz = int(r_rec["size"])
        l_mt = float(l_rec["mtime"])
        r_mt = float(r_rec["mtime"])
        l_hash: Optional[str] = None
        r_hash: Optional[str] = None

        mt_diff = l_mt - r_mt
        same_mtime = abs(mt_diff) <= max(0.0, opts.mtime_tolerance_sec)

        if l_sz != r_sz:
            if mt_diff > opts.mtime_tolerance_sec:
                status = CompareStatus.DIFF_LEFT_NEWER
            elif mt_diff < -opts.mtime_tolerance_sec:
                status = CompareStatus.DIFF_RIGHT_NEWER
            else:
                status = CompareStatus.DIFF_CONTENT
            c_diff += 1
        elif opts.verify_sha256:
            try:
                l_hash = _sha256_file_quick(l_rec["path"])
                r_hash = _sha256_file_quick(r_rec["path"])
                if l_hash == r_hash:
                    status = CompareStatus.IDENTICAL
                    c_ident += 1
                else:
                    if mt_diff > opts.mtime_tolerance_sec:
                        status = CompareStatus.DIFF_LEFT_NEWER
                    elif mt_diff < -opts.mtime_tolerance_sec:
                        status = CompareStatus.DIFF_RIGHT_NEWER
                    else:
                        status = CompareStatus.DIFF_CONTENT
                    c_diff += 1
            except OSError:
                status = CompareStatus.DIFF_CONTENT
                c_diff += 1
        else:
            if same_mtime:
                status = CompareStatus.IDENTICAL
                c_ident += 1
            elif mt_diff > 0:
                status = CompareStatus.DIFF_LEFT_NEWER
                c_diff += 1
            else:
                status = CompareStatus.DIFF_RIGHT_NEWER
                c_diff += 1

        entries.append(
            CompareEntry(
                rel_key_cf=k,
                rel_display=l_rec["rel_disp"],
                is_dir=False,
                status=status,
                left_path=l_rec["path"],
                right_path=r_rec["path"],
                left_size=l_sz,
                right_size=r_sz,
                left_mtime=l_mt,
                right_mtime=r_mt,
                left_sha256=l_hash,
                right_sha256=r_hash,
            )
        )

    return CompareSummary(
        left_root=norm_left,
        right_root=norm_right,
        entries=entries,
        left_only_count=c_left,
        right_only_count=c_right,
        diff_count=c_diff,
        identical_count=c_ident,
        skipped_link_count=c_link,
    )


@contextlib.contextmanager
def _locked_sync_paths(source: str, target_parent: str, source_root: str, target_root: str):
    """Pin every Windows ancestor against writes/deletion, rejecting all reparse points.

    Path-only prechecks cannot protect against concurrent ancestor replacement.
    Other platforms fail closed until an equivalent descriptor-relative backend exists.
    """
    if os.name != "nt":
        raise PermissionError("안전한 선택 복사는 Windows 경로 잠금이 필요합니다.")
    from ctypes import wintypes

    class FileInformation(ctypes.Structure):
        _fields_ = [("attributes", wintypes.DWORD), ("created", wintypes.FILETIME),
                    ("accessed", wintypes.FILETIME), ("written", wintypes.FILETIME),
                    ("volume", wintypes.DWORD), ("size_high", wintypes.DWORD),
                    ("size_low", wintypes.DWORD), ("links", wintypes.DWORD),
                    ("index_high", wintypes.DWORD), ("index_low", wintypes.DWORD)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                       ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    create.restype = wintypes.HANDLE
    info = kernel.GetFileInformationByHandle
    info.argtypes = [wintypes.HANDLE, ctypes.POINTER(FileInformation)]
    info.restype = wintypes.BOOL
    close = kernel.CloseHandle
    close.argtypes = [wintypes.HANDLE]
    close.restype = wintypes.BOOL
    handles = []
    locked = set()

    def pin(path, create_missing=False, leaf_file=False):
        absolute = Path(os.path.abspath(path))
        chain = list(reversed(absolute.parents)) + [absolute]
        for item in chain:
            key = str(item).casefold()
            if key in locked:
                continue
            if not os.path.lexists(item) and create_missing:
                # The parent is already pinned, so mkdir cannot traverse a replaced ancestor.
                os.mkdir(item)
            handle = create(str(item), 0x80, 0x1, None, 3, 0x02200000, None)
            if handle == ctypes.c_void_p(-1).value:
                raise ctypes.WinError(ctypes.get_last_error())
            handles.append(handle)
            details = FileInformation()
            if not info(handle, ctypes.byref(details)):
                raise ctypes.WinError(ctypes.get_last_error())
            if details.attributes & FILE_ATTRIBUTE_REPARSE_POINT:
                raise PermissionError(f"경로의 심볼릭 링크/Junction/Reparse 차단: {item}")
            if not (leaf_file and item == absolute) and not details.attributes & 0x10:
                raise NotADirectoryError(str(item))
            locked.add(key)

    try:
        # Pin roots before creating any missing destination subdirectory.
        pin(source_root)
        pin(target_root)
        pin(source, leaf_file=not os.path.isdir(source))
        pin(target_parent, create_missing=True)
        yield
    finally:
        for handle in reversed(handles):
            close(handle)


def _copy_file_exclusive_no_overwrite(src_file: str, dst_file: str) -> None:
    """Create the destination exclusively while caller holds the ancestor locks.

    No rename/unlink cleanup uses a mutable pathname. Failure cleanup marks only
    our exclusively held file handle for deletion; existing files stay untouched.
    """
    base = os.path.basename(dst_file)
    seg_err = validate_safe_filename_segment(base)
    if seg_err:
        raise PermissionError(f"대상 파일명 보안 차단('{base}'): {seg_err}")
    if os.name != "nt":
        raise PermissionError("안전한 선택 복사는 Windows 경로 잠금이 필요합니다.")
    import msvcrt
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                       ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    create.restype = wintypes.HANDLE
    with open(src_file, "rb") as rf:
        # CREATE_NEW is atomic and refuses any existing file/link, including a late collision.
        handle = create(dst_file, 0x40010000, 0, None, 1, 0x00200000, None)
        if handle == ctypes.c_void_p(-1).value:
            error = ctypes.get_last_error()
            if error in (80, 183):
                raise FileExistsError(f"기존 파일 보호(덮어쓰기 차단): {dst_file}")
            raise ctypes.WinError(error)
        descriptor = None
        wf = None
        try:
            descriptor = msvcrt.open_osfhandle(handle, os.O_WRONLY | os.O_BINARY)
            wf = os.fdopen(descriptor, "wb")
            shutil.copyfileobj(rf, wf, length=262144)
            wf.flush()
            source_stat = os.fstat(rf.fileno())
            modified = wintypes.FILETIME()
            ticks = source_stat.st_mtime_ns // 100 + 116444736000000000
            modified.dwLowDateTime = ticks & 0xffffffff
            modified.dwHighDateTime = ticks >> 32
            set_time = kernel.SetFileTime
            set_time.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(wintypes.FILETIME)]
            set_time.restype = wintypes.BOOL
            if not set_time(handle, None, None, ctypes.byref(modified)):
                raise ctypes.WinError(ctypes.get_last_error())
        except BaseException as exc:
            disposition = ctypes.c_ubyte(1)
            remove_by_handle = kernel.SetFileInformationByHandle
            remove_by_handle.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
            remove_by_handle.restype = wintypes.BOOL
            if not remove_by_handle(handle, 4, ctypes.byref(disposition), ctypes.sizeof(disposition)):
                raise OSError(f"복사 실패 후 새 사본 정리 실패: {ctypes.WinError(ctypes.get_last_error())}") from exc
            raise
        finally:
            if wf is not None:
                wf.close()
            elif descriptor is not None:
                os.close(descriptor)
            else:
                close = kernel.CloseHandle
                close.argtypes = [wintypes.HANDLE]
                close(handle)



def _make_safe_side_by_side_dest(dest_dir: str, filename: str, tag: str = "sync") -> str:
    stem, ext = _split_name_and_ext(filename, is_dir=False)
    counter = 1
    while True:
        cand_name = f"{stem}_{tag}_{counter}{ext}"
        if _find_case_insensitive_entry(dest_dir, cand_name) is None:
            return safe_norm_path(os.path.join(dest_dir, cand_name))
        counter += 1


def execute_selective_sync_copy(
    selected_entries: Sequence[CompareEntry],
    direction: str,
    left_root: str,
    right_root: str,
    conflict_policy: str = "block",
) -> SyncCopyResult:
    """
    비교 항목 중 선택된 항목을 지정 방향('left_to_right' 또는 'right_to_left')으로 안전 복사합니다.
    - conflict_policy="block" (기본값): 대상에 이미 동명 파일이 있으면 절대 덮어쓰지 않고 skipped_conflicts에 기록.
    - conflict_policy="rename_copy": 대상 원본을 그대로 보존하고 `파일명_sync_1.ext` 안전 사본 이름으로 저장.
    - 어떤 경우에도 기존 파일을 삭제하거나 덮어쓰지 않습니다.
    """
    if direction not in ("left_to_right", "right_to_left"):
        raise ValueError(f"지원하지 않는 동기화 방향입니다: {direction}")
    if conflict_policy not in ("block", "rename_copy"):
        raise ValueError(f"허용되지 않는 충돌 정책입니다(덮어쓰기 금지): {conflict_policy}")

    norm_left = safe_norm_path(left_root)
    norm_right = safe_norm_path(right_root)
    if norm_left.casefold() == norm_right.casefold():
        return SyncCopyResult(
            copied_count=0,
            skipped_conflicts=[],
            errors=["기준 폴더와 대상 폴더가 동일합니다."],
            created_paths=[],
        )

    copied = 0
    skipped_conflicts: List[str] = []
    errors: List[str] = []
    created_paths: List[str] = []

    for entry in selected_entries:
        if entry.status == CompareStatus.SKIPPED_LINK:
            skipped_conflicts.append(f"{entry.rel_display}: 심볼릭 링크/Reparse 보호 제외")
            continue

        src_path = entry.left_path if direction == "left_to_right" else entry.right_path
        dst_root = norm_right if direction == "left_to_right" else norm_left
        if not src_path:
            continue

        rel_parts = [seg for seg in entry.rel_display.replace("\\", "/").split("/") if seg]
        seg_bad = next(
            (validate_safe_filename_segment(seg) for seg in rel_parts if validate_safe_filename_segment(seg)),
            None,
        )
        if seg_bad:
            errors.append(f"{entry.rel_display}: {seg_bad}")
            continue

        target_path = safe_norm_path(os.path.join(dst_root, *rel_parts))
        target_parent = os.path.dirname(target_path)
        target_name = os.path.basename(target_path)

        source_root = norm_left if direction == "left_to_right" else norm_right
        try:
            if not rel_parts or os.path.normcase(os.path.commonpath([os.path.abspath(src_path), os.path.abspath(source_root)])) != os.path.normcase(os.path.abspath(source_root)):
                raise PermissionError("비교 기준 폴더 밖의 원본 경로입니다.")
            with _locked_sync_paths(src_path, target_parent, source_root, dst_root):
                if entry.is_dir:
                    existing_ci = _find_case_insensitive_entry(target_parent, target_name)
                    if existing_ci is not None:
                        if os.path.isdir(existing_ci) and not is_symlink_or_reparse_point(existing_ci):
                            continue
                        skipped_conflicts.append(f"{entry.rel_display}: 동명 항목 충돌 차단")
                        continue
                    try:
                        os.makedirs(target_path, exist_ok=False)
                        copied += 1
                        created_paths.append(target_path)
                    except OSError as exc:
                        errors.append(f"{entry.rel_display}: 폴더 생성 실패 ({exc})")
                    continue

                existing_ci = _find_case_insensitive_entry(target_parent, target_name)
                if existing_ci is not None or os.path.lexists(target_path):
                    if conflict_policy == "block":
                        skipped_conflicts.append(
                            f"{entry.rel_display}: 기존 파일 보호로 덮어쓰기 차단 ('{os.path.basename(existing_ci or target_path)}')"
                        )
                        continue
                    target_path = _make_safe_side_by_side_dest(target_parent, target_name, tag="sync")

                try:
                    _copy_file_exclusive_no_overwrite(src_path, target_path)
                    copied += 1
                    created_paths.append(target_path)
                except FileExistsError as exc:
                    skipped_conflicts.append(f"{entry.rel_display}: {exc}")
                except OSError as exc:
                    errors.append(f"{entry.rel_display}: 복사 실패; 새 불완전 사본이 남을 수 있습니다 ({exc})")
        except OSError as exc:
            errors.append(f"{entry.rel_display}: 안전 경로 검증/복사 실패 ({exc})")

    return SyncCopyResult(
        copied_count=copied,
        skipped_conflicts=skipped_conflicts,
        errors=errors,
        created_paths=created_paths,
    )


# ===========================================================================
# 4. 기능 3: 폴더 실제 용량 계산 (Calculate Occupied Space, Alt+Shift+Enter)
# ===========================================================================

@dataclass
class FolderSizeSummary:
    """폴더 하위 실제 용량 합산 결과."""
    folder_path: str
    total_bytes: int
    file_count: int
    dir_count: int
    skipped_links: int = 0
    error_count: int = 0
    cancelled: bool = False

    @property
    def formatted_size(self) -> str:
        return format_bytes(self.total_bytes)


def calculate_folder_occupied_size(
    folder_path: str,
    cancel_event: Optional[threading.Event] = None,
    max_depth: int = 128,
) -> FolderSizeSummary:
    """
    지정 폴더의 하위 모든 일반 파일 실제 용량과 파일·폴더 수를 고속 합산합니다.
    - 심볼릭 링크 및 Windows Junction/Reparse Point를 절대 따라가지 않아 무한 루프를 원천 방지합니다.
    - 동일 물리 파일(하드링크 st_dev/st_ino) 중복 합산을 방지합니다.
    """
    norm_folder = safe_norm_path(folder_path)
    if not norm_folder or not os.path.exists(norm_folder):
        return FolderSizeSummary(norm_folder, 0, 0, 0, error_count=1)
    if is_symlink_or_reparse_point(norm_folder):
        return FolderSizeSummary(norm_folder, 0, 0, 0, skipped_links=1)

    total_bytes = 0
    file_count = 0
    dir_count = 0
    skipped_links = 0
    error_count = 0

    seen_inodes: Set[Tuple[int, int]] = set()
    seen_dirs: Set[Tuple[int, int]] = set()

    try:
        root_st = os.lstat(norm_folder)
        if root_st.st_ino:
            seen_dirs.add((root_st.st_dev, root_st.st_ino))
    except OSError:
        return FolderSizeSummary(norm_folder, 0, 0, 0, error_count=1)

    stack: List[Tuple[str, int]] = [(norm_folder, 0)]
    while stack:
        if cancel_event is not None and cancel_event.is_set():
            return FolderSizeSummary(
                norm_folder,
                total_bytes,
                file_count,
                dir_count,
                skipped_links=skipped_links,
                error_count=error_count,
                cancelled=True,
            )

        curr_dir, depth = stack.pop()
        if depth > max_depth:
            continue

        try:
            scandir_it = os.scandir(curr_dir)
        except OSError:
            error_count += 1
            continue

        with scandir_it as it:
            for entry in it:
                if cancel_event is not None and cancel_event.is_set():
                    return FolderSizeSummary(
                        norm_folder,
                        total_bytes,
                        file_count,
                        dir_count,
                        skipped_links=skipped_links,
                        error_count=error_count,
                        cancelled=True,
                    )

                entry_p = entry.path
                if is_symlink_or_reparse_point(entry_p):
                    skipped_links += 1
                    continue

                try:
                    st = os.lstat(entry_p)
                except OSError:
                    error_count += 1
                    continue

                if stat.S_ISDIR(st.st_mode):
                    if st.st_ino:
                        d_key = (st.st_dev, st.st_ino)
                        if d_key in seen_dirs:
                            continue
                        seen_dirs.add(d_key)
                    dir_count += 1
                    stack.append((entry_p, depth + 1))
                elif stat.S_ISREG(st.st_mode):
                    file_count += 1
                    if st.st_ino and st.st_nlink > 1:
                        f_key = (st.st_dev, st.st_ino)
                        if f_key in seen_inodes:
                            continue
                        seen_inodes.add(f_key)
                    total_bytes += st.st_size

    return FolderSizeSummary(
        folder_path=norm_folder,
        total_bytes=total_bytes,
        file_count=file_count,
        dir_count=dir_count,
        skipped_links=skipped_links,
        error_count=error_count,
        cancelled=False,
    )


def calculate_immediate_subfolders_sizes(
    parent_dir: str,
    target_folders: Optional[Sequence[str]] = None,
    include_hidden: bool = False,
    cancel_event: Optional[threading.Event] = None,
) -> Dict[str, FolderSizeSummary]:
    """선택된 폴더들(또는 parent_dir 내 전체 직속 하위 폴더)의 실제 용량 맵을 반환합니다."""
    results: Dict[str, FolderSizeSummary] = {}
    folders_to_calc: List[str] = []

    if target_folders:
        for p in target_folders:
            norm_p = safe_norm_path(p)
            if os.path.isdir(norm_p) and not is_symlink_or_reparse_point(norm_p):
                folders_to_calc.append(norm_p)
    else:
        norm_parent = safe_norm_path(parent_dir)
        if os.path.isdir(norm_parent) and not is_symlink_or_reparse_point(norm_parent):
            try:
                with os.scandir(norm_parent) as it:
                    for entry in it:
                        if not include_hidden and entry.name.startswith("."):
                            continue
                        if not is_symlink_or_reparse_point(entry.path):
                            try:
                                if entry.is_dir(follow_symlinks=False):
                                    folders_to_calc.append(safe_norm_path(entry.path))
                            except OSError:
                                continue
            except OSError:
                pass

    for folder in folders_to_calc:
        if cancel_event is not None and cancel_event.is_set():
            break
        results[folder] = calculate_folder_occupied_size(folder, cancel_event=cancel_event)
    return results


# ===========================================================================
# 5. 기능 4: 파일 해시(MD5/SHA-1/SHA-256) 계산·검증 & 3단계 고속 중복 파일 찾기
# ===========================================================================

@dataclass(frozen=True)
class FileHashRecord:
    """단일 파일의 3종 해시(MD5, SHA-1, SHA-256) 계산 결과."""
    file_path: str
    file_name: str
    size_bytes: int
    md5: str
    sha1: str
    sha256: str


@dataclass(frozen=True)
class HashVerificationResult:
    """기대 해시 문자열(클립보드/사용자 입력)과의 대조 결과."""
    matched: bool
    algorithm: str
    expected_clean: str
    actual_hash: str
    message: str


@dataclass(frozen=True)
class DuplicateFileEntry:
    """중복 파일 그룹 내 개별 파일 정보."""
    path: str
    name: str
    parent_dir: str
    size_bytes: int
    mtime: float


@dataclass
class DuplicateGroup:
    """바이트 단위 SHA-256 완전 일치 중복 파일 그룹."""
    group_id: int
    size_bytes: int
    sha256: str
    files: List[DuplicateFileEntry]

    @property
    def wasted_bytes(self) -> int:
        return self.size_bytes * max(0, len(self.files) - 1)


@dataclass
class DuplicateScanResult:
    """3단계 고속 중복 파일 탐색 결과 요약."""
    root_dir: str
    scanned_files: int
    stage1_candidate_files: int
    stage2_candidate_files: int
    stage3_hashed_files: int
    groups: List[DuplicateGroup]
    total_wasted_bytes: int
    skipped_links: int = 0
    skipped_hardlinks: int = 0
    cancelled: bool = False


def compute_file_hashes(
    file_path: str,
    chunk_size: int = 524288,
    cancel_event: Optional[threading.Event] = None,
) -> FileHashRecord:
    """
    단일 파일 스트리밍 1회 읽기로 MD5, SHA-1, SHA-256 해시를 동시에 계산합니다.
    심볼릭 링크는 안전을 위해 거부합니다.
    """
    norm_p = safe_norm_path(file_path)
    if is_symlink_or_reparse_point(norm_p):
        raise PermissionError(f"심볼릭 링크/Reparse 파일은 해시 계산 대상에서 차단됩니다: {norm_p}")
    st = os.stat(norm_p, follow_symlinks=False)
    if not stat.S_ISREG(st.st_mode):
        raise ValueError(f"일반 파일만 해시를 계산할 수 있습니다: {norm_p}")

    h_md5 = hashlib.md5()
    h_sha1 = hashlib.sha1()
    h_sha256 = hashlib.sha256()

    with open(norm_p, "rb") as fp:
        while True:
            if cancel_event is not None and cancel_event.is_set():
                raise InterruptedError("사용자 요청으로 해시 계산이 중단되었습니다.")
            chunk = fp.read(chunk_size)
            if not chunk:
                break
            h_md5.update(chunk)
            h_sha1.update(chunk)
            h_sha256.update(chunk)

    return FileHashRecord(
        file_path=norm_p,
        file_name=os.path.basename(norm_p),
        size_bytes=st.st_size,
        md5=h_md5.hexdigest(),
        sha1=h_sha1.hexdigest(),
        sha256=h_sha256.hexdigest(),
    )


_HEX_HASH_EXTRACT_RE = re.compile(r"\b([0-9a-fA-F]{32}|[0-9a-fA-F]{40}|[0-9a-fA-F]{64})\b")


def verify_expected_hash(record: FileHashRecord, raw_expected: str) -> HashVerificationResult:
    """
    클립보드 또는 입력창의 해시 문자열(`sha256sum` 포맷 `<hash> *file` 포함)에서
    해시 알고리즘(MD5 32자 / SHA-1 40자 / SHA-256 64자)을 자동 감지해 일치 여부를 검증합니다.
    """
    stripped = (raw_expected or "").strip()
    if not stripped:
        return HashVerificationResult(
            matched=False,
            algorithm="NONE",
            expected_clean="",
            actual_hash="",
            message="비교할 해시값을 입력하거나 클립보드에서 붙여넣으세요.",
        )

    m = _HEX_HASH_EXTRACT_RE.search(stripped)
    if not m:
        return HashVerificationResult(
            matched=False,
            algorithm="INVALID",
            expected_clean=stripped,
            actual_hash="",
            message="유효한 MD5(32자), SHA-1(40자), SHA-256(64자) 16진수 해시 형식이 아닙니다.",
        )

    clean_hex = m.group(1).lower()
    if len(clean_hex) == 32:
        algo, actual = "MD5", record.md5.lower()
    elif len(clean_hex) == 40:
        algo, actual = "SHA-1", record.sha1.lower()
    else:
        algo, actual = "SHA-256", record.sha256.lower()

    is_match = clean_hex == actual
    msg = (
        f"검증 통과: {algo} 해시가 정확히 일치합니다."
        if is_match
        else f"검증 불일치: 기대 {algo} 해시와 실제 파일 해시가 다릅니다!"
    )
    return HashVerificationResult(
        matched=is_match,
        algorithm=algo,
        expected_clean=clean_hex,
        actual_hash=actual,
        message=msg,
    )


def export_hash_manifest(
    records: Sequence[FileHashRecord],
    output_path: str,
    algorithm: str = "sha256",
) -> str:
    """표준 sha256sum / md5sum 호환 체크섬 매니페스트 파일을 비덮어쓰기('x') 모드로 저장합니다."""
    algo_norm = algorithm.lower().replace("-", "")
    if algo_norm not in ("md5", "sha1", "sha256"):
        raise ValueError(f"지원하지 않는 해시 알고리즘입니다: {algorithm}")

    norm_out = safe_norm_path(output_path)
    parent = os.path.dirname(norm_out)
    base = os.path.basename(norm_out)
    seg_err = validate_safe_filename_segment(base)
    if seg_err:
        raise PermissionError(seg_err)
    if _find_case_insensitive_entry(parent, base) is not None or os.path.lexists(norm_out):
        raise FileExistsError(f"기존 파일 보호(덮어쓰기 차단): '{norm_out}' 파일이 이미 존재합니다.")

    lines: List[str] = []
    for rec in records:
        digest = getattr(rec, algo_norm)
        lines.append(f"{digest} *{rec.file_name}")

    anchor = Path(os.path.abspath(parent)).anchor
    with _locked_sync_paths(anchor, parent, anchor, anchor):
        with open(norm_out, "x", encoding="utf-8", newline="\n") as fp:
            fp.write("\n".join(lines) + ("\n" if lines else ""))
    return norm_out


def _partial_edge_hash(file_path: str, size_bytes: int, edge_bytes: int = 4096) -> str:
    """2단계 고속 필터링용 앞 4KB + 뒤 4KB 부분 해시를 계산합니다."""
    h = hashlib.sha256()
    with open(file_path, "rb") as fp:
        if size_bytes <= edge_bytes * 2:
            h.update(fp.read())
        else:
            h.update(fp.read(edge_bytes))
            fp.seek(size_bytes - edge_bytes)
            h.update(fp.read(edge_bytes))
    return h.hexdigest()


def find_duplicate_files_3stage(
    root_dir: str,
    recursive: bool = True,
    min_size_bytes: int = 1,
    include_hidden: bool = False,
    cancel_event: Optional[threading.Event] = None,
) -> DuplicateScanResult:
    """
    3단계 고속 파이프라인으로 바이트 단위 중복 파일 그룹을 안전하게 탐지합니다 (자동 삭제 0건).
      - Stage 1: 파일 크기(st_size) 그룹화 -> 유일 크기 파일 디스크 I/O 0바이트로 즉시 제외
      - Stage 2: 앞 4KB + 뒤 4KB 부분 SHA-256 해시 -> 고정 크기 비동일 파일 초고속 제외
      - Stage 3: 전체 스트리밍 SHA-256 해시 확정 (동일 물리 inode 하드링크는 중복 낭비에서 자동 제외)
    """
    norm_root = safe_norm_path(root_dir)
    if not norm_root or not os.path.isdir(norm_root) or is_symlink_or_reparse_point(norm_root):
        return DuplicateScanResult(norm_root, 0, 0, 0, 0, [], 0)

    size_buckets: Dict[int, List[DuplicateFileEntry]] = {}
    seen_inodes: Set[Tuple[int, int]] = set()
    seen_dirs: Set[Tuple[int, int]] = set()
    scanned_files = 0
    skipped_links = 0
    skipped_hardlinks = 0

    try:
        st_r = os.lstat(norm_root)
        if st_r.st_ino:
            seen_dirs.add((st_r.st_dev, st_r.st_ino))
    except OSError:
        return DuplicateScanResult(norm_root, 0, 0, 0, 0, [], 0)

    stack: List[str] = [norm_root]
    while stack:
        if cancel_event is not None and cancel_event.is_set():
            return DuplicateScanResult(norm_root, scanned_files, 0, 0, 0, [], 0, cancelled=True)
        curr = stack.pop()
        try:
            scandir_it = os.scandir(curr)
        except OSError:
            continue
        with scandir_it as it:
            for entry in it:
                if not include_hidden and entry.name.startswith("."):
                    continue
                if is_symlink_or_reparse_point(entry.path):
                    skipped_links += 1
                    continue
                try:
                    st = os.lstat(entry.path)
                except OSError:
                    continue

                if stat.S_ISDIR(st.st_mode):
                    if recursive:
                        if st.st_ino:
                            d_id = (st.st_dev, st.st_ino)
                            if d_id in seen_dirs:
                                continue
                            seen_dirs.add(d_id)
                        stack.append(safe_norm_path(entry.path))
                elif stat.S_ISREG(st.st_mode):
                    scanned_files += 1
                    if st.st_size < min_size_bytes:
                        continue
                    if st.st_ino and st.st_nlink > 1:
                        f_id = (st.st_dev, st.st_ino)
                        if f_id in seen_inodes:
                            skipped_hardlinks += 1
                            continue
                        seen_inodes.add(f_id)
                    norm_f = safe_norm_path(entry.path)
                    size_buckets.setdefault(st.st_size, []).append(
                        DuplicateFileEntry(
                            path=norm_f,
                            name=entry.name,
                            parent_dir=os.path.dirname(norm_f),
                            size_bytes=st.st_size,
                            mtime=st.st_mtime,
                        )
                    )

    stage1_groups = {sz: items for sz, items in size_buckets.items() if len(items) >= 2}
    stage1_cnt = sum(len(v) for v in stage1_groups.values())

    partial_buckets: Dict[Tuple[int, str], List[DuplicateFileEntry]] = {}
    for sz, items in stage1_groups.items():
        for f_entry in items:
            if cancel_event is not None and cancel_event.is_set():
                return DuplicateScanResult(
                    norm_root, scanned_files, stage1_cnt, 0, 0, [], 0,
                    skipped_links=skipped_links, skipped_hardlinks=skipped_hardlinks, cancelled=True
                )
            try:
                p_hash = _partial_edge_hash(f_entry.path, sz)
                partial_buckets.setdefault((sz, p_hash), []).append(f_entry)
            except OSError:
                continue

    stage2_groups = {k: v for k, v in partial_buckets.items() if len(v) >= 2}
    stage2_cnt = sum(len(v) for v in stage2_groups.values())

    full_buckets: Dict[Tuple[int, str], List[DuplicateFileEntry]] = {}
    stage3_hashed = 0
    for (sz, p_hash), items in stage2_groups.items():
        if sz <= 8192:
            full_buckets[(sz, p_hash)] = items
            continue
        for f_entry in items:
            if cancel_event is not None and cancel_event.is_set():
                return DuplicateScanResult(
                    norm_root, scanned_files, stage1_cnt, stage2_cnt, stage3_hashed, [], 0,
                    skipped_links=skipped_links, skipped_hardlinks=skipped_hardlinks, cancelled=True
                )
            try:
                stage3_hashed += 1
                full_h = _sha256_file_quick(f_entry.path)
                full_buckets.setdefault((sz, full_h), []).append(f_entry)
            except OSError:
                continue

    confirmed_groups: List[DuplicateGroup] = []
    sorted_confirmed = sorted(
        ((sz, full_h, items) for (sz, full_h), items in full_buckets.items() if len(items) >= 2),
        key=lambda x: (-x[0] * (len(x[2]) - 1), -x[0], x[1]),
    )
    for g_idx, (sz, full_h, items) in enumerate(sorted_confirmed, start=1):
        ordered_files = sorted(items, key=lambda e: (e.mtime, e.path.casefold()))
        confirmed_groups.append(
            DuplicateGroup(
                group_id=g_idx,
                size_bytes=sz,
                sha256=full_h,
                files=ordered_files,
            )
        )

    total_wasted = sum(g.wasted_bytes for g in confirmed_groups)
    return DuplicateScanResult(
        root_dir=norm_root,
        scanned_files=scanned_files,
        stage1_candidate_files=stage1_cnt,
        stage2_candidate_files=stage2_cnt,
        stage3_hashed_files=stage3_hashed,
        groups=confirmed_groups,
        total_wasted_bytes=total_wasted,
        skipped_links=skipped_links,
        skipped_hardlinks=skipped_hardlinks,
        cancelled=False,
    )


# ===========================================================================
# 6. 기능 5: 파일 목록 내보내기 (CSV/MD/HTML/TXT) + 플랫 뷰(Ctrl+B) + 탭 복제·잠금
# ===========================================================================

class ExportFormat(str, enum.Enum):
    CSV = "csv"
    MARKDOWN = "md"
    HTML = "html"
    TXT = "txt"


@dataclass(frozen=True)
class ExportOptions:
    """파일 목록 내보내기 옵션 계약."""
    fmt: ExportFormat = ExportFormat.CSV
    recursive: bool = False
    include_hidden: bool = False
    include_sha256: bool = False
    sanitize_csv_formulas: bool = True
    dark_html: bool = False


@dataclass(frozen=True)
class ExportRecord:
    """내보내기용 정규화 파일/폴더 행 데이터."""
    name: str
    rel_path: str
    full_path: str
    is_dir: bool
    type_label: str
    size_bytes: int
    size_display: str
    modified_iso: str
    sha256: str = ""


def _sanitize_csv_cell(val: str, enabled: bool) -> str:
    if enabled and val and val[0] in CSV_DANGEROUS_PREFIXES:
        return "'" + val
    return val


def collect_export_records(
    root_dir: str,
    options: Optional[ExportOptions] = None,
    folder_size_cache: Optional[Dict[str, FolderSizeSummary]] = None,
) -> List[ExportRecord]:
    """지정 폴더(단일 계층 또는 하위 재귀)의 파일 목록을 수집하여 정렬된 ExportRecord 리스트로 반환합니다."""
    opts = options or ExportOptions()
    norm_root = safe_norm_path(root_dir)
    if not norm_root or not os.path.isdir(norm_root) or is_symlink_or_reparse_point(norm_root):
        return []

    records: List[ExportRecord] = []
    seen_dirs: Set[Tuple[int, int]] = set()
    try:
        st_r = os.lstat(norm_root)
        if st_r.st_ino:
            seen_dirs.add((st_r.st_dev, st_r.st_ino))
    except OSError:
        return []

    def _scan_dir(curr_dir: str, rel_prefix: str) -> None:
        try:
            with os.scandir(curr_dir) as it:
                entries = sorted(
                    list(it),
                    key=lambda e: (not e.is_dir(follow_symlinks=False), e.name.casefold()),
                )
        except OSError:
            return

        for entry in entries:
            if not opts.include_hidden and entry.name.startswith("."):
                continue
            full_p = safe_norm_path(entry.path)
            if is_symlink_or_reparse_point(full_p):
                continue
            try:
                st = os.lstat(entry.path)
            except OSError:
                continue

            is_d = stat.S_ISDIR(st.st_mode)
            rel_p = f"{rel_prefix}/{entry.name}" if rel_prefix else entry.name
            mod_str = datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S")

            if is_d:
                cached = folder_size_cache.get(full_p) if folder_size_cache else None
                sz_b = cached.total_bytes if cached else 0
                sz_disp = cached.formatted_size if cached else "<DIR>"
                records.append(
                    ExportRecord(
                        name=entry.name,
                        rel_path=rel_p,
                        full_path=full_p,
                        is_dir=True,
                        type_label="폴더",
                        size_bytes=sz_b,
                        size_display=sz_disp,
                        modified_iso=mod_str,
                        sha256="",
                    )
                )
                if opts.recursive:
                    if st.st_ino:
                        d_id = (st.st_dev, st.st_ino)
                        if d_id in seen_dirs:
                            continue
                        seen_dirs.add(d_id)
                    _scan_dir(full_p, rel_p)
            elif stat.S_ISREG(st.st_mode):
                ext = Path(entry.name).suffix.lower()
                t_lbl = f"{ext[1:].upper()} 파일" if ext else "파일"
                sha_val = ""
                if opts.include_sha256:
                    try:
                        sha_val = _sha256_file_quick(full_p)
                    except OSError:
                        sha_val = ""
                records.append(
                    ExportRecord(
                        name=entry.name,
                        rel_path=rel_p,
                        full_path=full_p,
                        is_dir=False,
                        type_label=t_lbl,
                        size_bytes=st.st_size,
                        size_display=format_bytes(st.st_size),
                        modified_iso=mod_str,
                        sha256=sha_val,
                    )
                )

    _scan_dir(norm_root, "")
    return records


def render_export_content(
    root_dir: str,
    records: Sequence[ExportRecord],
    options: Optional[ExportOptions] = None,
) -> str:
    """수집된 ExportRecord 목록을 CSV / Markdown / HTML / TXT 문자열로 렌더링합니다."""
    opts = options or ExportOptions()
    headers = ["이름", "상대 경로", "유형", "크기(Bytes)", "크기(표시)", "수정한 날짜"]
    if opts.include_sha256:
        headers.append("SHA-256")

    total_files = sum(1 for r in records if not r.is_dir)
    total_dirs = sum(1 for r in records if r.is_dir)
    total_bytes = sum(r.size_bytes for r in records if not r.is_dir)
    generated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if opts.fmt == ExportFormat.CSV:
        sio = io.StringIO()
        writer = csv.writer(sio, lineterminator="\n")
        writer.writerow(headers)
        for r in records:
            row = [
                _sanitize_csv_cell(r.name, opts.sanitize_csv_formulas),
                _sanitize_csv_cell(r.rel_path, opts.sanitize_csv_formulas),
                r.type_label,
                str(r.size_bytes),
                r.size_display,
                r.modified_iso,
            ]
            if opts.include_sha256:
                row.append(r.sha256)
            writer.writerow(row)
        return sio.getvalue()

    if opts.fmt == ExportFormat.MARKDOWN:
        def _esc_md(s: str) -> str:
            return s.replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ")

        lines = [
            f"# 폴더 파일 목록 — `{_esc_md(os.path.basename(root_dir) or root_dir)}`",
            "",
            f"- **기준 경로**: `{_esc_md(root_dir)}`",
            f"- **생성 시각**: {generated_at}",
            f"- **요약**: 폴더 {total_dirs:,}개 · 파일 {total_files:,}개 · 총 파일 용량 {format_bytes(total_bytes)} ({total_bytes:,} B)",
            "",
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join(["---", "---", "---", "---:", "---:", "---"] + (["---"] if opts.include_sha256 else [])) + " |",
        ]
        for r in records:
            cols = [
                _esc_md(r.name),
                _esc_md(r.rel_path),
                _esc_md(r.type_label),
                f"{r.size_bytes:,}",
                _esc_md(r.size_display),
                r.modified_iso,
            ]
            if opts.include_sha256:
                cols.append(f"`{r.sha256}`" if r.sha256 else "-")
            lines.append("| " + " | ".join(cols) + " |")
        return "\n".join(lines) + "\n"

    if opts.fmt == ExportFormat.HTML:
        theme = ADDON_THEMES["dark" if opts.dark_html else "light"]
        rows_html: List[str] = []
        for r in records:
            sha_td = f"<td class='mono'>{html.escape(r.sha256)}</td>" if opts.include_sha256 else ""
            rows_html.append(
                "<tr>"
                f"<td>{html.escape(r.name)}</td>"
                f"<td>{html.escape(r.rel_path)}</td>"
                f"<td>{html.escape(r.type_label)}</td>"
                f"<td class='num'>{r.size_bytes:,}</td>"
                f"<td class='num'>{html.escape(r.size_display)}</td>"
                f"<td>{html.escape(r.modified_iso)}</td>"
                f"{sha_td}"
                "</tr>"
            )
        th_html = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
        return (
            "<!DOCTYPE html>\n<html lang='ko'>\n<head>\n<meta charset='utf-8'>\n"
            f"<title>파일 목록 — {html.escape(os.path.basename(root_dir) or root_dir)}</title>\n"
            "<style>\n"
            f"body {{ font-family: 'Pretendard', 'Malgun Gothic', system-ui, sans-serif; background: {theme['bg_window']}; color: {theme['text_primary']}; margin: 24px; line-height: 1.5; word-break: keep-all; }}\n"
            f".card {{ background: {theme['bg_surface']}; border: 1px solid {theme['border']}; border-radius: 8px; padding: 20px; }}\n"
            f"h1 {{ margin: 0 0 8px 0; font-size: 20px; }}\n"
            f".meta {{ color: {theme['text_secondary']}; font-size: 13px; margin-bottom: 16px; }}\n"
            f"table {{ width: 100%; border-collapse: collapse; font-size: 13px; font-variant-numeric: tabular-nums; }}\n"
            f"th {{ background: {theme['bg_elevated']}; color: {theme['text_primary']}; text-align: left; padding: 8px 10px; border-bottom: 2px solid {theme['border']}; }}\n"
            f"td {{ padding: 7px 10px; border-bottom: 1px solid {theme['border']}; }}\n"
            "td.num { text-align: right; }\n"
            "td.mono { font-family: 'JetBrains Mono', Consolas, monospace; font-size: 11px; }\n"
            "</style>\n</head>\n<body>\n<div class='card'>\n"
            f"<h1>파일 목록 리포트</h1>\n"
            f"<div class='meta'>경로: {html.escape(root_dir)} | 생성: {html.escape(generated_at)} | 폴더 {total_dirs:,}개 · 파일 {total_files:,}개 ({html.escape(format_bytes(total_bytes))})</div>\n"
            f"<table><thead><tr>{th_html}</tr></thead><tbody>\n"
            + "\n".join(rows_html)
            + "\n</tbody></table>\n</div>\n</body>\n</html>\n"
        )

    lines_txt = [
        f"PyQuadDir 파일 목록 내보내기 — {root_dir}",
        f"생성 시각: {generated_at} | 폴더 {total_dirs:,}개, 파일 {total_files:,}개, 총 용량 {format_bytes(total_bytes)} ({total_bytes:,} B)",
        "=" * 96,
        f"{'유형':<10}  {'크기':>12}  {'수정한 날짜':<19}  상대 경로",
        "-" * 96,
    ]
    for r in records:
        line = f"{r.type_label:<10}  {r.size_display:>12}  {r.modified_iso:<19}  {r.rel_path}"
        if opts.include_sha256 and r.sha256:
            line += f"  [{r.sha256}]"
        lines_txt.append(line)
    return "\n".join(lines_txt) + "\n"


def export_file_list_safe(
    root_dir: str,
    output_path: str,
    options: Optional[ExportOptions] = None,
    folder_size_cache: Optional[Dict[str, FolderSizeSummary]] = None,
) -> Tuple[str, int]:
    """
    파일 목록을 지정 형식(CSV/MD/HTML/TXT)으로 안전하게 내보냅니다.
    - 기존 파일 덮어쓰기를 원천 차단('x' 배타적 생성 모드)하며, CSV는 Excel 호환을 위해 UTF-8-SIG(BOM)로 기록합니다.
    """
    opts = options or ExportOptions()
    norm_out = safe_norm_path(output_path)
    parent = os.path.dirname(norm_out)
    base = os.path.basename(norm_out)

    seg_err = validate_safe_filename_segment(base)
    if seg_err:
        raise PermissionError(seg_err)
    if is_symlink_or_reparse_point(parent):
        raise PermissionError(f"대상 폴더가 심볼릭 링크/Junction입니다: {parent}")
    if _find_case_insensitive_entry(parent, base) is not None or os.path.lexists(norm_out):
        raise FileExistsError(f"기존 파일 보호(덮어쓰기 차단): '{norm_out}' 파일이 이미 존재합니다.")

    records = collect_export_records(root_dir, opts, folder_size_cache=folder_size_cache)
    rendered = render_export_content(root_dir, records, opts)
    encoding = "utf-8-sig" if opts.fmt == ExportFormat.CSV else "utf-8"

    anchor = Path(os.path.abspath(parent)).anchor
    with _locked_sync_paths(anchor, parent, anchor, anchor):
        with open(norm_out, "x", encoding=encoding, newline="\n") as fp:
            fp.write(rendered)
    return norm_out, len(records)


def collect_flat_view_records(
    root_dir: str,
    show_hidden: bool = False,
    show_extensions: bool = True,
    sort_by: str = "name",
    sort_asc: bool = True,
    max_entries: int = 20000,
) -> Tuple[List[Dict[str, object]], bool]:
    """
    플랫 뷰(Ctrl+B, 하위 폴더 파일 모아보기)용 레코드 목록을 생성합니다.
    PyQuadDir `DirectoryTab._collect_sorted_entries`의 반환 스키마와 100% 호환되며,
    심볼릭 링크 루프를 차단하고 `max_entries` 상한 초과 시 `(records, truncated=True)`를 반환합니다.
    """
    norm_root = safe_norm_path(root_dir)
    if not norm_root or not os.path.isdir(norm_root) or is_symlink_or_reparse_point(norm_root):
        return [], False

    records: List[Dict[str, object]] = []
    truncated = False
    seen_dirs: Set[Tuple[int, int]] = set()
    try:
        st_r = os.lstat(norm_root)
        if st_r.st_ino:
            seen_dirs.add((st_r.st_dev, st_r.st_ino))
    except OSError:
        return [], False

    stack: List[Tuple[str, str]] = [(norm_root, "")]
    while stack:
        curr_dir, rel_prefix = stack.pop()
        try:
            scandir_it = os.scandir(curr_dir)
        except OSError:
            continue
        with scandir_it as it:
            entries_local = sorted(list(it), key=lambda e: e.name.casefold(), reverse=True)
            for entry in entries_local:
                if not show_hidden and entry.name.startswith("."):
                    continue
                full_p = safe_norm_path(entry.path)
                if is_symlink_or_reparse_point(full_p):
                    continue
                try:
                    st = os.lstat(entry.path)
                except OSError:
                    continue

                rel_name = f"{rel_prefix}/{entry.name}" if rel_prefix else entry.name
                if stat.S_ISDIR(st.st_mode):
                    if st.st_ino:
                        d_id = (st.st_dev, st.st_ino)
                        if d_id in seen_dirs:
                            continue
                        seen_dirs.add(d_id)
                    stack.append((full_p, rel_name))
                elif stat.S_ISREG(st.st_mode):
                    if len(records) >= max_entries:
                        truncated = True
                        stack.clear()
                        break
                    ext = Path(entry.name).suffix.lower()
                    if show_extensions or not ext:
                        disp_rel = rel_name
                    else:
                        stem_part = Path(entry.name).stem
                        disp_rel = f"{rel_prefix}/{stem_part}" if rel_prefix else stem_part
                    date_str = datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")
                    day_group = datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d")
                    type_str = f"{ext[1:].upper()} 파일" if ext else "파일"
                    records.append(
                        {
                            "name": entry.name,
                            "disp_name": disp_rel,
                            "path": full_p,
                            "is_dir": False,
                            "ext": ext,
                            "size_b": st.st_size,
                            "size_str": format_bytes(st.st_size),
                            "type_str": type_str,
                            "mtime": st.st_mtime,
                            "ctime": st.st_ctime,
                            "date_str": date_str,
                            "day_group": day_group,
                        }
                    )

    def _key_fn(r: Dict[str, object]) -> object:
        if sort_by == "modified":
            return r["mtime"]
        if sort_by == "created":
            return r["ctime"]
        if sort_by == "size":
            return r["size_b"]
        if sort_by == "type":
            return str(r["type_str"]).lower()
        if sort_by == "ext":
            return str(r["ext"]).lower()
        return str(r["disp_name"]).lower()

    records.sort(key=_key_fn, reverse=not sort_asc)
    return records, truncated


@dataclass
class TabLockState:
    """개별 탭 잠금 상태."""
    locked: bool = False
    locked_root_path: str = ""


class TabLockManager:
    """패널 탭 복제 및 탭 잠금(닫기 보호 + 잠금 기준 경로 복귀) 상태 머신."""

    def __init__(self) -> None:
        self._states: Dict[int, TabLockState] = {}

    def _key(self, tab_obj: object) -> int:
        return id(tab_obj)

    def is_locked(self, tab_obj: object) -> bool:
        st = self._states.get(self._key(tab_obj))
        return bool(st and st.locked)

    def locked_root(self, tab_obj: object) -> str:
        st = self._states.get(self._key(tab_obj))
        return st.locked_root_path if st else ""

    def toggle_lock(self, tab_obj: object, current_path: str) -> TabLockState:
        k = self._key(tab_obj)
        curr = self._states.get(k)
        if curr and curr.locked:
            new_st = TabLockState(locked=False, locked_root_path="")
        else:
            new_st = TabLockState(locked=True, locked_root_path=safe_norm_path(current_path))
        self._states[k] = new_st
        return new_st

    def can_close_tab(self, tab_obj: object) -> bool:
        return not self.is_locked(tab_obj)

    def unregister(self, tab_obj: object) -> None:
        self._states.pop(self._key(tab_obj), None)


# ===========================================================================
# 7. PyQt6 다이얼로그 4종 및 PyQuadDir v3.1.1 플러그앤플레이 컨트롤러
# ===========================================================================

def _load_qt6(qt_override: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """실제 PyQt6 모듈을 지연 로드하거나 헤드리스 테스트용 Qt 호환 바인딩을 주입받습니다."""
    if qt_override is not None:
        return qt_override
    try:
        from PyQt6 import QtCore, QtGui, QtWidgets
    except ImportError:
        from PySide6 import QtCore, QtGui, QtWidgets  # type: ignore[no-redef]
    return {"QtCore": QtCore, "QtGui": QtGui, "QtWidgets": QtWidgets}


def _open_multi_rename_dialog(
    parent: Any,
    target_paths: Sequence[str],
    dark_mode: bool,
    undo_stack: List[RenameUndoBatch],
    on_changed_callback: Callable[[], None],
    qt_mods: Optional[Dict[str, Any]] = None,
) -> Any:
    qt = _load_qt6(qt_mods)
    QtGui, QtWidgets = qt["QtGui"], qt["QtWidgets"]
    theme = ADDON_THEMES["dark" if dark_mode else "light"]

    dlg = QtWidgets.QDialog(parent)
    dlg.setWindowTitle("✏️ 일괄 이름 바꾸기 (Multi-Rename Tool — Ctrl+M)")
    dlg.resize(980, 660)
    dlg.setStyleSheet(build_addon_dialog_qss(dark_mode))

    root_lay = QtWidgets.QVBoxLayout(dlg)
    root_lay.setSpacing(8)

    form_group = QtWidgets.QGroupBox("이름 변환 규칙 ([NAME]=원본이름, [N]=연번, [YMD]=수정일)")
    grid = QtWidgets.QGridLayout(form_group)
    grid.setHorizontalSpacing(10)
    grid.setVerticalSpacing(6)

    ed_template = QtWidgets.QLineEdit("[NAME]")
    ed_prefix = QtWidgets.QLineEdit("")
    ed_prefix.setPlaceholderText("앞에 붙일 접두사 (예: 2026_)")
    ed_suffix = QtWidgets.QLineEdit("")
    ed_suffix.setPlaceholderText("뒤에 붙일 접미사 (예: _v1 또는 _[N])")

    ed_find = QtWidgets.QLineEdit("")
    ed_find.setPlaceholderText("찾을 문자열 또는 정규식 패턴")
    ed_replace = QtWidgets.QLineEdit("")
    ed_replace.setPlaceholderText("바꿀 문자열")
    chk_regex = QtWidgets.QCheckBox("정규식(Regex)")
    chk_case_sens = QtWidgets.QCheckBox("대소문자 구분")

    sp_start = QtWidgets.QSpinBox()
    sp_start.setRange(0, 999999)
    sp_start.setValue(1)
    sp_step = QtWidgets.QSpinBox()
    sp_step.setRange(1, 10000)
    sp_step.setValue(1)
    sp_pad = QtWidgets.QSpinBox()
    sp_pad.setRange(1, 10)
    sp_pad.setValue(2)
    chk_auto_num = QtWidgets.QCheckBox("[N] 미입력 시 끝에 연번 자동 추가")

    cmb_case = QtWidgets.QComboBox()
    cmb_case.addItem("대소문자 원본 유지", CaseTransform.KEEP.value)
    cmb_case.addItem("모두 소문자 (lower)", CaseTransform.LOWER.value)
    cmb_case.addItem("모두 대문자 (UPPER)", CaseTransform.UPPER.value)
    cmb_case.addItem("단어 첫 글자 대문자 (Title)", CaseTransform.TITLE.value)
    cmb_case.addItem("문장 첫 글자 대문자 (Sentence)", CaseTransform.SENTENCE.value)

    cmb_ext = QtWidgets.QComboBox()
    cmb_ext.addItem("확장자 원본 유지", ExtensionMode.KEEP.value)
    cmb_ext.addItem("지정 확장자로 변경", ExtensionMode.REPLACE.value)
    cmb_ext.addItem("확장자 소문자 변환", ExtensionMode.LOWER.value)
    cmb_ext.addItem("확장자 대문자 변환", ExtensionMode.UPPER.value)
    cmb_ext.addItem("확장자 제거", ExtensionMode.REMOVE.value)

    ed_ext = QtWidgets.QLineEdit("")
    ed_ext.setPlaceholderText("변경할 확장자 (예: png)")
    ed_ext.setEnabled(False)

    grid.addWidget(QtWidgets.QLabel("이름 템플릿:"), 0, 0)
    grid.addWidget(ed_template, 0, 1)
    grid.addWidget(QtWidgets.QLabel("접두사:"), 0, 2)
    grid.addWidget(ed_prefix, 0, 3)
    grid.addWidget(QtWidgets.QLabel("접미사:"), 0, 4)
    grid.addWidget(ed_suffix, 0, 5)

    grid.addWidget(QtWidgets.QLabel("찾기:"), 1, 0)
    grid.addWidget(ed_find, 1, 1)
    grid.addWidget(QtWidgets.QLabel("바꾸기:"), 1, 2)
    grid.addWidget(ed_replace, 1, 3)
    opt_row = QtWidgets.QHBoxLayout()
    opt_row.addWidget(chk_regex)
    opt_row.addWidget(chk_case_sens)
    grid.addLayout(opt_row, 1, 4, 1, 2)

    num_row = QtWidgets.QHBoxLayout()
    num_row.addWidget(QtWidgets.QLabel("시작:"))
    num_row.addWidget(sp_start)
    num_row.addWidget(QtWidgets.QLabel("증가:"))
    num_row.addWidget(sp_step)
    num_row.addWidget(QtWidgets.QLabel("자릿수:"))
    num_row.addWidget(sp_pad)
    num_row.addWidget(chk_auto_num)
    grid.addWidget(QtWidgets.QLabel("연번 [N]:"), 2, 0)
    grid.addLayout(num_row, 2, 1, 1, 3)
    grid.addWidget(QtWidgets.QLabel("대소문자:"), 2, 4)
    grid.addWidget(cmb_case, 2, 5)

    grid.addWidget(QtWidgets.QLabel("확장자 규칙:"), 3, 0)
    grid.addWidget(cmb_ext, 3, 1)
    grid.addWidget(QtWidgets.QLabel("새 확장자:"), 3, 2)
    grid.addWidget(ed_ext, 3, 3)

    btn_insert_n = QtWidgets.QPushButton("🔢 접미사에 _[N] 삽입")
    btn_insert_n.clicked.connect(lambda: ed_suffix.setText(ed_suffix.text() + "_[N]"))
    grid.addWidget(btn_insert_n, 3, 4, 1, 2)
    root_lay.addWidget(form_group)

    lbl_status = QtWidgets.QLabel("")
    root_lay.addWidget(lbl_status)

    tbl = QtWidgets.QTableWidget()
    tbl.setColumnCount(4)
    tbl.setHorizontalHeaderLabels(["기존 이름", "새 이름 (실시간 미리보기)", "변경 비교", "검증 상태"])
    tbl.setAlternatingRowColors(True)
    tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
    tbl.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
    hdr = tbl.horizontalHeader()
    hdr.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
    hdr.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
    hdr.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
    hdr.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Interactive)
    tbl.setColumnWidth(3, 190)
    root_lay.addWidget(tbl, stretch=1)

    btn_bar = QtWidgets.QHBoxLayout()
    btn_undo = QtWidgets.QPushButton("↩️ 직전 일괄 변경 실행 취소 (Undo)")
    btn_reset = QtWidgets.QPushButton("초기화")
    btn_apply = QtWidgets.QPushButton("✅ 안전 검증 후 일괄 이름 변경 실행")
    btn_apply.setObjectName("PrimaryActionBtn")
    btn_close = QtWidgets.QPushButton("닫기")

    btn_bar.addWidget(btn_undo)
    btn_bar.addWidget(btn_reset)
    btn_bar.addStretch(1)
    btn_bar.addWidget(btn_apply)
    btn_bar.addWidget(btn_close)
    root_lay.addLayout(btn_bar)

    state: Dict[str, Any] = {"paths": list(target_paths), "plan": None}

    def _refresh_undo_btn() -> None:
        if undo_stack:
            last = undo_stack[-1]
            btn_undo.setEnabled(True)
            btn_undo.setText(f"↩️ 직전 일괄 변경 실행 취소 ({len(last.entries)}개 복원)")
        else:
            btn_undo.setEnabled(False)
            btn_undo.setText("↩️ 실행 취소 내역 없음")

    def _current_rule() -> MultiRenameRule:
        ext_mode_val = ExtensionMode(cmb_ext.currentData())
        ed_ext.setEnabled(ext_mode_val == ExtensionMode.REPLACE)
        return MultiRenameRule(
            name_template=ed_template.text() or "[NAME]",
            prefix=ed_prefix.text(),
            suffix=ed_suffix.text(),
            find_text=ed_find.text(),
            replace_text=ed_replace.text(),
            use_regex=chk_regex.isChecked(),
            case_sensitive=chk_case_sens.isChecked(),
            counter_start=sp_start.value(),
            counter_step=sp_step.value(),
            counter_padding=sp_pad.value(),
            append_counter_if_no_token=chk_auto_num.isChecked(),
            case_transform=CaseTransform(cmb_case.currentData()),
            extension_mode=ext_mode_val,
            custom_extension=ed_ext.text(),
        )

    def _update_preview() -> None:
        rule = _current_rule()
        plan = plan_multi_rename(state["paths"], rule)
        state["plan"] = plan
        tbl.setRowCount(len(plan.items))

        for r_i, it in enumerate(plan.items):
            c0 = QtWidgets.QTableWidgetItem(it.old_name)
            c1 = QtWidgets.QTableWidgetItem(it.new_name)
            c2 = QtWidgets.QTableWidgetItem(it.diff_summary)
            if it.conflict_reason:
                c3 = QtWidgets.QTableWidgetItem(f"차단: {it.conflict_reason}")
                c3.setBackground(QtGui.QColor(theme["badge_err_bg"]))
                c3.setForeground(QtGui.QColor(theme["badge_err_fg"]))
            elif it.changed:
                c3 = QtWidgets.QTableWidgetItem("변경 가능 (안전)")
                c3.setBackground(QtGui.QColor(theme["badge_ok_bg"]))
                c3.setForeground(QtGui.QColor(theme["badge_ok_fg"]))
            else:
                c3 = QtWidgets.QTableWidgetItem("동일 (건너뜀)")
            tbl.setItem(r_i, 0, c0)
            tbl.setItem(r_i, 1, c1)
            tbl.setItem(r_i, 2, c2)
            tbl.setItem(r_i, 3, c3)

        if plan.has_errors:
            lbl_status.setText(f"⚠️ 충돌/규칙 오류 {len(plan.error_messages)}건 감지 — 실행이 사전 차단됩니다: {plan.error_messages[0]}")
            lbl_status.setStyleSheet(
                f"background-color: {theme['badge_err_bg']}; color: {theme['badge_err_fg']}; padding: 6px 10px; border-radius: 5px; font-weight: 700;"
            )
            btn_apply.setEnabled(False)
        else:
            lbl_status.setText(
                f"대상 {len(plan.items)}개 중 변경 예정 {plan.changed_count}개 · 충돌 0건 (기존 파일 덮어쓰기 원천 차단 적용)"
            )
            lbl_status.setStyleSheet(
                f"background-color: {theme['badge_ok_bg']}; color: {theme['badge_ok_fg']}; padding: 6px 10px; border-radius: 5px; font-weight: 700;"
            )
            btn_apply.setEnabled(plan.changed_count > 0)
        _refresh_undo_btn()

    def _on_reset() -> None:
        ed_template.setText("[NAME]")
        ed_prefix.clear()
        ed_suffix.clear()
        ed_find.clear()
        ed_replace.clear()
        chk_regex.setChecked(False)
        chk_case_sens.setChecked(False)
        sp_start.setValue(1)
        sp_step.setValue(1)
        sp_pad.setValue(2)
        chk_auto_num.setChecked(False)
        cmb_case.setCurrentIndex(0)
        cmb_ext.setCurrentIndex(0)
        ed_ext.clear()
        _update_preview()

    def _on_apply() -> None:
        plan = state.get("plan")
        if plan is None:
            return
        ok, batch, errs = execute_multi_rename_plan(plan)
        if not ok or batch is None:
            QtWidgets.QMessageBox.warning(dlg, "일괄 이름 변경 차단", "\n".join(errs[:8]))
            _update_preview()
            return
        if batch.entries:
            undo_stack.append(batch)
            new_map = {e.old_path.casefold(): e.new_path for e in batch.entries}
            state["paths"] = [new_map.get(p.casefold(), p) for p in state["paths"]]
        on_changed_callback()
        _update_preview()

    def _on_undo() -> None:
        if not undo_stack:
            return
        last_batch = undo_stack[-1]
        ok, errs = undo_multi_rename_batch(last_batch)
        if not ok:
            QtWidgets.QMessageBox.warning(dlg, "실행 취소 차단", "\n".join(errs[:8]))
            return
        undo_stack.pop()
        rev_map = {e.new_path.casefold(): e.old_path for e in last_batch.entries}
        state["paths"] = [rev_map.get(p.casefold(), p) for p in state["paths"]]
        on_changed_callback()
        _update_preview()

    for sig in (
        ed_template.textChanged,
        ed_prefix.textChanged,
        ed_suffix.textChanged,
        ed_find.textChanged,
        ed_replace.textChanged,
        ed_ext.textChanged,
        chk_regex.toggled,
        chk_case_sens.toggled,
        chk_auto_num.toggled,
        sp_start.valueChanged,
        sp_step.valueChanged,
        sp_pad.valueChanged,
        cmb_case.currentIndexChanged,
        cmb_ext.currentIndexChanged,
    ):
        sig.connect(lambda *_: _update_preview())

    btn_reset.clicked.connect(_on_reset)
    btn_apply.clicked.connect(_on_apply)
    btn_undo.clicked.connect(_on_undo)
    btn_close.clicked.connect(dlg.accept)

    _update_preview()
    dlg.exec()
    return dlg


def _open_compare_panes_dialog(
    parent: Any,
    pane_paths: Sequence[Tuple[str, str]],
    active_pane_idx: int,
    dark_mode: bool,
    include_hidden: bool,
    on_synced_callback: Callable[[], None],
    qt_mods: Optional[Dict[str, Any]] = None,
) -> Any:
    qt = _load_qt6(qt_mods)
    QtCore, QtGui, QtWidgets = qt["QtCore"], qt["QtGui"], qt["QtWidgets"]
    Qt = QtCore.Qt
    theme = ADDON_THEMES["dark" if dark_mode else "light"]

    dlg = QtWidgets.QDialog(parent)
    dlg.setWindowTitle("⚖️ 패널 간 폴더 비교 · 동기화 미리보기 (Compare Panes — Shift+F2)")
    dlg.resize(1060, 680)
    dlg.setStyleSheet(build_addon_dialog_qss(dark_mode))

    lay = QtWidgets.QVBoxLayout(dlg)
    lay.setSpacing(8)

    top_grp = QtWidgets.QGroupBox("비교 대상 패널 및 기준 설정")
    top_grid = QtWidgets.QGridLayout(top_grp)

    cmb_left = QtWidgets.QComboBox()
    cmb_right = QtWidgets.QComboBox()
    for title, p_str in pane_paths:
        lbl = f"[{title}] {p_str}"
        cmb_left.addItem(lbl, p_str)
        cmb_right.addItem(lbl, p_str)

    cmb_left.setCurrentIndex(active_pane_idx if 0 <= active_pane_idx < len(pane_paths) else 0)
    default_right = (active_pane_idx + 1) % max(1, len(pane_paths))
    cmb_right.setCurrentIndex(default_right)

    chk_rec = QtWidgets.QCheckBox("하위 폴더 재귀 포함")
    chk_sha = QtWidgets.QCheckBox("동일 크기 파일 SHA-256 내용 정밀 대조")
    cmb_filter = QtWidgets.QComboBox()
    cmb_filter.addItem("차이 항목만 보기 (동일 숨김)", "diff_only")
    cmb_filter.addItem("전체 항목 보기", "all")
    cmb_filter.addItem("좌측 전용 항목만", CompareStatus.LEFT_ONLY.value)
    cmb_filter.addItem("우측 전용 항목만", CompareStatus.RIGHT_ONLY.value)
    cmb_filter.addItem("크기·날짜·해시 상이 항목만", "mismatch_only")

    btn_run_cmp = QtWidgets.QPushButton("🔍 다시 비교")
    btn_run_cmp.setObjectName("PrimaryActionBtn")

    top_grid.addWidget(QtWidgets.QLabel("좌측(기준) 패널:"), 0, 0)
    top_grid.addWidget(cmb_left, 0, 1, 1, 3)
    top_grid.addWidget(QtWidgets.QLabel("우측(대상) 패널:"), 1, 0)
    top_grid.addWidget(cmb_right, 1, 1, 1, 3)
    top_grid.addWidget(chk_rec, 2, 0, 1, 1)
    top_grid.addWidget(chk_sha, 2, 1, 1, 1)
    top_grid.addWidget(cmb_filter, 2, 2, 1, 1)
    top_grid.addWidget(btn_run_cmp, 2, 3, 1, 1)
    lay.addWidget(top_grp)

    lbl_summary = QtWidgets.QLabel("")
    lay.addWidget(lbl_summary)

    tbl = QtWidgets.QTableWidget()
    tbl.setColumnCount(6)
    tbl.setHorizontalHeaderLabels(["선택", "상대 경로", "비교 상태", "좌측 크기 / 수정일", "우측 크기 / 수정일", "SHA-256 요약"])
    tbl.setAlternatingRowColors(True)
    tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
    tbl.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
    hdr = tbl.horizontalHeader()
    hdr.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Fixed)
    tbl.setColumnWidth(0, 56)
    hdr.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
    hdr.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Interactive)
    tbl.setColumnWidth(2, 175)
    hdr.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Interactive)
    tbl.setColumnWidth(3, 195)
    hdr.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeMode.Interactive)
    tbl.setColumnWidth(4, 195)
    hdr.setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeMode.Interactive)
    tbl.setColumnWidth(5, 140)
    lay.addWidget(tbl, stretch=1)

    act_bar = QtWidgets.QHBoxLayout()
    chk_rename_conflict = QtWidgets.QCheckBox("동명 파일 존재 시 안전 사본(_sync_N)으로 저장 (원본 덮어쓰기 영구 금지)")
    btn_sel_left = QtWidgets.QPushButton("좌측 전용 전체 체크")
    btn_sel_right = QtWidgets.QPushButton("우측 전용 전체 체크")
    btn_copy_lr = QtWidgets.QPushButton("➡️ 체크 항목 좌측 → 우측 복사")
    btn_copy_lr.setObjectName("PrimaryActionBtn")
    btn_copy_rl = QtWidgets.QPushButton("⬅️ 체크 항목 우측 → 좌측 복사")
    btn_close = QtWidgets.QPushButton("닫기")

    act_bar.addWidget(chk_rename_conflict)
    act_bar.addStretch(1)
    act_bar.addWidget(btn_sel_left)
    act_bar.addWidget(btn_sel_right)
    act_bar.addWidget(btn_copy_lr)
    act_bar.addWidget(btn_copy_rl)
    act_bar.addWidget(btn_close)
    lay.addLayout(act_bar)

    state: Dict[str, Any] = {"summary": None, "visible_entries": []}

    def _fmt_side(sz: Optional[int], mt: Optional[float], is_dir: bool) -> str:
        if mt is None and sz is None:
            return "—"
        dt_s = datetime.datetime.fromtimestamp(mt).strftime("%Y-%m-%d %H:%M") if mt else "-"
        sz_s = "<DIR>" if is_dir else format_bytes(sz or 0)
        return f"{sz_s}  |  {dt_s}"

    def _render_table() -> None:
        summary: Optional[CompareSummary] = state["summary"]
        if summary is None:
            return
        f_mode = cmb_filter.currentData()
        filtered: List[CompareEntry] = []
        for e in summary.entries:
            if f_mode == "diff_only" and e.status == CompareStatus.IDENTICAL:
                continue
            if f_mode == CompareStatus.LEFT_ONLY.value and e.status != CompareStatus.LEFT_ONLY:
                continue
            if f_mode == CompareStatus.RIGHT_ONLY.value and e.status != CompareStatus.RIGHT_ONLY:
                continue
            if f_mode == "mismatch_only" and e.status not in (
                CompareStatus.DIFF_LEFT_NEWER,
                CompareStatus.DIFF_RIGHT_NEWER,
                CompareStatus.DIFF_CONTENT,
            ):
                continue
            filtered.append(e)

        state["visible_entries"] = filtered
        tbl.setRowCount(len(filtered))

        for r_i, e in enumerate(filtered):
            chk_item = QtWidgets.QTableWidgetItem("")
            chk_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            default_chk = e.status in (CompareStatus.LEFT_ONLY, CompareStatus.RIGHT_ONLY)
            chk_item.setCheckState(Qt.CheckState.Checked if default_chk else Qt.CheckState.Unchecked)

            st_lbl = COMPARE_STATUS_LABELS.get(e.status, e.status.value)
            st_item = QtWidgets.QTableWidgetItem(st_lbl)
            if e.status == CompareStatus.LEFT_ONLY:
                st_item.setBackground(QtGui.QColor(theme["badge_left_bg"]))
                st_item.setForeground(QtGui.QColor(theme["badge_left_fg"]))
            elif e.status == CompareStatus.RIGHT_ONLY:
                st_item.setBackground(QtGui.QColor(theme["badge_right_bg"]))
                st_item.setForeground(QtGui.QColor(theme["badge_right_fg"]))
            elif e.status == CompareStatus.IDENTICAL:
                st_item.setBackground(QtGui.QColor(theme["badge_ok_bg"]))
                st_item.setForeground(QtGui.QColor(theme["badge_ok_fg"]))
            else:
                st_item.setBackground(QtGui.QColor(theme["badge_warn_bg"]))
                st_item.setForeground(QtGui.QColor(theme["badge_warn_fg"]))

            sha_txt = "-"
            if e.left_sha256 or e.right_sha256:
                lh = (e.left_sha256 or "")[:8]
                rh = (e.right_sha256 or "")[:8]
                sha_txt = f"{lh} / {rh}"

            tbl.setItem(r_i, 0, chk_item)
            tbl.setItem(r_i, 1, QtWidgets.QTableWidgetItem(e.rel_display))
            tbl.setItem(r_i, 2, st_item)
            tbl.setItem(r_i, 3, QtWidgets.QTableWidgetItem(_fmt_side(e.left_size, e.left_mtime, e.is_dir)))
            tbl.setItem(r_i, 4, QtWidgets.QTableWidgetItem(_fmt_side(e.right_size, e.right_mtime, e.is_dir)))
            tbl.setItem(r_i, 5, QtWidgets.QTableWidgetItem(sha_txt))

        lbl_summary.setText(
            f"좌측 전용: {summary.left_only_count}개  |  우측 전용: {summary.right_only_count}개  |  "
            f"크기·날짜·해시 상이: {summary.diff_count}개  |  동일: {summary.identical_count}개"
        )

    def _run_compare() -> None:
        l_dir = str(cmb_left.currentData() or "")
        r_dir = str(cmb_right.currentData() or "")
        opts = CompareOptions(
            recursive=chk_rec.isChecked(),
            verify_sha256=chk_sha.isChecked(),
            include_hidden=include_hidden,
        )
        state["summary"] = compare_directories(l_dir, r_dir, opts)
        _render_table()

    def _check_by_status(target_status: CompareStatus) -> None:
        vis: List[CompareEntry] = state["visible_entries"]
        for r_i, e in enumerate(vis):
            it = tbl.item(r_i, 0)
            if it is not None:
                it.setCheckState(
                    Qt.CheckState.Checked if e.status == target_status else Qt.CheckState.Unchecked
                )

    def _run_sync(direction: str) -> None:
        summary: Optional[CompareSummary] = state["summary"]
        vis: List[CompareEntry] = state["visible_entries"]
        if summary is None:
            return
        chosen: List[CompareEntry] = []
        for r_i, e in enumerate(vis):
            it = tbl.item(r_i, 0)
            if it is not None and it.checkState() == Qt.CheckState.Checked:
                chosen.append(e)
        if not chosen:
            QtWidgets.QMessageBox.information(dlg, "안내", "복사할 항목을 먼저 체크해 주세요.")
            return
        policy = "rename_copy" if chk_rename_conflict.isChecked() else "block"
        res = execute_selective_sync_copy(
            chosen, direction, summary.left_root, summary.right_root, conflict_policy=policy
        )
        on_synced_callback()
        _run_compare()
        msg_lines = [f"✅ 안전 복사 완료: {res.copied_count}개"]
        if res.skipped_conflicts:
            msg_lines.append(f"🛡️ 덮어쓰기 보호로 건너뜀: {len(res.skipped_conflicts)}개")
            msg_lines.extend(res.skipped_conflicts[:5])
        if res.errors:
            msg_lines.append(f"⚠️ 오류: {len(res.errors)}개")
            msg_lines.extend(res.errors[:5])
        QtWidgets.QMessageBox.information(dlg, "동기화 복사 결과", "\n".join(msg_lines))

    btn_run_cmp.clicked.connect(_run_compare)
    cmb_left.currentIndexChanged.connect(lambda *_: _run_compare())
    cmb_right.currentIndexChanged.connect(lambda *_: _run_compare())
    chk_rec.toggled.connect(lambda *_: _run_compare())
    chk_sha.toggled.connect(lambda *_: _run_compare())
    cmb_filter.currentIndexChanged.connect(lambda *_: _render_table())
    btn_sel_left.clicked.connect(lambda: _check_by_status(CompareStatus.LEFT_ONLY))
    btn_sel_right.clicked.connect(lambda: _check_by_status(CompareStatus.RIGHT_ONLY))
    btn_copy_lr.clicked.connect(lambda: _run_sync("left_to_right"))
    btn_copy_rl.clicked.connect(lambda: _run_sync("right_to_left"))
    btn_close.clicked.connect(dlg.accept)

    _run_compare()
    dlg.exec()
    return dlg


def _open_checksum_duplicate_dialog(
    parent: Any,
    current_dir: str,
    selected_paths: Sequence[str],
    dark_mode: bool,
    include_hidden: bool,
    select_paths_in_tab_cb: Callable[[Sequence[str]], None],
    qt_mods: Optional[Dict[str, Any]] = None,
) -> Any:
    qt = _load_qt6(qt_mods)
    QtCore, QtGui, QtWidgets = qt["QtCore"], qt["QtGui"], qt["QtWidgets"]
    Qt = QtCore.Qt
    theme = ADDON_THEMES["dark" if dark_mode else "light"]

    dlg = QtWidgets.QDialog(parent)
    dlg.setWindowTitle("🔐 파일 해시 계산·검증 및 3단계 고속 중복 파일 찾기 (Ctrl+Shift+H)")
    dlg.resize(1020, 660)
    dlg.setStyleSheet(build_addon_dialog_qss(dark_mode))

    root_lay = QtWidgets.QVBoxLayout(dlg)
    tabs = QtWidgets.QTabWidget()
    root_lay.addWidget(tabs, stretch=1)

    tab_hash = QtWidgets.QWidget()
    h_lay = QtWidgets.QVBoxLayout(tab_hash)

    verify_row = QtWidgets.QHBoxLayout()
    ed_expected = QtWidgets.QLineEdit("")
    ed_expected.setPlaceholderText("비교할 해시값(MD5 32자 / SHA-1 40자 / SHA-256 64자) 입력 또는 붙여넣기")
    btn_paste_clip = QtWidgets.QPushButton("📋 클립보드 해시 붙여넣기")
    btn_export_sha = QtWidgets.QPushButton("💾 .sha256 매니페스트 저장")
    verify_row.addWidget(QtWidgets.QLabel("해시 대조:"))
    verify_row.addWidget(ed_expected, stretch=1)
    verify_row.addWidget(btn_paste_clip)
    verify_row.addWidget(btn_export_sha)
    h_lay.addLayout(verify_row)

    lbl_verify_badge = QtWidgets.QLabel("파일을 선택하면 단일 패스 스트리밍으로 MD5 · SHA-1 · SHA-256을 계산합니다.")
    h_lay.addWidget(lbl_verify_badge)

    tbl_hash = QtWidgets.QTableWidget()
    tbl_hash.setColumnCount(6)
    tbl_hash.setHorizontalHeaderLabels(["파일명", "크기", "MD5", "SHA-1", "SHA-256", "검증 결과"])
    tbl_hash.setAlternatingRowColors(True)
    tbl_hash.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
    tbl_hash.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
    hh = tbl_hash.horizontalHeader()
    hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Interactive)
    tbl_hash.setColumnWidth(0, 170)
    hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Interactive)
    tbl_hash.setColumnWidth(1, 90)
    hh.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
    hh.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Stretch)
    hh.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeMode.Stretch)
    hh.setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeMode.Interactive)
    tbl_hash.setColumnWidth(5, 130)
    h_lay.addWidget(tbl_hash, stretch=1)

    btn_copy_sha256 = QtWidgets.QPushButton("📋 선택 행 SHA-256 클립보드 복사")
    h_lay.addWidget(btn_copy_sha256)
    tabs.addTab(tab_hash, "🔐 파일 해시 계산 · 검증 (MD5 / SHA-1 / SHA-256)")

    tab_dup = QtWidgets.QWidget()
    d_lay = QtWidgets.QVBoxLayout(tab_dup)

    dup_ctrl = QtWidgets.QHBoxLayout()
    chk_dup_rec = QtWidgets.QCheckBox("하위 폴더 포함 스캔")
    chk_dup_rec.setChecked(True)
    sp_min_kb = QtWidgets.QSpinBox()
    sp_min_kb.setRange(0, 1024 * 1024)
    sp_min_kb.setValue(0)
    sp_min_kb.setSuffix(" KB 이상 (0=1B 이상)")
    btn_scan_dup = QtWidgets.QPushButton("🚀 3단계 고속 중복 스캔 시작 (크기 → 앞·뒤 4KB → SHA-256)")
    btn_scan_dup.setObjectName("PrimaryActionBtn")
    dup_ctrl.addWidget(QtWidgets.QLabel(f"대상 폴더: {current_dir}"))
    dup_ctrl.addStretch(1)
    dup_ctrl.addWidget(chk_dup_rec)
    dup_ctrl.addWidget(sp_min_kb)
    dup_ctrl.addWidget(btn_scan_dup)
    d_lay.addLayout(dup_ctrl)

    lbl_dup_summary = QtWidgets.QLabel("자동 삭제는 일절 수행하지 않으며, 중복 여부를 바이트 단위로 안전하게 확인합니다.")
    d_lay.addWidget(lbl_dup_summary)

    tbl_dup = QtWidgets.QTableWidget()
    tbl_dup.setColumnCount(6)
    tbl_dup.setHorizontalHeaderLabels(["선택", "그룹", "파일명", "폴더 경로", "크기 / 수정일", "전체 SHA-256"])
    tbl_dup.setAlternatingRowColors(True)
    tbl_dup.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
    tbl_dup.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
    dh = tbl_dup.horizontalHeader()
    dh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Fixed)
    tbl_dup.setColumnWidth(0, 56)
    dh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Fixed)
    tbl_dup.setColumnWidth(1, 74)
    dh.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Interactive)
    tbl_dup.setColumnWidth(2, 180)
    dh.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Stretch)
    dh.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeMode.Interactive)
    tbl_dup.setColumnWidth(4, 195)
    dh.setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeMode.Interactive)
    tbl_dup.setColumnWidth(5, 165)
    d_lay.addWidget(tbl_dup, stretch=1)

    dup_btn_row = QtWidgets.QHBoxLayout()
    btn_mark_newer = QtWidgets.QPushButton("그룹별 가장 오래된 원본 1개 제외 · 나머지 체크")
    btn_select_in_pane = QtWidgets.QPushButton("🔍 체크된 항목을 현재 탐색기 패널에서 선택")
    dup_btn_row.addWidget(btn_mark_newer)
    dup_btn_row.addStretch(1)
    dup_btn_row.addWidget(btn_select_in_pane)
    d_lay.addLayout(dup_btn_row)
    tabs.addTab(tab_dup, "🧬 중복 파일 찾기 (3단계 고속 스캔 · 자동삭제 없음)")

    close_btn = QtWidgets.QPushButton("닫기")
    close_btn.clicked.connect(dlg.accept)
    root_lay.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)

    hash_records: List[FileHashRecord] = []
    for sp in selected_paths:
        norm_sp = safe_norm_path(sp)
        if os.path.isfile(norm_sp) and not is_symlink_or_reparse_point(norm_sp):
            try:
                hash_records.append(compute_file_hashes(norm_sp))
            except Exception:
                continue

    if not hash_records:
        tabs.setCurrentIndex(1)

    def _render_hashes() -> None:
        tbl_hash.setRowCount(len(hash_records))
        exp_str = ed_expected.text()
        any_match = False
        for r_i, rec in enumerate(hash_records):
            vres = verify_expected_hash(rec, exp_str)
            if vres.matched:
                any_match = True
            v_item = QtWidgets.QTableWidgetItem(
                "일치 (MATCH)" if vres.matched else ("대기" if vres.algorithm == "NONE" else "불일치")
            )
            if vres.matched:
                v_item.setBackground(QtGui.QColor(theme["badge_ok_bg"]))
                v_item.setForeground(QtGui.QColor(theme["badge_ok_fg"]))
            elif vres.algorithm not in ("NONE",):
                v_item.setBackground(QtGui.QColor(theme["badge_err_bg"]))
                v_item.setForeground(QtGui.QColor(theme["badge_err_fg"]))

            tbl_hash.setItem(r_i, 0, QtWidgets.QTableWidgetItem(rec.file_name))
            tbl_hash.setItem(r_i, 1, QtWidgets.QTableWidgetItem(format_bytes(rec.size_bytes)))
            tbl_hash.setItem(r_i, 2, QtWidgets.QTableWidgetItem(rec.md5))
            tbl_hash.setItem(r_i, 3, QtWidgets.QTableWidgetItem(rec.sha1))
            tbl_hash.setItem(r_i, 4, QtWidgets.QTableWidgetItem(rec.sha256))
            tbl_hash.setItem(r_i, 5, v_item)

        if exp_str.strip() and hash_records:
            if any_match:
                lbl_verify_badge.setText("✅ 입력한 해시값과 일치하는 파일이 확인되었습니다.")
                lbl_verify_badge.setStyleSheet(
                    f"background-color: {theme['badge_ok_bg']}; color: {theme['badge_ok_fg']}; padding: 6px 10px; border-radius: 5px; font-weight: 700;"
                )
            else:
                lbl_verify_badge.setText("❌ 입력한 해시값과 일치하는 파일이 없습니다.")
                lbl_verify_badge.setStyleSheet(
                    f"background-color: {theme['badge_err_bg']}; color: {theme['badge_err_fg']}; padding: 6px 10px; border-radius: 5px; font-weight: 700;"
                )

    dup_rows_meta: List[Tuple[int, int, DuplicateFileEntry]] = []

    def _run_dup_scan() -> None:
        min_b = max(1, sp_min_kb.value() * 1024)
        res = find_duplicate_files_3stage(
            current_dir,
            recursive=chk_dup_rec.isChecked(),
            min_size_bytes=min_b,
            include_hidden=include_hidden,
        )
        dup_rows_meta.clear()
        for grp in res.groups:
            for idx_in_grp, fe in enumerate(grp.files):
                dup_rows_meta.append((grp.group_id, idx_in_grp, fe))

        tbl_dup.setRowCount(len(dup_rows_meta))
        sha_by_gid = {g.group_id: g.sha256 for g in res.groups}
        for r_i, (gid, idx_in_grp, fe) in enumerate(dup_rows_meta):
            chk_it = QtWidgets.QTableWidgetItem("")
            chk_it.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            chk_it.setCheckState(Qt.CheckState.Unchecked)
            dt_s = datetime.datetime.fromtimestamp(fe.mtime).strftime("%Y-%m-%d %H:%M")
            g_lbl = f"#{gid}" + (" (원본기준)" if idx_in_grp == 0 else f" (중복+{idx_in_grp})")
            tbl_dup.setItem(r_i, 0, chk_it)
            tbl_dup.setItem(r_i, 1, QtWidgets.QTableWidgetItem(g_lbl))
            tbl_dup.setItem(r_i, 2, QtWidgets.QTableWidgetItem(fe.name))
            tbl_dup.setItem(r_i, 3, QtWidgets.QTableWidgetItem(fe.parent_dir))
            tbl_dup.setItem(r_i, 4, QtWidgets.QTableWidgetItem(f"{format_bytes(fe.size_bytes)} | {dt_s}"))
            tbl_dup.setItem(r_i, 5, QtWidgets.QTableWidgetItem(sha_by_gid.get(gid, "")))

        lbl_dup_summary.setText(
            f"스캔 {res.scanned_files:,}개 → 1단계(동일크기) {res.stage1_candidate_files:,}개 → "
            f"2단계(부분해시) {res.stage2_candidate_files:,}개 → 최종 중복 그룹 {len(res.groups):,}개 "
            f"(중복 점유 용량: {format_bytes(res.total_wasted_bytes)})"
        )

    def _mark_duplicates_keep_oldest() -> None:
        for r_i, (_, idx_in_grp, _) in enumerate(dup_rows_meta):
            it = tbl_dup.item(r_i, 0)
            if it is not None:
                it.setCheckState(Qt.CheckState.Checked if idx_in_grp > 0 else Qt.CheckState.Unchecked)

    def _select_checked_in_explorer() -> None:
        targets = [
            fe.path
            for r_i, (_, _, fe) in enumerate(dup_rows_meta)
            if tbl_dup.item(r_i, 0) is not None and tbl_dup.item(r_i, 0).checkState() == Qt.CheckState.Checked
        ]
        if not targets:
            QtWidgets.QMessageBox.information(dlg, "안내", "탐색기에서 선택할 항목을 먼저 체크해 주세요.")
            return
        select_paths_in_tab_cb(targets)
        dlg.accept()

    def _paste_clip() -> None:
        clip = QtWidgets.QApplication.clipboard()
        if clip is not None:
            ed_expected.setText(clip.text().strip())

    def _copy_selected_sha() -> None:
        row = tbl_hash.currentRow()
        if 0 <= row < len(hash_records):
            clip = QtWidgets.QApplication.clipboard()
            if clip is not None:
                clip.setText(hash_records[row].sha256)

    def _save_manifest() -> None:
        if not hash_records:
            return
        default_out = os.path.join(current_dir, f"checksums_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.sha256")
        out_file, _ = QtWidgets.QFileDialog.getSaveFileName(
            dlg, "SHA-256 체크섬 매니페스트 저장 (비덮어쓰기)", default_out, "SHA-256 Checksum (*.sha256)"
        )
        if out_file:
            try:
                saved = export_hash_manifest(hash_records, out_file, "sha256")
                QtWidgets.QMessageBox.information(dlg, "저장 완료", f"체크섬 파일을 저장했습니다:\n{saved}")
            except Exception as exc:
                QtWidgets.QMessageBox.warning(dlg, "저장 차단", str(exc))

    ed_expected.textChanged.connect(lambda *_: _render_hashes())
    btn_paste_clip.clicked.connect(_paste_clip)
    btn_export_sha.clicked.connect(_save_manifest)
    btn_copy_sha256.clicked.connect(_copy_selected_sha)
    btn_scan_dup.clicked.connect(_run_dup_scan)
    btn_mark_newer.clicked.connect(_mark_duplicates_keep_oldest)
    btn_select_in_pane.clicked.connect(_select_checked_in_explorer)

    _render_hashes()
    dlg.exec()
    return dlg


def _open_export_list_dialog(
    parent: Any,
    current_dir: str,
    dark_mode: bool,
    include_hidden: bool,
    folder_size_cache: Optional[Dict[str, FolderSizeSummary]],
    qt_mods: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    qt = _load_qt6(qt_mods)
    QtWidgets = qt["QtWidgets"]

    dlg = QtWidgets.QDialog(parent)
    dlg.setWindowTitle("📤 파일 목록 내보내기 (CSV / Markdown / HTML / TXT — Ctrl+Shift+E)")
    dlg.resize(560, 310)
    dlg.setStyleSheet(build_addon_dialog_qss(dark_mode))

    lay = QtWidgets.QVBoxLayout(dlg)
    grp = QtWidgets.QGroupBox(f"내보내기 옵션 — {current_dir}")
    form = QtWidgets.QGridLayout(grp)

    cmb_fmt = QtWidgets.QComboBox()
    cmb_fmt.addItem("CSV 스프레드시트 (.csv, UTF-8 BOM + 수식주입 방어)", ExportFormat.CSV.value)
    cmb_fmt.addItem("Markdown 표 (.md)", ExportFormat.MARKDOWN.value)
    cmb_fmt.addItem("HTML 리포트 (.html, WCAG 테마)", ExportFormat.HTML.value)
    cmb_fmt.addItem("일반 텍스트 (.txt, 정렬 표)", ExportFormat.TXT.value)

    chk_rec = QtWidgets.QCheckBox("하위 폴더까지 재귀적으로 모두 포함")
    chk_sha = QtWidgets.QCheckBox("각 파일의 SHA-256 해시 컬럼 포함")

    form.addWidget(QtWidgets.QLabel("출력 형식:"), 0, 0)
    form.addWidget(cmb_fmt, 0, 1)
    form.addWidget(chk_rec, 1, 0, 1, 2)
    form.addWidget(chk_sha, 2, 0, 1, 2)
    lay.addWidget(grp)

    btn_row = QtWidgets.QHBoxLayout()
    btn_export = QtWidgets.QPushButton("💾 파일로 저장 (기존 파일 덮어쓰기 차단)")
    btn_export.setObjectName("PrimaryActionBtn")
    btn_cancel = QtWidgets.QPushButton("취소")
    btn_row.addStretch(1)
    btn_row.addWidget(btn_export)
    btn_row.addWidget(btn_cancel)
    lay.addLayout(btn_row)

    saved_holder: List[str] = []

    def _do_export() -> None:
        fmt = ExportFormat(cmb_fmt.currentData())
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        folder_leaf = Path(current_dir).name or "root"
        default_name = f"filelist_{folder_leaf}_{stamp}.{fmt.value}"
        default_path = os.path.join(current_dir, default_name)
        out_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            dlg,
            "파일 목록 저장 (기존 파일과 겹치지 않는 새 파일명 지정)",
            default_path,
            f"*.{fmt.value}",
        )
        if not out_path:
            return
        opts = ExportOptions(
            fmt=fmt,
            recursive=chk_rec.isChecked(),
            include_hidden=include_hidden,
            include_sha256=chk_sha.isChecked(),
            dark_html=dark_mode,
        )
        try:
            saved_p, row_cnt = export_file_list_safe(
                current_dir, out_path, opts, folder_size_cache=folder_size_cache
            )
            saved_holder.append(saved_p)
            QtWidgets.QMessageBox.information(
                dlg, "내보내기 완료", f"총 {row_cnt:,}개 항목을 안전하게 저장했습니다:\n{saved_p}"
            )
            dlg.accept()
        except Exception as exc:
            QtWidgets.QMessageBox.warning(dlg, "내보내기 차단", str(exc))

    btn_export.clicked.connect(_do_export)
    btn_cancel.clicked.connect(dlg.reject)
    dlg.exec()
    return saved_holder[0] if saved_holder else None


class PyQuadDirAddonController:
    """
    PyQuadDir v3.1.1 `QDirMainWindow` 인스턴스에 5대 핵심 부가기능과 단축키·메뉴·플랫뷰·탭 잠금을
    원본 코드 훼손 없이 비침투적으로 장착하는 어댑터 컨트롤러입니다.
    """

    def __init__(self, main_window: Any, qt_mods: Optional[Dict[str, Any]] = None) -> None:
        self.win = main_window
        self.qt = _load_qt6(qt_mods)
        self.undo_stack: List[RenameUndoBatch] = []
        self.folder_size_cache: Dict[str, FolderSizeSummary] = {}
        self.tab_locks = TabLockManager()
        self._installed_tabs: Set[int] = set()
        self._installed_panes: Set[int] = set()

    def install(self) -> "PyQuadDirAddonController":
        QtGui, QtWidgets = self.qt["QtGui"], self.qt["QtWidgets"]

        if hasattr(self.win, "cmd_tb"):
            self.btn_tools = QtWidgets.QToolButton()
            self.btn_tools.setText("🧰 도구 ▾")
            self.btn_tools.setToolTip(
                "부가기능 도구 모음: 일괄 이름 바꾸기(Ctrl+M), 패널 비교(Shift+F2), 폴더 용량(Alt+Shift+Enter), 해시/중복 찾기, 목록 내보내기, 플랫 뷰(Ctrl+B)"
            )
            if hasattr(self.btn_tools, "setFocusPolicy") and hasattr(self.qt["QtCore"].Qt, "FocusPolicy"):
                self.btn_tools.setFocusPolicy(self.qt["QtCore"].Qt.FocusPolicy.NoFocus)
            self.btn_tools.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
            self.tools_menu = QtWidgets.QMenu(self.btn_tools)
            self.tools_menu.aboutToShow.connect(lambda: self.populate_tools_menu(self.tools_menu))
            self.btn_tools.setMenu(self.tools_menu)
            self.win.cmd_tb.addWidget(self.btn_tools)

            if hasattr(self.win, "_set_toolbar_compact_mode"):
                orig_compact = self.win._set_toolbar_compact_mode

                def _wrapped_compact(tier: str) -> None:
                    orig_compact(tier)
                    if tier == "mobile_portrait":
                        self.btn_tools.setText("🧰")
                    elif tier == "mobile_landscape":
                        self.btn_tools.setText("🧰도구▾")
                    else:
                        self.btn_tools.setText("🧰 도구 ▾")

                self.win._set_toolbar_compact_mode = _wrapped_compact

        if hasattr(self.win, "_shortcut_rename"):
            orig_rename = self.win._shortcut_rename

            def _smart_rename() -> None:
                if hasattr(self.win, "_is_text_input_focused") and self.win._is_text_input_focused():
                    return
                tab = self._active_tab()
                if tab is not None:
                    sel = tab.selected_file_paths()
                    if len(sel) >= 2:
                        self.open_multi_rename()
                        return
                orig_rename()

            self.win._shortcut_rename = _smart_rename

        QShortcut = QtGui.QShortcut
        QKeySequence = QtGui.QKeySequence
        shortcuts = [
            ("Ctrl+M", self.open_multi_rename),
            ("Ctrl+Shift+Z", self.undo_last_multi_rename),
            ("Shift+F2", self.open_compare_panes),
            ("Alt+Shift+Return", self.calculate_active_folder_sizes),
            ("Alt+Shift+Enter", self.calculate_active_folder_sizes),
            ("Ctrl+Shift+H", self.open_checksum_and_duplicates),
            ("Ctrl+Shift+E", self.open_export_file_list),
            ("Ctrl+B", self.toggle_active_flat_view),
            ("Ctrl+Shift+K", self.duplicate_active_tab),
            ("Ctrl+Shift+L", self.toggle_active_tab_lock),
            ("Ctrl+P", self.open_quick_palette),
        ]
        self._shortcuts = [QShortcut(QKeySequence(seq), self.win, activated=fn) for seq, fn in shortcuts]

        for pane in getattr(self.win, "panes", []):
            self._hook_pane(pane)

        self.win._addons_controller = self
        return self

    def _active_pane(self) -> Any:
        return self.win.active_pane() if hasattr(self.win, "active_pane") else None

    def _active_tab(self) -> Any:
        pane = self._active_pane()
        return pane.current_tab() if pane is not None else None

    def _hook_pane(self, pane: Any) -> None:
        if id(pane) in self._installed_panes:
            return
        self._installed_panes.add(id(pane))
        Qt = self.qt["QtCore"].Qt

        orig_add_tab = pane.add_new_tab

        def _wrapped_add_tab(path_str: Optional[str] = None) -> Any:
            tab = orig_add_tab(path_str)
            self._hook_tab(tab)
            return tab

        pane.add_new_tab = _wrapped_add_tab

        orig_close_tab = pane.close_tab

        def _wrapped_close_tab(index: int) -> None:
            w = pane.tab_widget.widget(index)
            if w is not None and not self.tab_locks.can_close_tab(w):
                self._notify("🔒 잠긴 탭은 닫을 수 없습니다. (Ctrl+Shift+L로 탭 잠금 해제 후 닫기)")
                return
            if w is not None:
                self.tab_locks.unregister(w)
            orig_close_tab(index)

        pane.close_tab = _wrapped_close_tab

        if hasattr(pane, "_refresh_all_tab_titles"):
            orig_refresh_titles = pane._refresh_all_tab_titles

            def _wrapped_refresh_titles() -> None:
                orig_refresh_titles()
                for i in range(pane.tab_widget.count()):
                    w = pane.tab_widget.widget(i)
                    if w is None:
                        continue
                    txt = pane.tab_widget.tabText(i)
                    badges = ""
                    if self.tab_locks.is_locked(w):
                        badges += "🔒 "
                    if getattr(w, "_flat_view_enabled", False):
                        badges += "[플랫] "
                    if badges and not txt.startswith(badges.strip()[:1]):
                        pane.tab_widget.setTabText(i, f"{badges}{txt}")

            pane._refresh_all_tab_titles = _wrapped_refresh_titles

        tab_bar = pane.tab_widget.tabBar()
        if hasattr(tab_bar, "setContextMenuPolicy"):
            tab_bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            tab_bar.customContextMenuRequested.connect(
                lambda pos, p=pane, tb=tab_bar: self._show_tab_bar_menu(p, tb, pos)
            )

        for i in range(pane.tab_widget.count()):
            w = pane.tab_widget.widget(i)
            if w is not None:
                self._hook_tab(w)

    def _show_tab_bar_menu(self, pane: Any, tab_bar: Any, pos: Any) -> None:
        QtWidgets = self.qt["QtWidgets"]
        idx = tab_bar.tabAt(pos) if hasattr(tab_bar, "tabAt") else pane.tab_widget.currentIndex()
        if idx < 0:
            idx = pane.tab_widget.currentIndex()
        w = pane.tab_widget.widget(idx)
        if w is None:
            return

        menu = QtWidgets.QMenu(pane)
        act_dup = menu.addAction("📑 이 탭 복제 (Ctrl+Shift+K)")
        is_locked = self.tab_locks.is_locked(w)
        act_lock = menu.addAction("🔓 탭 잠금 해제 (Ctrl+Shift+L)" if is_locked else "🔒 이 탭 잠금 (Ctrl+Shift+L)")
        act_root = None
        if is_locked:
            root_p = self.tab_locks.locked_root(w)
            act_root = menu.addAction(f"📂 잠금 기준 경로로 복귀 ({Path(root_p).name or root_p})")
        menu.addSeparator()
        act_close_others = menu.addAction("❌ 잠기지 않은 다른 탭 모두 닫기")

        chosen = menu.exec(tab_bar.mapToGlobal(pos))
        if chosen == act_dup:
            self.duplicate_tab_in_pane(pane, idx)
        elif chosen == act_lock:
            self.toggle_tab_lock_in_pane(pane, idx)
        elif act_root is not None and chosen == act_root:
            w.navigate_to(self.tab_locks.locked_root(w), record_history=True)
        elif chosen == act_close_others:
            for i in range(pane.tab_widget.count() - 1, -1, -1):
                if i != idx:
                    cand = pane.tab_widget.widget(i)
                    if cand is not None and self.tab_locks.can_close_tab(cand):
                        pane.close_tab(i)

    def _hook_tab(self, tab: Any) -> None:
        if id(tab) in self._installed_tabs:
            return
        self._installed_tabs.add(id(tab))
        tab._flat_view_enabled = False

        orig_collect = tab._collect_sorted_entries

        def _wrapped_collect(p: Path) -> List[Dict[str, object]]:
            if getattr(tab, "_flat_view_enabled", False):
                recs, truncated = collect_flat_view_records(
                    str(p),
                    show_hidden=bool(getattr(self.win, "show_hidden_files", False)),
                    show_extensions=bool(getattr(self.win, "show_file_extensions", True)),
                    sort_by=getattr(tab, "sort_by", "name"),
                    sort_asc=bool(getattr(tab, "sort_asc", True)),
                )
                tab._flat_view_truncated = truncated
                return recs

            records = orig_collect(p)
            any_cached_dir = False
            for r in records:
                if r.get("is_dir"):
                    f_path = safe_norm_path(str(r.get("path", "")))
                    cached = self.folder_size_cache.get(f_path)
                    if cached is not None:
                        r["size_b"] = cached.total_bytes
                        r["size_str"] = f"{cached.formatted_size} ({cached.file_count:,}파일)"
                        any_cached_dir = True

            if any_cached_dir and getattr(tab, "sort_by", "name") == "size":
                dirs = [r for r in records if r["is_dir"]]
                files = [r for r in records if not r["is_dir"]]
                dirs.sort(key=lambda x: int(x["size_b"]), reverse=not tab.sort_asc)
                records = dirs + files
            return records

        tab._collect_sorted_entries = _wrapped_collect

        if hasattr(tab, "update_status_summary"):
            orig_summary = tab.update_status_summary

            def _wrapped_summary() -> None:
                orig_summary()
                prefix_tags: List[str] = []
                if getattr(tab, "_flat_view_enabled", False):
                    trunc_note = " · 상한 도달" if getattr(tab, "_flat_view_truncated", False) else ""
                    prefix_tags.append(f"🗂️ 플랫 뷰 ON{trunc_note}")
                sel = tab.selected_file_paths()
                sel_dirs_cached = [
                    self.folder_size_cache[safe_norm_path(sp)]
                    for sp in sel
                    if safe_norm_path(sp) in self.folder_size_cache
                ]
                if sel_dirs_cached:
                    sum_b = sum(c.total_bytes for c in sel_dirs_cached)
                    sum_f = sum(c.file_count for c in sel_dirs_cached)
                    prefix_tags.append(f"폴더 실용량 {format_bytes(sum_b)} ({sum_f:,}파일)")
                if prefix_tags and hasattr(tab, "summary_label"):
                    base_txt = tab.summary_label.text()
                    tab.summary_label.setText(f"[{' | '.join(prefix_tags)}]  {base_txt}")

            tab.update_status_summary = _wrapped_summary

    def populate_tools_menu(self, menu: Any) -> None:
        menu.clear()
        tab = self._active_tab()
        flat_on = bool(tab and getattr(tab, "_flat_view_enabled", False))
        locked_on = bool(tab and self.tab_locks.is_locked(tab))

        menu.addAction("✏️ 일괄 이름 바꾸기 (Multi-Rename)...\tCtrl+M").triggered.connect(self.open_multi_rename)
        a_undo = menu.addAction(
            f"↩️ 직전 일괄 이름 변경 실행 취소 ({len(self.undo_stack[-1].entries)}개)\tCtrl+Shift+Z"
            if self.undo_stack
            else "↩️ 직전 일괄 이름 변경 실행 취소 (내역 없음)\tCtrl+Shift+Z"
        )
        a_undo.setEnabled(bool(self.undo_stack))
        a_undo.triggered.connect(self.undo_last_multi_rename)

        menu.addSeparator()
        menu.addAction("⚖️ 패널 간 폴더 비교 · 동기화 미리보기...\tShift+F2").triggered.connect(self.open_compare_panes)
        menu.addAction("📊 폴더 실제 용량 계산 (<DIR> → 실제 크기)\tAlt+Shift+Enter").triggered.connect(
            self.calculate_active_folder_sizes
        )
        menu.addAction("🔐 파일 해시(MD5/SHA) 검증 · 중복 파일 찾기...\tCtrl+Shift+H").triggered.connect(
            self.open_checksum_and_duplicates
        )

        menu.addSeparator()
        menu.addAction("📤 현재 파일 목록 내보내기 (CSV/MD/HTML/TXT)...\tCtrl+Shift+E").triggered.connect(
            self.open_export_file_list
        )
        a_flat = menu.addAction(
            f"{'✅ ' if flat_on else ''}🗂️ 플랫 뷰 (하위 폴더 파일 모아보기 토글)\tCtrl+B"
        )
        a_flat.triggered.connect(self.toggle_active_flat_view)

        menu.addSeparator()
        menu.addAction("📑 현재 탭 복제 (Duplicate Tab)\tCtrl+Shift+K").triggered.connect(self.duplicate_active_tab)
        menu.addAction(
            f"{'🔓 현재 탭 잠금 해제' if locked_on else '🔒 현재 탭 잠금 (닫기 방지)'}\tCtrl+Shift+L"
        ).triggered.connect(self.toggle_active_tab_lock)
        menu.addSeparator()
        menu.addAction("⚡ 빠른 폴더 이동 · 명령 팔레트 (Quick Palette)...\tCtrl+P").triggered.connect(
            self.open_quick_palette
        )

    def populate_tab_context_menu(self, menu: Any, tab: Any, _selected_paths: Sequence[str]) -> None:
        """DirectoryTab 우클릭 메뉴(`_show_context_menu`) 하단에 부가기능 서브메뉴를 주입합니다."""
        menu.addSeparator()
        sub = menu.addMenu("🧰 고급 부가기능 (이름변경·패널비교·해시·내보내기)") if hasattr(menu, "addMenu") else menu
        self.populate_tools_menu(sub)

    def _reselect_paths_in_tab(self, tab: Any, paths: Sequence[str]) -> None:
        if not paths:
            return
        targets_cf = {safe_norm_path(p).casefold() for p in paths}
        Qt = self.qt["QtCore"].Qt
        if hasattr(tab, "table") and hasattr(tab.table, "rowCount"):
            tab.table.clearSelection()
            for row in range(tab.table.rowCount()):
                it = tab.table.item(row, 0)
                if it is not None:
                    p_val = it.data(Qt.ItemDataRole.UserRole)
                    if p_val and safe_norm_path(str(p_val)).casefold() in targets_cf:
                        for c_i in range(tab.table.columnCount()):
                            cell = tab.table.item(row, c_i)
                            if cell is not None:
                                cell.setSelected(True)
        if hasattr(tab, "icon_list") and hasattr(tab.icon_list, "count"):
            tab.icon_list.clearSelection()
            for i in range(tab.icon_list.count()):
                l_it = tab.icon_list.item(i)
                if l_it is not None:
                    p_val = l_it.data(Qt.ItemDataRole.UserRole)
                    if p_val and safe_norm_path(str(p_val)).casefold() in targets_cf:
                        l_it.setSelected(True)
        if hasattr(tab, "update_status_summary"):
            tab.update_status_summary()

    def _notify(self, msg: str, timeout: int = 5000) -> None:
        if hasattr(self.win, "show_status_message"):
            self.win.show_status_message(msg, timeout)
        elif hasattr(self.win, "statusBar") and self.win.statusBar() is not None:
            self.win.statusBar().showMessage(msg, timeout)

    def open_multi_rename(self) -> None:
        tab = self._active_tab()
        if tab is None or not tab.current_path:
            return
        targets = tab.selected_file_paths()
        if not targets:
            try:
                with os.scandir(tab.current_path) as it:
                    targets = [
                        safe_norm_path(e.path)
                        for e in sorted(list(it), key=lambda x: x.name.casefold())
                        if (getattr(self.win, "show_hidden_files", False) or not e.name.startswith("."))
                        and not is_symlink_or_reparse_point(e.path)
                    ]
            except OSError:
                targets = []
        if not targets:
            self._notify("일괄 이름을 변경할 파일이나 폴더가 없습니다.")
            return
        _open_multi_rename_dialog(
            self.win,
            targets,
            dark_mode=bool(getattr(self.win, "dark_mode", True)),
            undo_stack=self.undo_stack,
            on_changed_callback=self.win.refresh_all_panes,
            qt_mods=self.qt,
        )

    def undo_last_multi_rename(self) -> None:
        if not self.undo_stack:
            self._notify("실행 취소할 일괄 이름 변경 내역이 없습니다.")
            return
        last_batch = self.undo_stack[-1]
        ok, errs = undo_multi_rename_batch(last_batch)
        if not ok:
            self.qt["QtWidgets"].QMessageBox.warning(self.win, "실행 취소 차단", "\n".join(errs[:6]))
            return
        self.undo_stack.pop()
        self.win.refresh_all_panes()
        self._notify(f"↩️ 직전 일괄 이름 변경({len(last_batch.entries)}개)을 원본 이름으로 안전하게 복원했습니다.")

    def open_compare_panes(self) -> None:
        panes = getattr(self.win, "panes", [])
        if not panes:
            return
        pane_paths = [(p.pane_title, p.current_path()) for p in panes]
        active_idx = int(getattr(self.win, "active_pane_index", 0))
        _open_compare_panes_dialog(
            self.win,
            pane_paths=pane_paths,
            active_pane_idx=active_idx,
            dark_mode=bool(getattr(self.win, "dark_mode", True)),
            include_hidden=bool(getattr(self.win, "show_hidden_files", False)),
            on_synced_callback=self.win.refresh_all_panes,
            qt_mods=self.qt,
        )

    def calculate_active_folder_sizes(self) -> Dict[str, FolderSizeSummary]:
        tab = self._active_tab()
        if tab is None or not tab.current_path:
            return {}
        prev_selected = tab.selected_file_paths()
        sel_dirs = [p for p in prev_selected if os.path.isdir(p)]
        computed = calculate_immediate_subfolders_sizes(
            tab.current_path,
            target_folders=sel_dirs if sel_dirs else None,
            include_hidden=bool(getattr(self.win, "show_hidden_files", False)),
        )
        self.folder_size_cache.update(computed)
        tab.refresh()
        if prev_selected:
            self._reselect_paths_in_tab(tab, prev_selected)
        total_b = sum(s.total_bytes for s in computed.values())
        total_f = sum(s.file_count for s in computed.values())
        self._notify(
            f"📊 폴더 {len(computed):,}개 실제 용량 계산 완료: 총 {format_bytes(total_b)} (하위 파일 {total_f:,}개)"
        )
        return computed

    def open_checksum_and_duplicates(self) -> None:
        tab = self._active_tab()
        if tab is None or not tab.current_path:
            return

        def _select_multi(paths: Sequence[str]) -> None:
            if not paths:
                return
            first_parent = os.path.dirname(safe_norm_path(paths[0]))
            if safe_norm_path(tab.current_path).casefold() != first_parent.casefold():
                tab.navigate_to(first_parent, record_history=True)
            self._reselect_paths_in_tab(tab, paths)
            self._notify(f"🔍 중복 확인 대상 {len(paths)}개 항목을 선택했습니다. (자동 삭제 없음)")

        _open_checksum_duplicate_dialog(
            self.win,
            current_dir=tab.current_path,
            selected_paths=tab.selected_file_paths(),
            dark_mode=bool(getattr(self.win, "dark_mode", True)),
            include_hidden=bool(getattr(self.win, "show_hidden_files", False)),
            select_paths_in_tab_cb=_select_multi,
            qt_mods=self.qt,
        )

    def open_export_file_list(self) -> Optional[str]:
        tab = self._active_tab()
        if tab is None or not tab.current_path:
            return None
        saved = _open_export_list_dialog(
            self.win,
            current_dir=tab.current_path,
            dark_mode=bool(getattr(self.win, "dark_mode", True)),
            include_hidden=bool(getattr(self.win, "show_hidden_files", False)),
            folder_size_cache=self.folder_size_cache,
            qt_mods=self.qt,
        )
        if saved:
            tab.refresh()
            self._notify(f"📤 파일 목록 내보내기 완료: {saved}")
        return saved

    def toggle_active_flat_view(self) -> bool:
        pane = self._active_pane()
        tab = self._active_tab()
        if tab is None or pane is None:
            return False
        new_state = not bool(getattr(tab, "_flat_view_enabled", False))
        tab._flat_view_enabled = new_state
        tab.refresh()
        if hasattr(pane, "_refresh_all_tab_titles"):
            pane._refresh_all_tab_titles()
        self._notify(
            "🗂️ 플랫 뷰 활성화: 하위 폴더의 모든 파일을 한 화면에 모아 표시합니다. (Ctrl+B로 해제)"
            if new_state
            else "📁 일반 폴더 뷰로 복귀했습니다."
        )
        return new_state

    def duplicate_tab_in_pane(self, pane: Any, tab_index: Optional[int] = None) -> Any:
        idx = pane.tab_widget.currentIndex() if tab_index is None else tab_index
        src_tab = pane.tab_widget.widget(idx)
        if src_tab is None:
            return None
        new_tab = pane.add_new_tab(src_tab.current_path)
        for attr in ("sort_by", "sort_asc", "group_by"):
            if hasattr(src_tab, attr):
                setattr(new_tab, attr, getattr(src_tab, attr))
        if hasattr(src_tab, "view_mode") and hasattr(new_tab, "set_view_mode"):
            new_tab.set_view_mode(src_tab.view_mode)
        new_tab.refresh()
        self._notify(f"📑 탭 복제 완료: {src_tab.current_path}")
        return new_tab

    def duplicate_active_tab(self) -> Any:
        pane = self._active_pane()
        return self.duplicate_tab_in_pane(pane) if pane is not None else None

    def toggle_tab_lock_in_pane(self, pane: Any, tab_index: Optional[int] = None) -> Optional[TabLockState]:
        idx = pane.tab_widget.currentIndex() if tab_index is None else tab_index
        tab = pane.tab_widget.widget(idx)
        if tab is None:
            return None
        st = self.tab_locks.toggle_lock(tab, tab.current_path)
        if hasattr(pane, "_refresh_all_tab_titles"):
            pane._refresh_all_tab_titles()
        self._notify(
            f"🔒 탭 잠금 설정됨 (기준 경로: {st.locked_root_path})"
            if st.locked
            else "🔓 탭 잠금이 해제되었습니다."
        )
        return st


    def collect_quick_palette_entries(self) -> List[Tuple[str, str, Callable[[], None]]]:
        """즐겨찾기, 4분할 열린 탭, 최근 방문 기록, 부가기능 명령을 퍼지 검색용 목록으로 수집합니다."""
        items: List[Tuple[str, str, Callable[[], None]]] = []
        active_pane = self._active_pane()

        def _go_dir(target_p: str) -> Callable[[], None]:
            return lambda: active_pane.navigate_current_tab(target_p) if active_pane is not None else None

        items.append(("명령 · 일괄 이름 바꾸기 (Ctrl+M)", "command:multi-rename", self.open_multi_rename))
        items.append(("명령 · 패널 간 폴더 비교·동기화 (Shift+F2)", "command:compare-panes", self.open_compare_panes))
        items.append(("명령 · 폴더 실제 용량 계산 (Alt+Shift+Enter)", "command:folder-size", lambda: (self.calculate_active_folder_sizes(), None)[1]))
        items.append(("명령 · 파일 해시 검증 및 중복 파일 찾기 (Ctrl+Shift+H)", "command:hash-duplicates", self.open_checksum_and_duplicates))
        items.append(("명령 · 파일 목록 내보내기 CSV/MD/HTML/TXT (Ctrl+Shift+E)", "command:export-list", lambda: (self.open_export_file_list(), None)[1]))
        items.append(("명령 · 플랫 뷰 토글 (Ctrl+B)", "command:flat-view", lambda: (self.toggle_active_flat_view(), None)[1]))
        items.append(("명령 · 현재 탭 복제 (Ctrl+Shift+K)", "command:duplicate-tab", lambda: (self.duplicate_active_tab(), None)[1]))
        items.append(("명령 · 현재 탭 잠금 토글 (Ctrl+Shift+L)", "command:lock-tab", lambda: (self.toggle_active_tab_lock(), None)[1]))

        seen_paths: Set[str] = set()
        for fav in getattr(self.win, "favorites", []):
            fp = str(fav.get("path", "")).strip()
            fn = str(fav.get("name", "")).strip() or fp
            if fp and fp.casefold() not in seen_paths:
                seen_paths.add(fp.casefold())
                items.append((f"⭐ 즐겨찾기 · {fn}", fp, _go_dir(fp)))

        for p_idx, pane in enumerate(getattr(self.win, "panes", [])):
            for t_idx in range(pane.tab_widget.count()):
                w = pane.tab_widget.widget(t_idx)
                cp = getattr(w, "current_path", "")
                if cp:
                    key = f"tab:{p_idx}:{t_idx}:{cp.casefold()}"
                    if key not in seen_paths:
                        seen_paths.add(key)
                        items.append((f"🗂️ {p_idx + 1}번 창 탭 #{t_idx + 1} · {Path(cp).name or cp}", cp, _go_dir(cp)))
                for hp in reversed(getattr(w, "history", [])):
                    if hp and hp.casefold() not in seen_paths:
                        seen_paths.add(hp.casefold())
                        items.append((f"🕘 최근 경로 · {Path(hp).name or hp}", hp, _go_dir(hp)))

        return items

    def open_quick_palette(self) -> None:
        QtCore, QtWidgets = self.qt["QtCore"], self.qt["QtWidgets"]
        dark_mode = bool(getattr(self.win, "dark_mode", True))
        dlg = QtWidgets.QDialog(self.win)
        dlg.setWindowTitle("⚡ 빠른 폴더 이동 · 명령 팔레트 (Ctrl+P)")
        dlg.resize(680, 440)
        dlg.setStyleSheet(build_addon_dialog_qss(dark_mode))

        lay = QtWidgets.QVBoxLayout(dlg)
        ed = QtWidgets.QLineEdit()
        ed.setPlaceholderText("이동할 폴더명, 경로 일부 또는 실행할 기능 이름 입력 후 Enter...")
        lay.addWidget(ed)

        lst = QtWidgets.QListWidget()
        lay.addWidget(lst, stretch=1)

        entries = self.collect_quick_palette_entries()
        filtered: List[Tuple[str, str, Callable[[], None]]] = []

        def _refresh_list(query: str) -> None:
            nonlocal filtered
            tokens = [tok for tok in query.strip().casefold().split() if tok]
            filtered = [
                e for e in entries
                if all(tok in f"{e[0]} {e[1]}".casefold() for tok in tokens)
            ]
            lst.clear()
            for title, detail, _ in filtered:
                label = f"{title}   —   {detail}" if not detail.startswith("command:") else title
                lst.addItem(label)
            if lst.count() > 0:
                lst.setCurrentRow(0)

        def _execute_selected() -> None:
            row = lst.currentRow()
            if 0 <= row < len(filtered):
                action = filtered[row][2]
                dlg.accept()
                action()

        ed.textChanged.connect(_refresh_list)
        ed.returnPressed.connect(_execute_selected)
        lst.itemDoubleClicked.connect(lambda _it: _execute_selected())
        _refresh_list("")
        ed.setFocus()
        dlg.exec()

    def toggle_active_tab_lock(self) -> Optional[TabLockState]:
        pane = self._active_pane()
        return self.toggle_tab_lock_in_pane(pane) if pane is not None else None


def install_pyquaddir_addons(
    main_window: Any,
    qt_mods: Optional[Dict[str, Any]] = None,
) -> PyQuadDirAddonController:
    """
    PyQuadDir v3.1.1의 `QDirMainWindow.__init__` 마지막 줄에 호출하여 5대 부가기능을 즉시 활성화합니다:
        from pyquaddir_addons import install_pyquaddir_addons
        install_pyquaddir_addons(self)
    """
    existing = getattr(main_window, "_addons_controller", None)
    if isinstance(existing, PyQuadDirAddonController):
        return existing
    ctrl = PyQuadDirAddonController(main_window, qt_mods=qt_mods)
    return ctrl.install()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
archive_safe_core.py — PyQuadDir v2.5 / Q-Dir v3.1 독립 압축 안전 코어 모듈
=============================================================================
[핵심 보안·무결성·경합 방어 설계]
1. 첫 쓰기 전 전수 검사 (inspect_archive_entries):
   - .., 드라이브/절대/UNC, NTFS ADS(:), 예약 파일명, 끝 공백/점, 심볼릭/하드 링크·Junction/Reparse,
     대소문자 중복 및 대상 기존 파일/폴더 충돌을 첫 바이트 쓰기 전에 차단합니다.
2. 덮어쓰기(overwrite=True) 경로 완전 제거 및 비덮어쓰기 전용 게시:
   - overwrite=True 요청은 즉시 거부(ValueError / False)하며 코드 내 os.replace 호출을 완전히 제거했습니다.
   - 게시 전 스테이징 파일/폴더에서 확보한 고유 식별자(src_id / pre_records)만 기록하며,
     게시 후 대상 경로에서 식별자를 다시 읽지 않아 게시 직후 다른 작성자의 교체 경합을 원천 차단합니다.
3. 커널 핸들 기반 검증 삭제 (_delete_by_verified_handle):
   - Windows: CreateFileW(DELETE | FILE_READ_ATTRIBUTES, FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_BACKUP_SEMANTICS)로
     핸들을 연 뒤 GetFileInformationByHandle로 게시 전 스테이징 ID와 대조하고, 일치할 때만
     SetFileInformationByHandle(FileDispositionInfoEx=21 / FileDispositionInfo=4)로 열린 핸들 자체를 삭제합니다.
   - POSIX: O_NOFOLLOW 파일 디스크립터를 먼저 열어 fstat으로 게시 전 스테이징 ID를 검증한 뒤 삭제합니다.
"""

from __future__ import annotations

import ctypes
import os
import platform
import re
import shutil
import stat
import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

ARCHIVE_EXTENSIONS = {
    ".zip", ".tar", ".gz", ".tgz", ".bz2", ".tbz2", ".xz", ".txz"
}

FILE_ATTRIBUTE_REPARSE_POINT = 0x0400
IO_REPARSE_TAG_MOUNT_POINT = 0xA0000003
IO_REPARSE_TAG_SYMLINK = 0xA000000C

WINDOWS_RESERVED_NAMES: Set[str] = {
    "CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$", "CLOCK$",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
    "COM¹", "COM²", "COM³", "LPT¹", "LPT²", "LPT³",
}

WINDOWS_INVALID_CHARS: Set[str] = set('<>:"|?*')


def is_archive_file(file_path: str) -> bool:
    if not file_path or os.path.isdir(file_path):
        return False
    name_low = Path(file_path).name.lower()
    if name_low.endswith((".tar.gz", ".tar.bz2", ".tar.xz")):
        return True
    return Path(name_low).suffix in ARCHIVE_EXTENSIONS


def strip_archive_stem(file_path: str) -> str:
    name = Path(file_path).name
    low = name.lower()
    for compound in (".tar.gz", ".tar.bz2", ".tar.xz"):
        if low.endswith(compound):
            return name[: -len(compound)] or "extracted"
    return Path(name).stem or "extracted"


def decode_zip_filename(info: zipfile.ZipInfo) -> str:
    """구형 Windows/알집 ZIP 엔트리의 CP949/EUC-KR 한글 파일명(0x800 미설정 또는 CP437 모지바케)을 복원합니다."""
    raw_name = info.filename
    if all(ord(ch) < 128 for ch in raw_name):
        return raw_name
    try:
        raw_bytes = raw_name.encode("cp437")
    except UnicodeEncodeError:
        # 이미 정상 유니코드(예: 한글 음절 U+AC00~U+D7A3)인 경우 그대로 반환
        return raw_name
    for enc in ("utf-8", "cp949", "euc-kr"):
        try:
            return raw_bytes.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw_name


def is_symlink_or_reparse_point(path_str: str) -> bool:
    """
    지정된 경로가 심볼릭 링크, Windows 디렉터리 Junction(mklink /J), 마운트 포인트,
    또는 Reparse Point인지 정밀 판별합니다.
    """
    if not path_str:
        return False
    try:
        if os.path.islink(path_str):
            return True
    except Exception:
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
    except Exception:
        pass
    if platform.system() == "Windows":
        try:
            attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path_str))
            if attrs != 0xFFFFFFFF and (attrs & FILE_ATTRIBUTE_REPARSE_POINT):
                return True
        except Exception:
            pass
    return False


def _find_case_insensitive_existing(parent_dir: str, segment_name: str) -> Optional[str]:
    """parent_dir 내부에서 segment_name과 대소문자 구분 없이 일치하는 기존 항목 경로를 반환합니다."""
    if not parent_dir or not segment_name:
        return None
    direct = os.path.join(parent_dir, segment_name)
    try:
        if os.path.lexists(direct):
            return direct
    except Exception:
        pass
    try:
        if not os.path.isdir(parent_dir) or is_symlink_or_reparse_point(parent_dir):
            return None
        target_cf = segment_name.casefold()
        with os.scandir(parent_dir) as it:
            for entry in it:
                if entry.name.casefold() == target_cf:
                    return os.path.join(parent_dir, entry.name)
    except Exception:
        pass
    return None


def _ensure_no_reparse_in_base_dir(base_dir: str) -> None:
    """대상 기준 폴더 자체 및 상위 경로에 심볼릭 링크/Junction이 없는지 검사합니다."""
    norm_base = safe_norm_path(base_dir)
    if not norm_base:
        raise PermissionError("보안 차단: 유효하지 않은 대상 폴더 경로입니다.")
    curr = Path(norm_base)
    chain: List[Path] = []
    while True:
        chain.append(curr)
        if curr.parent == curr:
            break
        curr = curr.parent
    # 루트(드라이브 루트)는 제외하고 하위 경로 체인에서 링크/Junction 여부 확인
    for p in reversed(chain[:-1]):
        p_str = str(p)
        if os.path.lexists(p_str) and is_symlink_or_reparse_point(p_str):
            raise PermissionError(
                f"보안 차단: 대상 경로 체인에 심볼릭 링크 또는 Junction(Reparse Point)이 존재합니다 ({p_str})"
            )


def _validate_segment_security(seg: str, full_raw_path: str) -> None:
    """단일 경로 세그먼트에 대해 탈출·예약어·끝 공백/점·금지 문자·ADS 여부를 검증합니다."""
    if not seg:
        raise PermissionError(f"보안 차단: 빈 경로 세그먼트가 포함되어 있습니다 ({full_raw_path})")
    if seg == "..":
        raise PermissionError(f"보안 차단: 상위 폴더 탈출('..') 경로가 포함되어 있습니다 ({full_raw_path})")
    if seg == ".":
        raise PermissionError(f"보안 차단: 허용되지 않는 상대 현재 경로('.') 세그먼트입니다 ({full_raw_path})")
    if seg.endswith(" ") or seg.endswith("."):
        raise PermissionError(
            f"보안 차단: 파일/폴더 이름 끝에 공백 또는 마침표('.')를 사용할 수 없습니다 ({full_raw_path})"
        )
    if ":" in seg:
        raise PermissionError(
            f"보안 차단: NTFS 대체 데이터 스트림(ADS) 또는 드라이브 콜론(':')이 포함되어 있습니다 ({full_raw_path})"
        )
    for ch in seg:
        if ord(ch) < 32 or ch in WINDOWS_INVALID_CHARS:
            raise PermissionError(
                f"보안 차단: 파일명에 허용되지 않는 특수/제어 문자가 포함되어 있습니다 ({full_raw_path})"
            )
    stem = seg.rstrip(" .").split(".")[0].upper()
    if stem in WINDOWS_RESERVED_NAMES:
        raise PermissionError(
            f"보안 차단: Windows 예약 장치 파일명('{seg}')은 사용할 수 없습니다 ({full_raw_path})"
        )


def validate_archive_member_path(dest_root: str, member_rel_path: str) -> Tuple[str, List[str], bool]:
    r"""
    ZIP·TAR 항목의 경로를 첫 쓰기 전에 정밀 검증하고 (안전한 대상 절대경로, 세그먼트 리스트, 디렉터리 여부)를 반환합니다.
    차단 대상:
      - 빈 문자열, NULL 바이트, 제어 문자(< 0x20)
      - 절대 경로(`/absolute.txt`, `\absolute.txt`) 및 UNC 경로(`\\server\share\a`, `//server/share/a`)
      - Windows 드라이브 문자(`C:\evil.txt`, `C:/evil.txt`, `C:relative.txt`)
      - NTFS 대체 데이터 스트림(ADS: `file.txt:stream`, `file.txt::$DATA`, `dir:ads/a.txt`)
      - 상위 경로 탈출(`..`) 및 현재 경로(`.`) 세그먼트
      - 세그먼트 끝 공백/마침표(`file.txt `, `file.`), Windows 금지 특수문자(`<>:"|?*`)
      - Windows 예약 파일명(`CON`, `PRN`, `AUX`, `NUL`, `COM1..9`, `LPT1..9` 등 확장자 포함)
      - 대상 폴더 내부의 기존 심볼릭 링크 / Junction(Reparse Point) 경유
    """
    if not isinstance(member_rel_path, str) or not member_rel_path:
        raise PermissionError("보안 차단: 비어 있는 압축 항목 경로입니다.")
    if "\x00" in member_rel_path:
        raise PermissionError("보안 차단: NULL 바이트가 포함된 경로입니다.")
    for ch in member_rel_path:
        if ord(ch) < 32:
            raise PermissionError(f"보안 차단: 제어 문자가 포함된 압축 항목 경로입니다 ({member_rel_path!r})")

    # 1. 루트/절대 경로 및 UNC 경로 차단 (선행 '/' 또는 '\' 제거 금지!)
    if member_rel_path.startswith(("/", "\\")):
        if member_rel_path.startswith(("\\\\", "//")):
            raise PermissionError(f"보안 차단: UNC 네트워크 경로 형식은 허용되지 않습니다 ({member_rel_path})")
        raise PermissionError(f"보안 차단: 루트/절대 경로 형식은 허용되지 않습니다 ({member_rel_path})")

    # 2. 드라이브 문자 및 NTFS ADS(':') 차단
    if re.match(r"^[A-Za-z]:", member_rel_path):
        raise PermissionError(f"보안 차단: 드라이브 문자가 포함된 경로는 허용되지 않습니다 ({member_rel_path})")
    if ":" in member_rel_path:
        raise PermissionError(
            f"보안 차단: NTFS 대체 데이터 스트림(ADS) 또는 콜론(':') 경로는 허용되지 않습니다 ({member_rel_path})"
        )

    is_dir_entry = member_rel_path.endswith(("/", "\\"))
    normalized_slashes = member_rel_path.replace("\\", "/")
    if is_dir_entry:
        normalized_slashes = normalized_slashes.rstrip("/")

    if not normalized_slashes:
        raise PermissionError(f"보안 차단: 유효한 하위 경로가 없는 항목입니다 ({member_rel_path})")

    raw_segments = normalized_slashes.split("/")
    clean_segments: List[str] = []
    for seg in raw_segments:
        _validate_segment_security(seg, member_rel_path)
        clean_segments.append(seg)

    norm_root = safe_norm_path(dest_root)
    _ensure_no_reparse_in_base_dir(norm_root)

    target = safe_norm_path(os.path.join(norm_root, *clean_segments))
    try:
        common = os.path.commonpath([norm_root, target])
    except ValueError:
        raise PermissionError(f"보안 차단: 대상 폴더와 다른 드라이브를 가리키는 경로입니다 ({member_rel_path})")

    if common.casefold() != norm_root.casefold() or target.casefold() == norm_root.casefold():
        raise PermissionError(f"보안 차단: 대상 폴더 외부를 가리키는 압축 항목입니다 ({member_rel_path})")

    # 3. 대상 폴더 내부의 기존 경로 체인에 심볼릭 링크/Junction(Reparse Point)이 있는지 검사
    real_root = safe_norm_path(os.path.realpath(norm_root))
    curr_parent = norm_root
    for seg in clean_segments:
        existing_match = _find_case_insensitive_existing(curr_parent, seg)
        check_path = existing_match if existing_match is not None else os.path.join(curr_parent, seg)
        if os.path.lexists(check_path):
            if is_symlink_or_reparse_point(check_path):
                raise PermissionError(
                    f"보안 차단: 대상 경로에 심볼릭 링크 또는 Junction(Reparse Point)이 존재합니다 ({check_path})"
                )
            real_check = safe_norm_path(os.path.realpath(check_path))
            try:
                if os.path.commonpath([real_root, real_check]).casefold() != real_root.casefold():
                    raise PermissionError(
                        f"보안 차단: 대상 경로가 외부 디렉터리(Junction/심볼릭 링크)로 연결되어 있습니다 ({check_path})"
                    )
            except ValueError:
                raise PermissionError(
                    f"보안 차단: 대상 경로가 다른 드라이브(Junction)로 연결되어 있습니다 ({check_path})"
                )
        curr_parent = check_path

    return target, clean_segments, is_dir_entry


def _validate_safe_extract_dest(dest_root: str, member_rel_path: str) -> str:
    """하위 호환 래퍼: ZIP·TAR 항목 경로 검증 후 안전한 대상 절대 경로를 반환합니다."""
    target, _, _ = validate_archive_member_path(dest_root, member_rel_path)
    return target


def _check_zip_member_not_link_or_special(info: zipfile.ZipInfo, decoded_name: str) -> None:
    """ZIP 엔트리가 심볼릭 링크, Reparse Point, FIFO/소켓/디바이스 특수 파일인지 검사합니다."""
    unix_mode = (info.external_attr >> 16) & 0xFFFF
    dos_attr = info.external_attr & 0xFFFF
    if stat.S_ISLNK(unix_mode):
        raise PermissionError(f"보안 차단: ZIP 내부에 심볼릭 링크 항목이 포함되어 있습니다 ({decoded_name})")
    if (
        stat.S_ISFIFO(unix_mode)
        or stat.S_ISCHR(unix_mode)
        or stat.S_ISBLK(unix_mode)
        or stat.S_ISSOCK(unix_mode)
    ):
        raise PermissionError(f"보안 차단: ZIP 내부에 특수 디바이스/파이프 항목이 포함되어 있습니다 ({decoded_name})")
    if dos_attr & FILE_ATTRIBUTE_REPARSE_POINT:
        raise PermissionError(
            f"보안 차단: ZIP 내부에 Windows Junction/Reparse Point 속성 항목이 포함되어 있습니다 ({decoded_name})"
        )


def _check_tar_member_not_link_or_special(member: tarfile.TarInfo) -> None:
    """TAR 엔트리가 심볼릭 링크, 하드 링크, FIFO, 디바이스 파일인지 검사합니다."""
    if member.issym() or member.islnk():
        raise PermissionError(
            f"보안 차단: TAR 내부에 심볼릭/하드 링크 항목이 포함되어 있습니다 ({member.name} -> {member.linkname})"
        )
    if member.isfifo() or member.ischr() or member.isblk() or member.isdev():
        raise PermissionError(f"보안 차단: TAR 내부에 특수 디바이스/파이프 항목이 포함되어 있습니다 ({member.name})")
    if not (member.isfile() or member.isdir()):
        raise PermissionError(f"보안 차단: 지원하지 않는 TAR 특수 엔트리 유형입니다 ({member.name})")


def inspect_archive_entries(
    archive_path: str,
    target_root: str,
    overwrite: bool = False,
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    첫 바이트를 디스크에 쓰기 전에 ZIP·TAR 아카이브의 모든 엔트리와 대상 폴더를 전수 검사합니다.
    검증 항목:
      1. 아카이브 형식 판별 (.zip / .tar 계열)
      2. 모든 엔트리의 경로 안전성 (.., 드라이브, 절대/루트, UNC, NTFS ADS, 예약어, 끝 공백/점)
      3. 아카이브 내 심볼릭/하드 링크·Junction/Reparse·특수 파일 차단
      4. 아카이브 내부 대소문자 무시 중복 파일(`a.txt` vs `A.TXT`) 및 파일↔폴더 충돌 차단
      5. 대상 폴더 내 기존 심볼릭 링크/Junction 차단 및 기존 파일/폴더 충돌 차단(`overwrite=False`)
    """
    arc_norm = safe_norm_path(archive_path)
    if overwrite:
        raise ValueError("보안 정책상 기존 파일 덮어쓰기(overwrite=True) 경로는 제공하지 않습니다.")
    if not os.path.isfile(arc_norm):
        raise FileNotFoundError(f"압축 파일을 찾을 수 없습니다: {arc_norm}")
    if is_symlink_or_reparse_point(arc_norm):
        raise PermissionError(f"보안 차단: 심볼릭 링크 또는 Junction 압축 파일은 열 수 없습니다 ({arc_norm})")

    norm_target_root = safe_norm_path(target_root)
    _ensure_no_reparse_in_base_dir(norm_target_root)

    low_name = Path(arc_norm).name.lower()
    archive_kind = ""
    raw_entries: List[Dict[str, Any]] = []

    if low_name.endswith(".zip") or zipfile.is_zipfile(arc_norm):
        archive_kind = "zip"
        with zipfile.ZipFile(arc_norm, "r") as zf:
            for idx, info in enumerate(zf.infolist()):
                decoded_name = decode_zip_filename(info)
                _check_zip_member_not_link_or_special(info, decoded_name)
                is_dir = decoded_name.endswith(("/", "\\")) or info.is_dir()
                raw_entries.append({
                    "index": idx,
                    "raw_name": decoded_name,
                    "is_dir": is_dir,
                    "zip_info": info,
                })
    elif tarfile.is_tarfile(arc_norm) or low_name.endswith(
        (".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz", ".txz")
    ):
        archive_kind = "tar"
        with tarfile.open(arc_norm, "r:*") as tf:
            for idx, member in enumerate(tf.getmembers()):
                _check_tar_member_not_link_or_special(member)
                raw_entries.append({
                    "index": idx,
                    "raw_name": member.name,
                    "is_dir": member.isdir(),
                    "tar_member_name": member.name,
                })
    else:
        raise ValueError(
            "지원하지 않는 압축 형식이거나 손상된 아카이브입니다 (보안을 위해 외부 추출기 실행이 비활성화됨)."
        )

    seen_files_ci: Dict[str, str] = {}
    seen_dirs_ci: Dict[str, str] = {}
    validated_plan: List[Dict[str, Any]] = []

    for entry in raw_entries:
        raw_name = str(entry["raw_name"])
        target_abs, segments, is_dir_syntax = validate_archive_member_path(norm_target_root, raw_name)
        is_dir = bool(entry["is_dir"] or is_dir_syntax)
        rel_norm = "/".join(segments)
        rel_ci = rel_norm.casefold()

        # 아카이브 내부 상위 디렉터리 프리픽스 충돌 검사
        for depth in range(1, len(segments)):
            prefix_rel = "/".join(segments[:depth])
            prefix_ci = prefix_rel.casefold()
            if prefix_ci in seen_files_ci:
                raise FileExistsError(
                    f"압축 항목 충돌 차단: 파일('{seen_files_ci[prefix_ci]}')과 하위 폴더 경로('{raw_name}')가 충돌합니다."
                )
            seen_dirs_ci.setdefault(prefix_ci, prefix_rel)

        if is_dir:
            if rel_ci in seen_files_ci:
                raise FileExistsError(
                    f"압축 항목 충돌 차단: 파일('{seen_files_ci[rel_ci]}')과 폴더('{raw_name}') 이름이 중복됩니다."
                )
            seen_dirs_ci.setdefault(rel_ci, raw_name)
        else:
            if rel_ci in seen_files_ci:
                raise FileExistsError(
                    f"보안/무결성 차단: 압축 파일 내 대소문자 중복 항목이 존재합니다 ('{seen_files_ci[rel_ci]}' vs '{raw_name}')"
                )
            if rel_ci in seen_dirs_ci:
                raise FileExistsError(
                    f"압축 항목 충돌 차단: 폴더('{seen_dirs_ci[rel_ci]}')와 파일('{raw_name}') 이름이 중복됩니다."
                )
            seen_files_ci[rel_ci] = raw_name

        # 대상 파일시스템 기존 항목(대소문자 무시 포함) 충돌 검사
        curr_fs_dir = norm_target_root
        for depth, seg in enumerate(segments):
            is_last = depth == len(segments) - 1
            existing_match = _find_case_insensitive_existing(curr_fs_dir, seg)
            if existing_match is not None:
                if is_symlink_or_reparse_point(existing_match):
                    raise PermissionError(
                        f"보안 차단: 대상 경로에 심볼릭 링크 또는 Junction(Reparse Point)이 존재합니다 ({existing_match})"
                    )
                if not overwrite:
                    raise FileExistsError(
                        f"기존 파일/폴더 보호(덮어쓰기 금지): 대상에 이미 '{existing_match}' 항목이 존재합니다."
                    )
                if not is_last and not os.path.isdir(existing_match):
                    raise FileExistsError(
                        f"경로 충돌 차단: 대상의 기존 파일('{existing_match}') 위에 하위 폴더를 생성할 수 없습니다."
                    )
                if is_last:
                    if is_dir and not os.path.isdir(existing_match):
                        raise FileExistsError(
                            f"경로 충돌 차단: 대상의 기존 파일('{existing_match}')과 압축 폴더('{raw_name}')가 충돌합니다."
                        )
                    if (not is_dir) and os.path.isdir(existing_match):
                        raise FileExistsError(
                            f"경로 충돌 차단: 대상의 기존 폴더('{existing_match}')와 압축 파일('{raw_name}')이 충돌합니다."
                        )
                curr_fs_dir = existing_match
            else:
                curr_fs_dir = os.path.join(curr_fs_dir, seg)

        validated_plan.append({
            **entry,
            "is_dir": is_dir,
            "segments": segments,
            "rel_norm": rel_norm,
            "target_abs": target_abs,
        })

    return archive_kind, validated_plan


def _assert_tree_contains_no_reparse_or_links(root_dir: str) -> None:
    """원본 또는 스테이징 트리를 순회하며 심볼릭 링크나 Junction(Reparse Point)이 없는지 검증합니다."""
    norm_r = safe_norm_path(root_dir)
    if is_symlink_or_reparse_point(norm_r):
        raise PermissionError(f"보안 차단: 루트 경로가 심볼릭 링크 또는 Junction입니다 ({norm_r})")
    if not os.path.isdir(norm_r):
        return
    for cur_root, dirs, files in os.walk(norm_r, followlinks=False):
        if is_symlink_or_reparse_point(cur_root):
            raise PermissionError(f"보안 차단: 하위 경로에 심볼릭 링크 또는 Junction이 포함되어 있습니다 ({cur_root})")
        for name in list(dirs) + list(files):
            full_p = os.path.join(cur_root, name)
            if is_symlink_or_reparse_point(full_p):
                raise PermissionError(
                    f"보안 차단: 경로 내부에 심볼릭 링크 또는 Junction(Reparse Point)이 포함되어 있습니다 ({full_p})"
                )


def compress_items_to_archive(
    src_paths: List[str],
    output_archive_path: str,
    archive_format: str = "zip",
    overwrite: bool = False,
) -> Tuple[bool, str, int]:
    """
    선택한 파일 및 디렉토리(하위 폴더 및 빈 폴더 포함)를 .zip, .tar.gz, .tar 포맷으로 압축합니다.
    - 기본값(overwrite=False)으로 기존 아카이브 파일을 절대 삭제하거나 덮어쓰지 않습니다.
    - 원본 항목에 심볼릭 링크/Junction이 있으면 사전 차단합니다.
    - 전용 임시 파일에 먼저 생성·검증한 뒤 최종 경로로 반영합니다.
    반환값: (성공 여부, 생성된 압축파일 경로 또는 오류 메시지, 압축된 항목 수)
    """
    if overwrite:
        return False, "보안 정책상 기존 아카이브 덮어쓰기(overwrite=True) 경로는 제공하지 않습니다.", 0
    if not src_paths:
        return False, "압축할 원본 파일이나 폴더가 지정되지 않았습니다.", 0

    valid_srcs: List[str] = []
    seen_top_names_ci: Set[str] = set()
    for raw_p in src_paths:
        norm_p = safe_norm_path(raw_p)
        if not norm_p or not os.path.lexists(norm_p):
            return False, f"압축할 원본 경로가 존재하지 않습니다: {raw_p}", 0
        try:
            _ensure_no_reparse_in_base_dir(norm_p)
            _assert_tree_contains_no_reparse_or_links(norm_p)
        except Exception as exc:
            return False, f"압축 보안 차단: {exc}", 0
        top_ci = Path(norm_p).name.casefold()
        if top_ci in seen_top_names_ci:
            return False, f"압축 차단: 대소문자를 무시했을 때 동일한 이름의 원본 항목이 중복 선택되었습니다 ({Path(norm_p).name})", 0
        seen_top_names_ci.add(top_ci)
        valid_srcs.append(norm_p)

    out_norm = safe_norm_path(output_archive_path)
    fmt = archive_format.lower().strip(".")
    if fmt == "zip" and not out_norm.lower().endswith(".zip"):
        out_norm += ".zip"
    elif fmt in ("tar.gz", "tgz") and not out_norm.lower().endswith((".tar.gz", ".tgz")):
        out_norm += ".tar.gz"
    elif fmt == "tar" and not out_norm.lower().endswith(".tar"):
        out_norm += ".tar"

    out_parent = safe_norm_path(os.path.dirname(out_norm))
    out_filename = Path(out_norm).name
    try:
        _validate_segment_security(out_filename, out_norm)
        if os.path.lexists(out_parent):
            _ensure_no_reparse_in_base_dir(out_parent)
    except Exception as exc:
        return False, f"압축 대상 경로 오류: {exc}", 0

    existing_archive = _find_case_insensitive_existing(out_parent, out_filename)
    if existing_archive is not None or os.path.lexists(out_norm):
        target_disp = existing_archive or out_norm
        if not overwrite:
            return (
                False,
                f"기존 아카이브 보호(덮어쓰기 금지): 대상 경로에 이미 '{target_disp}' 파일/폴더가 존재합니다.",
                0,
            )
        if os.path.isdir(target_disp) or is_symlink_or_reparse_point(target_disp):
            return False, f"압축 오류: 대상 경로('{target_disp}')가 폴더이거나 링크여서 덮어쓸 수 없습니다.", 0

    os.makedirs(out_parent, exist_ok=True)
    fd, tmp_archive = tempfile.mkstemp(prefix=".qdir_arc_stage_", suffix=".tmp", dir=out_parent)
    os.close(fd)
    item_count = 0

    try:
        if fmt == "zip":
            with zipfile.ZipFile(tmp_archive, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
                for src in valid_srcs:
                    src_p = Path(src)
                    base_name = src_p.name
                    if src_p.is_file():
                        zf.write(src, arcname=base_name)
                        item_count += 1
                    elif src_p.is_dir():
                        wrote_any = False
                        for root, dirs, files in os.walk(src, followlinks=False):
                            rel_root = os.path.relpath(root, src_p.parent).replace("\\", "/")
                            if not dirs and not files:
                                zinfo = zipfile.ZipInfo(rel_root.rstrip("/") + "/")
                                zinfo.external_attr = (stat.S_IFDIR | 0o755) << 16
                                zinfo.flag_bits |= 0x800
                                zf.writestr(zinfo, b"")
                                item_count += 1
                                wrote_any = True
                            for f_name in files:
                                full_f = os.path.join(root, f_name)
                                if safe_norm_path(full_f).casefold() in (
                                    out_norm.casefold(),
                                    safe_norm_path(tmp_archive).casefold(),
                                ):
                                    continue
                                arc_rel = os.path.relpath(full_f, src_p.parent).replace("\\", "/")
                                zf.write(full_f, arcname=arc_rel)
                                item_count += 1
                                wrote_any = True
                        if not wrote_any:
                            zinfo = zipfile.ZipInfo(base_name.rstrip("/") + "/")
                            zinfo.external_attr = (stat.S_IFDIR | 0o755) << 16
                            zinfo.flag_bits |= 0x800
                            zf.writestr(zinfo, b"")
                            item_count += 1
        else:
            mode_w = "w:gz" if fmt in ("tar.gz", "tgz") else "w"
            with tarfile.open(tmp_archive, mode_w) as tf:
                for src in valid_srcs:
                    src_p = Path(src)
                    tf.add(src, arcname=src_p.name, recursive=True)
                    item_count += 1

        # 커밋 직전 기존 아카이브 존재 여부 재확인 (동시 충돌 방어, 기존 파일 삭제 절대 금지)
        race_existing = _find_case_insensitive_existing(out_parent, out_filename)
        if (race_existing is not None or os.path.lexists(out_norm)) and not overwrite:
            try:
                os.unlink(tmp_archive)
            except Exception:
                pass
            return (
                False,
                f"기존 아카이브 보호(동시 충돌 차단): '{race_existing or out_norm}' 파일이 이미 존재하여 보존했습니다.",
                0,
            )

        try:
            _publish_file_no_overwrite(tmp_archive, out_norm)
        except FileExistsError:
            if os.path.lexists(tmp_archive):
                try:
                    os.unlink(tmp_archive)
                except Exception:
                    pass
            return False, f"기존 아카이브 보호: '{out_norm}' 파일이 이미 존재합니다.", 0

        return True, out_norm, item_count
    except Exception as exc:
        if os.path.exists(tmp_archive):
            try:
                os.unlink(tmp_archive)
            except Exception:
                pass
        return False, f"압축 중 오류가 발생했습니다: {exc}", 0


def _write_stream_exclusive(src_stream: Any, dst_path: str) -> None:
    """스테이징 폴더 내부에 파일을 독점 생성(O_CREAT | O_EXCL) 모드로 안전하게 기록합니다."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    fd = os.open(dst_path, flags, 0o644)
    try:
        with os.fdopen(fd, "wb") as dst_f:
            shutil.copyfileobj(src_stream, dst_f)
    except Exception:
        try:
            os.unlink(dst_path)
        except Exception:
            pass
        raise


NodeIdentity = Tuple[int, int, int, int]
CommittedRecord = Tuple[str, str, Optional[NodeIdentity]]


def _supports_non_overwriting_rename() -> bool:
    """현재 OS의 os.rename이 기존 대상 존재 시 덮어쓰지 않고 실패(FileExistsError)하는지 반환합니다."""
    return os.name == "nt" or platform.system() == "Windows"


if os.name == "nt":
    from ctypes import wintypes as _wintypes

    class _WIN32_FILETIME(ctypes.Structure):
        _fields_ = [("dwLowDateTime", _wintypes.DWORD), ("dwHighDateTime", _wintypes.DWORD)]

    class _BY_HANDLE_FILE_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("dwFileAttributes", _wintypes.DWORD),
            ("ftCreationTime", _WIN32_FILETIME),
            ("ftLastAccessTime", _WIN32_FILETIME),
            ("ftLastWriteTime", _WIN32_FILETIME),
            ("dwVolumeSerialNumber", _wintypes.DWORD),
            ("nFileSizeHigh", _wintypes.DWORD),
            ("nFileSizeLow", _wintypes.DWORD),
            ("nNumberOfLinks", _wintypes.DWORD),
            ("nFileIndexHigh", _wintypes.DWORD),
            ("nFileIndexLow", _wintypes.DWORD),
        ]

    class _FILE_DISPOSITION_INFO(ctypes.Structure):
        _fields_ = [("DeleteFile", _wintypes.BOOLEAN)]

    class _FILE_DISPOSITION_INFO_EX(ctypes.Structure):
        _fields_ = [("Flags", _wintypes.DWORD)]

    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _k32.CreateFileW.argtypes = [
        _wintypes.LPCWSTR, _wintypes.DWORD, _wintypes.DWORD, _wintypes.LPVOID,
        _wintypes.DWORD, _wintypes.DWORD, _wintypes.HANDLE,
    ]
    _k32.CreateFileW.restype = _wintypes.HANDLE
    _k32.GetFileInformationByHandle.argtypes = [
        _wintypes.HANDLE, ctypes.POINTER(_BY_HANDLE_FILE_INFORMATION),
    ]
    _k32.GetFileInformationByHandle.restype = _wintypes.BOOL
    _k32.SetFileInformationByHandle.argtypes = [
        _wintypes.HANDLE, ctypes.c_int, _wintypes.LPVOID, _wintypes.DWORD,
    ]
    _k32.SetFileInformationByHandle.restype = _wintypes.BOOL
    _k32.CloseHandle.argtypes = [_wintypes.HANDLE]
    _k32.CloseHandle.restype = _wintypes.BOOL
    _INVALID_HANDLE_VALUES = (None, 0, -1, ctypes.c_void_p(-1).value)


def _stat_identity(path_str: str) -> Optional[NodeIdentity]:
    """파일/폴더의 (st_dev, st_ino, st_size, st_mtime_ns) 고유 식별자를 핸들/lstat으로 반환합니다."""
    if os.name == "nt":
        try:
            # FILE_READ_ATTRIBUTES(0x80), SHARE_ALL(0x7), OPEN_EXISTING(3), OPEN_REPARSE|BACKUP_SEMANTICS(0x02200000)
            h = _k32.CreateFileW(path_str, 0x0080, 0x07, None, 3, 0x02200000, None)
            if h not in _INVALID_HANDLE_VALUES:
                try:
                    info = _BY_HANDLE_FILE_INFORMATION()
                    if _k32.GetFileInformationByHandle(h, ctypes.byref(info)):
                        if info.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT:
                            return None
                        vol = int(info.dwVolumeSerialNumber)
                        ino = (int(info.nFileIndexHigh) << 32) | int(info.nFileIndexLow)
                        sz = (int(info.nFileSizeHigh) << 32) | int(info.nFileSizeLow)
                        mt = (int(info.ftLastWriteTime.dwHighDateTime) << 32) | int(info.ftLastWriteTime.dwLowDateTime)
                        return (vol, ino, sz, mt)
                finally:
                    _k32.CloseHandle(h)
        except Exception:
            pass
    try:
        st = os.lstat(path_str)
        if stat.S_ISLNK(st.st_mode) or (getattr(st, "st_file_attributes", 0) & FILE_ATTRIBUTE_REPARSE_POINT):
            return None
        mtime_ns = int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000)))
        return (int(st.st_dev), int(st.st_ino), int(st.st_size), mtime_ns)
    except OSError:
        return None


def _same_identity(
    id_a: Optional[NodeIdentity],
    id_b: Optional[NodeIdentity],
    is_dir: bool = False,
) -> bool:
    """두 파일/디렉터리 식별자가 동일한 커널 객체인지 판별합니다."""
    if id_a is None or id_b is None:
        return False
    if id_a[1] != 0 and id_b[1] != 0:
        if is_dir:
            return (id_a[0], id_a[1]) == (id_b[0], id_b[1])
        return id_a == id_b
    return id_a == id_b


def _delete_by_verified_handle(
    path_str: str,
    expected_id: Optional[NodeIdentity],
    is_dir: bool = False,
) -> bool:
    """
    검사 후 이름만으로 삭제(lstat -> unlink/rmdir)하는 TOCTOU 경합을 제거하기 위해:
    - Windows: DELETE 권한과 FILE_FLAG_OPEN_REPARSE_POINT로 커널 핸들을 연 뒤,
      그 열린 핸들에서 직접 GetFileInformationByHandle로 게시 전 스테이징 ID(expected_id)와 일치하는지 검증하고,
      일치할 때만 SetFileInformationByHandle(FileDispositionInfoEx/FileDispositionInfo)로 열린 핸들 자체를 삭제합니다.
    - POSIX: O_NOFOLLOW로 파일 디스크립터를 먼저 열어 fstat이 expected_id와 일치하는지 검증한 뒤 삭제합니다.
    """
    if not path_str or expected_id is None:
        return False

    if os.name == "nt":
        try:
            # DELETE(0x00010000) | FILE_READ_ATTRIBUTES(0x0080) = 0x00010080
            h = _k32.CreateFileW(path_str, 0x00010080, 0x07, None, 3, 0x02200000, None)
            if h in _INVALID_HANDLE_VALUES:
                return False
            try:
                info = _BY_HANDLE_FILE_INFORMATION()
                if not _k32.GetFileInformationByHandle(h, ctypes.byref(info)):
                    return False
                if info.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT:
                    return False
                actual_is_dir = bool(info.dwFileAttributes & 0x0010)
                if actual_is_dir != is_dir:
                    return False
                curr_id: NodeIdentity = (
                    int(info.dwVolumeSerialNumber),
                    (int(info.nFileIndexHigh) << 32) | int(info.nFileIndexLow),
                    (int(info.nFileSizeHigh) << 32) | int(info.nFileSizeLow),
                    (int(info.ftLastWriteTime.dwHighDateTime) << 32) | int(info.ftLastWriteTime.dwLowDateTime),
                )
                if not _same_identity(curr_id, expected_id, is_dir=is_dir):
                    return False
                # FileDispositionInfoEx (Class=21, DELETE|POSIX_SEMANTICS=0x3) 우선 시도 후 FileDispositionInfo(Class=4) 폴백
                disp_ex = _FILE_DISPOSITION_INFO_EX(0x00000003)
                if _k32.SetFileInformationByHandle(h, 21, ctypes.byref(disp_ex), ctypes.sizeof(disp_ex)):
                    return True
                disp_std = _FILE_DISPOSITION_INFO(1)
                if _k32.SetFileInformationByHandle(h, 4, ctypes.byref(disp_std), ctypes.sizeof(disp_std)):
                    return True
                return False
            finally:
                _k32.CloseHandle(h)
        except Exception:
            return False

    # POSIX: O_NOFOLLOW로 fd를 먼저 열어 fstat으로 게시 전 스테이징 ID 검증
    fd = -1
    try:
        open_flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        if is_dir and hasattr(os, "O_DIRECTORY"):
            open_flags |= os.O_DIRECTORY
        fd = os.open(path_str, open_flags)
        st_fd = os.fstat(fd)
        if stat.S_ISLNK(st_fd.st_mode) or (stat.S_ISDIR(st_fd.st_mode) != is_dir):
            return False
        curr_fd_id: NodeIdentity = (
            int(st_fd.st_dev),
            int(st_fd.st_ino),
            int(st_fd.st_size),
            int(getattr(st_fd, "st_mtime_ns", int(st_fd.st_mtime * 1_000_000_000))),
        )
        if not _same_identity(curr_fd_id, expected_id, is_dir=is_dir):
            return False
        st_path = os.lstat(path_str)
        if (int(st_path.st_dev), int(st_path.st_ino)) != (curr_fd_id[0], curr_fd_id[1]):
            return False
        fd_recheck = os.open(path_str, open_flags)
        try:
            st_fd2 = os.fstat(fd_recheck)
            if (int(st_fd2.st_dev), int(st_fd2.st_ino)) != (curr_fd_id[0], curr_fd_id[1]):
                return False
        finally:
            os.close(fd_recheck)
        if is_dir:
            os.rmdir(path_str)
        else:
            os.unlink(path_str)
        return True
    except OSError:
        return False
    finally:
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass


def _safe_unlink_if_same_file(path_str: str, expected_id: Optional[NodeIdentity]) -> bool:
    """게시 전 스테이징 ID(expected_id)가 열린 핸들의 파일과 일치할 때만 안전하게 제거합니다."""
    return _delete_by_verified_handle(path_str, expected_id, is_dir=False)


def _safe_rmdir_if_same_dir(path_str: str, expected_id: Optional[NodeIdentity]) -> bool:
    """게시 전 스테이징 ID(expected_id)가 열린 핸들의 빈 폴더와 일치할 때만 안전하게 제거합니다."""
    return _delete_by_verified_handle(path_str, expected_id, is_dir=True)


def _publish_file_no_overwrite(src_file: str, dst_file: str) -> NodeIdentity:
    """
    overwrite=False 전용 파일 게시 함수 (os.replace 및 게시 후 대상 ID 재조회 절대 금지):
    - 항상 게시 전 스테이징 파일의 고유 식별자(src_id)만 반환하여, 게시 직후 다른 작성자가
      같은 이름의 파일을 삭제·교체하더라도 다른 작성자의 파일 ID가 우리 소유로 기록되지 않게 보장합니다.
    """
    parent_dir = os.path.dirname(dst_file)
    base_name = os.path.basename(dst_file)
    existing_ci = _find_case_insensitive_existing(parent_dir, base_name)
    if existing_ci is not None or os.path.lexists(dst_file):
        raise FileExistsError(f"기존 파일 보호(동시 충돌 차단): '{existing_ci or dst_file}' 항목이 이미 존재합니다.")

    # 반드시 게시(link/rename) 전에 스테이징 원본에서 식별자를 확보하고 이를 그대로 반환
    src_id = _stat_identity(src_file)
    if src_id is None:
        raise FileNotFoundError(f"스테이징 원본 파일을 찾을 수 없습니다: {src_file}")

    linked = False
    link_exc: Optional[OSError] = None
    try:
        os.link(src_file, dst_file)
        linked = True
    except FileExistsError as exc:
        raise FileExistsError(f"기존 파일 보호(동시 충돌 차단): '{dst_file}' 파일이 이미 존재합니다.") from exc
    except OSError as exc:
        link_exc = exc

    if linked:
        try:
            os.unlink(src_file)
        except OSError as unlink_exc:
            _safe_unlink_if_same_file(dst_file, src_id)
            raise RuntimeError(
                f"스테이징 파일 정리(unlink) 실패로 게시를 중단하고 롤백했습니다: {unlink_exc}"
            ) from unlink_exc
        return src_id

    if not _supports_non_overwriting_rename():
        raise RuntimeError(
            f"하드링크를 지원하지 않으며 비덮어쓰기 rename을 보장할 수 없어 게시를 중단합니다: {link_exc}"
        ) from link_exc

    existing_ci = _find_case_insensitive_existing(parent_dir, base_name)
    if existing_ci is not None or os.path.lexists(dst_file):
        raise FileExistsError(f"기존 파일 보호(동시 충돌 차단): '{existing_ci or dst_file}' 파일이 이미 존재합니다.")

    os.rename(src_file, dst_file)
    return src_id


def _snapshot_tree_records(src_dir: str, dst_dir: str) -> List[CommittedRecord]:
    """디렉터리 rename 전에 스테이징 내부 디렉터리/파일의 고유 식별자(prev_id)와 목표 경로를 기록합니다."""
    records: List[CommittedRecord] = []
    root_id = _stat_identity(src_dir)
    if root_id is None:
        raise FileNotFoundError(f"스테이징 디렉터리를 찾을 수 없습니다: {src_dir}")
    records.append(("dir", dst_dir, root_id))
    for cur_root, dirs, files in os.walk(src_dir, topdown=True, followlinks=False):
        rel_root = os.path.relpath(cur_root, src_dir)
        target_cur = dst_dir if rel_root == "." else os.path.join(dst_dir, rel_root)
        for d_name in dirs:
            s_d = os.path.join(cur_root, d_name)
            t_d = os.path.join(target_cur, d_name)
            records.append(("dir", t_d, _stat_identity(s_d)))
        for f_name in files:
            s_f = os.path.join(cur_root, f_name)
            t_f = os.path.join(target_cur, f_name)
            records.append(("file", t_f, _stat_identity(s_f)))
    return records


def _publish_dir_no_overwrite(
    src_dir: str,
    dst_dir: str,
    committed_records: List[CommittedRecord],
) -> None:
    """
    overwrite=False 전용 새 폴더 게시 함수 (os.replace, 공유 폴더 병합, 게시 후 대상 ID 재조회 절대 금지):
    - 게시 전 스테이징 트리에서 확보한 식별자(pre_records)만 기록하며, 게시 후 대상 경로에서 ID를 다시 읽지 않습니다.
    """
    parent_dir = os.path.dirname(dst_dir)
    base_name = os.path.basename(dst_dir)
    existing_ci = _find_case_insensitive_existing(parent_dir, base_name)
    if existing_ci is not None or os.path.lexists(dst_dir):
        raise FileExistsError(
            f"기존 폴더/파일 보호(공유 폴더 병합 금지): '{existing_ci or dst_dir}' 항목이 이미 존재합니다."
        )

    if _supports_non_overwriting_rename():
        pre_records = _snapshot_tree_records(src_dir, dst_dir)
        os.rename(src_dir, dst_dir)
        committed_records.extend(pre_records)
        return

    # 비Windows(POSIX): os.mkdir 독점 생성 직후 O_NOFOLLOW fd로 디렉터리 ID 확보
    os.mkdir(dst_dir, 0o755)
    committed_records.append(("dir", dst_dir, _stat_identity(dst_dir)))
    for entry_name in sorted(os.listdir(src_dir)):
        s_child = os.path.join(src_dir, entry_name)
        d_child = os.path.join(dst_dir, entry_name)
        if os.path.isdir(s_child) and not is_symlink_or_reparse_point(s_child):
            _publish_dir_no_overwrite(s_child, d_child, committed_records)
        else:
            f_id = _publish_file_no_overwrite(s_child, d_child)
            committed_records.append(("file", d_child, f_id))


def _rollback_committed_records(committed_records: List[CommittedRecord]) -> None:
    """
    트랜잭션 롤백: 게시 전 스테이징에서 기록한 고유 식별자(rec_id)를 열린 핸들에서 직접 검증하여
    일치하는 파일과 빈 디렉터리만 핸들 기반으로 제거합니다(경로 이름 기반 삭제 경합 원천 차단).
    """
    for kind, abs_p, rec_id in reversed(committed_records):
        if kind == "file":
            _safe_unlink_if_same_file(abs_p, rec_id)

    dir_records = [r for r in committed_records if r[0] == "dir"]
    dir_records.sort(key=lambda r: len(Path(r[1]).parts), reverse=True)
    for _, abs_d, rec_id in dir_records:
        _safe_rmdir_if_same_dir(abs_d, rec_id)


def extract_archive_smart(
    archive_path: str,
    dest_dir: str,
    create_subfolder: bool = False,
    overwrite: bool = False,
    atomic_subfolder_only: bool = False,
) -> Tuple[bool, str, int]:
    """
    .zip, .tar, .tar.gz, .tgz, .tar.bz2, .tar.xz 압축 파일을 안전하게 해제합니다.
    [v3.1 핵심 보안·무결성 정책]
    1. 첫 쓰기 전 전수 검사(`inspect_archive_entries`):
       - `..`, 드라이브 문자, 절대/루트 경로, UNC, NTFS ADS(`:`), 예약 파일명, 끝 공백/점,
         심볼릭/하드 링크·Junction/Reparse, 대소문자 중복 및 대상 기존 파일/폴더 충돌을 사전 차단합니다.
       - 외부 추출기(`7z`, `tar`) CLI 폴백은 검증 우회 방지를 위해 비활성화되었습니다.
    2. 기본 덮어쓰기 금지(`overwrite=False`) 및 전용 임시 스테이징 폴더 추출 후 원자적 반영:
       - 먼저 전용 스테이징 폴더에 전체 항목을 풀고 검증한 뒤 대상 폴더에 반영합니다.
       - 추출 실패나 동시 충돌 시 기존 대상 파일(`existing.txt`)은 100% 보존되며 부분 반입 파일이 남지 않습니다.
    반환값: (성공 여부, 압축 해제된 대상 폴더 경로 또는 오류 메시지, 해제된 파일 수)
    """
    if overwrite:
        return False, "압축 해제 실패: 보안 정책상 기존 파일 덮어쓰기(overwrite=True) 경로는 제공하지 않습니다.", 0
    arc_norm = safe_norm_path(archive_path)
    if not os.path.isfile(arc_norm):
        return False, f"압축 파일을 찾을 수 없습니다: {arc_norm}", 0

    dest_base = safe_norm_path(dest_dir)
    if not dest_base:
        return False, "대상 폴더 경로가 비어 있습니다.", 0

    try:
        _ensure_no_reparse_in_base_dir(dest_base)
    except Exception as exc:
        return False, f"압축 해제 실패: {exc}", 0

    if create_subfolder:
        sub_name = strip_archive_stem(arc_norm).rstrip(" .") or "extracted"
        try:
            _validate_segment_security(sub_name, sub_name)
        except Exception as exc:
            return False, f"압축 해제 실패: {exc}", 0
        existing_sub = _find_case_insensitive_existing(dest_base, sub_name)
        if existing_sub is not None:
            if is_symlink_or_reparse_point(existing_sub):
                return (
                    False,
                    f"압축 해제 실패: 보안 차단 - 대상 하위 경로가 링크/Junction입니다 ({existing_sub})",
                    0,
                )
            if not overwrite:
                return (
                    False,
                    f"압축 해제 실패: 기존 폴더/파일 보호(덮어쓰기 금지) - '{existing_sub}' 항목이 이미 존재합니다.",
                    0,
                )
        target_root = safe_norm_path(os.path.join(dest_base, sub_name))
    else:
        target_root = dest_base

    # 1단계: 첫 쓰기 전 전수 검사 (이 단계에서는 디스크에 어떠한 폴더나 파일도 쓰지 않음)
    try:
        archive_kind, plan = inspect_archive_entries(arc_norm, target_root, overwrite=overwrite)
    except Exception as exc:
        return False, f"압축 해제 실패: {exc}", 0

    # 2단계: 전용 임시 스테이징 디렉터리에 전체 추출 및 무결성 검증
    stage_parent_base = dest_base if os.path.isdir(dest_base) else os.path.dirname(dest_base)
    try:
        os.makedirs(stage_parent_base, exist_ok=True)
        _ensure_no_reparse_in_base_dir(stage_parent_base)
    except Exception as exc:
        return False, f"압축 해제 실패: {exc}", 0

    staging_dir = tempfile.mkdtemp(prefix=".qdir_extract_stage_", dir=stage_parent_base)
    extracted_count = 0

    try:
        if archive_kind == "zip":
            with zipfile.ZipFile(arc_norm, "r") as zf:
                for item in plan:
                    segs: List[str] = item["segments"]
                    stage_target = safe_norm_path(os.path.join(staging_dir, *segs))
                    if os.path.commonpath([staging_dir, stage_target]).casefold() != staging_dir.casefold():
                        raise PermissionError(f"보안 차단: 스테이징 경로 이탈 감지 ({item['raw_name']})")
                    if item["is_dir"]:
                        os.makedirs(stage_target, exist_ok=True)
                        continue
                    os.makedirs(os.path.dirname(stage_target), exist_ok=True)
                    zinfo: zipfile.ZipInfo = item["zip_info"]
                    with zf.open(zinfo, "r") as src_f:
                        _write_stream_exclusive(src_f, stage_target)
                    extracted_count += 1
        elif archive_kind == "tar":
            with tarfile.open(arc_norm, "r:*") as tf:
                members = tf.getmembers()
                for item in plan:
                    segs = item["segments"]
                    stage_target = safe_norm_path(os.path.join(staging_dir, *segs))
                    if os.path.commonpath([staging_dir, stage_target]).casefold() != staging_dir.casefold():
                        raise PermissionError(f"보안 차단: 스테이징 경로 이탈 감지 ({item['raw_name']})")
                    if item["is_dir"]:
                        os.makedirs(stage_target, exist_ok=True)
                        continue
                    os.makedirs(os.path.dirname(stage_target), exist_ok=True)
                    member = members[int(item["index"])]
                    src_f = tf.extractfile(member)
                    if src_f is None:
                        raise IOError(f"TAR 항목 스트림을 읽을 수 없습니다: {item['raw_name']}")
                    with src_f:
                        _write_stream_exclusive(src_f, stage_target)
                    extracted_count += 1

        # 스테이징 트리 전체에 링크/Junction이 없는지 사후 검증
        _assert_tree_contains_no_reparse_or_links(staging_dir)

        # 3단계: 원자적/트랜잭션 반영 (동시 충돌 시 100% 롤백)
        _ensure_no_reparse_in_base_dir(dest_base)

        committed_records: List[CommittedRecord] = []
        if create_subfolder or not os.path.lexists(target_root):
            parent_of_target = os.path.dirname(target_root)
            os.makedirs(parent_of_target, exist_ok=True)
            _ensure_no_reparse_in_base_dir(parent_of_target)
            try:
                _publish_dir_no_overwrite(staging_dir, target_root, committed_records)
            except Exception:
                _rollback_committed_records(committed_records)
                raise
            return True, target_root, extracted_count

        if atomic_subfolder_only and not overwrite:
            raise FileExistsError(
                f"원자적 전용 새 폴더 게시 모드: 대상 폴더('{target_root}')가 이미 존재하여 공유 폴더 반입을 거부합니다."
            )
        if not os.path.isdir(target_root) or is_symlink_or_reparse_point(target_root):
            raise PermissionError(f"보안/충돌 차단: 대상 경로가 유효한 일반 폴더가 아닙니다 ({target_root})")
        _ensure_no_reparse_in_base_dir(target_root)

        top_names = sorted(os.listdir(staging_dir))
        # 커밋 직전 모든 최상위 항목에 대해 동시 충돌 및 링크 재검사
        for top_name in top_names:
            existing_top = _find_case_insensitive_existing(target_root, top_name)
            if existing_top is not None:
                if is_symlink_or_reparse_point(existing_top):
                    raise PermissionError(
                        f"보안 차단: 대상 경로에 링크/Junction이 감지되었습니다 ({existing_top})"
                    )
                if not overwrite:
                    raise FileExistsError(
                        f"기존 파일/폴더 보호(동시 충돌 및 공유 폴더 병합 차단): '{existing_top}' 항목이 이미 존재합니다."
                    )

        try:
            for top_name in top_names:
                src_top = os.path.join(staging_dir, top_name)
                dst_top = os.path.join(target_root, top_name)
                existing_top = _find_case_insensitive_existing(target_root, top_name)
                if existing_top is not None and not overwrite:
                    raise FileExistsError(
                        f"기존 파일/폴더 보호(동시 충돌 및 공유 폴더 병합 차단): '{existing_top}' 항목이 이미 존재합니다."
                    )
                if os.path.isdir(src_top) and not is_symlink_or_reparse_point(src_top):
                    _publish_dir_no_overwrite(src_top, dst_top, committed_records)
                else:
                    f_id = _publish_file_no_overwrite(src_top, dst_top)
                    committed_records.append(("file", dst_top, f_id))
        except Exception:
            _rollback_committed_records(committed_records)
            raise

        return True, target_root, extracted_count
    except Exception as exc:
        return False, f"압축 해제 실패: {exc}", 0
    finally:
        if os.path.exists(staging_dir):
            shutil.rmtree(staging_dir, ignore_errors=True)


def elide_middle_smart(text: str, max_visual_cols: int = 20) -> str:
    """한글(폭 2)과 영문/숫자(폭 1)의 시각적 폭을 계산해 확장자를 보존하며 가운데 말줄임을 수행합니다."""
    def _vlen(s: str) -> int:
        return sum(2 if ord(ch) > 127 else 1 for ch in s)

    if _vlen(text) <= max_visual_cols:
        return text
    keep_tail = min(6, max(3, len(text) // 3))
    tail = text[-keep_tail:]
    target_head = max(4, max_visual_cols - _vlen(tail) - 2)
    head_chars: List[str] = []
    acc = 0
    for ch in text:
        w = 2 if ord(ch) > 127 else 1
        if acc + w > target_head:
            break
        head_chars.append(ch)
        acc += w
    return f"{''.join(head_chars)}…{tail}"


def safe_norm_path(path_str: str) -> str:
    """
    Google Drive(G:) 등 가상 드라이브에서 `Path.resolve()` 호출 시 발생하는
    Reparse Point 우회 및 `\\\\?\\` 확장 경로 왜곡을 방지하고 안전하게 표준 경로를 반환합니다.
    """
    if not path_str:
        return ""
    s = str(path_str).strip()
    if s.startswith("\\\\?\\UNC\\"):
        s = "\\\\" + s[8:]
    elif s.startswith("\\\\?\\"):
        s = s[4:]
    return os.path.normpath(os.path.abspath(s))
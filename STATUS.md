# PyQuadDir Project Status

- **Project ID**: `pyquaddir`
- **Canonical Workspace Path**: `D:\workspace\projects\active\pyquaddir`
- **Desktop Shortcut**: `%USERPROFILE%\Desktop\PyQuadDir.lnk` -> `D:\workspace\projects\active\pyquaddir\dist\PyQuadDir.exe`
- **GitHub Repository**: `https://github.com/shinjaehyun20/PyQuadDir` (Public, MIT License)
- **Current Version**: `v3.1.0` (`2026-11-05`)
- **Status**: `ACTIVE / PRODUCTION`

## Summary of Capabilities (v3.1.0)
- **보안 및 트랜잭션 아카이브 코어 (archive_safe_core.py)**: `overwrite=True` 및 `os.replace` 전면 제거, 첫 바이트 쓰기 전 전수 검사(`inspect_archive_entries`: 상위 경로 탈출, 드라이브 문자, UNC, NTFS ADS, Windows 예약명, 끝 공백/점, 대소문자 중복, 심볼릭링크/Junction/Reparse 차단), 임시 스테이징 후 원자적(`os.rename`) 게시, 공유 쓰기 경합 시 게시 전 스테이징 식별자(`src_id`) 대조 커널 핸들 기반 롤백(`_delete_by_verified_handle`).
- **다크 모드 세부 정보 창 명암비 개선**: `InspectorPane` 내 `InspectorTitleLabel`, `InspectorMetaLabel`, `InspectorPreviewLabel` 오브젝트명 추가 및 고대비 팔레트(`#38BDF8` 다크 / `#1E3A8A` 라이트) 적용 (WCAG AA ≥ 4.5:1 준수).
- **좁은 패널 흰색 탭 바 제거 및 긴 한글 탭·주소창 가독성 확보**: 좁은 패널의 탭 바 배경을 다크 `#0F172A` / 라이트 `#E2E8F0`로 고정, `elide_middle_smart` 중간 생략으로 식별성 보존, 활성 탭 마커(`●`) 및 전체 경로 툴팁, 편집 가능한 주소창(`setReadOnly(False)`).
- **빈 영역 마우스 드래그 다중 선택 (QRubberBand)**: 패널 빈 영역 클릭 드래그 시 고무줄 사각형 선택(QRubberBand) 지원 (기존 파일 D&D 유지).
- **반응형 뷰포트 레이아웃 무손실 보존**: 360px 세로 / 780px 가로 모바일 뷰포트 전환 시에도 `preferred_desktop_layout`을 보존하여 프로그램 재실행 시 4분할 데스크톱 탭/세션 설정 보호.
- **Real-Time Session Restoration & Layout Lock (v2.5)**: Real-time dual-path session persistence (`~/.pyquaddir_config.json` & `.pyquaddir_session.json`) on every folder navigation/tab switch/exit with `resolve_restorable_dir()` parent fallback, `ElidedLabel` (`QSizePolicy.Ignored`) zero-jump layout stabilization, and 50:50 synchronized top/bottom quad splitters (`_on_top_splitter_moved` / `_on_bottom_splitter_moved`).
- **Triple-Engine Support**: Automatic `PySide6` / `PyQt6` detection with built-in `Tkinter (ttk)` zero-dependency fallback (`--tk`).
- **Virtual Drive (`G:`) Safe Path & Pre-Launch Diagnostics (v2.4)**: Removed `Path.resolve()` distortion via `safe_norm_path()`, added pre-launch magic header & cloud streaming diagnostics (`diagnose_file_health`), and local temp cache bypass execution (`copy_to_local_temp_cache`).
- **Built-in Universal `.xlsx` / `.html` / HEX Viewer (v2.4)**: Zero-dependency `.xlsx` sheet table parser (`parse_xlsx_preview_sheets`), HTML previewer, and smart encoding text reader (`read_text_file_smart`) plus `file:///` URL-encoded address bar navigation (`normalize_user_input_path`).
- **High-Visibility Vector Icon Command Bar (v2.2)**: Custom antialiased 20×20px Windows 11-style color vector icons rendered via `QPainter` (`create_ui_icon`) + full-width Favorites Bar (`⭐`).
- **`Ctrl + Mouse Wheel` Real-Time Zoom (v2.2)**: Smooth 8-stage view transition (`details` → `list` → `content` → `tiles` → `small_icons` → `medium_icons` → `large_icons` → `extra_large_icons` up to 220px).
- **Keyboard-First Navigation (v2.2)**: Full `Enter`/`Return` folder navigation & file execution and `Backspace` parent folder navigation across both `FileTableView` and `FileIconListView`.
- **Portfolio & Marketing Visual Showcase**: Privacy-safe (`Zero-PII`) Hero Banner (`assets/social-preview-banner.png`), animated action GIF (`assets/demo-quad-action.gif`), Dark/Light high-DPI screenshots (`assets/demo-dark.png`, `assets/demo-light.png`), and Mermaid 3-layer system architecture documentation.
- **Standalone Portable Build**: `build_exe.py` builds a standalone zero-install Windows executable (`dist/PyQuadDir.exe`).

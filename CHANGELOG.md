# PyQuadDir Changelog

All notable changes to the PyQuadDir project are documented in this file.

---

## [v3.1.1] - 2026-11-05

### Fixed
- Save detached session snapshots on Qt shutdown without reading deleted widgets.
- Restore saved window geometry; keep the supported minimum height at 420px.
- Keep long filenames readable in the Inspector and preserve pane state when closing it.
- Align Windows executable metadata and the application title with v3.1.1.

### Documentation
- Add direct Windows download, first-run steps and local-settings/privacy guidance.
- Make the Inspector regression fixture independent of a developer-specific path.

---

## [v3.1.0] - 2026-11-05

### Added
- **Safe Transactional Archive Core (`archive_safe_core.py`)**:
  - Pre-write full inspection (`inspect_archive_entries`) guarding against directory traversal (`..`), absolute/drive/UNC paths, NTFS Alternate Data Streams (`:`), Windows reserved device names (`CON`, `PRN`, `AUX`, `NUL`, `COM1-9`, `LPT1-9`), trailing dots/spaces, case-insensitive collisions, and symlink/junction escapes.
  - Zero-overwrite architecture: Completely eliminates `overwrite=True` execution paths and `os.replace` calls.
  - Kernel-handle verified rollback (`_delete_by_verified_handle` via Win32 `CreateFileW` + `GetFileInformationByHandle` + `SetFileInformationByHandle`) ensuring other writers' files are never unlinked during race conditions.
- **Empty Pane RubberBand Marquee Selection**:
  - Dragging over empty space in `FileTableView` and `FileIconListView` triggers `QRubberBand` multi-item selection while preserving file Drag & Drop.
- **Verification Test Suite (`tests/test_q_dir_v31.py`)**:
  - 17 comprehensive synthetic environment test suites (TC-01 ~ TC-17) covering encoding, collision, rollback, and permission constraints.

### Changed
- **InspectorPane Dark/Light Contrast Optimization**:
  - Added explicit QObject IDs (`InspectorTitleLabel`, `InspectorMetaLabel`, `InspectorPreviewLabel`) with high-contrast styling (`#38BDF8` dark / `#1E3A8A` light), achieving full WCAG AA (≥ 4.5:1) compliance and eliminating black-on-dark text artifacts.
- **Narrow Pane Tab Bar & Address Bar Usability**:
  - Fixed tab bar background rendering artifacts on narrow panels with `#0F172A` (dark) and `#E2E8F0` (light) styling.
  - Introduced `elide_middle_smart` to retain distinguishable prefixes and suffixes for long Korean folder names.
  - Added active tab indicator (`●`), full path tooltips, and permanently editable address bars (`setReadOnly(False)`).
- **Responsive Viewport Layout Lock**:
  - Preserved `preferred_desktop_layout` during narrow viewport (360px vertical / 780px horizontal) adaptations so desktop 4-quad multi-tab sessions are never overridden on restart.

---

## [v2.5.0] - 2026-10-23

### Added
- Real-time dual-path session persistence (`~/.pyquaddir_config.json` & `.pyquaddir_session.json`).
- `resolve_restorable_dir()` parent fallback for invalid/unmounted paths.
- Synchronized 50:50 top and bottom quad splitters (`_on_top_splitter_moved` / `_on_bottom_splitter_moved`).

### Fixed
- `ElidedLabel` (`QSizePolicy.Ignored`) zero-jump layout sizing on dynamic folder navigation.

---

## [v2.4.0] - 2026-10-22

### Added
- Virtual cloud drive (`G:`) safe normalization (`safe_norm_path`).
- Built-in lightweight zero-dependency `.xlsx` sheet viewer and HTML previewer.
- Pre-launch magic header and file health diagnostics (`diagnose_file_health`).

---

## [v2.2.0] - 2026-10-22

### Added
- Windows 11 antialiased vector command bar icons rendered via `QPainter`.
- `Ctrl + Mouse Wheel` 8-stage smooth zoom (details to 220px extra-large icons).
- Keyboard-first navigation (`Enter`/`Return` to execute/enter, `Backspace` to ascend).

---

## [v2.0.0] - 2026-10-22

### Added
- Complete UI overhaul with 8 view modes and live inspector.

---

## [v1.0.0] - 2026-10-22

### Initial Release
- 4-quad multi-tab file explorer for Windows desktop with dual Qt/Tkinter engine support.

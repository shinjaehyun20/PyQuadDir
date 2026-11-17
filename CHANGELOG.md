# PyQuadDir Changelog

All notable changes to the PyQuadDir project are documented in this file.

---

## [v3.2.0] - 2026-11-17

### Fixed
- **Multi-File Move & Drag Selection Preservation (`FileTableView`, `FileIconListView`, `TkDirectoryTab`)**:
  - Replaced selection-clearing `setCurrentIndex(idx)` / `setCurrentItem(item)` calls on already-selected items with `QItemSelectionModel.SelectionFlag.NoUpdate` and pre-drag immutable `_drag_paths` snapshots across Details, Content, Tiles, Icons, and List views.
  - Preserved multi-selection on right-click context menus, copied all selected paths (`\n`-joined) on path copy, avoided self-folder drop traps when dropping onto a selected folder, and returned `"break"` on Tkinter `<ButtonPress-1>` multi-item drags.
- **Address Bar Paste & `Enter` Navigation (`AddressLineEdit`, `normalize_user_input_path`, `navigate_to`)**:
  - Consumed `Key_Return` / `Key_Enter` inside `AddressLineEdit` so `QDirMainWindow.keyPressEvent` no longer activates row 0 (`..` parent directory) after focus shifts to the file list.
  - Initialized default focus index to the first non-parent entry (`NoUpdate`) on refresh/focus-in.
  - Stripped quotes, newlines, trailing slashes, `file:///` URIs, and Windows Properties Unicode bidi/zero-width control characters (`\u202a`–`\u202e`, `\u200b`, `\ufeff`); pasting a file path navigates to its leaf parent directory and highlights the file without unexpectedly launching external executables.

### Added
- **Clean-Room REA Explorer Power Tools (`pyquaddir_addons.py` + `🧰 도구 ▾`)**:
  - **Multi-Rename Tool (`Ctrl+M` / multi-select `F2` / Undo `Ctrl+Shift+Z`)**: Prefix/suffix, regex/plain find-replace, `[N]` sequence counter, case/extension transforms, live preview, collision/ADS/reserved-name blocking, and 2-phase UUID staging with 1-click Undo.
  - **Compare & Sync Panes (`Shift+F2`)**: Side-by-side comparison across panes 1–4 by name, size, timestamp, and optional SHA-256 with non-overwriting selective sync copy.
  - **Folder Occupied Size Calculation (`Alt+Shift+Enter`)**: On-demand recursive directory byte/file count calculation rendered directly in `<DIR>` size cells and status summary.
  - **File Checksum & 3-Stage Duplicate Finder (`Ctrl+Shift+H`)**: MD5 / SHA-1 / SHA-256 calculation, clipboard hash verification, and size -> edge-hash -> full SHA-256 duplicate group detection (zero auto-delete).
  - **Export File List (`Ctrl+Shift+E`), Flat View (`Ctrl+B`), Tab Duplicate/Lock (`Ctrl+Shift+K` / `Ctrl+Shift+L`), and Quick Palette (`Ctrl+P`)**.

### Integration fixes and limits
- Guard the original Qt close/rename slots so tab-close signals respect locks and F2/the toolbar route multiple selections to batch rename.
- Protect all ancestor directories during add-on writes on Windows; reject junctions and keep destination files exclusive during selective copy. Failed copies delete only their own open file handle.
- Use full Windows file identities when excluding hard links from size and duplicate calculations.
- Add native Qt drag/drop and write-safety regressions; keep the archive core unchanged.
- Add-on writes require Windows. Recursive scans and hashes currently run synchronously; source publication does not publish a new downloadable executable.
- Match installation requirements and the packager to the actual PyQt6 engine; document supported `--engine qt` / `--engine tk` options and keep the Windows version resource in source control.
- Restrict only PyInstaller's child-process PATH to Windows and Python directories, preventing unrelated ICU DLLs from entering the executable. Keep the caller's environment and system-runtime policy unchanged.
- Unregister mock GUI exit callbacks before resetting test profiles, so interpreter shutdown cannot save test folders into a user's settings.

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

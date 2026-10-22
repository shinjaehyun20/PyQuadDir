# PyQuadDir Project Status

- **Project Slug**: `pyquaddir`
- **Canonical Workspace Path**: `D:\workspace\projects\active\pyquaddir`
- **Repository**: `https://github.com/shinjaehyun20/PyQuadDir`
- **Version**: `v2.0.0`
- **License**: MIT License
- **Status**: Active / Public Release

## Changelog

### v2.0.0 (2026-10-22)
- **Windows 11 Explorer-Style Command Bar**: Added `[⊕ 새로 만들기 ▾]`, Cut/Copy/Paste/Rename/Delete buttons, `[📤 다른 패널로 전송 ▾]`, `[⇅ 정렬 ▾]` (Name, Modified, Type, Size, Extension, Created + Grouping by Type/Date/Size), and `[⊞ 보기 ▾]` dropdown menus.
- **Compact Top Bar & Full-Width Favorites Bar**: Consolidated Layout and Drive selectors into compact dropdown menus so the Favorites (`⭐`) bar spans the full window width.
- **8 View Modes & Live Image Thumbnail Caching**: Added Extra Large/Large/Medium/Small Icons, List, Details, Tiles, and Content view modes with in-memory image thumbnail rendering (`.png`, `.jpg`, `.webp`, `.gif`, `.bmp`, `.svg`, `.ico`, `.tif`).
- **Right-Side Preview & Details Inspector Pane**: Added toggleable `[◧ 미리 보기]` and `[◨ 세부 정보]` inspector panes for live image/resolution preview and text/code preview.
- **Parent Folder (`..`) Selection Guard**: Excluded `📁 .. (상위 폴더)` when selecting all items (`Ctrl+A`) or multi-selecting via drag.

### v1.0.0 (2026-10-22)
- Initial open-source release of **PyQuadDir Desktop Explorer**.
- Added Triple-Engine runtime compatibility (`PySide6`, `PyQt6`, and built-in `Tkinter` fallback).
- Added 6 dynamic quad/split view layouts (`Ctrl+1` ~ `Ctrl+6`), per-pane multi-tab browsing, cross-pane drag-and-drop file transfer with conflict resolution, and customizable file extension color highlighting.
- Added zero-dependency pure-Python `.ico` icon generator and `PyInstaller` single-executable (`PyQuadDir.exe`) builder (`build_exe.py`).

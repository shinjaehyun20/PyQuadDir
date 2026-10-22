# PyQuadDir Project Status

- **Project ID**: `pyquaddir`
- **Canonical Workspace Path**: `D:\workspace\projects\active\pyquaddir`
- **Desktop Shortcut**: `%USERPROFILE%\Desktop\PyQuadDir.lnk` -> `D:\workspace\projects\active\pyquaddir\dist\PyQuadDir.exe`
- **GitHub Repository**: `https://github.com/shinjaehyun20/PyQuadDir` (Public, MIT License)
- **Current Version**: `v2.4.0` (`2026-10-23`)
- **Status**: `ACTIVE / PRODUCTION`

## Summary of Capabilities (v2.4.0)
- **Triple-Engine Support**: Automatic `PySide6` / `PyQt6` detection with built-in `Tkinter (ttk)` zero-dependency fallback (`--tk`).
- **Virtual Drive (`G:`) Safe Path & Pre-Launch Diagnostics (v2.4)**: Removed `Path.resolve()` distortion via `safe_norm_path()`, added pre-launch magic header & cloud streaming diagnostics (`diagnose_file_health`), and local temp cache bypass execution (`copy_to_local_temp_cache`).
- **Built-in Universal `.xlsx` / `.html` / HEX Viewer (v2.4)**: Zero-dependency `.xlsx` sheet table parser (`parse_xlsx_preview_sheets`), HTML previewer, and smart encoding text reader (`read_text_file_smart`) plus `file:///` URL-encoded address bar navigation (`normalize_user_input_path`).
- **High-Visibility Vector Icon Command Bar (v2.2)**: Custom antialiased 20×20px Windows 11-style color vector icons rendered via `QPainter` (`create_ui_icon`) + full-width Favorites Bar (`⭐`).
- **`Ctrl + Mouse Wheel` Real-Time Zoom (v2.2)**: Smooth 8-stage view transition (`details` → `list` → `content` → `tiles` → `small_icons` → `medium_icons` → `large_icons` → `extra_large_icons` up to 220px).
- **Keyboard-First Navigation (v2.2)**: Full `Enter`/`Return` folder navigation & file execution and `Backspace` parent folder navigation across both `FileTableView` and `FileIconListView`.
- **Portfolio & Marketing Visual Showcase**: Privacy-safe (`Zero-PII`) Hero Banner (`assets/social-preview-banner.png`), animated action GIF (`assets/demo-quad-action.gif`), Dark/Light high-DPI screenshots (`assets/demo-dark.png`, `assets/demo-light.png`), and Mermaid 3-layer system architecture documentation.
- **Standalone Portable Build**: `build_exe.py` builds a standalone zero-install Windows executable (`dist/PyQuadDir.exe`).

"""Exercise the native Qt selection model and drop handlers offscreen."""
import importlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import traceback
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def probe(module_name, folder):
    from PyQt6.QtCore import QPoint, QPointF, QTimer, Qt
    from PyQt6.QtGui import QDrag, QDropEvent, QMouseEvent, QShortcut
    from PyQt6.QtCore import QEvent
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QApplication, QDialog

    sys.path.insert(0, str(ROOT))
    mod = importlib.import_module(module_name)
    mod.set_active_profile(str(folder / "profile"))
    errors = []
    original_exec = QApplication.exec

    def check():
        app = QApplication.instance()
        win = next(w for w in app.topLevelWidgets() if hasattr(w, "panes"))
        win._is_initializing = False
        try:
            assert getattr(win, "_addons_controller", None) is not None
            controller = win._addons_controller
            for width in (360, 780, 1520):
                win.resize(width, 940)
                app.processEvents()
                bar = win.menuBar()
                assert bar.isVisible()
                tools_rect = bar.actionGeometry(win.tools_access_menu.menuAction())
                assert tools_rect.isValid() and tools_rect.right() < win.width()
                with mock.patch.object(controller, "open_multi_rename") as open_rename:
                    QTest.mouseClick(bar, Qt.MouseButton.LeftButton, pos=tools_rect.center())
                    app.processEvents()
                    menu = win.tools_access_menu
                    assert menu.isVisible(), (module_name, width)
                    action = next(a for a in menu.actions() if "일괄 이름 바꾸기" in a.text())
                    assert action.isEnabled()
                    QTest.mouseClick(menu, Qt.MouseButton.LeftButton, pos=menu.actionGeometry(action).center())
                    app.processEvents()
                    assert open_rename.call_count == 1, width
                help_rect = bar.actionGeometry(win.help_access_menu.menuAction())
                assert help_rect.isValid() and help_rect.right() < win.width()
                with mock.patch.object(QDialog, "exec", return_value=0) as about_dialog:
                    QTest.mouseClick(bar, Qt.MouseButton.LeftButton, pos=help_rect.center())
                    app.processEvents()
                    menu = win.help_access_menu
                    assert menu.isVisible()
                    action = next(a for a in menu.actions() if a.text() == "버전정보")
                    QTest.mouseClick(menu, Qt.MouseButton.LeftButton, pos=menu.actionGeometry(action).center())
                    app.processEvents()
                    assert about_dialog.call_count == 1, width
            win.resize(1520, 940)
            app.processEvents()
            pane = win.panes[0]
            pane.add_new_tab(str(folder))
            locked_index = pane.tab_widget.currentIndex()
            controller.toggle_tab_lock_in_pane(pane, locked_index)
            before = pane.tab_widget.count()
            pane.tab_widget.tabCloseRequested.emit(locked_index)
            assert pane.tab_widget.count() == before, "X close signal bypassed tab lock"
            controller.toggle_tab_lock_in_pane(pane, locked_index)
            pane.tab_widget.tabCloseRequested.emit(locked_index)
            assert pane.tab_widget.count() == before - 1
            win._set_active_pane(0)
            active = pane.current_tab()
            with mock.patch.object(active, "selected_file_paths", return_value=["one", "two"]), \
                 mock.patch.object(active, "rename_selected_item") as single, \
                 mock.patch.object(controller, "open_multi_rename") as multi, \
                 mock.patch.object(win, "_is_text_input_focused", return_value=False):
                next(sc for sc in win.findChildren(QShortcut) if sc.key().toString() == "F2").activated.emit()
                win.act_rename.click()
                assert multi.call_count == 2 and single.call_count == 0
            for mode in ("details", "tiles"):
                source, target = folder / (mode + "_source"), folder / (mode + "_target")
                source.mkdir()
                target.mkdir()
                names = ["보고서_하나.txt", "second.md", "third.csv", "folder"]
                for name in names[:3]:
                    (source / name).write_text(name, encoding="utf-8")
                (source / names[3]).mkdir()
                (source / names[3] / "nested.txt").write_text("nested", encoding="utf-8")
                src, dst = win.panes[0].current_tab(), win.panes[1].current_tab()
                src.navigate_to(str(source))
                dst.navigate_to(str(target))
                src.set_view_mode(mode)
                dst.set_view_mode(mode)
                app.processEvents()
                view = src.table if mode == "details" else src.icon_list
                view.selectAll()
                assert len(view.selected_file_paths()) == 4
                item = view.item(2, 0) if mode == "details" else view.item(2)
                rect = view.visualItemRect(item)
                QTest.mousePress(view.viewport(), Qt.MouseButton.LeftButton,
                                 Qt.KeyboardModifier.NoModifier, rect.center())
                assert len(view.selected_file_paths()) == 4, mode
                assert len(view._drag_paths) == 4, mode
                captured = []

                def capture_drag(drag, *args):
                    # Copy the MIME object while QDrag owns it.
                    captured.append([url.toLocalFile() for url in drag.mimeData().urls()])
                    return Qt.DropAction.MoveAction

                with mock.patch.object(QDrag, "exec", capture_drag):
                    pos = rect.center() + QPoint(0, 30)
                    event = QMouseEvent(QEvent.Type.MouseMove, QPointF(pos), QPointF(pos),
                                        Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton,
                                        Qt.KeyboardModifier.NoModifier)
                    view.mouseMoveEvent(event)
                assert len(captured) == 1 and len(captured[0]) == 4, (mode, captured)
                from PyQt6.QtCore import QMimeData, QUrl
                mime = QMimeData()
                mime.setUrls([QUrl.fromLocalFile(path) for path in captured[0]])
                drop = QDropEvent(QPointF(5, 500), Qt.DropAction.MoveAction, mime,
                                  Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ShiftModifier)
                dest_view = dst.table if mode == "details" else dst.icon_list
                dest_view.dropEvent(drop)
                assert all(not (source / name).exists() for name in names), mode
                assert all((target / name).exists() for name in names), mode
                assert (target / "folder" / "nested.txt").read_text() == "nested"
            if os.environ.get("QDIR_TEST_SCREENSHOTS"):
                from PyQt6.QtGui import QFontDatabase, QFont
                if os.name == "nt":
                    font_path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "malgun.ttf"
                    font_id = QFontDatabase.addApplicationFont(str(font_path))
                    families = QFontDatabase.applicationFontFamilies(font_id)
                    if families:
                        app.setFont(QFont(families[0], 9))
                screenshot_dir = Path(os.environ["QDIR_TEST_SCREENSHOTS"])
                screenshot_dir.mkdir(parents=True, exist_ok=True)
                win.resize(1520, 940)
                win.set_layout_mode("quad")
                win.equalize_splitters()
                for pane in win.panes:
                    pane.current_tab().navigate_to(str(folder / "tiles_target"))
                for dark in (True, False):
                    if win.dark_mode != dark:
                        win._toggle_theme()
                    QTest.qWait(250)
                    theme = "dark" if dark else "light"
                    assert win.grab().save(str(screenshot_dir / (module_name + "-" + theme + ".png")))
            print("Native Qt details/tiles: four selections preserved, four MIME paths and four moved items")
        except BaseException:
            errors.append(traceback.format_exc())
        finally:
            win.close()
            app.quit()

    def hooked(self):
        QTimer.singleShot(300, check)
        return original_exec()

    QApplication.exec = hooked
    try:
        mod.run_pyqt6_app()
    except SystemExit as exc:
        assert exc.code == 0
    assert not errors, "\n".join(errors)


class NativeMultiselectRegression(unittest.TestCase):
    def test_real_qt_multiselect_and_drop(self):
        for module in ("pyquaddir", "q_dir"):
            with self.subTest(module=module), tempfile.TemporaryDirectory(prefix="native_multi_") as tmp:
                result = subprocess.run(
                    [sys.executable, "-B", str(Path(__file__).resolve()), module, tmp],
                    cwd=ROOT, env=dict(os.environ, QT_QPA_PLATFORM="offscreen", PYTHONUTF8="1"),
                    capture_output=True, text=True, timeout=45,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    if len(sys.argv) == 3:
        probe(sys.argv[1], Path(sys.argv[2]))
    else:
        unittest.main()

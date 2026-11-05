"""Isolated real Qt events and QWidget.grab; no desktop input.

Supported short-height viewport remains 780x420 (not 780x360).
"""
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIX = Path('D:/workspace/tmp/pyquaddir-inspector-20261105_141655_86e40b')


def probe(module, folder):
    from PyQt6.QtCore import QTimer, Qt, QPoint
    from PyQt6.QtGui import QFontDatabase, QTextOption
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtTest import QTest
    sys.path.insert(0, str(ROOT))
    q = importlib.import_module(module)
    q.set_active_profile(str(folder / 'profile'))
    files = folder / 'files'
    files.mkdir(exist_ok=True)
    name = '2026년_상반기_차세대_정보시스템_고도화_사업_제안서_최종본_검토자료.txt'
    (files / name).write_text('preview fixture', encoding='utf-8')
    for i in range(60):
        (files / ('item_%03d.txt' % i)).write_text('fixture', encoding='utf-8')
    q.save_app_config({'pane_tabs': [[str(files)]] * 4, 'pane_active_tab_indices': [0]*4, 'pane_tab_view_modes': [['details']]*4, 'window_geometry': [0,0,1520,940,False], 'layout_mode': 'quad'})
    original_exec = QApplication.exec
    errors, records = [], []

    def exercise():
        app = QApplication.instance()
        win = next(w for w in app.topLevelWidgets() if hasattr(w, 'panes'))
        try:
            for f in ['malgun.ttf', 'malgunbd.ttf', 'seguiemj.ttf', 'segoeui.ttf']:
                QFontDatabase.addApplicationFont('C:/Windows/Fonts/' + f)
            win._is_initializing = False
            win._set_active_pane(0)
            tab = win.active_pane().current_tab()
            tab.refresh()
            win.toggle_inspector_pane('details', True)
            app.processEvents()
            # Real itemSelectionChanged -> DirectoryTab signal -> main window.
            row = next(i for i in range(tab.table.rowCount()) if name in tab.table.item(i, 0).text())
            tab.table.selectRow(row)
            app.processEvents()
            inspector = win.inspector_pane
            assert q.safe_norm_path(inspector.current_target_path) == q.safe_norm_path(str(files / name))
            assert inspector.name_heading.toPlainText() == name
            assert inspector.name_heading.wordWrapMode() == QTextOption.WrapMode.WrapAnywhere
            assert inspector.meta_label.wordWrapMode() == QTextOption.WrapMode.WrapAnywhere
            assert not inspector.img_label.isVisible()
            QTest.mouseClick(inspector.btn_copy_path, Qt.MouseButton.LeftButton)
            assert q.safe_norm_path(app.clipboard().text()) == q.safe_norm_path(str(files / name))
            for width, height in [(1520,940), (360,780), (780,360)]:
                win.close_inspector_pane()
                win.resize(width,height)
                app.processEvents()
                tab.table.verticalScrollBar().setValue(15)
                before = (win.active_pane_index, win.active_pane().tab_widget.currentIndex(), tab.view_mode, tab.table.verticalScrollBar().value())
                for dark in [True, False]:
                    win.dark_mode = dark
                    win._apply_theme()
                    win.toggle_inspector_pane('details', True)
                    app.processEvents()
                    rect = inspector.geometry()
                    assert win.centralWidget().rect().contains(rect), (width, rect, win.centralWidget().rect())
                    close_pos = inspector.btn_close.mapTo(win.centralWidget(), QPoint(0,0))
                    assert win.centralWidget().rect().contains(close_pos)
                    assert win.centralWidget().rect().contains(close_pos + QPoint(inspector.btn_close.width()-1, inspector.btn_close.height()-1))
                    if width < 760:
                        assert not win.main_splitter.isVisible()
                    else:
                        assert inspector.width() == 320
                    assert win.width() == width
                    assert win.grab().save(str(folder / ('%s-%s.png' % (width, 'dark' if dark else 'light'))))
                    if width == 780:
                        bar = inspector.meta_label.verticalScrollBar()
                        assert bar.maximum() > 0
                        QTest.mouseClick(bar, Qt.MouseButton.LeftButton, pos=QPoint(bar.width() // 2, bar.height() - 3))
                        app.processEvents()
                        assert bar.value() > 0, (bar.value(), bar.maximum(), bar.size())
                        assert '액세스한 날짜' in inspector.meta_label.toPlainText()
                    records.append({'requested':[width,height], 'actual':[win.width(),win.height()], 'inspector':[rect.x(),rect.y(),rect.width(),rect.height()], 'close':[close_pos.x(), close_pos.y(),inspector.btn_close.width(),inspector.btn_close.height()], 'dark':dark})
                    QTest.mouseClick(inspector.btn_close, Qt.MouseButton.LeftButton)
                    app.processEvents()
                    after = (win.active_pane_index, win.active_pane().tab_widget.currentIndex(), tab.view_mode, tab.table.verticalScrollBar().value())
                    assert before == after, (before, after)
                    assert win.main_splitter.isVisible()
                if width == 780:
                    assert win.height() == 420
            (folder / 'geometry.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
        except BaseException as exc:
            import traceback
            errors.append(traceback.format_exc())
        finally:
            win.close()
            app.quit()

    def exec_probe(self):
        QTimer.singleShot(400, exercise)
        return original_exec()
    QApplication.exec = exec_probe
    try:
        q.run_pyqt6_app()
    except SystemExit as exc:
        assert exc.code == 0
    assert not errors, errors


class InspectorRegression(unittest.TestCase):
    def test_real_selection_viewport_restore_and_copy(self):
        for module in ('pyquaddir', 'q_dir'):
            with self.subTest(module=module):
                folder = FIX / module
                for name in ['home','appdata','profile','tmp']:
                    (folder / name).mkdir(parents=True, exist_ok=True)
                env = dict(os.environ, QT_QPA_PLATFORM='offscreen', PYTHONUTF8='1', HOME=str(folder/'home'), USERPROFILE=str(folder/'home'), APPDATA=str(folder/'appdata'), LOCALAPPDATA=str(folder/'appdata'), TMP=str(folder/'tmp'), TEMP=str(folder/'tmp'), TMPDIR=str(folder/'tmp'))
                result = subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),'--probe',module,str(folder)], env=env, cwd=ROOT, capture_output=True, text=True, timeout=45)
                (folder/'stdout.txt').write_text(result.stdout, encoding='utf-8')
                (folder/'stderr.txt').write_text(result.stderr, encoding='utf-8')
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertNotIn('Traceback', result.stderr)
                self.assertNotIn('RuntimeError', result.stderr)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--probe':
        probe(sys.argv[2], Path(sys.argv[3]))
    else:
        unittest.main()

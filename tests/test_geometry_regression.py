"""Isolated offscreen geometry recovery; no desktop interaction."""
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def probe(module, scenario, folder):
    from PyQt6.QtCore import QRect, QTimer
    from PyQt6.QtWidgets import QApplication
    sys.path.insert(0, str(ROOT))
    q = importlib.import_module(module)
    q.set_active_profile(config_path=str(folder / 'config.json'))
    cases = {
        'valid': [65, 81, 1180, 780, False],
        'negative': [-1200, 81, 1180, 780, False],
        'offscreen': [99999, 99999, 1180, 780, False],
        'corrupt': ['invalid', None, 'wide', {}, False],
        'maximized': [65, 81, 1180, 780, True],
    }
    q.save_app_config({'window_geometry': cases[scenario], 'pane_tabs': [[str(folder)]] * 4})
    class Screen:
        def __init__(self, rect): self.rect = rect
        def availableGeometry(self): return self.rect
    QApplication.screens = staticmethod(lambda: [Screen(QRect(0, 0, 1920, 1080)), Screen(QRect(-1920, 0, 1920, 1080))])
    original = QApplication.exec
    errors = []
    def check():
        app = QApplication.instance()
        try:
            win = next(w for w in app.topLevelWidgets() if hasattr(w, 'panes'))
            expected = cases[scenario]
            if scenario == 'corrupt': expected = [80, 60, 1520, 940, False]
            if scenario == 'offscreen': expected = [740, 300, 1180, 780, False]
            assert win.config['window_geometry'] == expected, (win.config['window_geometry'], expected)
            if scenario in ('valid', 'corrupt', 'offscreen'):
                assert [win.geometry().x(), win.geometry().y(), win.width(), win.height()] == expected[:4]
            if scenario == 'maximized':
                assert win.isMaximized()
                assert [win.normalGeometry().x(), win.normalGeometry().y(), win.normalGeometry().width(), win.normalGeometry().height()] == expected[:4]
            close = win.inspector_pane.btn_close
            assert close.text() == 'X' and close.width() > 0
            win._is_initializing = False
            win.close()
            print(json.dumps({'module': module, 'scenario': scenario, 'geometry': expected, 'close_label': close.text()}))
        except BaseException as exc:
            errors.append(repr(exc))
        finally:
            app.quit()
    def hooked(self):
        QTimer.singleShot(300, check)
        return original()
    QApplication.exec = hooked
    try:
        q.run_pyqt6_app()
    except SystemExit as exc:
        assert exc.code == 0
    assert not errors, errors


class GeometryRegression(unittest.TestCase):
    def test_geometry_recovery(self):
        for module in ('pyquaddir', 'q_dir'):
            for scenario in ('valid', 'negative', 'offscreen', 'corrupt', 'maximized'):
                with self.subTest(module=module, scenario=scenario), tempfile.TemporaryDirectory(prefix='geometry_') as tmp:
                    result = subprocess.run([sys.executable, '-B', str(Path(__file__).resolve()), module, scenario, tmp], cwd=ROOT, env=dict(os.environ, QT_QPA_PLATFORM='offscreen', PYTHONUTF8='1'), capture_output=True, text=True, timeout=30)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertNotIn('Traceback', result.stderr)
                    self.assertNotIn('Exception ignored', result.stderr)
                    print(result.stdout.strip())


if __name__ == '__main__':
    if len(sys.argv) == 4:
        probe(sys.argv[1], sys.argv[2], Path(sys.argv[3]))
    else:
        unittest.main()

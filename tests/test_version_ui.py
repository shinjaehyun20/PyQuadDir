"""Version UI contract; offscreen subprocesses and URL spy only."""
import importlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def probe(module_name, folder):
    from PyQt6.QtCore import QTimer
    from PyQt6.QtGui import QDesktopServices
    from PyQt6.QtWidgets import QApplication, QDialog, QLabel, QPushButton
    sys.path.insert(0, str(ROOT))
    mod = importlib.import_module(module_name)
    mod.set_active_profile(str(folder / 'profile'))
    errors = []
    original_exec = QApplication.exec

    def check():
        app = QApplication.instance()
        win = next(w for w in app.topLevelWidgets() if hasattr(w, 'panes'))
        try:
            assert win.windowTitle() == 'PyQuadDir Desktop Explorer'
            assert mod.APP_VERSION == '3.1.1'
            import build_exe
            assert mod.APP_VERSION == '.'.join(map(str, build_exe.APP_VERSION[:3]))
            assert win.btn_version.text() == '버전정보'
            assert not opener.called, 'startup must not open a browser'

            def inspect_dialog(dialog):
                assert dialog.windowTitle() == '버전정보'
                text = '\n'.join(label.text() for label in dialog.findChildren(QLabel))
                assert 'PyQuadDir Desktop Explorer' in text
                assert '현재 버전: 3.1.1' in text and 'MIT License' in text
                assert str(folder) not in text and 'C:/' not in text and 'D:/' not in text
                assert not opener.called, 'opening About must not check updates'
                button = next(b for b in dialog.findChildren(QPushButton) if b.text() == '업데이트 확인')
                button.click()
                opener.assert_called_once()
                assert opener.call_args.args[0].toString() == 'https://github.com/shinjaehyun20/PyQuadDir/releases/latest'
                return 0

            with patch.object(QDialog, 'exec', inspect_dialog):
                win.btn_version.click()
        except BaseException as exc:
            errors.append(repr(exc))
        finally:
            win.close()
            app.quit()

    def exec_probe(self):
        QTimer.singleShot(400, check)
        return original_exec()

    with patch.object(QDesktopServices, 'openUrl', return_value=True) as opener, patch.object(QApplication, 'exec', exec_probe):
        try:
            mod.run_pyqt6_app()
        except SystemExit as exc:
            assert exc.code == 0
    assert not errors, errors


class VersionUI(unittest.TestCase):
    def test_both_entrypoints_version_dialog_and_click_only_url(self):
        for module in ('pyquaddir', 'q_dir'):
            with self.subTest(module=module), tempfile.TemporaryDirectory(prefix='version_ui_') as tmp:
                folder = Path(tmp)
                env = os.environ.copy()
                env.update(QT_QPA_PLATFORM='offscreen', HOME=tmp, USERPROFILE=tmp, APPDATA=tmp, LOCALAPPDATA=tmp, XDG_CONFIG_HOME=tmp)
                result = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--probe', module, tmp], cwd=ROOT, env=env, capture_output=True, text=True, timeout=45)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertNotIn('Traceback', result.stderr)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--probe':
        probe(sys.argv[2], Path(sys.argv[3]))
    else:
        unittest.main()

"""Real offscreen Qt subprocess regression; never uses the interactive desktop."""
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def probe(module_name, phase, folder):
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication
    from PyQt6 import sip
    sys.path.insert(0, str(ROOT))
    mod = importlib.import_module(module_name)
    mod.set_active_profile(str(folder / 'profile'))
    original_exec = QApplication.exec
    errors = []

    def run_checks():
        try:
            app = QApplication.instance()
            win = next(w for w in app.topLevelWidgets() if hasattr(w, 'panes'))
            win._is_initializing = False
            if phase == 'write':
                for i, pane in enumerate(win.panes):
                    pane.tab_widget.widget(0).navigate_to(str(folder / ('pane' + str(i))))
                    pane.tab_widget.widget(0).set_view_mode(['details', 'list', 'tiles', 'large_icons'][i])
                win.resize(1100, 760)
                win.move(63, 79)
                win._set_active_pane(2)
                win.panes[1].add_new_tab(str(folder / 'removed'))
                win.panes[1].tab_widget.setCurrentIndex(1)
                win.save_config()
            win.save_config()
            state = win._exit_snapshot
            assert len(state['pane_tabs']) == 4, state
            for i in range(4):
                assert mod.safe_norm_path(state['pane_tabs'][i][0]) == mod.safe_norm_path(str(folder / ('pane' + str(i)))), state
            assert state['active_pane_index'] == 2, state
            assert state['pane_active_tab_indices'][1] == 1, state
            assert [modes[0] for modes in state['pane_tab_view_modes']] == ['details', 'list', 'tiles', 'large_icons'], state
            if phase != 'write':
                written = json.loads((folder / 'write.json').read_text(encoding='utf-8'))
                assert state['window_geometry'] == written['window_geometry'], state
            assert state['window_geometry'][2:4] == [1100, 760], state
            expected = folder / 'removed' if phase == 'write' else folder
            assert mod.safe_norm_path(state['pane_tabs'][1][1]) == mod.safe_norm_path(str(expected)), state
            assert win.grab().save(str(folder / (phase + '.png')))
            (folder / (phase + '.json')).write_text(json.dumps(state), encoding='utf-8')
            if phase == 'delete':
                # The fallback must not access any C++ widgets, even while dirty.
                callback = win._save_config_on_exit
                sip.delete(win)
                callback()
                callback()
            else:
                win.close()
                win.close()
                win._save_config_on_exit()
                sip.delete(win)
                win._save_config_on_exit()
        except BaseException as exc:
            errors.append(repr(exc))
        finally:
            QApplication.instance().quit()

    def exec_with_probe(self):
        QTimer.singleShot(400, run_checks)
        return original_exec()

    QApplication.exec = exec_with_probe
    try:
        mod.run_pyqt6_app()
    except SystemExit as exc:
        assert exc.code == 0, exc.code
    assert not errors, errors


class ShutdownRegression(unittest.TestCase):
    def test_real_restart_and_deleted_widgets(self):
        for module in ('pyquaddir', 'q_dir'):
            with self.subTest(module=module), tempfile.TemporaryDirectory(prefix='shutdown_') as tmp:
                folder = Path(tmp)
                for name in ['home', 'appdata', 'qtconfig', 'profile', 'removed'] + ['pane' + str(i) for i in range(4)]:
                    (folder / name).mkdir()
                env = os.environ.copy()
                env.update(QT_QPA_PLATFORM='offscreen', HOME=str(folder / 'home'), USERPROFILE=str(folder / 'home'), APPDATA=str(folder / 'appdata'), LOCALAPPDATA=str(folder / 'appdata'), XDG_CONFIG_HOME=str(folder / 'qtconfig'))
                for phase in ('write', 'read', 'delete'):
                    result = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--probe', module, phase, str(folder)], env=env, cwd=ROOT, capture_output=True, text=True, timeout=45)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertNotIn('RuntimeError', result.stderr)
                    self.assertNotIn('Traceback', result.stderr)
                    self.assertNotIn('Exception ignored', result.stderr)
                    if phase == 'write':
                        (folder / 'removed').rmdir()
                    evidence = os.environ.get('PYQUADDIR_EVIDENCE_DIR')
                    if evidence:
                        target = Path(evidence) / module
                        target.mkdir(parents=True, exist_ok=True)
                        for suffix in ('.png', '.json'):
                            shutil.copy2(folder / (phase + suffix), target / (phase + suffix))

    def test_version_resource_is_generated_from_contract(self):
        sys.path.insert(0, str(ROOT))
        import build_exe
        self.assertEqual(build_exe.APP_VERSION, (3, 1, 1, 0))
        with tempfile.TemporaryDirectory() as tmp:
            generated = build_exe.generate_version_file(Path(tmp) / 'version.txt')
            self.assertEqual(generated.read_text(encoding='utf-8'), (ROOT / 'version_info.txt').read_text(encoding='utf-8'))


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--probe':
        probe(sys.argv[2], sys.argv[3], Path(sys.argv[4]))
    else:
        unittest.main()

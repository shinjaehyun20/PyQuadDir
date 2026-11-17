"""Tk menu handlers call the real addon API without creating desktop windows."""
import hashlib
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from test_pyquaddir_multiselect import load_pyquaddir_symbols

ROOT = Path(__file__).resolve().parents[1]


class TkAddonContract(unittest.TestCase):
    def test_tk_hash_size_and_export_handlers(self):
        for name in ("pyquaddir.py", "q_dir.py"):
            with self.subTest(entry=name), tempfile.TemporaryDirectory(prefix="tk_addon_") as tmp:
                folder = Path(tmp)
                bundle = load_pyquaddir_symbols(ROOT / name)
                cls = bundle["tk"]["TkQDirApp"]
                app = cls.__new__(cls)
                first, second = folder / "한글.txt", folder / "second.txt"
                first.write_text("first", encoding="utf-8")
                second.write_text("second", encoding="utf-8")
                sub = folder / "sub"
                sub.mkdir()
                (sub / "nested.txt").write_text("nested", encoding="utf-8")
                values = ["sub", "<DIR>", "folder", ""]

                def tree_item(path, option=None, **kwargs):
                    if "values" in kwargs:
                        values[:] = kwargs["values"]
                    return values

                tab = SimpleNamespace(
                    current_path=str(folder),
                    selected_paths=lambda: [str(first), str(second), str(sub)],
                    tree=SimpleNamespace(get_children=lambda: (str(sub),), item=tree_item),
                    summary_var=SimpleNamespace(set=mock.Mock()),
                    refresh=mock.Mock(),
                )
                app._active_tk_tab = lambda: tab
                box = SimpleNamespace(showinfo=mock.Mock(), showwarning=mock.Mock())
                with mock.patch.dict(cls._tk_show_hashes.__globals__, messagebox=box):
                    app._tk_show_hashes()
                    box.showwarning.assert_not_called()
                    report = box.showinfo.call_args.args[1]
                    for file in (first, second):
                        self.assertIn(file.name, report)
                        self.assertIn(hashlib.sha256(file.read_bytes()).hexdigest(), report)
                        self.assertIn(hashlib.md5(file.read_bytes()).hexdigest(), report)
                    app._tk_calc_folder_sizes()
                    box.showwarning.assert_not_called()
                    self.assertIn("6 B", values[1])
                    tab.summary_var.set.assert_called_once()
                    app._tk_export_csv()
                    box.showwarning.assert_not_called()
                    tab.refresh.assert_called_once()
                    exported = list(folder.glob("file_list_*.csv"))
                    self.assertEqual(len(exported), 1)
                    self.assertIn(first.name, exported[0].read_text(encoding="utf-8-sig"))


if __name__ == "__main__":
    unittest.main()

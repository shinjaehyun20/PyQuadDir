import hashlib
from pathlib import Path
import tempfile
import unittest
from msvc_runtime_policy import without_bundled_msvc

class RuntimePolicyTests(unittest.TestCase):
    def test_exact_filter_preserves_other_entries(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'runtime'; p.write_bytes(b'fixture')
            expected = {'Qt/VCRUNTIME140.dll': hashlib.sha256(p.read_bytes()).hexdigest()}
            keep = ('Qt/Qt6Core.dll', 'untouched', 'BINARY')
            entries = [('Qt\\VCRUNTIME140.dll', str(p), 'BINARY'), keep]
            self.assertEqual(without_bundled_msvc(entries, expected), [keep])
            self.assertEqual(len(entries), 2)
            self.assertEqual(p.read_bytes(), b'fixture')

    def test_missing_changed_duplicate_and_relocated_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'runtime'; p.write_bytes(b'fixture')
            expected = {'VCRUNTIME140.dll': hashlib.sha256(p.read_bytes()).hexdigest()}
            e = ('VCRUNTIME140.dll', str(p), 'BINARY')
            for entries in ([], [e, e], [('elsewhere/VCRUNTIME140.dll', str(p), 'BINARY')]):
                with self.assertRaises(ValueError):
                    without_bundled_msvc(entries, expected)
            p.write_bytes(b'changed')
            with self.assertRaises(ValueError):
                without_bundled_msvc([e], expected)

"""Pure offline tests: safe ZIP extraction, source path containment, numeric semver."""
from pathlib import Path
import sys, tempfile, unittest, zipfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from build_stage import extract_safe
from resolve_release import SEMVER

class SafetyTests(unittest.TestCase):
    def test_semver_numeric(self):
        values = ['v22.3.0', 'v22.12.0', 'v9.9.9']
        self.assertEqual(max(values, key=lambda x: tuple(map(int, SEMVER.fullmatch(x).groups()))), 'v22.12.0')

    def test_zip_retains_empty_and_content(self):
        with tempfile.TemporaryDirectory() as path:
            root = Path(path)
            zpath = root/'a.zip'
            with zipfile.ZipFile(zpath, 'w') as z:
                z.writestr('root/empty/nested/', b'')
                z.writestr('root/a.txt', b'abc')
            extract_safe(zpath, root/'out')
            self.assertTrue((root/'out/root/empty/nested').is_dir())
            self.assertEqual((root/'out/root/a.txt').read_bytes(), b'abc')

    def test_zip_slip_refused(self):
        with tempfile.TemporaryDirectory() as path:
            root=Path(path)
            with zipfile.ZipFile(root/'x.zip','w') as z: z.writestr('../bad.txt', 'bad')
            with self.assertRaises(ValueError): extract_safe(root/'x.zip', root/'out')
            self.assertFalse((root/'bad.txt').exists())

    def test_case_collision_refused(self):
        with tempfile.TemporaryDirectory() as path:
            root=Path(path)
            with zipfile.ZipFile(root/'x.zip','w') as z:
                z.writestr('X.txt', '1')
                z.writestr('x.TXT', '2')
            with self.assertRaises(ValueError): extract_safe(root/'x.zip', root/'out')

if __name__ == '__main__': unittest.main()

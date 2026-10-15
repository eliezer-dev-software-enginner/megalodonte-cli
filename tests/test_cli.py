from pathlib import Path
import tempfile
import unittest
from megalodonte_cli import cli as MODULE


class NewApplicationTests(unittest.TestCase):
    def test_both_modes_include_build_packaging_and_actions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for mode, dependency in (("jsonc", "script-app"), ("native", "megalodonte-base")):
                app = MODULE.create(f"sample-{mode}", mode, f"Sample {mode}", root)
                self.assertTrue((app / ".git").is_dir())
                self.assertTrue((app / "packaging.toml").is_file())
                self.assertIn('icon_linux = "src/main/resources/icon.png"',
                              (app / "packaging.toml").read_text())
                self.assertEqual((app / "src/main/resources/icon.png").read_bytes()[:8],
                                 b"\x89PNG\r\n\x1a\n")
                self.assertTrue((app / "scripts/package.py").is_file())
                self.assertIn("package-javafx.yml@main", (app / ".github/workflows/package.yml").read_text())
                self.assertIn(dependency, (app / "build.gradle.kts").read_text())
                self.assertEqual((app / "src/main/resources/views/home.view.jsonc").exists(), mode == "jsonc")
            with self.assertRaises(FileExistsError):
                MODULE.create("sample-jsonc", "jsonc", "Duplicate", root)


if __name__ == "__main__":
    unittest.main()

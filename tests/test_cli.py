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

    def test_android_modes_use_android_bridge_without_javafx(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for mode in ("native", "jsonc"):
                app = MODULE.create(f"android-{mode}", mode, f"Android {mode}", root, platform="android")
                settings = (app / "settings.gradle.kts").read_text()
                build = (app / "app/build.gradle.kts").read_text()
                self.assertIn('include(":app", ":framework-core", ":android-bridge")', settings)
                self.assertIn('id("com.android.application")', build)
                self.assertNotIn('implementation("org.openjfx', build)
                self.assertFalse((app / "packaging.toml").exists())
                workflow = (app / ".github/workflows/android.yml").read_text()
                self.assertIn("MEGALODONTE_ANDROID_HOME: framework/megalodonte-android", workflow)
                self.assertTrue((app / ".git").is_dir())
                self.assertEqual((app / "app/src/main/assets/views/home.view.jsonc").exists(), mode == "jsonc")
                if mode == "jsonc":
                    view = (app / "app/src/main/assets/views/home.view.jsonc").read_text()
                    activity = (app / "app/src/main/java/megalodonte/app/android_jsonc/MainActivity.java").read_text()
                    self.assertIn('"action": "start"', view)
                    self.assertIn('"bind": "message"', view)
                    self.assertIn('screen.setState("message", "Tudo pronto!")', activity)
                self.assertEqual((app / "app/src/main/java/megalodonte/app/android_native/HomeScreen.java").exists(),
                                 mode == "native")


if __name__ == "__main__":
    unittest.main()

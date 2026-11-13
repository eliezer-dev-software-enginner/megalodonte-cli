from pathlib import Path
import tempfile
import tomllib
import unittest
from megalodonte_cli import cli as MODULE


class NewApplicationTests(unittest.TestCase):
    def test_desktop_escapes_backslashes_in_generated_formats(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for mode in ("native", "jsonc"):
                title = " \tPath \\ Demo"
                app = MODULE.create(f"escaped-{mode}", mode, title, root)
                packaging = tomllib.loads((app / "packaging.toml").read_text())
                self.assertEqual(packaging["app"]["name"], title)
                if mode == "native":
                    main = (app / "src/main/java/escaped_native/Main.java").read_text()
                    self.assertIn("AppHost extends MegalodonteApplication", main)
                    self.assertIn('MegalodonteApp.appIcon("/icon.png")', main)
                    self.assertIn("static void main(String[] args)", main)
                    self.assertNotIn("public static void main", main)
                    self.assertIn("MegalodonteApp.run(AppHost.class, args", main)
                    screen = (app / "src/main/java/escaped_native/HomeScreen.java").read_text()
                    self.assertIn(r'" \tPath \\ Demo"', main)
                    self.assertIn(r'" \tPath \\ Demo"', screen)
                else:
                    properties = (app / "src/main/resources/application.properties").read_text()
                    self.assertIn(r"app.name=\ \tPath \\ Demo", properties)

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
                readme = (app / "README.md").read_text()
                self.assertIn("## Executar", readme)
                self.assertIn("## Empacotar", readme)
                self.assertIn("## Ícone no Linux", readme)
                self.assertIn("xprop WM_CLASS", readme)
                self.assertIn("ThemeManager.setTheme(new MyTheme())", readme)
                self.assertIn("context.javafxStage().setMinWidth(980)", readme)
                self.assertIn("context.useView(new HomeScreen(), 1260, 780)", readme)
                self.assertIn("docs/images/live-reload.svg", readme)
                diagram = app / "docs/images/live-reload.svg"
                self.assertTrue(diagram.is_file())
                diagram_text = diagram.read_text()
                self.assertIn("World", diagram_text)
                self.assertIn("COMPILATION_RESULT", diagram_text)
                self.assertIn("Scene.setRoot", diagram_text)
                if mode == "native":
                    self.assertIn("public static final class AppHost extends MegalodonteApplication {}", readme)
                    self.assertIn("MegalodonteApp.run(AppHost.class, args", readme)
                else:
                    self.assertIn("app.icon=/icon.png", readme)
                    self.assertIn("host JavaFX compartilhado", readme)
                self.assertNotIn("/home/", readme)
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
                self.assertIn('implementation(project(":framework-core"))', build)
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

    def test_android_can_target_legacy_tv_box(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app = MODULE.create("android-tv", "native", "Android TV", root,
                                platform="android", min_sdk=25)
            build = (app / "app/build.gradle.kts").read_text()
            self.assertIn("minSdk = 25", build)
            self.assertIn("isCoreLibraryDesugaringEnabled = true", build)
            self.assertIn("coreLibraryDesugaring(", build)
            with self.assertRaises(ValueError):
                MODULE.create("too-old", "native", "Too Old", root,
                              platform="android", min_sdk=24)

    def test_roku_native_generates_java_screen_and_sideload_build(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app = MODULE.create("roku-hello", "native", "Roku Hello", root, platform="roku")
            self.assertTrue((app / ".git").is_dir())
            screen = (app / "src/main/java/megalodonte/app/roku_hello/HomeScreen.java").read_text()
            self.assertIn("RokuScene", screen)
            self.assertIn('new Button("Contador reativo", "counter")', screen)
            self.assertIn('Button.increment("Incrementar")', screen)
            self.assertIn('new Counter("Cliques", 0)', screen)
            self.assertIn("packageRoku", (app / "build.gradle.kts").read_text())
            self.assertIn("megalodonte-roku", (app / ".github/workflows/roku.yml").read_text())
            with self.assertRaises(ValueError):
                MODULE.create("roku-jsonc", "jsonc", "Unsupported", root, platform="roku")

    def test_projects_bundle_skill_and_support_sync_and_install(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for platform in ("desktop", "android", "roku"):
                app = MODULE.create(f"skill-{platform}", "native", "Skill Demo", root, platform=platform)
                skill = app / "skills/megalodonte-native-ui/SKILL.md"
                general = app / "skills/criterioso/SKILL.md"
                self.assertIn("name: megalodonte-native-ui", skill.read_text())
                self.assertIn("ErrorReporter.register", skill.read_text())
                self.assertIn("megalodonte dev --project .", skill.read_text())
                self.assertIn("init scripts se propagam aos builds incluídos", skill.read_text())
                self.assertIn("name: criterioso", general.read_text())
                self.assertIn("README principal em inglês", general.read_text())
                self.assertIn("skills/megalodonte-native-ui/SKILL.md", (app / "AGENTS.md").read_text())
                self.assertIn("skills/criterioso/SKILL.md", (app / "AGENTS.md").read_text())
                self.assertIn("megalodonte skills install --project .", (app / "README.md").read_text())
                if platform == "desktop":
                    self.assertIn("recuperam posição, tamanho, modo e intenção de foco", (app / "README.md").read_text())
                skill.write_text("stale")
                general.write_text("stale")
                self.assertEqual(MODULE.sync_skills(app), skill)
                self.assertIn("name: megalodonte-native-ui", skill.read_text())
                self.assertIn("ErrorReporter.register", skill.read_text())
                self.assertIn("name: criterioso", general.read_text())
                self.assertIn("README principal em inglês", general.read_text())
                self.assertEqual((app / "AGENTS.md").read_text().count("skills/criterioso/SKILL.md"), 1)
                codex_home = root / f"codex-{platform}"
                link = MODULE.install_skills(app, codex_home)
                self.assertTrue(link.is_symlink())
                self.assertEqual(link.resolve(), skill.parent.resolve())
                self.assertEqual((codex_home / "skills/criterioso").resolve(), general.parent.resolve())
                self.assertEqual(MODULE.install_skills(app, codex_home), link)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Create a Megalodonte desktop app with build, packaging and Actions wired together."""
from __future__ import annotations

import argparse
from importlib.resources import files
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


ASSETS = files("megalodonte_cli").joinpath("assets")


def find_workspace(start: Path) -> Path | None:
    for candidate in (start, *start.parents):
        if (candidate / "workspace.toml").is_file() and (candidate / "framework").is_dir():
            return candidate
    return None


def workflow(name: str, dependencies: str) -> str:
    return f'''name: Package installers
on:
  workflow_dispatch:
  push:
    tags: ['v*']
permissions:
  contents: write
concurrency:
  group: ${{{{ github.workflow }}}}-${{{{ github.ref }}}}
  cancel-in-progress: false
jobs:
  package:
    uses: eliezer-dev-software-enginner/megalodonte-packaging/.github/workflows/package-javafx.yml@main
    with:
      project-directory: .
      artifact-name: {name}
      dependencies: '{dependencies}'
      release: true
      smoke-test: true
'''


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def create(name: str, mode: str, display_name: str, output_root: Path, workspace: Path | None = None) -> Path:
    if not re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", name):
        raise ValueError("Name must be lowercase kebab-case, for example my-app")
    if mode not in {"jsonc", "native"}:
        raise ValueError("Mode must be jsonc or native")
    if not display_name.strip() or any(char in display_name for char in '\n\r"'):
        raise ValueError("Display name must be nonempty and contain no quotes or newlines")
    output_root = output_root.resolve()
    workspace = workspace.resolve() if workspace else find_workspace(output_root)
    destination = output_root / name
    if destination.exists():
        raise FileExistsError(f"Project already exists: {destination}")
    output_root.mkdir(parents=True, exist_ok=True)
    package = name.replace("-", "_")
    main_class = "megalodonte.script.ScriptLauncher" if mode == "jsonc" else f"{package}.Main"
    dependency = "megalodonte-script-app:0.1.0" if mode == "jsonc" else "megalodonte-components:1.0.0-beta"
    composite = "megalodonte-declarative/megalodonte-script-app" if mode == "jsonc" else "libraries/megalodonte-components"
    local_build = (workspace / "framework" / composite) if workspace else None
    local_build = local_build if local_build and local_build.is_dir() else None
    with tempfile.TemporaryDirectory(prefix="megalodonte-new-", dir=output_root) as temporary:
        root = Path(temporary)
        include = ""
        if local_build:
            relative = Path(os.path.relpath(local_build, destination)).as_posix()
            include = f'    includeBuild("{relative}")'
            if mode == "native":
                theme = Path(os.path.relpath(workspace / "framework/libraries/megalodonte-theme", destination)).as_posix()
                include += f'\n    includeBuild("{theme}")'
        write(root / "settings.gradle.kts", f'''rootProject.name = "{name}"
if (providers.gradleProperty("useLocalSources").orNull != "false") {{
{include}
}}''')
        write(root / "build.gradle.kts", f'''plugins {{
    application
    id("org.openjfx.javafxplugin") version "0.1.0"
}}
group = "megalodonte"
version = "0.1.0"
repositories {{ mavenLocal(); mavenCentral() }}
java {{ toolchain {{ languageVersion.set(JavaLanguageVersion.of(25)) }} }}
javafx {{ version = "25.0.1"; modules("javafx.controls", "javafx.graphics") }}
dependencies {{
    implementation("megalodonte:{dependency}")
    {('implementation("megalodonte:megalodonte-base:1.0.0-beta")' if mode == 'native' else '')}
    {('implementation("megalodonte:megalodonte-theme:1.0.0-beta")' if mode == 'native' else '')}
    testImplementation(platform("org.junit:junit-bom:5.10.0"))
    testImplementation("org.junit.jupiter:junit-jupiter")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
}}
application {{
    mainClass.set("{main_class}")
    applicationDefaultJvmArgs = listOf("--enable-native-access=ALL-UNNAMED")
}}
tasks.test {{ useJUnitPlatform() }}
tasks.withType<JavaCompile>().configureEach {{ options.encoding = "UTF-8" }}''')
        write(root / "packaging.toml", f'''schema_version = 1

[app]
name = "{display_name}"
version = "0.1.0"
main_class = "{main_class}"
icon_linux = "src/main/resources/icon.png"

[build]
mode = "distribution"
tasks = ["installDist"]
jar = "build/install/{name}/lib/{name}-{{version}}.jar"

[javafx]
version = "25.0.1"

[runtime]
modules = ["javafx.controls", "java.logging", "java.xml", "jdk.charsets"]
exclude_natives = ["libjfxwebkit.so", "libjfxmedia.so", "jfxwebkit.dll"]

[linux]
package_name = "{name}"
menu_group = "Office"''')
        write(root / ".gitignore", ".gradle/\nbuild/\ndist/\n.packaging/\n.idea/\n*.iml")
        write(root / "src/main/resources/icon.svg", '''<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">
  <rect width="256" height="256" rx="54" fill="#17384a"/>
  <path d="M47 128h162M128 47v162" stroke="#66d5c7" stroke-width="22" stroke-linecap="round"/>
</svg>''')
        shutil.copy2(ASSETS / "starter-icon.png", root / "src/main/resources/icon.png")
        if mode == "jsonc":
            write(root / "src/main/resources/application.properties", f'''app.name={display_name}
app.initialView=home
app.scriptsPackage={package}
app.views=/views
app.width=900
app.height=640
app.minWidth=600
app.minHeight=420''')
            view = {"version": 1, "id": "home", "states": {"mensagem": {"type": "string", "initial": ""}},
                    "view": {"type": "Column", "props": {"padding": 28, "spacing": 12, "fillWidth": True},
                             "children": [{"type": "Text", "props": {"text": display_name},
                                           "style": {"fontSize": 28, "bold": True}},
                                          {"type": "Text", "props": {"text": "Seu aplicativo Megalodonte está pronto."}}]}}
            write(root / "src/main/resources/views/home.view.jsonc", json.dumps(view, ensure_ascii=False, indent=2))
            write(root / f"src/main/java/{package}/Home.java", f'''package {package};

import megalodonte.script.ViewScript;

public final class Home extends ViewScript {{
    @Override public void onSubmit() {{ }}
}}''')
        else:
            write(root / f"src/main/java/{package}/Main.java", f'''package {package};

import megalodonte.application.MegalodonteApp;
import megalodonte.base.theme.ThemeManager;
import megalodonte.theme.DefaultTheme;

public final class Main {{
    public static void main(String[] args) {{
        ThemeManager.setTheme(new DefaultTheme());
        MegalodonteApp.appName("{display_name}");
        MegalodonteApp.run(context -> context.useView(new HomeScreen()));
    }}
}}''')
            write(root / f"src/main/java/{package}/HomeScreen.java", f'''package {package};

import megalodonte.base.components.Component;
import megalodonte.base.components.ScreenComponent;
import megalodonte.components.Text;
import megalodonte.components.layout_components.Container;
import megalodonte.props.ContainerProps;
import megalodonte.props.TextProps;

public final class HomeScreen implements ScreenComponent {{
    @Override public Component render() {{
        return new Container(new ContainerProps().paddingAll(28)).children(
                new Text("{display_name}", new TextProps().fontSize(28)));
    }}
}}''')
        write(root / "README.md", f'''# {display_name}

Megalodonte desktop application using the **{mode}** UI mode.

Run `./gradlew test` to check the project and `./gradlew run` to launch it.
Build an AppImage with `python3 scripts/package.py build appimage`.
The standard GitHub Actions caller builds AppImage, DEB and MSI installers on a matching `v*` tag or manual dispatch.
Replace the starter icon before publishing a release.''')
        for item in ("gradlew", "gradlew.bat"):
            shutil.copy2(ASSETS / item, root / item)
        shutil.copytree(ASSETS / "gradle/wrapper", root / "gradle/wrapper")
        (root / "scripts").mkdir()
        shutil.copy2(ASSETS / "package.py", root / "scripts/package.py")
        write(root / ".github/workflows/package.yml", workflow(name, "script-app" if mode == "jsonc" else ""))
        root.rename(destination)
    subprocess.run(["git", "init", "-q", "-b", "main", str(destination)], check=True)
    if workspace and output_root == (workspace / "applications").resolve():
        manifest = workspace / "workspace.toml"
        with manifest.open("a", encoding="utf-8") as stream:
            stream.write(f'\n[[repositories]]\npath = "applications/{name}"\nlocal_only = true\n')
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="Lowercase project name, for example my-app")
    parser.add_argument("--mode", choices=("jsonc", "native"), required=True)
    parser.add_argument("--display-name", help="Window and installer name (default: project name)")
    parser.add_argument("--output-root", type=Path, default=Path.cwd())
    parser.add_argument("--workspace", type=Path, help="Megalodonte workspace root for local source builds")
    args = parser.parse_args()
    try:
        print(create(args.name, args.mode, args.display_name or args.name, args.output_root, args.workspace))
    except (ValueError, FileExistsError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Project creation failed: {error}\n")


if __name__ == "__main__":
    main()

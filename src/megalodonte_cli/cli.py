#!/usr/bin/env python3
"""Create Megalodonte desktop, Android, and Roku projects."""
from __future__ import annotations

import argparse
from importlib.resources import files
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from xml.sax.saxutils import escape


ASSETS = files("megalodonte_cli").joinpath("assets")
SKILL_NAME = "megalodonte-native-ui"
SKILL_NAMES = (SKILL_NAME, "criterioso")


def sync_skills(project: Path) -> Path:
    """Copy the skills bundled with this CLI into an existing project."""
    project = project.resolve()
    if not (project / "AGENTS.md").is_file():
        raise ValueError(f"Not a Megalodonte project with AGENTS.md: {project}")
    for name in SKILL_NAMES:
        source = ASSETS / "skills" / name / "SKILL.md"
        destination = project / "skills" / name / "SKILL.md"
        write(destination, source.read_text(encoding="utf-8"))
    agents = project / "AGENTS.md"
    guidance = "\nPara investigação, implementação e validação de mudanças, leia `skills/criterioso/SKILL.md`.\n"
    if "skills/criterioso/SKILL.md" not in agents.read_text(encoding="utf-8"):
        with agents.open("a", encoding="utf-8") as stream:
            stream.write(guidance)
    return project / "skills" / SKILL_NAME / "SKILL.md"


def install_skills(project: Path, codex_home: Path | None = None) -> Path:
    """Register the project skill in Codex without duplicating its content."""
    project = project.resolve()
    home = codex_home or Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    destinations = []
    for name in SKILL_NAMES:
        source = project / "skills" / name
        if not (source / "SKILL.md").is_file():
            raise ValueError(f"Skill missing; run 'megalodonte skills sync --project {project}' first")
        destination = home.expanduser() / "skills" / name
        canonical = Path(str(ASSETS / "skills" / name)).resolve()
        if destination.is_symlink() and destination.resolve() in (source, canonical):
            destinations.append((destination, source, True))
        elif destination.exists() or destination.is_symlink():
            raise FileExistsError(f"Skill already installed at {destination}; remove it explicitly before changing its source")
        else:
            destinations.append((destination, source, False))
    for destination, source, installed in destinations:
        if not installed:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.symlink_to(source, target_is_directory=True)
    return destinations[0][0]


def write_skill_guidance(root: Path, platform: str) -> None:
    for name in SKILL_NAMES:
        source = ASSETS / "skills" / name / "SKILL.md"
        write(root / "skills" / name / "SKILL.md", source.read_text(encoding="utf-8"))
    write(root / "AGENTS.md", f'''# Megalodonte — {platform}

Antes de criar ou alterar interfaces, execute `megalodonte skills sync --project .`
quando o CLI estiver disponível e então leia `skills/{SKILL_NAME}/SKILL.md`.
Siga as regras comuns de composição, estado e tema; aplique as regras específicas
da plataforma indicada na skill. Se a skill ainda não estiver no catálogo do Codex,
ela continua obrigatória por esta instrução. Se o CLI não estiver instalado,
use a cópia versionada e informe que não foi possível sincronizar.''')
    with (root / "AGENTS.md").open("a", encoding="utf-8") as stream:
        stream.write("\n\nPara investigação, implementação e validação de mudanças, leia `skills/criterioso/SKILL.md`.\n")


SKILL_README = f'''

## Skills para agentes

Este projeto inclui [`skills/{SKILL_NAME}/SKILL.md`](skills/{SKILL_NAME}/SKILL.md)
para interface e [`skills/criterioso/SKILL.md`](skills/criterioso/SKILL.md)
para investigação e entrega de mudanças.
O `AGENTS.md` exige que agentes leiam as skills pertinentes; isso
funciona mesmo sem instalá-la no catálogo. Para usar `$` no Codex, execute na
raiz do projeto:

```sh
megalodonte skills install --project .
```

O comando cria vínculos para as duas skills em `~/.codex/skills` (ou
`$CODEX_HOME/skills`), sem duplicar os arquivos. Reinicie a conversa se o menu
de `$` não atualizar. Após atualizar o Megalodonte CLI, sincronize as versões
mais recentes com:

```sh
megalodonte skills sync --project .
```

O projeto mantém cópias versionadas; a instalação no Codex acompanha as
alterações dessas cópias automaticamente.
'''


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


def create(name: str, mode: str, display_name: str, output_root: Path,
           workspace: Path | None = None, platform: str = "desktop", min_sdk: int = 35) -> Path:
    if not re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", name):
        raise ValueError("Name must be lowercase kebab-case, for example my-app")
    if mode not in {"jsonc", "native"}:
        raise ValueError("Mode must be jsonc or native")
    if platform not in {"desktop", "android", "roku"}:
        raise ValueError("Platform must be desktop, android or roku")
    if not display_name.strip() or any(char in display_name for char in '\n\r"'):
        raise ValueError("Display name must be nonempty and contain no quotes or newlines")
    quoted_title = json.dumps(display_name, ensure_ascii=False)
    properties_title = display_name.replace("\\", "\\\\")
    properties_title = re.sub(r"^[ \t\f]+", lambda match: "".join(
        {" ": r"\ ", "\t": r"\t", "\f": r"\f"}[char] for char in match.group()), properties_title)
    output_root = output_root.resolve()
    workspace = workspace.resolve() if workspace else find_workspace(output_root)
    if platform == "android":
        if not 25 <= min_sdk <= 35:
            raise ValueError("Android min SDK must be between 25 and 35")
        return create_android(name, mode, display_name, output_root, workspace, min_sdk)
    if min_sdk != 35:
        raise ValueError("--min-sdk applies only to Android projects")
    if platform == "roku":
        if mode != "native":
            raise ValueError("Roku currently supports --mode native only")
        return create_roku(name, display_name, output_root, workspace)
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
name = {quoted_title}
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
            write(root / "src/main/resources/application.properties", f'''app.name={properties_title}
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
import megalodonte.application.MegalodonteApplication;
import megalodonte.base.theme.ThemeManager;
import megalodonte.theme.DefaultTheme;

public final class Main {{
    public static final class AppHost extends MegalodonteApplication {{}}

    public static void main(String[] args) {{
        ThemeManager.setTheme(new DefaultTheme());
        MegalodonteApp.appName({quoted_title});
        MegalodonteApp.appIcon("/icon.png");
        MegalodonteApp.run(AppHost.class, args, context -> context.useView(new HomeScreen()));
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
                new Text({quoted_title}, new TextProps().fontSize(28)));
    }}
}}''')
        write(root / "README.md", f'''# {display_name}

Aplicação desktop Megalodonte em modo **{mode}**. Este projeto inicial mostra uma tela nativa e serve como ponto de partida para a interface e as regras da aplicação.

## Executar

Requer JDK 25 e ambiente gráfico. Na raiz do repositório:

```sh
./gradlew test
./gradlew run
```

## Empacotar

`python3 scripts/package.py build appimage` cria um AppImage no Linux. O workflow de GitHub Actions gera AppImage, DEB e MSI em tags `v*` ou por execução manual; consulte [o workflow](.github/workflows/package.yml) para os requisitos de cada sistema.

## Código

A tela inicial está em `src/main/`.{SKILL_README}''')
        write_skill_guidance(root, "desktop")
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


def create_android(name: str, mode: str, display_name: str, output_root: Path,
                   workspace: Path | None, min_sdk: int) -> Path:
    """Generate an Android client against the framework's Android bridge sources."""
    destination = output_root / name
    if destination.exists():
        raise FileExistsError(f"Project already exists: {destination}")
    output_root.mkdir(parents=True, exist_ok=True)
    package = "megalodonte.app." + name.replace("-", "_")
    package_path = package.replace(".", "/")
    java_title = json.dumps(display_name, ensure_ascii=False)
    xml_title = escape(display_name, {'"': '&quot;'})
    framework = workspace / "framework/megalodonte-android" if workspace else None
    relative_framework = (Path(os.path.relpath(framework, destination)).as_posix()
                          if framework and framework.is_dir() else "framework/megalodonte-android")
    with tempfile.TemporaryDirectory(prefix="megalodonte-new-", dir=output_root) as temporary:
        root = Path(temporary)
        write(root / "settings.gradle.kts", f'''pluginManagement {{ repositories {{ google(); mavenCentral(); gradlePluginPortal() }} }}
dependencyResolutionManagement {{ repositories {{ google(); mavenCentral() }} }}
rootProject.name = "{name}"
include(":app", ":framework-core", ":android-bridge")
val framework = file(System.getenv("MEGALODONTE_ANDROID_HOME") ?: "{relative_framework}")
require(framework.resolve("android-bridge/build.gradle.kts").isFile) {{
    "Set MEGALODONTE_ANDROID_HOME to a checkout of megalodonte-android"
}}
project(":framework-core").projectDir = framework.resolve("framework-core")
project(":android-bridge").projectDir = framework.resolve("android-bridge")
includeBuild(framework.resolve("../libraries/megalodonte-core"))
includeBuild(framework.resolve("../libraries/megalodonte-theme"))
includeBuild(framework.resolve("../libraries/megalodonte-reactivity-portable"))''')
        write(root / "build.gradle.kts", '''plugins {
    id("com.android.application") version "9.0.1" apply false
    id("com.android.library") version "9.0.1" apply false
}''')
        write(root / "app/build.gradle.kts", f'''plugins {{ id("com.android.application") }}
android {{
    namespace = "{package}"
    compileSdk = 35
    defaultConfig {{
        applicationId = "{package}"
        minSdk = {min_sdk}
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0"
    }}
    compileOptions {{
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
        isCoreLibraryDesugaringEnabled = true
    }}
}}
dependencies {{
    implementation(project(":framework-core"))
    implementation(project(":android-bridge"))
    implementation("megalodonte:megalodonte-theme:1.0.0-beta")
    coreLibraryDesugaring("com.android.tools:desugar_jdk_libs:2.1.5")
}}
val verifyAndroidDependencies = tasks.register("verifyAndroidDependencies") {{
    doLast {{
        configurations.getByName("debugRuntimeClasspath").incoming.resolutionResult.allComponents.forEach {{ component ->
            val module = component.moduleVersion ?: return@forEach
            check(module.group != "org.openjfx") {{ "JavaFX must not be packaged in Android: $module" }}
        }}
    }}
}}
tasks.named("check") {{ dependsOn(verifyAndroidDependencies) }}''')
        write(root / "gradle.properties", "org.gradle.jvmargs=-Xmx2048m -Dfile.encoding=UTF-8")
        write(root / ".gitignore", ".gradle/\nbuild/\napp/build/\nlocal.properties\n.idea/\n*.iml")
        write(root / "app/src/main/AndroidManifest.xml", f'''<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <application android:label="{xml_title}" android:icon="@drawable/ic_megalodonte"
        android:theme="@android:style/Theme.Material.Light.NoActionBar" android:supportsRtl="true">
        <activity android:name="{package}.MainActivity" android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>''')
        write(root / "app/src/main/res/drawable/ic_megalodonte.xml", '''<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <corners android:radius="12dp"/><solid android:color="#17384a"/>
</shape>''')
        java = root / "app/src/main/java" / package_path
        if mode == "native":
            write(java / "MainActivity.java", f'''package {package};

import megalodonte.android.bridge.MegalodonteActivity;
import megalodonte.application.MegalodonteApp;
import megalodonte.base.theme.ThemeManager;
import megalodonte.theme.DefaultTheme;

public final class MainActivity extends MegalodonteActivity {{
    @Override protected void main() {{
        ThemeManager.setTheme(new DefaultTheme());
        MegalodonteApp.run(context -> context.useView(new HomeScreen()));
    }}
}}''')
            write(java / "HomeScreen.java", f'''package {package};

import megalodonte.base.components.Component;
import megalodonte.base.components.ScreenComponent;
import megalodonte.components.Text;
import megalodonte.components.layout_components.Container;
import megalodonte.props.ContainerProps;
import megalodonte.props.TextProps;

public final class HomeScreen implements ScreenComponent {{
    @Override public Component render() {{
        return new Container(new ContainerProps().paddingAll(24)).children(
                new Text({java_title}, new TextProps().fontSize(28)));
    }}
}}''')
        else:
            write(root / "app/src/main/assets/views/home.view.jsonc", json.dumps({
                "version": 1, "id": "home", "states": {"message": {"type": "string", "initial": ""}},
                "view": {"type": "Column",
                "props": {"padding": 24, "spacing": 12, "fillWidth": True},
                "children": [{"type": "Text", "props": {"text": display_name}, "style": {"fontSize": 28}},
                             {"type": "Text", "props": {"text": "Seu aplicativo Megalodonte está pronto."}},
                             {"type": "Button", "props": {"text": "Começar", "action": "start"}},
                             {"type": "Text", "props": {"bind": "message"}}]}
            }, ensure_ascii=False, indent=2))
            write(java / "MainActivity.java", f'''package {package};

import java.nio.charset.StandardCharsets;
import megalodonte.android.bridge.AndroidJsoncScreen;
import megalodonte.android.bridge.MegalodonteActivity;
import megalodonte.application.MegalodonteApp;
import megalodonte.base.theme.ThemeManager;
import megalodonte.theme.DefaultTheme;

public final class MainActivity extends MegalodonteActivity {{
    @Override protected void main() {{
        try (var stream = getAssets().open("views/home.view.jsonc")) {{
            String jsonc = new String(stream.readAllBytes(), StandardCharsets.UTF_8);
            ThemeManager.setTheme(new DefaultTheme());
            AndroidJsoncScreen screen = new AndroidJsoncScreen(jsonc);
            screen.onAction(action -> {{
                if ("start".equals(action)) screen.setState("message", "Tudo pronto!");
                else throw new IllegalArgumentException("Unknown action: " + action);
            }});
            MegalodonteApp.run(context -> context.useView(screen));
        }} catch (java.io.IOException error) {{
            throw new IllegalStateException("Cannot load home.view.jsonc", error);
        }}
    }}
}}''')
        for item in ("gradlew", "gradlew.bat"):
            shutil.copy2(ASSETS / item, root / item)
        shutil.copytree(ASSETS / "gradle/wrapper", root / "gradle/wrapper")
        write(root / "README.md", f'''# {display_name}

Megalodonte Android application using **{mode}** UI. It supports Android API {min_sdk} and later, and targets API 35.
Its screen uses only Megalodonte components; JSONC is rendered by the Android bridge.
The [Android JSONC guide](https://github.com/eliezer-dev-software-enginner/megalodonte-android/blob/main/docs/JSONC_ANDROID.md)
lists the supported component types, bindings and platform-specific properties.

Install JDK 25 and Android SDK Platform 35. Clone `megalodonte-android`,
`megalodonte-core`, `megalodonte-theme`, and `megalodonte-reactivity-portable`
under this project's `framework/` directory, or set
`MEGALODONTE_ANDROID_HOME` to the Android framework checkout. Then run:

```sh
./gradlew :app:assembleDebug :app:lintDebug
```

The APK is `app/build/outputs/apk/debug/app-debug.apk`. Open this directory in
Android Studio to run on a compatible device or emulator. If its editor shows
an import or constructor error while Gradle builds successfully, use **Sync
Project with Gradle Files** to refresh the local framework modules.{SKILL_README}''')
        write_skill_guidance(root, "android")
        write(root / ".github/workflows/android.yml", '''name: Build Android APK
on:
  workflow_dispatch:
  push:
    branches: [main]
jobs:
  apk:
    runs-on: ubuntu-latest
    env:
      MEGALODONTE_ANDROID_HOME: framework/megalodonte-android
    steps:
      - uses: actions/checkout@v4
      - uses: actions/checkout@v4
        with:
          repository: eliezer-dev-software-enginner/megalodonte-android
          path: framework/megalodonte-android
      - uses: actions/checkout@v4
        with:
          repository: eliezer-dev-software-enginner/megalodonte-core
          path: framework/libraries/megalodonte-core
      - uses: actions/checkout@v4
        with:
          repository: eliezer-dev-software-enginner/megalodonte-theme
          path: framework/libraries/megalodonte-theme
      - uses: actions/checkout@v4
        with:
          repository: eliezer-dev-software-enginner/megalodonte-reactivity-portable
          path: framework/libraries/megalodonte-reactivity-portable
      - uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: '25'
      - uses: android-actions/setup-android@v3
      - run: sdkmanager "platforms;android-35" "build-tools;36.0.0"
      - run: ./gradlew :app:assembleDebug :app:lintDebug :app:check
      - uses: actions/upload-artifact@v4
        with:
          name: android-debug-apk
          path: app/build/outputs/apk/debug/*.apk''')
        root.rename(destination)
    subprocess.run(["git", "init", "-q", "-b", "main", str(destination)], check=True)
    if workspace and output_root == (workspace / "applications").resolve():
        with (workspace / "workspace.toml").open("a", encoding="utf-8") as stream:
            stream.write(f'\n[[repositories]]\npath = "applications/{name}"\nlocal_only = true\n')
    return destination


def create_roku(name: str, display_name: str, output_root: Path,
                workspace: Path | None) -> Path:
    """Generate a Java-authored SceneGraph app and a sideloadable ZIP build."""
    destination = output_root / name
    if destination.exists():
        raise FileExistsError(f"Project already exists: {destination}")
    output_root.mkdir(parents=True, exist_ok=True)
    package = "megalodonte.app." + name.replace("-", "_")
    package_path = package.replace(".", "/")
    java_title = json.dumps(display_name, ensure_ascii=False)
    framework = workspace / "framework/megalodonte-roku" if workspace else None
    relative_framework = (Path(os.path.relpath(framework, destination)).as_posix()
                          if framework and framework.is_dir() else "framework/megalodonte-roku")
    with tempfile.TemporaryDirectory(prefix="megalodonte-new-", dir=output_root) as temporary:
        root = Path(temporary)
        write(root / "settings.gradle.kts", f'''rootProject.name = "{name}"
val roku = file(System.getenv("MEGALODONTE_ROKU_HOME") ?: "{relative_framework}")
require(roku.resolve("build.gradle.kts").isFile) {{
    "Set MEGALODONTE_ROKU_HOME to a checkout of megalodonte-roku"
}}
includeBuild(roku)''')
        write(root / "build.gradle.kts", f'''plugins {{ java }}
group = "megalodonte.app"
version = "0.1.0"
repositories {{ mavenCentral() }}
java {{ toolchain {{ languageVersion.set(JavaLanguageVersion.of(25)) }} }}
dependencies {{ implementation("megalodonte:megalodonte-roku:0.1.0") }}
tasks.register<JavaExec>("packageRoku") {{
    group = "distribution"
    description = "Generate a Roku sideload ZIP from the Java screen"
    classpath = sourceSets.main.get().runtimeClasspath
    mainClass.set("megalodonte.roku.RokuExporter")
    args("{package}.HomeScreen", {java_title}, "build/roku/{name}.zip")
}}''')
        write(root / f"src/main/java/{package_path}/HomeScreen.java", f'''package {package};

import megalodonte.roku.RokuScene;
import megalodonte.roku.RokuScreen;
import megalodonte.components.Button;
import megalodonte.components.Counter;
import megalodonte.components.Text;
import megalodonte.theme.Theme;
import megalodonte.application.Router;
import java.util.List;

public final class HomeScreen implements RokuScreen {{
    @Override public Theme theme() {{
        return new Theme("0x142536FF", "0x7CE0D6FF", "0xFFFFFFFF", "0x31566EFF", "0x237E9DFF");
    }}

    @Override public RokuScene render() {{
        return new RokuScene("home", {java_title},
                "Use as setas e OK do controle remoto para navegar.",
                new Text("Feito com Megalodonte", 100, 100, 800, 70),
                new Button("Sobre o projeto", "about"),
                new Button("Contador reativo", "counter"));
    }}

    @Override public List<RokuScene> pages() {{
        return new Router().route(render())
                .route(new RokuScene("about", "Criado em Java",
                        "O build Megalodonte gerou esta tela nativa SceneGraph.",
                        new Button("Voltar ao início", "home")))
                .route(new RokuScene("counter", "Estado na Roku",
                        "Pressione OK para mudar o valor sem reiniciar o aplicativo.",
                        new Counter("Cliques", 0), Button.increment("Incrementar"),
                        new Button("Voltar ao início", "home"))).pages();
    }}
}}''')
        write(root / "README.md", f'''# {display_name}

A Megalodonte Roku example authored in Java. The Java screen runs **at build time**;
the output is native Roku SceneGraph XML and BrightScript, not a JVM on the TV.
It has Home, About, and Counter routes. Up/Down selects a button, OK activates
it, and Back returns to the previous page. The counter label updates at runtime.

Requires JDK 25 and a checkout of `megalodonte-roku`. In the Megalodonte workspace,
the CLI wires its path automatically. Else set `MEGALODONTE_ROKU_HOME` to that checkout.

```sh
./gradlew packageRoku
```

Upload `build/roku/{name}.zip` in your Roku's Development Application Installer.
Enable developer mode first, open the device URL in a browser, and sign in as
`rokudev` with your developer password. The ZIP contains `manifest`, `source/`,
`components/`, and `images/` at its root. Only one sideloaded app can be installed
at a time. Edit `src/main/java/{package_path}/HomeScreen.java`, rebuild, and
upload the new ZIP to see changes.{SKILL_README}''')
        write_skill_guidance(root, "roku")
        write(root / ".gitignore", ".gradle/\nbuild/\n.idea/\n*.iml")
        for item in ("gradlew", "gradlew.bat"):
            shutil.copy2(ASSETS / item, root / item)
        shutil.copytree(ASSETS / "gradle/wrapper", root / "gradle/wrapper")
        write(root / ".github/workflows/roku.yml", '''name: Build Roku ZIP
on: [push, workflow_dispatch]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/checkout@v4
        with:
          repository: eliezer-dev-software-enginner/megalodonte-roku
          path: framework/megalodonte-roku
      - uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: '25'
      - run: ./gradlew packageRoku
        env:
          MEGALODONTE_ROKU_HOME: framework/megalodonte-roku
      - uses: actions/upload-artifact@v4
        with:
          name: roku-sideload-zip
          path: build/roku/*.zip''')
        root.rename(destination)
    subprocess.run(["git", "init", "-q", "-b", "main", str(destination)], check=True)
    if workspace and output_root == (workspace / "applications").resolve():
        with (workspace / "workspace.toml").open("a", encoding="utf-8") as stream:
            stream.write(f'\n[[repositories]]\npath = "applications/{name}"\nlocal_only = true\n')
    return destination


def main() -> None:
    if len(sys.argv) >= 2 and sys.argv[1] == "skills":
        skills_parser = argparse.ArgumentParser(description="Manage bundled Megalodonte skills")
        skills_parser.add_argument("skills", choices=("skills",))
        skills_parser.add_argument("action", choices=("sync", "install"))
        skills_parser.add_argument("--project", type=Path, default=Path.cwd())
        skills_args = skills_parser.parse_args()
        try:
            result = (sync_skills(skills_args.project) if skills_args.action == "sync"
                      else install_skills(skills_args.project))
            print(result)
        except (ValueError, FileExistsError, OSError) as error:
            skills_parser.exit(1, f"Skill operation failed: {error}\n")
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="Lowercase project name, for example my-app")
    parser.add_argument("--mode", choices=("jsonc", "native"), required=True)
    parser.add_argument("--platform", choices=("desktop", "android", "roku"), default="desktop")
    parser.add_argument("--min-sdk", type=int, default=35, help="Minimum Android API level (25–35; default 35)")
    parser.add_argument("--display-name", help="Window and installer name (default: project name)")
    parser.add_argument("--output-root", type=Path, default=Path.cwd())
    parser.add_argument("--workspace", type=Path, help="Megalodonte workspace root for local source builds")
    args = parser.parse_args()
    try:
        print(create(args.name, args.mode, args.display_name or args.name,
                     args.output_root, args.workspace, args.platform, args.min_sdk))
    except (ValueError, FileExistsError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Project creation failed: {error}\n")


if __name__ == "__main__":
    main()

# Megalodonte CLI

Create desktop and Android applications with Megalodonte. The CLI supports declarative JSONC views (`jsonc`) and Java screens composed from Megalodonte components (`native`) on both platforms. It generates a Gradle build, wrapper, starter screen, GitHub Actions workflow, icon, and local Git repository. Desktop projects also receive AppImage, DEB and MSI packaging.

## Install

Requires Python 3.11 or later. From this repository:

```sh
python3 -m pip install --user .
```

For an editable development installation, use `python3 -m pip install -e .` in a virtual environment.

## Create an application

From the desired parent directory:

```sh
megalodonte my-app --mode jsonc --display-name "My App"
megalodonte another-app --mode native
megalodonte phone-app --platform android --mode native
megalodonte phone-jsonc --platform android --mode jsonc
```

On desktop, `jsonc` creates a declarative starter view and a Java `ViewScript`; `native` creates a Java screen composed from Megalodonte components. On Android, `native` creates a `ScreenComponent`; `jsonc` stores the view under `app/src/main/assets/views/` and renders it through the Android bridge. The Android JSONC renderer currently supports Text, Button, Column, Row and Container, string states bound to Text, and Button actions handled in Java. Unsupported types fail explicitly. The project is created in `./my-app` (or the chosen `--output-root`). The CLI also runs `git init`, so Git must be available. Names must start with a lowercase letter and may contain lowercase letters, digits, and single hyphens between groups; `--mode` is required. Desktop builds target Java 25 and JavaFX 25.0.1. To test and launch a desktop project:

```sh
cd my-app
./gradlew test
./gradlew run
```

Gradle needs a Java 25 toolchain. The wrapper may download Gradle, and the build needs its Megalodonte dependencies from Maven local, Maven Central, or the local workspace builds described below.

For local Linux AppImage packaging, install the separate `megalodonte-packaging` Python library, then run `python3 scripts/package.py build appimage` from the generated project. The generated packaging script can also locate that library's source in a sibling `framework/megalodonte-packaging/src` directory, or via `MEGALODONTE_PACKAGING_HOME` pointing to its repository root. The generated GitHub Actions caller invokes the shared `megalodonte-packaging` workflow to build AppImage, DEB, and MSI installers on a `v*` tag or manual dispatch; configure a GitHub remote before pushing a tag.

Inside `megalodonte-world`, pass `--output-root applications --workspace .` to register the new app in `workspace.toml` and include the framework's local source builds. Outside the workspace, the generated Gradle build uses published dependencies from Maven local or Maven Central. The workflow uses the shared `megalodonte-packaging` reusable workflow.

## Android projects

Android projects target API 35 and compile Java 17 source. Install JDK 25 and Android SDK Platform 35, then run `./gradlew :app:assembleDebug :app:lintDebug`; the APK is under `app/build/outputs/apk/debug/`. The project uses the source modules in `megalodonte-android` and shared core, theme and portable reactivity libraries. When it is outside `megalodonte-world`, put these checkouts under the project's `framework/` directory or set `MEGALODONTE_ANDROID_HOME` to the Android backend checkout (with the shared libraries in its sibling `libraries/` directory). The generated workflow checks out these sources and uploads a debug APK. Android projects do not use JavaFX or desktop packaging.

## Development

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Keep the generated workflow aligned with `megalodonte-packaging/tools/configure_client_actions.py` when the shared packaging contract changes.

The repository's GitHub Actions workflow tests the installed command and checks that its bundled Gradle wrapper and packaging assets are present. Local end-to-end validation on 2026-10-15 also compiled newly generated JSONC and native applications using the workspace composite builds (`./gradlew test --offline` in each generated application).

## License

No license file is included in this repository. Usage and redistribution terms need confirmation from the project owner.

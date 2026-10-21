# Megalodonte CLI

Create desktop, Android, and Roku applications with Megalodonte. Desktop and Android support declarative JSONC views (`jsonc`) and Java screens (`native`). Roku initially supports Java-authored native screens: Java runs at build time and produces SceneGraph XML and BrightScript for the TV. The CLI generates a Gradle build, wrapper, starter screen, GitHub Actions workflow, icon, and local Git repository. Desktop projects also receive AppImage, DEB and MSI packaging.

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
megalodonte roku-hello-world --platform roku --mode native --display-name "Megalodonte Roku Hello"
```

On desktop, `jsonc` creates a declarative starter view and a Java `ViewScript`; `native` creates a Java screen composed from Megalodonte components. On Android, `native` creates a `ScreenComponent`; `jsonc` stores the view under `app/src/main/assets/views/` and renders it through the Android bridge. See the [Android component guide](https://github.com/eliezer-dev-software-enginner/megalodonte-android/blob/main/docs/JSONC_ANDROID.md) for supported components, behavior, and property differences from desktop. The project is created in `./my-app` (or the chosen `--output-root`). The CLI also runs `git init`, so Git must be available. Names must start with a lowercase letter and may contain lowercase letters, digits, and single hyphens between groups; `--mode` is required. Desktop builds target Java 25 and JavaFX 25.0.1. To test and launch a desktop project:

```sh
cd my-app
./gradlew test
./gradlew run
```

Gradle needs a Java 25 toolchain. The wrapper may download Gradle, and the build needs its Megalodonte dependencies from Maven local, Maven Central, or the local workspace builds described below.

For local Linux AppImage packaging, install the separate `megalodonte-packaging` Python library, then run `python3 scripts/package.py build appimage` from the generated project. The generated packaging script can also locate that library's source in a sibling `framework/megalodonte-packaging/src` directory, or via `MEGALODONTE_PACKAGING_HOME` pointing to its repository root. The generated GitHub Actions caller invokes the shared `megalodonte-packaging` workflow to build AppImage, DEB, and MSI installers on a `v*` tag or manual dispatch; configure a GitHub remote before pushing a tag.

Inside `megalodonte-world`, pass `--output-root applications --workspace .` to register the new app in `workspace.toml` and include the framework's local source builds. Outside the workspace, the generated Gradle build uses published dependencies from Maven local or Maven Central. The workflow uses the shared `megalodonte-packaging` reusable workflow.

## Android projects

Android projects require Android 15 (API 35) or later: their minimum and target SDK are both 35. They compile Java 17 source. Install JDK 25 and Android SDK Platform 35. The project uses the source modules in `megalodonte-android` and the shared core, theme and portable reactivity libraries. Outside `megalodonte-world`, place the source checkouts relative to the generated project as follows:

```text
my-app/
  framework/
    megalodonte-android/
    libraries/
      megalodonte-core/
      megalodonte-theme/
      megalodonte-reactivity-portable/
```

Alternatively, set `MEGALODONTE_ANDROID_HOME` to the `megalodonte-android` checkout; its sibling `libraries/` directory must still contain the three shared library checkouts. From the generated project, run:

```sh
./gradlew :app:assembleDebug :app:lintDebug
```

The debug APK is `app/build/outputs/apk/debug/app-debug.apk`. The generated workflow checks out these sources and uploads a debug APK. Android projects do not use JavaFX or desktop packaging.

## Roku

`--platform roku --mode native` generates a Java `HomeScreen` using
`megalodonte-roku`. Run `./gradlew packageRoku`; the result is
`build/roku/<project>.zip`, ready for Roku Developer Mode sideloading. Set
`MEGALODONTE_ROKU_HOME` to a checkout of `megalodonte-roku` when the project is
outside this workspace. The first Roku component set is a heading and message;
arbitrary Java code and desktop/Android components cannot run on Roku. The
generated BrightScript can be checked with the BrighterScript CLI (`bsc`).

## Development

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Keep the generated workflow aligned with `megalodonte-packaging/tools/configure_client_actions.py` when the shared packaging contract changes.

The repository's GitHub Actions workflow tests the installed command and checks that its bundled Gradle wrapper and packaging assets are present. Local end-to-end validation on 2026-10-15 also compiled newly generated JSONC and native applications using the workspace composite builds (`./gradlew test --offline` in each generated application).

## License

No license file is included in this repository. Usage and redistribution terms need confirmation from the project owner.

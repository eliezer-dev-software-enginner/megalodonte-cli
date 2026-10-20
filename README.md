# Megalodonte CLI

Create JavaFX desktop applications using the Megalodonte framework. The CLI is a standalone Python package with two UI modes: declarative JSONC views (`jsonc`) and Java screens composed from Megalodonte components (`native`). It generates a Gradle build, wrapper, starter screen, packaging configuration, standard GitHub Actions caller, icon, and local Git repository.

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
```

The project is created in `./my-app` (or the chosen `--output-root`). The CLI also runs `git init`, so Git must be available. Names must use lowercase letters, digits, and hyphens, starting with a letter; `--mode` is required. The generated Gradle build targets Java 25 and JavaFX 25.0.1. From the new project, run `./gradlew test` to test it and `./gradlew run` to launch it, with a Java 25 toolchain available to Gradle. The wrapper may download Gradle and the build needs its Megalodonte dependencies from Maven local, Maven Central, or the local workspace builds described below.

For local Linux AppImage packaging, install the separate `megalodonte-packaging` Python library, then run `python3 scripts/package.py build appimage` from the generated project. The generated packaging script can also locate that library's source in a sibling `framework/megalodonte-packaging/src` directory, or via `MEGALODONTE_PACKAGING_HOME` pointing to its repository root. The generated GitHub Actions caller invokes the shared `megalodonte-packaging` workflow to build AppImage, DEB, and MSI installers on a `v*` tag or manual dispatch; configure a GitHub remote before pushing a tag.

Inside `megalodonte-world`, pass `--output-root applications --workspace .` to register the new app in `workspace.toml` and include the framework's local source builds. Outside the workspace, the generated Gradle build uses published dependencies from Maven local or Maven Central. The workflow uses the shared `megalodonte-packaging` reusable workflow.

## Development

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Keep the generated workflow aligned with `megalodonte-packaging/tools/configure_client_actions.py` when the shared packaging contract changes.

The repository's GitHub Actions workflow tests the installed command and checks that its bundled Gradle wrapper and packaging assets are present. Local end-to-end validation on 2026-10-15 also compiled newly generated JSONC and native applications using the workspace composite builds (`./gradlew test --offline` in each generated application).

## License

No license file is included in this repository. Usage and redistribution terms need confirmation from the project owner.

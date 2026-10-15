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

The project is created in `./my-app` (or the chosen `--output-root`). Run `./gradlew test` and `./gradlew run` from the new project. Use `python3 scripts/package.py build appimage` for local Linux packaging. Push a `v*` tag to run the generated AppImage, DEB, and MSI workflow after configuring a GitHub remote.

Inside `megalodonte-world`, pass `--output-root applications --workspace .` to register the new app in `workspace.toml` and include the framework's local source builds. Outside the workspace, the generated Gradle build uses published dependencies from Maven local or Maven Central. The workflow uses the shared `megalodonte-packaging` reusable workflow.

## Development

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Keep the generated workflow aligned with `megalodonte-packaging/tools/configure_client_actions.py` when the shared packaging contract changes.

The repository's GitHub Actions workflow tests the installed command and checks that its bundled Gradle wrapper and packaging assets are present. Local end-to-end validation on 2026-10-15 also compiled newly generated JSONC and native applications using the workspace composite builds (`./gradlew test --offline` in each generated application).

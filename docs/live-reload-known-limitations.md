# Live reload: composite builds and remaining limits

## Fixed: init script applied to included libraries

The initial implementation failed on Minastex during configuration of
`:megalodonte-core`, reporting `Live reload requires a single-project desktop
application plugin build`. Gradle propagates init scripts to included builds;
the application guard and shadow output override were incorrectly applied to
library builds too. An isolated generated-app test did not cover this topology.

The CLI now passes the supervised application's directory through
`megalodonte.live.project`. Before mutating any build, the init script compares
that canonical path with the current root project directory. Only the matching
application receives the shadow output, application checks and prepare task.
Included builds and buildSrc keep their ordinary outputs. No application settings
change or `useLocalSources=false` workaround is required.

## Validation

### Fixed: second compilation lost included library classes

The subsequent Minastex report showed a successful initial build followed by
missing `megalodonte.base.theme` classes in the second build. The
[reported log](diagnostics/minastex-live-reload-second-build.txt) is preserved
with the workstation path anonymized. Reproduction required no source edits:
two prepare calls in the same session were sufficient. The core JAR ended up
containing only its manifest, and Gradle reported compiler options changing
between tasks from different builds despite unchanged build scripts.

The CLI no longer passes a shared `--project-cache-dir`. Gradle now retains its
normal per-build `.gradle` metadata while the application's compiled output stays
in the temporary shadow directory. With this change, three consecutive prepare
calls on the real Minastex succeeded and unchanged compilation tasks were
`UP-TO-DATE`. There is no need to delete user caches or run `clean` on each edit.
This follows Gradle's distinction between
[project-specific cache and build output](https://docs.gradle.org/current/userguide/directory_layout.html).

The integration fixture now includes a nested library, calls its API from the
outer library, and calls that library from the app. After editing the app it
checks that dependency hashes are unchanged and both JARs still contain their
expected classes, in addition to checking reload in the same process.

- The real Minastex composite build successfully ran `megalodonteLivePrepare`,
  compiled the application into the temporary session and produced a valid
  launcher descriptor for `minastex_pedidos.Main`. This check did not launch
  Minastex or exercise its business workflows.
- `tests/integration_live_reload.py` now includes a local Java library through
  `includeBuild`. It checks the library's own JAR output and isolation from the
  application's shadow classes, then runs the app and verifies reload in the
  same process, compilation-error recovery and the dependency restart guard.

Run the integration check explicitly with a display, JDK 25 and locally published
framework artifacts:

```sh
PYTHONPATH=src python tests/integration_live_reload.py
```

## Remaining limits

The supervised application must still be a single-project, non-modular desktop
build using Gradle's application plugin. This restriction does not apply to its
included library builds. Library outputs may be compiled in their usual build
directories; the application output and active runtime mirror are isolated.

Library source trees are not watched automatically. Stop/start the session after
editing them to rebuild and freeze the new dependency JARs. Changes to resolved
dependency contents, launch configuration or Java class structure automatically
restart the application child in a regular `megalodonte dev` session; adding JARs
to an already running class loader is not supported. In-memory application state
is lost on that fallback. Framework-managed windows created again during startup
restore their saved bounds, window mode and foreground/background intent.
JavaFX cannot portably restore an exact OS z-order, and secondary windows that
startup does not recreate remain closed. `--no-restart-on-incompatible` keeps
the previous generation active instead.

Structural Java edits, cached JSONC views, custom launch hooks and unmanaged
windows retain the limits described in the
[base live reload guide](https://github.com/eliezer-dev-software-enginner/megalodonte-base/blob/main/docs/LIVE_RELOAD.md).

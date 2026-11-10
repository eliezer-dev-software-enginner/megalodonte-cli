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
dependency contents or launch configuration require a restart; adding JARs to an
already running class loader is not supported. In-memory state is lost on restart.

Structural Java edits, cached JSONC views, custom launch hooks and unmanaged
windows retain the limits described in the
[base live reload guide](https://github.com/eliezer-dev-software-enginner/megalodonte-base/blob/main/docs/LIVE_RELOAD.md).

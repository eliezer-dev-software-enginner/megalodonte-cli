"""Incremental shadow compilation and explicit JVM live-reload supervision."""
from __future__ import annotations

import argparse
import hashlib
from importlib.resources import files
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import zipfile


def fingerprint(paths: list[Path]) -> dict[str, str]:
    """Content hashes avoid recompiling on timestamp-only editor saves."""
    result = {}
    for root in paths:
        candidates = sorted(root.rglob('*')) if root.is_dir() else [root]
        for path in candidates:
            if path.is_file():
                result[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


class SourceWatcher:
    """Cache content hashes between polls; an editor timestamp alone is not a change."""
    def __init__(self):
        self.cache = {}

    def scan(self, paths: list[Path]) -> dict[str, str]:
        result = {}
        fresh = {}
        for root in paths:
            candidates = sorted(root.rglob('*')) if root.is_dir() else [root]
            for path in candidates:
                if root.name == 'buildSrc' and set(path.relative_to(root).parts) & {'build', '.gradle'}:
                    continue
                try:
                    if not path.is_file():
                        continue
                    stat = path.stat()
                    stamp = (stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size, stat.st_ino)
                    cached = self.cache.get(str(path))
                    digest = cached[1] if cached and cached[0] == stamp else hashlib.sha256(path.read_bytes()).hexdigest()
                except FileNotFoundError:
                    continue  # common during editor atomic-save rename
                fresh[str(path)] = (stamp, digest)
                result[str(path)] = digest
        self.cache = fresh
        return result


def snapshot(outputs: list[str], target: Path) -> None:
    """Freeze successful classes/resources; conflicting resource roots are rejected."""
    target.mkdir(parents=True)
    for directory in outputs:
        source = Path(directory)
        if not source.exists():
            continue
        for path in source.rglob('*'):
            if not path.is_file():
                continue
            destination = target / path.relative_to(source)
            if destination.exists():
                raise ValueError(f'Duplicate runtime output: {destination.relative_to(target)}')
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)


def dependencies(description: dict) -> list[Path]:
    output = {Path(path).resolve() for path in description['outputs']}
    return [Path(path).resolve() for path in description['classpath'] if Path(path).resolve() not in output]


def agent_jar(description: dict) -> Path:
    for path in dependencies(description):
        if path.suffix != '.jar':
            continue
        with zipfile.ZipFile(path) as jar:
            if 'META-INF/MANIFEST.MF' not in jar.namelist():
                continue
            manifest = jar.read('META-INF/MANIFEST.MF').decode('utf-8')
            if 'Premain-Class: megalodonte.application.reload.ReloadAgent' in manifest:
                return path
    raise ValueError('Update/publish megalodonte-base locally: its JAR must contain ReloadAgent')


def launch_command(description: dict, session: Path) -> list[str]:
    jars = dependencies(description)
    # JavaFX native modules must be on the module path; application/framework code
    # uses the system class loader so JVM Instrumentation can redefine it in place.
    fx = [path for path in jars if path.name.startswith('javafx-') and path.suffix == '.jar'
          and any(part in path.name for part in ('-linux', '-win', '-mac'))]
    cp = [session / 'active', *(path for path in jars if path not in fx)]
    options = list(description['jvmArgs'])
    if any(arg == '--module-path' or arg.startswith('--module-path=') or arg == '-p' for arg in options):
        raise ValueError('Custom module paths are not supported by megalodonte dev')
    if fx:
        options += ['--module-path', os.pathsep.join(map(str, fx)), '--add-modules', 'ALL-MODULE-PATH']
    return [description['java'], *options, f'-javaagent:{agent_jar(description)}={session}',
            '-cp', os.pathsep.join(map(str, cp)), description['main'], *description['args']]


def runtime_signature(description: dict) -> tuple:
    """Detect changed JAR contents as well as dependency paths and launch settings."""
    return (json.dumps({key: value for key, value in description.items()
                        if key not in {'outputs', 'watch'}}, sort_keys=True), fingerprint(dependencies(description)))


class DevelopmentSession:
    def __init__(self, project: Path, session: Path, offline: bool, restart: bool):
        self.project, self.session = project.resolve(), session
        self.offline, self.restart = offline, restart
        self.process = None
        self.description = None
        self.signature = None
        self.generation = 0
        self.last_good = None
        self.watcher = SourceWatcher()
        self.watch = [self.project / 'src', self.project / 'build.gradle.kts', self.project / 'build.gradle',
                      self.project / 'settings.gradle.kts', self.project / 'settings.gradle',
                      self.project / 'gradle.properties', self.project / 'gradle', self.project / 'buildSrc']

    def prepare(self) -> dict | None:
        wrapper = self.project / ('gradlew.bat' if os.name == 'nt' else 'gradlew')
        if not wrapper.is_file():
            raise ValueError(f'Gradle wrapper not found in {self.project}')
        init = files('megalodonte_cli').joinpath('assets/live-reload.init.gradle')
        command = ([str(wrapper)] if os.name == 'nt' else ['bash', str(wrapper)])
        # Keep Gradle's per-build caches: overriding project-cache-dir can share
        # execution history between root tasks in nested composite builds.
        command += ['--console=plain',
                    f'-Dmegalodonte.live.project={self.project}',
                    f'-Dmegalodonte.live.session={self.session}', '--init-script', str(init),
                    'megalodonteLivePrepare']
        if self.offline:
            command.append('--offline')
        print('[live-reload] Compiling shadow world (Gradle incremental build)...', flush=True)
        result = subprocess.run(command, cwd=self.project)
        if result.returncode:
            print('[live-reload] Build failed; running application was not changed.', flush=True)
            return None
        return json.loads((self.session / 'launch.json').read_text(encoding='utf-8'))

    def start(self, description: dict, generation: Path) -> None:
        # Validate launch support before stopping an existing process.
        command = launch_command(description, self.session)
        self.stop()
        active = self.session / 'active'
        if active.exists():
            shutil.rmtree(active)  # owned temporary mirror only, never project source/data
        shutil.copytree(generation, active)
        # Dependencies are frozen too: an unrelated Maven Local publication must
        # not silently replace code/resources beneath the running JVM.
        frozen = self.session / f'libraries-{self.generation}'
        frozen.mkdir()
        copied = []
        for index, source in enumerate(dependencies(description)):
            target = frozen / str(index) / source.name
            target.parent.mkdir()
            if source.is_dir():
                shutil.copytree(source, target)
            else:
                shutil.copy2(source, target)
            copied.append(str(target))
        launch = {**description, 'classpath': [*description['outputs'], *copied]}
        command = launch_command(launch, self.session)
        for marker in ('request', 'response'):
            (self.session / marker).unlink(missing_ok=True)
        self.process = subprocess.Popen(command, cwd=description['workingDir'],
                                        env={**os.environ, **description.get('environment', {})})
        self.description = description
        self.signature = runtime_signature(description)
        print(f'[live-reload] Application PID {self.process.pid}; world {self.session}', flush=True)

    def stop(self) -> None:
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()

    def reload(self, description: dict, generation: Path) -> bool:
        if self.signature != runtime_signature(description):
            status = 'RESTART_REQUIRED'
            print('[live-reload] Dependencies or launch configuration changed.', flush=True)
        else:
            marker = self.session / 'request.tmp'
            marker.write_text(str(self.generation), encoding='utf-8')
            marker.replace(self.session / 'request')
            started = time.monotonic()
            warned = False
            while self.process.poll() is None:
                response = self.session / 'response'
                if response.exists():
                    lines = response.read_text(encoding='utf-8').splitlines()
                    if len(lines) >= 2 and lines[0] == str(self.generation):
                        status = lines[1]
                        print('[live-reload] ' + ' '.join(lines[1:]), flush=True)
                        break
                if not warned and time.monotonic() - started > 10:
                    print('[live-reload] Waiting for the application UI thread. Ctrl+C stops the session.', flush=True)
                    warned = True
                time.sleep(.1)
            else:
                raise RuntimeError('Application exited before acknowledging reload')
        if status == 'RESTART_REQUIRED':
            if self.restart:
                print('[live-reload] Restarting as requested; in-memory state will reset.', flush=True)
                self.start(description, generation)
                return True
            print('[live-reload] Old version remains active. Stop/start dev, or opt in with --restart-on-incompatible.', flush=True)
        if status == 'FATAL':
            raise RuntimeError('Agent could not roll back the reload; stopping this development session')
        return status == 'APPLIED'

    def build(self, expected: dict) -> bool:
        description = self.prepare()
        if description is None:
            return False
        if self.watcher.scan(self.watch) != expected:
            print('[live-reload] Source changed during compilation; discarding stale result.', flush=True)
            return False
        self.watch = list(dict.fromkeys([*self.watch, *(Path(path) for path in description['watch'])]))
        self.generation += 1
        generation = self.session / 'generations' / str(self.generation)
        snapshot(description['outputs'], generation)
        if self.process is None:
            self.start(description, generation)
            accepted = True
        else:
            accepted = self.reload(description, generation)
        if accepted:
            if self.last_good is not None:
                shutil.rmtree(self.last_good)
            self.last_good = generation
        else:
            shutil.rmtree(generation)
        return accepted

    def run(self, debounce: float) -> int:
        observed = self.watcher.scan(self.watch)
        self.build(observed)
        # Recompute after prepare discovers custom source sets.
        previous = observed
        deadline = None
        while self.process is None or self.process.poll() is None:
            time.sleep(.2)
            current = self.watcher.scan(self.watch)
            if current != previous:
                previous = current
                deadline = time.monotonic() + debounce
            if deadline is not None and time.monotonic() >= deadline:
                self.build(current)
                deadline = None
        return self.process.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=Path.cwd())
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--restart-on-incompatible', action='store_true',
                        help='Restart on structural/dependency changes, losing in-memory state')
    parser.add_argument('--debounce', type=float, default=.6, help='Quiet seconds before compiling (default .6)')
    args = parser.parse_args(argv)
    if not .1 <= args.debounce <= 30:
        parser.error('--debounce must be between .1 and 30 seconds')
    try:
        with tempfile.TemporaryDirectory(prefix='megalodonte-live-') as directory:
            session = DevelopmentSession(args.project, Path(directory), args.offline, args.restart_on_incompatible)
            try:
                return session.run(args.debounce)
            finally:
                session.stop()
    except KeyboardInterrupt:
        print('\n[live-reload] Session stopped.', flush=True)
        return 0
    except (OSError, ValueError, RuntimeError) as error:
        print(f'[live-reload] {error}', flush=True)
        return 1

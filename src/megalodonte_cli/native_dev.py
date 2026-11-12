"""Experimental Java messaging workers with a persistent native window host."""
from __future__ import annotations

import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import threading
import time
import zipfile

from .dev import DevelopmentSession, dependencies, fingerprint, snapshot


def host_dependencies(description: dict) -> list[Path]:
    prefixes = ('megalodonte-base-', 'megalodonte-core-', 'gson-', 'slf4j-api-', 'javafx-', 'error_prone_annotations-')
    return [jar for jar in dependencies(description) if jar.name.startswith(prefixes)]


def native_command(description: dict, jars: list[Path], classes: list[Path], main: str,
                   arguments: list[str], host: bool) -> list[str]:
    options = list(description['jvmArgs'])
    if any(arg in ('--module-path', '-p') or arg.startswith('--module-path=') for arg in options):
        raise ValueError('Custom module paths are not supported by the native messaging host')
    fx = [jar for jar in jars if host and jar.name.startswith('javafx-')
          and any(part in jar.name for part in ('-linux', '-win', '-mac'))]
    if fx:
        options += ['--module-path', os.pathsep.join(map(str, fx)), '--add-modules', 'ALL-MODULE-PATH']
    return [description['java'], *options, '-cp', os.pathsep.join(map(str, [*classes, *(jar for jar in jars if jar not in fx)])),
            main, *arguments]


class NativeDevelopmentSession(DevelopmentSession):
    """Own the host JVM; compiled generations run in separate worker JVMs.

    Generations remain on disk until the session ends, since retired workers may
    still be shutting down when the host acknowledges a successful replacement.
    """
    def __init__(self, project: Path, session: Path, offline: bool, worker_main: str):
        super().__init__(project, session, offline, False)
        self.worker_main = worker_main
        self.control_sequence = 0
        self.received_sequence = 0
        self.responses = queue.Queue(maxsize=4)
        self.host_signature = None
        self.last_result = None

    def _signature(self, description: dict):
        return (description['java'], tuple(description['jvmArgs']), fingerprint(host_dependencies(description)))

    def _freeze(self, jars: list[Path], directory: Path) -> list[Path]:
        directory.mkdir()
        result = []
        for index, jar in enumerate(jars):
            target = directory / str(index) / jar.name
            target.parent.mkdir()
            if jar.is_dir():
                shutil.copytree(jar, target)
            else:
                shutil.copy2(jar, target)
            result.append(target)
        return result

    def _start_host(self, description: dict):
        jars = host_dependencies(description)
        available = False
        for jar in jars:
            if jar.suffix == '.jar':
                with zipfile.ZipFile(jar) as archive:
                    available |= 'megalodonte/application/messaging/NativeHostSupervisor.class' in archive.namelist()
        if not available:
            raise ValueError('Publish/update megalodonte-base: NativeHostSupervisor is required')
        frozen = self._freeze(jars, self.session / 'host-libraries')
        command = native_command(description, frozen, [],
                                 'megalodonte.application.messaging.NativeHostSupervisor', [], True)
        self.process = subprocess.Popen(command, cwd=description['workingDir'],
                                        env={**os.environ, **description.get('environment', {})},
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        text=True, encoding='utf-8')
        self.host_signature = self._signature(description)
        threading.Thread(target=self._read_responses, daemon=True).start()
        print(f'[native-host] Persistent host PID {self.process.pid}', flush=True)

    def _read_responses(self):
        try:
            while True:
                line = self.process.stdout.readline(1024 * 1024 + 1)
                if not line:
                    raise RuntimeError('Native host disconnected')
                if len(line) > 1024 * 1024 or not line.endswith('\n'):
                    raise RuntimeError('Invalid native host frame')
                message = json.loads(line)
                if (message.get('version') != 1 or message.get('generation') != 1
                        or message.get('sequence') != self.received_sequence + 1 or message.get('type') != 'RESULT'):
                    raise RuntimeError('Invalid native host envelope')
                self.received_sequence = message['sequence']
                self.responses.put(message['payload'], timeout=1)
        except Exception as error:
            try:
                self.responses.put(error, timeout=1)
            except queue.Full:
                pass

    def _send(self, kind: str, body: dict):
        self.control_sequence += 1
        message = dict(version=1, generation=1, sequence=self.control_sequence, type=kind, payload=body)
        self.process.stdin.write(json.dumps(message) + '\n')
        self.process.stdin.flush()

    def _replace(self, description: dict, generation: Path) -> bool:
        if self.process is None:
            self._start_host(description)
        elif self.host_signature != self._signature(description):
            print('[native-host] Host runtime changed. Existing windows kept; stop/start is required.', flush=True)
            return False
        jars = self._freeze(dependencies(description), self.session / f'worker-libraries-{self.generation}')
        command = native_command(description, jars, [generation], self.worker_main, description['args'], False)
        self._send('REPLACE', dict(command=command, directory=description['workingDir'],
                                   environment=description.get('environment', {})))
        started = time.monotonic()
        warned = False
        while True:
            try:
                result = self.responses.get(timeout=.2)
            except queue.Empty:
                if self.process.poll() is not None:
                    raise RuntimeError('Native host exited before acknowledging replacement')
                if not warned and time.monotonic() - started > 10:
                    print('[native-host] Waiting for candidate/host. Ctrl+C stops the session.', flush=True)
                    warned = True
                continue
            if isinstance(result, Exception):
                raise RuntimeError(str(result)) from result
            if result.get('request') != self.control_sequence:
                raise RuntimeError('Unexpected native host response sequence')
            self.last_result = result
            print('[native-host] ' + result['status'] + ' ' + result.get('detail',
                  f"generation {result.get('generation')}; {result.get('windows')} windows"), flush=True)
            return result['status'] == 'APPLIED'

    def build(self, expected: dict) -> bool:
        description = self.prepare()
        if description is None:
            return False
        if self.watcher.scan(self.watch) != expected:
            print('[native-host] Source changed during compilation; discarding stale result.', flush=True)
            return False
        self.watch = list(dict.fromkeys([*self.watch, *(Path(path) for path in description['watch'])]))
        self.generation += 1
        generation = self.session / 'generations' / str(self.generation)
        snapshot(description['outputs'], generation)
        accepted = self._replace(description, generation)
        if accepted:
            self.last_good = generation
        return accepted

    def stop(self):
        if self.process is not None and self.process.poll() is None:
            try:
                self._send('CLOSE', {})
                self.process.stdin.close()
                self.process.wait(timeout=3)
            except (OSError, subprocess.TimeoutExpired):
                super().stop()
        if self.process is not None:
            for stream in (self.process.stdin, self.process.stdout):
                if stream is not None:
                    stream.close()

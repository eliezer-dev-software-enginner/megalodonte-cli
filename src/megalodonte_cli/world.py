"""Content-addressed project map used by the live-reload compilation world."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import re
import shutil
from typing import Iterable


PROTOCOL_VERSION = 1
IGNORED_PARTS = {'.git', '.gradle', '.idea', 'build', 'out', 'target', '__pycache__'}
BUILD_FILES = {
    'build.gradle', 'build.gradle.kts', 'settings.gradle', 'settings.gradle.kts',
    'gradle.properties', 'gradle-wrapper.properties', 'libs.versions.toml',
}
JAVA_TOKEN = re.compile(
    r'"""(?:.|\n)*?"""|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|'
    r'//[^\n]*|/\*.*?\*/|[A-Za-z_$][\w$]*|\d+(?:\.\d+)?|\S', re.DOTALL
)
TYPE = re.compile(r'\b(?:class|interface|enum|record)\s+([A-Za-z_$][\w$]*)')
PACKAGE = re.compile(r'\bpackage\s+([\w.]+)\s*;')
IMPORT = re.compile(r'\bimport\s+(?:static\s+)?([\w.*]+)\s*;')


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def java_tokens(source: str) -> list[str]:
    """Lexical change map. Compilation remains class/source-unit granular."""
    return [token for token in JAVA_TOKEN.findall(source)
            if not token.startswith('//') and not token.startswith('/*')]


@dataclass(frozen=True)
class Entry:
    path: str
    kind: str
    sha256: str
    size: int
    token_sha256: str | None = None
    package: str | None = None
    declared_types: tuple[str, ...] = ()
    imports: tuple[str, ...] = ()


def kind(path: Path) -> str:
    if path.name == '.env' or path.name.startswith('.env.'):
        return 'environment'
    if path.name in BUILD_FILES or 'buildSrc' in path.parts or path.parts[:1] == ('gradle',):
        return 'build'
    if path.suffix == '.java':
        return 'java'
    if 'resources' in path.parts:
        return 'resource'
    return 'project'


def entry(root: Path, path: Path) -> Entry:
    relative = path.relative_to(root)
    data = path.read_bytes()
    category = kind(relative)
    if category != 'java':
        return Entry(relative.as_posix(), category, digest(data), len(data))
    source = data.decode('utf-8')
    tokens = java_tokens(source)
    package_match = PACKAGE.search(source)
    return Entry(relative.as_posix(), category, digest(data), len(data),
                 digest('\0'.join(tokens).encode()),
                 package_match.group(1) if package_match else '',
                 tuple(TYPE.findall(source)), tuple(IMPORT.findall(source)))


def project_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob('*')):
        if not path.is_file() or any(part in IGNORED_PARTS for part in path.relative_to(root).parts):
            continue
        yield path


class CompilationWorld:
    """Mirrors project inputs and records JSON delta messages without secret contents."""
    def __init__(self, project: Path, session: Path):
        self.project = project.resolve()
        self.root = session / 'world'
        self.inputs = self.root / 'project'
        self.blobs = self.root / 'blobs'
        self.protocol = self.root / 'protocol'
        self.previous: dict[str, Entry] = {}
        self.previous_artifacts: dict[str, dict] = {}
        self.generation = 0

    def update(self) -> dict:
        current = {item.path: item for item in (entry(self.project, path) for path in project_files(self.project))}
        added = sorted(set(current) - set(self.previous))
        deleted = sorted(set(self.previous) - set(current))
        changed = sorted(path for path in set(current) & set(self.previous)
                         if current[path].sha256 != self.previous[path].sha256)
        self.generation += 1
        initial = not self.previous
        for relative in [*added, *changed]:
            item = current[relative]
            source = self.project / relative
            if item.kind != 'environment':
                blob = self.blobs / item.sha256
                if not blob.exists():
                    blob.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, blob)
                destination = self.inputs / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(blob, destination)
        for relative in deleted:
            if self.previous[relative].kind != 'environment':
                (self.inputs / relative).unlink(missing_ok=True)
        environment_changed = not initial and any(
            (current.get(path) or self.previous[path]).kind == 'environment'
            for path in [*added, *changed, *deleted]
        )
        request = {
            'version': PROTOCOL_VERSION,
            'generation': self.generation,
            'type': 'PROJECT_SNAPSHOT' if initial else 'PROJECT_DELTA',
            'project': self.project.name,
            'entries': [asdict(current[path]) for path in sorted(current)] if initial else [],
            'delta': {
                'added': [asdict(current[path]) for path in added],
                'changed': [asdict(current[path]) for path in changed],
                'deleted': deleted,
            },
            'requiresRestart': environment_changed,
            'restartReasons': ['environment'] if environment_changed else [],
        }
        self.protocol.mkdir(parents=True, exist_ok=True)
        target = self.protocol / f'{self.generation:06d}-request.json'
        target.write_text(json.dumps(request, ensure_ascii=False, indent=2), encoding='utf-8')
        (self.protocol / 'latest-request.json').write_text(target.read_text(encoding='utf-8'), encoding='utf-8')
        self.previous = current
        return request

    def response(self, request: dict, status: str, outputs: Iterable[Path] = (), detail: str = '') -> dict:
        artifacts: dict[str, dict] = {}
        for root in outputs:
            if not root.exists():
                continue
            for path in sorted(root.rglob('*')):
                if path.is_file():
                    item = {'path': path.relative_to(root).as_posix(),
                            'kind': 'class' if path.suffix == '.class' else 'resource',
                            'sha256': digest(path.read_bytes()), 'size': path.stat().st_size}
                    artifacts[item['kind'] + ':' + item['path']] = item
        changed = [item for key, item in sorted(artifacts.items())
                   if self.previous_artifacts.get(key) != item]
        deleted = sorted(set(self.previous_artifacts) - set(artifacts)) if artifacts else []
        response = {'version': PROTOCOL_VERSION, 'generation': request['generation'],
                    'type': 'COMPILATION_RESULT', 'status': status, 'detail': detail,
                    'artifactDelta': {'changed': changed, 'deleted': deleted}}
        target = self.protocol / f"{request['generation']:06d}-response.json"
        target.write_text(json.dumps(response, ensure_ascii=False, indent=2), encoding='utf-8')
        (self.protocol / 'latest-response.json').write_text(target.read_text(encoding='utf-8'), encoding='utf-8')
        if artifacts and status == 'APPLIED':
            self.previous_artifacts = artifacts
        return response

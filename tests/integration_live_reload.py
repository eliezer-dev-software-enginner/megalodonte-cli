"""Explicit integration check: JDK 25, Gradle cache, published libraries and display required.

Run: PYTHONPATH=src python tests/integration_live_reload.py
Creates only a disposable CLI consumer. Does not exercise users' applications.
"""
from pathlib import Path
import json
import tempfile
import zipfile

from megalodonte_cli.cli import create
from megalodonte_cli.dev import DevelopmentSession, fingerprint


def main():
    with tempfile.TemporaryDirectory(prefix='megalodonte-live-consumer-') as directory:
        root = Path(directory)
        app = create('reload-demo', 'native', 'Live reload integration', root)
        # Gradle propagates init scripts to included builds. They must retain
        # their own outputs and must not be treated as application launchers.
        library = root / 'local-library'
        library.mkdir()
        (library / 'settings.gradle.kts').write_text('rootProject.name = "local-library"\nincludeBuild("nested-library")')
        (library / 'build.gradle.kts').write_text('plugins { `java-library` }; group = "example"; version = "1"\n'
                                               'dependencies { api("example:nested-library:1") }')
        library_source = library / 'src/main/java/example/LocalLibrary.java'
        library_source.parent.mkdir(parents=True)
        library_source.write_text('package example; public class LocalLibrary { public static String value() { return nested.Value.text(); } }')
        nested = library / 'nested-library'
        nested.mkdir()
        (nested / 'settings.gradle.kts').write_text('rootProject.name = "nested-library"')
        (nested / 'build.gradle.kts').write_text('plugins { `java-library` }; group = "example"; version = "1"\n'
                                              'tasks.withType<JavaCompile>().configureEach { options.release.set(17) }')
        nested_source = nested / 'src/main/java/nested/Value.java'
        nested_source.parent.mkdir(parents=True)
        nested_source.write_text('package nested; public class Value { public static String text() { return "library"; } }')
        (app / 'src/main/java/reload_demo/LibraryProbe.java').write_text(
            'package reload_demo; class LibraryProbe { String value() { return example.LocalLibrary.value(); } }')
        settings = app / 'settings.gradle.kts'
        settings.write_text(settings.read_text() + '\nincludeBuild("../local-library")\n')
        build = app / 'build.gradle.kts'
        build.write_text(build.read_text().replace('dependencies {', 'dependencies {\n    implementation("example:local-library:1")'))
        build.write_text(build.read_text().replace(
            'applicationDefaultJvmArgs = listOf(',
            'applicationDefaultJvmArgs = listOf(' + json.dumps('-Duser.home=' + str(root / 'app-home')) + ', '))
        session_dir = root / 'session'
        session_dir.mkdir()
        session = DevelopmentSession(app, session_dir, True, False)
        source = app / 'src/main/java/reload_demo/HomeScreen.java'
        original = source.read_text()
        try:
            assert session.build(fingerprint(session.watch))
            pid = session.process.pid
            assert not (app / 'build').exists(), 'Build must stay in isolated world'
            assert (library / 'build/libs/local-library-1.jar').is_file()
            assert not (session_dir / 'build/classes/java/main/example/LocalLibrary.class').exists()
            libraries = [library / 'build/libs/local-library-1.jar', nested / 'build/libs/nested-library-1.jar']
            library_hashes = fingerprint(libraries)
            # Compiling the next generation also gives JavaFX time to finish startup.
            source.write_text(original.replace('Live reload integration', 'Updated live'))
            assert session.build(fingerprint(session.watch))
            assert session.process.pid == pid
            assert '1 windows' in (session_dir / 'response').read_text()
            assert fingerprint(libraries) == library_hashes, 'App edits must not corrupt included JARs'
            for jar, entry in zip(libraries, ['example/LocalLibrary.class', 'nested/Value.class']):
                with zipfile.ZipFile(jar) as contents:
                    assert entry in contents.namelist(), 'A successful build must not produce empty library JARs'
            source.write_text('invalid java code')
            assert not session.build(fingerprint(session.watch))
            assert session.process.poll() is None
            source.write_text(original)
            assert session.build(fingerprint(session.watch))
            # Adding a dependency changes the runtime. No automatic restart.
            build.write_text(build.read_text().replace('dependencies {', 'dependencies {\n    runtimeOnly("org.slf4j:slf4j-simple:2.0.17")'))
            assert not session.build(fingerprint(session.watch))
            assert session.process.pid == pid
            assert session.process.poll() is None
            print('PASS: nested composite incremental builds, intact library JARs, in-process reload, compile-error recovery and dependency guard')
        finally:
            session.stop()


if __name__ == '__main__':
    main()

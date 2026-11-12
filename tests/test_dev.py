import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock, call
import zipfile

from megalodonte_cli import dev


class LiveReloadTests(unittest.TestCase):
    def test_watcher_debounces_edits_and_builds_latest_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session = dev.DevelopmentSession(root, root, True, False)
            session.process = Mock()
            session.process.poll.side_effect = [None, None, None, 0]
            session.process.returncode = 0
            original, intermediate, latest = {'code': 'a'}, {'code': 'b'}, {'code': 'c'}
            with patch.object(session.watcher, 'scan', side_effect=[original, intermediate, latest, latest]), \
                 patch.object(dev.time, 'sleep'), \
                 patch.object(dev.time, 'monotonic', side_effect=[0, .2, .3, .4, 1.5]), \
                 patch.object(session, 'build') as build:
                self.assertEqual(0, session.run(.6))
                self.assertEqual([call(original), call(latest)], build.call_args_list)

    def test_content_fingerprint_and_snapshot_are_independent_of_source_mutations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / 'output'
            output.mkdir()
            file = output / 'App.class'
            file.write_bytes(b'first')
            before = dev.fingerprint([output])
            dev.snapshot([str(output)], root / 'world')
            file.write_bytes(b'later')
            self.assertNotEqual(before, dev.fingerprint([output]))
            self.assertEqual(b'first', (root / 'world/App.class').read_bytes())

    def test_duplicate_output_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('java', 'resources'):
                (root / name).mkdir()
                (root / name / 'same').write_text(name)
            with self.assertRaisesRegex(ValueError, 'Duplicate'):
                dev.snapshot([str(root / 'java'), str(root / 'resources')], root / 'world')

    def test_dependencies_change_when_same_path_jar_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            jar = Path(directory) / 'library.jar'
            jar.write_bytes(b'one')
            description = dict(outputs=[], classpath=[str(jar)], main='App')
            before = dev.runtime_signature(description)
            jar.write_bytes(b'two')
            self.assertNotEqual(before, dev.runtime_signature(description))

    def test_failed_build_and_stale_build_never_apply(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session = dev.DevelopmentSession(root, root, True, False)
            with patch.object(session, 'prepare', return_value=None), patch.object(session, 'reload') as apply:
                self.assertFalse(session.build({}))
                apply.assert_not_called()
            with patch.object(session, 'prepare', return_value={'outputs': []}), \
                 patch.object(session.watcher, 'scan', return_value={'changed': 'new'}), \
                 patch.object(session, 'reload') as apply:
                self.assertFalse(session.build({'changed': 'old'}))
                apply.assert_not_called()

    def test_dependency_change_requires_explicit_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session = dev.DevelopmentSession(root, root, True, False)
            session.signature = 'old'
            with patch.object(dev, 'runtime_signature', return_value='new'), patch.object(session, 'start') as start:
                self.assertFalse(session.reload({}, root))
                start.assert_not_called()
                session.restart = True
                self.assertTrue(session.reload({}, root))
                start.assert_called_once()

    def test_launch_uses_frozen_world_agent_and_javafx_modules(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            agent = root / 'base.jar'
            with zipfile.ZipFile(agent, 'w') as jar:
                jar.writestr('META-INF/MANIFEST.MF', 'Premain-Class: megalodonte.application.reload.ReloadAgent\n')
            fx = root / 'javafx-controls-25-linux.jar'
            description = dict(java='java', outputs=[str(root / 'build/classes')],
                               classpath=[str(root / 'build/classes'), str(agent), str(fx)],
                               jvmArgs=['-Xmx512m'], args=['hello'], main='App')
            command = dev.launch_command(description, root)
            self.assertIn(f'-javaagent:{agent}={root}', command)
            self.assertIn(str(fx), command)
            cp = command[command.index('-cp') + 1]
            self.assertIn(str(root / 'active'), cp)
            self.assertNotIn('build/classes', cp)
            self.assertEqual(['App', 'hello'], command[-2:])

    def test_watcher_caches_unchanged_files_and_detects_deletion(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'Home.java'
            source.write_text('before')
            watcher = dev.SourceWatcher()
            first = watcher.scan([root])
            with patch.object(Path, 'read_bytes', side_effect=AssertionError('Unchanged file reread')):
                self.assertEqual(first, watcher.scan([root]))
            source.write_text('after')
            self.assertNotEqual(first, watcher.scan([root]))
            source.unlink()
            self.assertEqual({}, watcher.scan([root]))


if __name__ == '__main__':
    unittest.main()

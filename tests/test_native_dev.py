import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from megalodonte_cli.dev import main
from megalodonte_cli.native_dev import NativeDevelopmentSession, native_command


class NativeDevTests(unittest.TestCase):
    def test_opt_in_requires_worker_and_disallows_host_restart(self):
        for args in (['--native-host'], ['--worker-main', 'Worker'],
                     ['--native-host', '--worker-main', 'Worker', '--restart-on-incompatible']):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                main(args)
            self.assertEqual(2, error.exception.code)

    def test_host_runtime_changes_keep_existing_process(self):
        with tempfile.TemporaryDirectory() as directory:
            session = NativeDevelopmentSession(Path(directory), Path(directory), True, 'Worker')
            session.process = object()
            session.host_signature = 'old'
            with patch.object(session, '_signature', return_value='new'), patch.object(session, '_send') as send:
                self.assertFalse(session._replace({}, Path(directory)))
                send.assert_not_called()

    def test_host_and_worker_have_separate_classpaths_without_agent(self):
        description = dict(java='java', jvmArgs=[])
        fx = Path('/deps/javafx-controls-25-linux.jar')
        host = native_command(description, [fx, Path('/deps/base.jar')], [], 'Host', [], True)
        worker = native_command(description, [fx, Path('/deps/base.jar')], [Path('/generation')], 'Worker', ['argument'], False)
        self.assertIn('--module-path', host)
        self.assertNotIn('--module-path', worker)
        self.assertIn('/generation', worker[worker.index('-cp') + 1])
        self.assertFalse(any(item.startswith('-javaagent') for item in host + worker))


if __name__ == '__main__':
    unittest.main()

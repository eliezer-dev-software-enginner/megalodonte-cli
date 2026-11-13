import io
import os
import unittest
from unittest.mock import patch

from megalodonte_cli.console import live


class TerminalBuffer(io.StringIO):
    def isatty(self):
        return True


class ConsoleTests(unittest.TestCase):
    def test_redirected_output_has_no_ansi_sequences(self):
        output = io.StringIO()
        live('APPLIED 2 classes', 'success', output)
        self.assertEqual('[live-reload] APPLIED 2 classes\n', output.getvalue())

    def test_force_color_uses_rich_styles(self):
        output = TerminalBuffer()
        with patch.dict(os.environ, {'TERM': 'xterm-256color'}, clear=True):
            live('RESTART_REQUIRED', 'warning', output)
        self.assertIn('\033[', output.getvalue())

    def test_no_color_wins_for_plain_logs(self):
        output = TerminalBuffer()
        with patch.dict(os.environ, {'NO_COLOR': '1', 'TERM': 'xterm-256color'}, clear=True):
            live('FAILED', 'error', output)
        self.assertNotIn('\033[', output.getvalue())


if __name__ == '__main__':
    unittest.main()

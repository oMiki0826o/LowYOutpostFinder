"""Failing regression cases for stopping the entire native scanner subprocess tree."""
import os
import signal
import subprocess
import unittest
from unittest.mock import MagicMock, patch

from lowy_outpost_finder.process_control import launch_scanner, stop_scanner


class ProcessControlTests(unittest.TestCase):
    @unittest.skipIf(os.name == 'nt', 'POSIX process-group contract')
    def test_scanner_is_started_in_separate_process_session(self):
        with patch('lowy_outpost_finder.process_control.subprocess.Popen') as spawn:
            launch_scanner(['python3', '-V'], cwd='.')
            self.assertTrue(spawn.call_args.kwargs['start_new_session'])

    @unittest.skipIf(os.name == 'nt', 'POSIX process-group contract')
    def test_stop_terminates_process_group_not_only_python_parent(self):
        process = MagicMock(spec=subprocess.Popen)
        process.pid = 9876
        with patch('lowy_outpost_finder.process_control.os.killpg') as kill_group:
            stop_scanner(process)
        kill_group.assert_called_once_with(9876, signal.SIGTERM)

    def test_already_gone_process_is_safe(self):
        process = MagicMock(spec=subprocess.Popen)
        process.pid = 9876
        with patch('lowy_outpost_finder.process_control.os.killpg') as kill_group:
            with patch('lowy_outpost_finder.process_control.subprocess.run') as child:
                with patch('lowy_outpost_finder.process_control.os.name', 'posix'):
                    kill_group.side_effect = ProcessLookupError()
                    stop_scanner(process)
                    child.assert_not_called()


if __name__ == '__main__':
    unittest.main()

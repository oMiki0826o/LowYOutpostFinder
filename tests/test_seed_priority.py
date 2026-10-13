"""File: test_seed_priority.py
Modification: 2026-10-12 — prioritize cheap no-chunk sampling before finite vanilla checks.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from gui_model import SearchRequest, build_arguments


class SeedPriorityTests(unittest.TestCase):
    def test_seed_vanilla_terrain_gui_forwards_priority_and_source(self):
        req = SearchRequest(mode='seed-vanilla', version='1.21.8', seed='123',
                            radius='8192', out='out.csv', server_jar='server.jar',
                            eula_accepted=True, priority='terrain',
                            core_archive='source.tar.gz')
        argv, env = build_arguments(req, language='en-US')
        self.assertEqual(argv[argv.index('--priority') + 1], 'terrain')
        self.assertEqual(argv[argv.index('--core-archive') + 1], 'source.tar.gz')
        self.assertEqual(env, {})

    def test_seed_vanilla_defaults_near_origin(self):
        req = SearchRequest(mode='seed-vanilla', version='26.3', seed='123',
                            radius='8192', out='out.csv', server_jar='server.jar',
                            eula_accepted=True)
        argv, _ = build_arguments(req)
        self.assertEqual(argv[argv.index('--priority') + 1], 'near-origin')

    def test_seed_vanilla_terrain_rejects_unverified_versions(self):
        req = SearchRequest(mode='seed-vanilla', version='26.3', seed='123',
                            radius='8192', out='out.csv', server_jar='server.jar',
                            eula_accepted=True, priority='terrain')
        with self.assertRaisesRegex(ValueError, '1.21.8'):
            build_arguments(req, language='en-US')

    def test_seed_vanilla_passes_requested_priority_to_live_search(self):
        from vanilla_oracle import run_vanilla
        from tests.test_vanilla_oracle import VanillaOracleTests
        with tempfile.TemporaryDirectory() as td:
            jar = VanillaOracleTests().make_bundle(td)
            opts = SimpleNamespace(eula_accepted=True, server_jar=jar, version='1.21.8',
                seed=123, radius=8192, limit=1, timeout=10, startup_timeout=60,
                java='java', memory=2048, max_y=0, out=Path(td) / 'out.csv',
                audit=Path(td) / 'audit.csv', priority='terrain', core_archive=Path(td) / 'core.tar.gz')
            observed = {}
            def check_options(a):
                observed['priority'] = a.priority
                observed['core_archive'] = a.core_archive
                a.audit.write_text('status\nabsent\n', encoding='utf8')
            with patch('vanilla_oracle.subprocess.Popen'), \
                patch('vanilla_oracle.ensure_compatible_java', return_value=21), \
                patch('vanilla_oracle._wait_ready'), \
                patch('vanilla_oracle._stop_server'), \
                patch('finder.run_search_live', side_effect=check_options):
                run_vanilla(opts)
            self.assertEqual(observed['priority'], 'terrain')
            self.assertEqual(observed['core_archive'], Path(td) / 'core.tar.gz')

    def test_cli_accepts_prioritization_flag(self):
        import finder
        with patch('vanilla_oracle.run_vanilla') as fake:
            result = finder.main(['seed-vanilla', '--version', '1.21.8', '--seed', '123',
                        '--server-jar', 'fake.jar', '--priority', 'terrain',
                        '--out', 'result.csv'])
            self.assertEqual(result, 0)
            self.assertEqual(fake.call_args.args[0].priority, 'terrain')


if __name__ == '__main__':
    unittest.main()

"""File: test_vanilla_oracle.py
Modification: 2026-10-12 — regression contracts for an isolated vanilla seed-to-Y workflow.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gui_model import SearchRequest, build_arguments


class VanillaOracleTests(unittest.TestCase):
    def make_bundle(self, folder, version='1.21.8'):
        jar = Path(folder) / 'server.jar'
        with zipfile.ZipFile(jar, 'w') as z:
            z.writestr(f'META-INF/versions/{version}/server-{version}.jar', b'\x00')
        return jar

    def test_requires_explicit_eula_before_execution(self):
        from vanilla_oracle import run_vanilla
        with tempfile.TemporaryDirectory() as directory:
            jar = self.make_bundle(directory)
            args = SimpleNamespace(eula_accepted=False, server_jar=jar, version='1.21.8',
                                   seed=123, radius=1024, limit=1, timeout=10,
                                   startup_timeout=60, java='java', memory=2048,
                                   max_y=0, out=Path(directory) / 'result.csv')
            with patch('vanilla_oracle.subprocess.Popen') as popen:
                with self.assertRaisesRegex(ValueError, 'EULA'):
                    run_vanilla(args)
                popen.assert_not_called()

    def test_rejects_wrong_version_and_unverifiable_jars(self):
        from vanilla_oracle import verify_bundle
        with tempfile.TemporaryDirectory() as directory:
            jar = self.make_bundle(directory, '1.21.8')
            self.assertEqual(verify_bundle(jar, '1.21.8'), '1.21.8')
            with self.assertRaisesRegex(ValueError, 'version'):
                verify_bundle(jar, '26.3')
            bad = Path(directory) / 'unrecognized.jar'
            with zipfile.ZipFile(bad, 'w') as z:
                z.writestr('README', 'unknown')
            with self.assertRaisesRegex(ValueError, 'identify'):
                verify_bundle(bad, '1.21.8')
            bad.write_bytes(b'not-a-zip')
            with self.assertRaisesRegex(ValueError, 'valid Java archive'):
                verify_bundle(bad, '1.21.8')

    def test_server_properties_loopback_only(self):
        from vanilla_oracle import server_properties
        result = server_properties(-10, 'A-secret', 25566, 25577)
        for line in ('level-seed=-10', 'server-ip=127.0.0.1',
                     'rcon.port=25577', 'server-port=25566',
                     'rcon.password=A-secret', 'enable-rcon=true', 'white-list=true'):
            self.assertIn(line + '\n', result)

    def test_gui_requires_eula_and_jar_without_exposing_password(self):
        with tempfile.TemporaryDirectory() as directory:
            jar = self.make_bundle(directory)
            req = SearchRequest(mode='seed-vanilla', version='1.21.8',
                    seed='123', radius='512', out='results.csv',
                    server_jar=str(jar), eula_accepted=False)
            with self.assertRaisesRegex(ValueError, 'EULA|授權'):
                build_arguments(req)
            ok = SearchRequest(mode='seed-vanilla', version='1.21.8', seed='123',
                    radius='512', out='results.csv', server_jar=str(jar), eula_accepted=True)
            arg, env = build_arguments(ok)
            self.assertEqual(arg[0], 'seed-vanilla')
            self.assertIn('--eula-accepted', arg)
            self.assertIn('--server-jar', arg)
            self.assertEqual(env, {})

    def test_finder_has_seed_vanilla_command_and_validates_eula(self):
        import finder
        with tempfile.TemporaryDirectory() as directory:
            jar = self.make_bundle(directory)
            command = ['seed-vanilla', '--version', '1.21.8', '--seed', '0',
                       '--server-jar', str(jar), '--radius', '0',
                       '--out', str(Path(directory) / 'results.csv')]
            self.assertEqual(finder.main(command), 2)
            self.assertFalse((Path(directory) / 'results.csv').exists())

    def test_no_candidate_prevents_pointless_server_launch(self):
        from vanilla_oracle import run_vanilla
        with tempfile.TemporaryDirectory() as directory:
            jar = self.make_bundle(directory)
            args = SimpleNamespace(eula_accepted=True, server_jar=jar, version='1.21.8',
                                   seed=123, radius=0, limit=1, timeout=10,
                                   startup_timeout=60, java='java', memory=2048,
                                   max_y=0, out=Path(directory) / 'result.csv', audit=None)
            with patch('vanilla_oracle.subprocess.Popen') as popen:
                with self.assertRaisesRegex(ValueError, 'No placement candidates'):
                    run_vanilla(args)
                popen.assert_not_called()

    def test_server_startup_failure_stops_process_and_cleans_world(self):
        from vanilla_oracle import run_vanilla, VanillaStartupError
        with tempfile.TemporaryDirectory() as directory:
            jar = self.make_bundle(directory)
            args = SimpleNamespace(eula_accepted=True, server_jar=jar, version='1.21.8',
                                   seed=123, radius=8192, limit=1, timeout=10,
                                   startup_timeout=60, java='java', memory=2048,
                                   max_y=0, out=Path(directory) / 'result.csv', audit=None)
            with patch('vanilla_oracle.subprocess.Popen') as popen, \
                 patch('vanilla_oracle.ensure_compatible_java', return_value=21), \
                 patch('vanilla_oracle._wait_ready', side_effect=VanillaStartupError('failed')), \
                 patch('vanilla_oracle._stop_server') as stop:
                process = popen.return_value
                with self.assertRaisesRegex(VanillaStartupError, 'failed'):
                    run_vanilla(args)
                popen.assert_called_once()
                stop.assert_called_once()
                self.assertIs(stop.call_args.args[0], process)
                self.assertFalse(Path(popen.call_args.kwargs['cwd']).exists())

    def test_managed_run_hands_off_isolated_world_and_purges_password(self):
        from vanilla_oracle import run_vanilla
        from finder import FIELDS, write_csv
        import os
        with tempfile.TemporaryDirectory() as directory:
            jar = self.make_bundle(directory)
            out = Path(directory) / 'verified.csv'
            args = SimpleNamespace(eula_accepted=True, server_jar=jar, version='1.21.8',
                                   seed=123, radius=8192, limit=1, timeout=10,
                                   startup_timeout=60, java='java', memory=2048,
                                   max_y=0, out=out, audit=None)
            observed = {}
            def fake_live(options):
                observed['world'] = options.world
                observed['password'] = os.environ.get('LOWYOUTPOST_TEMP_RCON')
                self.assertTrue((options.world.parent / 'server.properties').is_file())
                self.assertFalse(out.exists())
                write_csv(options.audit, [{'status': 'absent'}], FIELDS)
                write_csv(options.out, [], FIELDS)
            before = os.environ.get('LOWYOUTPOST_TEMP_RCON')
            with patch('vanilla_oracle.subprocess.Popen'), \
                 patch('vanilla_oracle.ensure_compatible_java', return_value=21), \
                 patch('vanilla_oracle._wait_ready'), \
                 patch('vanilla_oracle._stop_server') as stop, \
                 patch('finder.run_search_live', side_effect=fake_live):
                run_vanilla(args)
                stop.assert_called_once()
            self.assertTrue(out.exists())
            self.assertFalse(observed['world'].exists())
            self.assertGreater(len(observed['password']), 30)
            self.assertEqual(os.environ.get('LOWYOUTPOST_TEMP_RCON'), before)

    def test_pending_validation_does_not_claim_zero_eligible_outposts(self):
        from vanilla_oracle import classify_run
        self.assertEqual(classify_run(['absent', 'not_full'])['confidence'], 'incomplete')
        self.assertEqual(classify_run(['absent'])['confidence'], 'no_confirmed_towers')
        self.assertEqual(classify_run(['verified_tower', 'absent'])['confidence'], 'partial')
        self.assertEqual(classify_run(['verified_tower'])['confidence'], 'verified')


if __name__ == '__main__':
    unittest.main()

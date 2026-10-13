"""File: test_v2_vanilla_center.py
Modification: 2026-10-13 — custom-center preflight must not silently scan (0,0).
"""
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
from finder import candidates
from test_vanilla_oracle import VanillaOracleTests

class VanillaCenterTests(unittest.TestCase):
    def test_radius_zero_at_real_candidate_reaches_vanilla_startup(self):
        from vanilla_oracle import run_vanilla, VanillaStartupError
        first=next(iter(candidates(123,8192)))
        self.assertEqual(list(candidates(123,0)),[])
        with tempfile.TemporaryDirectory() as td:
            jar=VanillaOracleTests().make_bundle(td)
            args=SimpleNamespace(eula_accepted=True,server_jar=jar,
                version='1.21.8',seed=123,radius=0,center_x=first['x'],
                center_z=first['z'],limit=1,timeout=10,startup_timeout=60,
                java='java',memory=2048,max_y=0,out=Path(td)/'hits.csv',audit=None)
            with patch('vanilla_oracle.ensure_compatible_java',return_value=21), \
                 patch('vanilla_oracle.subprocess.Popen') as popen, \
                 patch('vanilla_oracle._wait_ready',side_effect=VanillaStartupError('stop test')), \
                 patch('vanilla_oracle._stop_server') as stop:
                with self.assertRaisesRegex(VanillaStartupError,'stop test'):
                    run_vanilla(args)
                popen.assert_called_once()
                stop.assert_called_once()

if __name__=='__main__':unittest.main()

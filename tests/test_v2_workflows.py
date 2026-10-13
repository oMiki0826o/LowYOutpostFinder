"""File: test_v2_workflows.py
Modification: 2026-10-13 — user-defined search origin, seed geometry and resilient live audits.
"""
from __future__ import annotations

import csv
import os
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from lowy_outpost_finder.cli import candidates, base_row, main


class CenteredCandidateTests(unittest.TestCase):
    def test_origin_compatibility_and_negative_center_bounds(self):
        for seed in (0, 123, -1):
            self.assertEqual(list(candidates(seed, 8192)),
                             list(candidates(seed, 8192, center_x=0, center_z=0)))
            for center_x, center_z, radius in ((-619, -1024, 64), (400, -40, 1024), (0, 0, 8192)):
                actual = {(r['chunk_x'], r['chunk_z']) for r in
                          candidates(seed, radius, center_x=center_x, center_z=center_z)}
                from lowy_outpost_finder.cli import OUTPOST, region_position, pass_legacy_frequency, pass_village_exclusion
                expected = set()
                for rz in range(-40, 41):
                    for rx in range(-40, 41):
                        cx, cz = region_position(seed, rx, rz, OUTPOST)
                        if (center_x-radius <= cx*16 <= center_x+radius and
                            center_z-radius <= cz*16 <= center_z+radius and
                            pass_legacy_frequency(seed, cx, cz) and
                            pass_village_exclusion(seed, cx, cz)):
                            expected.add((cx, cz))
                self.assertEqual(actual, expected)

    def test_candidate_cli_nonzero_center_matches_python(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)/'center.csv'
            self.assertEqual(main(['candidates','--seed','123','--radius','2048',
                                   '--center-x','-500','--center-z','1100','--out',str(path)]), 0)
            with path.open(encoding='utf-8') as handle:
                rows = list(csv.DictReader(handle))
            expected = list(candidates(123, 2048, center_x=-500, center_z=1100))
            self.assertEqual([(int(r['chunk_x']),int(r['chunk_z'])) for r in rows],
                             [(r['chunk_x'],r['chunk_z']) for r in expected])

    def test_gui_passes_custom_center_for_candidate_and_vanilla_modes(self):
        from lowy_outpost_finder.gui_model import SearchRequest, build_arguments
        candidate, _ = build_arguments(SearchRequest(mode='candidates', out='result.csv',
                                                      center_x='-500', center_z='2048'))
        self.assertEqual(candidate[candidate.index('--center-x')+1], '-500')
        with tempfile.TemporaryDirectory() as td:
            fake = Path(td)/'server.jar'; fake.write_text('test')
            v, _ = build_arguments(SearchRequest(mode='seed-vanilla',out='out.csv',
                          server_jar=str(fake), eula_accepted=True, center_x='-500', center_z='2048'))
            self.assertEqual(v[v.index('--center-z')+1], '2048')


class LiveAuditProgressTests(unittest.TestCase):
    def test_checkpoint_atomic_after_each_saved_position_even_on_interruption(self):
        from lowy_outpost_finder.live import run_live
        items = list(candidates(123,8192))[:2]
        selected = [(123, r['chunk_x'], r['chunk_z']) for r in items]
        first = base_row(123,selected[0][1],selected[0][2],status='absent')
        class Existing:
            def __init__(self, *a): pass
            def __enter__(self): return self
            def __exit__(self, *a): pass
            def close(self): pass
            def get(self,*a): return object()
        class Server:
            def __init__(self,*a):pass
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def command(self,s):
                if s=='seed':return 'Seed: [123]'
                raise AssertionError(s)
        def exam(chunk, seed,cx,cz, **kw):
            if (cx,cz)==(selected[0][1],selected[0][2]):return first
            raise KeyboardInterrupt('simulate user cancellation')
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)/'checkpoint.csv'
            args = SimpleNamespace(password_env='LOWY_V2_TEST',host='127.0.0.1',port=25575,
                allow_remote=False, version='auto', world=Path(td), candidates=Path(td)/'candidates.csv',
                limit=2,timeout=10,out=Path(td)/'audit.csv',checkpoint=path)
            with patch.dict(os.environ, {'LOWY_V2_TEST':'test'}), \
                 patch('lowy_outpost_finder.live.confirmed_world',return_value=({'DataVersion':4440},123)),\
                 patch('lowy_outpost_finder.versions.detect_world_version',return_value=('1.21.8',4440)),\
                 patch('lowy_outpost_finder.live.load_candidates',return_value=selected),\
                 patch('lowy_outpost_finder.live.is_candidate_start',return_value=True),\
                 patch('lowy_outpost_finder.live.WorldChunks',Existing),patch('lowy_outpost_finder.live.RCON',Server),patch('lowy_outpost_finder.live.examine',side_effect=exam):
                with self.assertRaises(KeyboardInterrupt):run_live(args)
            with path.open(encoding='utf-8') as f: rows=list(csv.DictReader(f))
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]['status'],'absent')
            self.assertFalse(args.out.exists())

    def test_progress_path_rejects_output_collision(self):
        from lowy_outpost_finder.live import check_checkpoint_path
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'same.csv'
            with self.assertRaisesRegex(ValueError,'checkpoint'):
                check_checkpoint_path(p,p)


if __name__ == '__main__': unittest.main()

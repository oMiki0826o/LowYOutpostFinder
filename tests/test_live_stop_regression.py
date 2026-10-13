"""File: test_live_stop_regression.py
Modification: 2026-10-13 — no early stop on only one Y condition.
"""
from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from finder import candidates, base_row
from live import run_live


class ExistingSave:
    def __init__(self, *args):
        pass
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def close(self):
        pass
    def get(self, *args):
        return object()


class FakeServer:
    def __init__(self, *args):
        pass
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def command(self, cmd):
        if cmd != 'seed':
            raise AssertionError(f'Saved chunks must not trigger extra generation: {cmd}')
        return 'Seed: [123]'


class LiveStopRegressionTests(unittest.TestCase):
    def test_returned_audit_preserves_selection_order_for_custom_center_proof(self):
        # The file may be sorted for presentation, but the caller's nearest
        # certificate MUST receive the order in which candidates were checked.
        positions = sorted(list(candidates(123, 8192)),
                           key=lambda p: p['x'] ** 2 + p['z'] ** 2)
        selected = [positions[-1], positions[0]]
        responses = {}
        for point in selected:
            responses[(point['chunk_x'], point['chunk_z'])] = base_row(
                123, point['chunk_x'], point['chunk_z'], status='absent')
        with tempfile.TemporaryDirectory() as td:
            args = SimpleNamespace(password_env='LOWY_STOP_TEST', host='127.0.0.1',
                   allow_remote=False, version='auto', world=Path(td),
                   candidates=Path(td)/'points.csv', limit=2, timeout=10,
                   port=25575, out=Path(td)/'audit.csv')
            with patch.dict(os.environ, {'LOWY_STOP_TEST':'fake'}), \
                 patch('live.confirmed_world', return_value=({'DataVersion':4440},123)), \
                 patch('versions.detect_world_version', return_value=('1.21.8',4440)), \
                 patch('live.load_candidates', return_value=[(123,p['chunk_x'],p['chunk_z']) for p in selected]), \
                 patch('live.is_candidate_start', return_value=True), \
                 patch('live.WorldChunks', ExistingSave), \
                 patch('live.RCON', FakeServer), \
                 patch('live.examine', side_effect=lambda chunk,seed,cx,cz,**kw: responses[(cx,cz)]):
                returned = run_live(args)
            self.assertEqual([(r['chunk_x'],r['chunk_z']) for r in returned],
                             [(p['chunk_x'],p['chunk_z']) for p in selected])

    def test_first_matching_center_but_wrong_base_does_not_stop(self):
        selected = sorted(list(candidates(123, 8192)),
                          key=lambda c: (c['x']**2+c['z']**2, c['chunk_x'],c['chunk_z']))[:2]
        def sample(c, base):
            row = base_row(123, c['chunk_x'], c['chunk_z'], status='verified_tower')
            row.update(base_plate_y=base, structure_center_y=-45, structure_min_y=-55,
                       structure_max_y=-35, watchtower_min_y=base,
                       watchtower_max_y=base+20)
            return row
        bad, good = sample(selected[0], 12), sample(selected[1], -54)
        lookup = {(bad['chunk_x'],bad['chunk_z']): bad,
                  (good['chunk_x'],good['chunk_z']): good}
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)/'audit.csv'
            args = SimpleNamespace(password_env='LOWY_STOP_TEST',host='127.0.0.1',
                       allow_remote=False, version='auto', world=Path(tmp),
                       candidates=Path(tmp)/'candidate.csv',limit=2,
                       timeout=10, port=25575, out=out,
                       stop_center_y_below=-37, stop_max_y=0)
            with patch.dict(os.environ, {'LOWY_STOP_TEST':'fake'}), \
                 patch('live.confirmed_world', return_value=({'DataVersion':4440},123)), \
                 patch('versions.detect_world_version', return_value=('1.21.8',4440)), \
                 patch('live.load_candidates', return_value=[(123,c['chunk_x'],c['chunk_z']) for c in selected]), \
                 patch('live.is_candidate_start', return_value=True), \
                 patch('live.WorldChunks',ExistingSave), \
                 patch('live.RCON',FakeServer), \
                 patch('live.examine',side_effect=lambda _chunk, _seed,cx,cz,**kw: lookup[(cx,cz)]):
                 rows=run_live(args)
            self.assertEqual(len(rows),2)
            self.assertEqual(rows[0]['base_plate_y'],12)
            self.assertEqual(rows[1]['base_plate_y'],-54)
            self.assertTrue(out.is_file())

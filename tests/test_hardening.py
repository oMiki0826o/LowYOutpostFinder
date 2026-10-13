"""File: test_hardening.py
Modification: 2026-10-12 — safety, reporting and bounds regression tests.
"""
from __future__ import annotations

import csv
import gzip
from pathlib import Path
from types import SimpleNamespace
import struct
import tempfile
import unittest
from unittest.mock import patch
import zlib

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import finder
from nbt import NBTError, MAX_NBT_BYTES, Region, load_level
from test_finder import generated_world


class HardeningTests(unittest.TestCase):
    def test_world_fails_if_region_unreadable_instead_of_silent_empty_csv(self):
        with tempfile.TemporaryDirectory() as td:
            world = Path(td)
            generated_world(world)
            (world / 'region' / 'r.-1.0.mca').write_bytes(b'BROKEN')
            args = SimpleNamespace(world=world, version='auto', radius=None,
                                   max_y=None, out=world / 'hits.csv')
            with self.assertRaisesRegex(RuntimeError, 'incomplete'):
                finder.run_world(args)

    def test_level_dat_gzip_bomb_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            world = Path(td)
            (world / 'level.dat').write_bytes(gzip.compress(b'x' * (MAX_NBT_BYTES + 64)))
            with self.assertRaisesRegex(NBTError, 'size limit'):
                load_level(world)

    def test_region_chunk_gzip_bomb_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'r.0.0.mca'
            payload = gzip.compress(b'x' * (MAX_NBT_BYTES + 64))
            frame = struct.pack('>iB', 1 + len(payload), 1) + payload
            data = bytearray(8192 + len(frame) + 4096)
            data[:4] = bytes([0, 0, 2, (len(frame) + 4095) // 4096])
            data[8192:8192 + len(frame)] = frame
            path.write_bytes(data)
            with Region(path) as region:
                with self.assertRaisesRegex(NBTError, 'size limit'):
                    region.read_chunk(0, 0)

    def test_world_scan_reports_errors_but_never_claims_zero_hits(self):
        with tempfile.TemporaryDirectory() as td:
            world = Path(td)
            generated_world(world)
            (world / 'region' / 'r.-1.0.mca').write_bytes(b'BROKEN')
            args = SimpleNamespace(world=world, version='auto', radius=None,
                                   max_y=None, out=world / 'results.csv')
            try:
                finder.run_world(args)
            except RuntimeError:
                pass
            else:
                self.fail('A partial world scan must raise rather than suggest exhaustive success')

    def test_candidate_refuses_impractically_large_search(self):
        with self.assertRaisesRegex(ValueError, 'region|regions|範圍'):
            next(finder.candidates(123, 30000000))


if __name__ == '__main__':
    unittest.main()

class BoundaryTests(unittest.TestCase):
    def test_failed_csv_export_preserves_existing_results(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'hits.csv'
            path.write_text('old data\n', encoding='utf-8')
            def invalid_rows():
                yield {'seed': '123'}
                raise RuntimeError('source error')
            with self.assertRaisesRegex(RuntimeError, 'source error'):
                finder.write_csv(path, invalid_rows(), ['seed'])
            self.assertEqual(path.read_text(encoding='utf-8'), 'old data\n')
            self.assertEqual(list(Path(td).glob('*.tmp')), [])

    def test_verified_candidates_reject_csv_without_version_column(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'missing-version.csv'
            path.write_text('seed,chunk_x,chunk_z,x,z\n123,0,0,0,0\n')
            with self.assertRaisesRegex(ValueError, '[Vv]ersion'):
                finder.load_candidates(path, expected_seed=123, expected_version='1.21.8')

    def test_non_candidate_rejected_before_game_generation(self):
        self.assertFalse(finder.is_candidate_start(123, -1, 2))
        self.assertTrue(all(finder.is_candidate_start(123, p['chunk_x'], p['chunk_z'])
                            for p in finder.candidates(123, 4096)))

    def test_live_restores_signal_handler(self):
        import signal
        import live
        old = signal.getsignal(signal.SIGTERM)
        with patch('live._run_live', return_value=[]):
            live.run_live(object())
        self.assertIs(signal.getsignal(signal.SIGTERM), old)

class LiveLimitTests(unittest.TestCase):
    def test_live_overlarge_limit_blocked_before_candidate_search(self):
        from gui_model import SearchRequest, build_arguments
        req = SearchRequest(mode='search-live', version='auto', world='test-world',
                            password='example', limit='257', out='hits.csv')
        with self.assertRaisesRegex(ValueError, '256'):
            build_arguments(req)

class TerrainPriorityTests(unittest.TestCase):
    def test_terrain_priority_csv_has_verified_version_before_live(self):
        with tempfile.TemporaryDirectory() as td:
            world = Path(td)
            generated_world(world)
            one = next(finder.candidates(123, 4096))
            args = SimpleNamespace(world=world, version='auto', priority='terrain', radius=4096,
                    limit=1, core_archive=Path('supplied-core.tar.gz'), max_y=0,
                    audit=world / 'audit.csv', out=world / 'results.csv')
            def native_run(argv, check):
                if '--csv' in argv:
                    output = Path(argv[argv.index('--csv')+1])
                    output.write_text('seed,chunk_x,chunk_z,x,z,projected_surface_y,biome_id,classification\n'
                                      f"123,{one['chunk_x']},{one['chunk_z']},{one['x']},{one['z']},-40,1,estimated_only\n")
            def live_read(args):
                loaded = finder.load_candidates(args.candidates, 123, '1.21.8')
                self.assertEqual(loaded, [(123, one['chunk_x'], one['chunk_z'])])
                return []
            with patch('finder.subprocess.run', side_effect=native_run), patch('live.run_live', side_effect=live_read):
                finder.run_search_live(args)
            self.assertTrue(args.out.exists())

class MixedVersionWorldTests(unittest.TestCase):
    def test_world_scan_discloses_unreadable_mixed_version_chunk(self):
        from test_finder import nbt
        with tempfile.TemporaryDirectory() as td:
            world = Path(td)
            generated_world(world)
            metadata = {'DataVersion': 5023, 'Version': {'Name': '26.3'},
                        'WorldGenSettings': {'seed': 123}}
            (world / 'level.dat').write_bytes(gzip.compress(nbt({'Data': metadata})))
            args = SimpleNamespace(world=world, version='auto', radius=None,
                                   max_y=None, out=world / 'hits.csv')
            with self.assertRaisesRegex(RuntimeError, 'incomplete'):
                finder.run_world(args)

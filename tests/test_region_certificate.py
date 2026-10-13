"""File: test_region_certificate.py
Modification: 2026-10-13 — test finite-area completeness before any lowest-Y claims.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from region_certificate import summarize_region, certify_world_region
from finder import candidates


class RegionCertificateTests(unittest.TestCase):
    def setUp(self):
        self.seed = 123
        self.version = '1.21.8'
        self.first = next(candidates(self.seed, 8192))
        self.second = list(candidates(self.seed, 8192))[1]
        self.expect = [self.first, self.second]

    def row(self, position, status, y=''):
        return dict(version=self.version, seed=self.seed,
                    chunk_x=position['chunk_x'], chunk_z=position['chunk_z'],
                    x=position['x'], z=position['z'], status=status,
                    base_plate_y=y, watchtower_min_y=y, watchtower_max_y=y,
                    geometry_status='match' if status == 'verified_tower' else 'not_applicable',
                    tower_vertical_status='match' if status == 'verified_tower' else 'not_applicable')

    def test_fully_inspected_area_proves_finite_minimum_only(self):
        rows = [self.row(self.first, 'verified_tower', '-25'),
                self.row(self.second, 'absent')]
        result = summarize_region(self.expect, rows, self.seed, self.version, radius=8192)
        self.assertTrue(result['coverage_complete'])
        self.assertEqual(result['lowest_confirmed_base_plate_y'], -25)
        self.assertEqual(result['lowest_confirmed_watchtower_y'], -25)
        self.assertEqual(result['status'], 'finite_region_complete')
        self.assertFalse(result['global_world_minimum_proven'])
        self.assertFalse(result['independent_seed_only_exactness_proven'])

    def test_incomplete_chunks_never_claim_a_minimum(self):
        rows = [self.row(self.first, 'verified_tower', '-20'),
                self.row(self.second, 'not_generated')]
        result = summarize_region(self.expect, rows, self.seed, self.version, radius=8192)
        self.assertEqual(result['status'], 'finite_region_incomplete')
        self.assertFalse(result['coverage_complete'])
        self.assertIsNone(result['lowest_confirmed_base_plate_y'])
        self.assertEqual(result['lowest_observed_base_plate_y'], -20)
        self.assertEqual(result['incomplete_count'], 1)

    def test_geometry_mismatch_never_certifies(self):
        row = self.row(self.first, 'verified_tower', '10')
        row['geometry_status'] = 'rotation_mismatch'
        result = summarize_region(self.expect, [row, self.row(self.second, 'absent')],
                                  self.seed, self.version, radius=8192)
        self.assertFalse(result['coverage_complete'])
        self.assertEqual(result['unresolved'][0]['reason'], 'geometry_not_confirmed')

    def test_no_tower_is_complete_but_reports_no_towers(self):
        rows = [self.row(p, 'absent') for p in self.expect]
        result = summarize_region(self.expect, rows, self.seed, self.version, radius=8192)
        self.assertEqual(result['status'], 'finite_region_complete_no_towers')
        self.assertIsNone(result['lowest_confirmed_base_plate_y'])
        self.assertTrue(result['coverage_complete'])

    def test_duplicate_row_is_error(self):
        one = self.row(self.first, 'absent')
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            summarize_region(self.expect, [one, one], self.seed, self.version, radius=8192)

    def test_extra_non_candidate_row_is_error(self):
        bad = self.row(self.first, 'absent')
        bad['chunk_x'] = int(bad['chunk_x']) + 4
        with self.assertRaisesRegex(ValueError, 'outside'):
            summarize_region(self.expect, [bad], self.seed, self.version, radius=8192)

    def test_inconsistent_version_and_coordinates_are_rejected(self):
        row = self.row(self.first, 'absent')
        row['version'] = '26.3'
        with self.assertRaisesRegex(ValueError, 'version'):
            summarize_region(self.expect, [row], self.seed, self.version, radius=8192)
        row['version'] = self.version
        row['x'] = int(row['x']) + 1
        with self.assertRaisesRegex(ValueError, 'coordinate'):
            summarize_region(self.expect, [row], self.seed, self.version, radius=8192)

    def test_missing_row_is_incomplete_not_zero_towers(self):
        result = summarize_region(self.expect, [self.row(self.first, 'absent')],
                                  self.seed, self.version, radius=8192)
        self.assertEqual(result['missing_candidates'], 1)
        self.assertFalse(result['coverage_complete'])

    def test_finite_certificate_requires_geometry_for_saved_towers(self):
        # Even a FULL chunk with a watchtower is not certified until its
        # actual baseplate footprint/rotation is checked against version assets.
        from finder import candidates
        import region_certificate
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            chunk = {'DataVersion': 4440, 'Status': 'minecraft:full',
                     'structures': {'starts': {'minecraft:pillager_outpost': {
                         'id': 'minecraft:pillager_outpost',
                         'Children': [
                             {'id': 'minecraft:jigsaw', 'BB': [0, 70, 0, 15, 99, 15],
                              'pool_element': {'location': 'minecraft:pillager_outpost/base_plate'}},
                             {'id': 'minecraft:jigsaw', 'BB': [0, 70, 0, 14, 90, 14],
                              'pool_element': {'location': 'minecraft:pillager_outpost/watchtower'}}]
                     }}}}
            rows = list(candidates(self.seed, 8192))
            origin = (rows[0]['chunk_x'], rows[0]['chunk_z'])
            chunk['structures']['starts']['minecraft:pillager_outpost'].update(ChunkX=origin[0], ChunkZ=origin[1])
            def fake_get(self, cx, cz):
                if (cx, cz) == origin:
                    return chunk
                return {'DataVersion': 4440, 'Status': 'minecraft:full',
                        'xPos': cx, 'zPos': cz, 'structures': {'starts': {}}}
            with patch('region_certificate.confirmed_world', return_value=({'DataVersion': 4440}, self.seed)), \
                 patch('region_certificate.detect_world_version', return_value=(self.version, 4440)), \
                 patch('region_certificate.WorldChunks.get', fake_get):
                report = region_certificate.certify_world_region(Path(td), 8192, Path(td) / 'out.json')
            self.assertFalse(report['coverage_complete'])
            self.assertEqual(report['incomplete_count'], 1)
            self.assertIsNone(report['lowest_confirmed_base_plate_y'])

    def test_rejects_world_modified_during_read(self):
        import region_certificate
        from nbt import region_filename
        with tempfile.TemporaryDirectory() as td:
            world = Path(td)
            position = self.first
            path = world / 'region' / region_filename(position['chunk_x'] // 32, position['chunk_z'] // 32)
            path.parent.mkdir()
            path.write_bytes(b'initial')
            def fake_get(self, cx, cz):
                if (cx, cz) == (position['chunk_x'], position['chunk_z']):
                    path.write_bytes(b'modified contents')
                return {'DataVersion': 4440, 'Status': 'minecraft:full',
                        'xPos': cx, 'zPos': cz, 'structures': {'starts': {}}}
            out = world / 'report.json'
            with patch('region_certificate.confirmed_world', return_value=({'DataVersion': 4440}, self.seed)), \
                 patch('region_certificate.detect_world_version', return_value=(self.version, 4440)), \
                 patch('region_certificate.WorldChunks.get', fake_get):
                with self.assertRaisesRegex(RuntimeError, 'changed during'):
                    region_certificate.certify_world_region(world, 8192, out)
            self.assertFalse(out.exists())

    def test_never_overwrites_minecraft_world_files(self):
        from region_certificate import certify_world_region
        with tempfile.TemporaryDirectory() as td:
            world = Path(td)
            level = world / 'level.dat'
            level.write_bytes(b'untouched original')
            with patch('region_certificate.confirmed_world', return_value=({'DataVersion': 4440}, self.seed)), \
                 patch('region_certificate.detect_world_version', return_value=(self.version, 4440)):
                with self.assertRaisesRegex(ValueError, 'world data'):
                    certify_world_region(world, 8192, level)
            self.assertEqual(level.read_bytes(), b'untouched original')

    def test_pending_candidates_file_contains_only_not_yet_full_origins(self):
        import csv
        from region_certificate import certify_world_region
        with tempfile.TemporaryDirectory() as td:
            world = Path(td)
            output = world / 'report.json'
            pending = world / 'pending.csv'
            original = self.first
            def fake_get(self, cx, cz):
                if (cx, cz) == (original['chunk_x'], original['chunk_z']):
                    return None
                return {'DataVersion': 4440, 'Status': 'minecraft:full',
                        'xPos': cx, 'zPos': cz, 'structures': {'starts': {}}}
            with patch('region_certificate.confirmed_world', return_value=({'DataVersion': 4440}, self.seed)), \
                 patch('region_certificate.detect_world_version', return_value=(self.version, 4440)), \
                 patch('region_certificate.WorldChunks.get', fake_get):
                report = certify_world_region(world, 8192, output, pending_output=pending)
            self.assertFalse(report['coverage_complete'])
            with pending.open(encoding='utf-8', newline='') as fp:
                queued = list(csv.DictReader(fp))
            self.assertEqual(len(queued), 1)
            self.assertEqual((int(queued[0]['chunk_x']), int(queued[0]['chunk_z'])),
                             (original['chunk_x'], original['chunk_z']))
            self.assertEqual(queued[0]['classification'], 'placement_candidate')

    def test_real_command_uses_world_snapshot_without_making_fake_world(self):
        from finder import FIELDS
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / 'report.json'
            rows_out = Path(td) / 'audit.csv'
            observed = []
            def fake_get(self, cx, cz):
                observed.append((cx, cz))
                return {'DataVersion': 4440, 'Status': 'minecraft:full',
                        'xPos': cx, 'zPos': cz, 'structures': {'starts': {}}}
            radius = 8192
            expected = list(candidates(self.seed, radius))
            with patch('region_certificate.confirmed_world', return_value=({'DataVersion': 4440}, self.seed)), \
                 patch('region_certificate.detect_world_version', return_value=(self.version, 4440)), \
                 patch('region_certificate.WorldChunks.get', fake_get):
                result = certify_world_region(Path(td), radius, out, rows_out, max_candidates=1000)
            self.assertTrue(result['coverage_complete'])
            self.assertEqual(len(observed), len(expected))
            self.assertTrue(out.exists())
            self.assertTrue(rows_out.exists())
            import csv
            with rows_out.open() as fp:
                self.assertTrue(set(FIELDS) <= set(csv.DictReader(fp).fieldnames))


if __name__ == '__main__':
    unittest.main()

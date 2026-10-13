"""File: test_geometry_audit.py
Modification: 2026-10-13 — independent expected-vs-saved Jigsaw geometry checks.
"""
from __future__ import annotations

import csv
import tempfile
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lowy_outpost_finder.cli import candidates
from lowy_outpost_finder.start_geometry import projection
from lowy_outpost_finder.geometry_audit import expected_base_box, audit_piece, audit_world
from tests.test_start_geometry import sample_jar
from tests.test_finder import generated_world


class GeometryAuditTests(unittest.TestCase):
    def test_baseplate_bbox_matches_all_rotations(self):
        x, z = -512, 32
        expected = (
            (-512, 32, -500, 48),
            (-528, 32, -512, 44),
            (-524, 16, -512, 32),
            (-512, 20, -496, 32),
        )
        for rotation, footprint in enumerate(expected):
            self.assertEqual(expected_base_box(x, z, 13, 17, rotation), footprint)

    def test_detect_wrong_rotation_even_if_height_matches(self):
        seed, cx, cz = 123, -23, 13
        p = projection(seed, cx, cz, (13, 2, 17))
        bb = expected_base_box(cx * 16, cz * 16, 13, 17, p.rotation)
        good = {'BB': [bb[0], -41, bb[1], bb[2], -40, bb[3]],
                'rotation': ('NONE', 'CLOCKWISE_90', 'CLOCKWISE_180', 'COUNTERCLOCKWISE_90')[p.rotation],
                'pool_element': {'location': 'minecraft:pillager_outpost/base_plate'}}
        self.assertEqual(audit_piece(good, p, cx, cz, (13, 2, 17))['geometry_status'], 'match')
        wrong = dict(good, rotation='NONE' if p.rotation else 'CLOCKWISE_90')
        self.assertEqual(audit_piece(wrong, p, cx, cz, (13, 2, 17))['geometry_status'], 'rotation_mismatch')
        wrong = dict(good, BB=[bb[0] + 1, -41, bb[1], bb[2] + 1, -40, bb[3]])
        self.assertEqual(audit_piece(wrong, p, cx, cz, (13, 2, 17))['geometry_status'], 'footprint_mismatch')

    def test_world_audit_requires_real_verified_start_and_no_false_exact_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            jar = root / 'assets.jar'
            sample_jar(jar)
            row = next(iter(candidates(123, 8192)))
            cx, cz = row['chunk_x'], row['chunk_z']
            world = root / 'world'
            generated_world(world, seed=123, chunk_x=cx, chunk_z=cz)
            source = root / 'candidates.csv'
            with source.open('w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['version', 'seed', 'chunk_x', 'chunk_z', 'x', 'z'])
                writer.writeheader()
                writer.writerow(dict(version='1.21.8', **{k: row[k] for k in ('seed', 'chunk_x', 'chunk_z', 'x', 'z')}))
            rows, report = audit_world(world, source, jar)
            self.assertEqual(report['checked'], 1)
            self.assertEqual(report['geometry_mismatch'], 1)
            self.assertFalse(report['full_version_height_exact'])
            self.assertEqual(rows[0]['status'], 'verified_tower')

    def test_height_sample_requires_projected_position_and_reports_signed_error(self):
        seed, cx, cz = 123, 6, -42
        size = (13, 2, 17)
        p = projection(seed, cx, cz, size)
        bb = expected_base_box(cx * 16, cz * 16, 13, 17, p.rotation)
        piece = {'BB': [bb[0], -30, bb[1], bb[2], -29, bb[3]],
                 'rotation': ('NONE', 'CLOCKWISE_90', 'CLOCKWISE_180', 'COUNTERCLOCKWISE_90')[p.rotation]}
        sample = audit_piece(piece, p, cx, cz, size, estimated={'sample_x': str(p.sample_x), 'sample_z': str(p.sample_z), 'rotation': str(p.rotation), 'projected_base_plate_y': '-27'})
        self.assertEqual(sample['geometry_status'], 'match')
        self.assertEqual(sample['height_error'], 3)
        bad_sample = audit_piece(piece, p, cx, cz, size, estimated={'sample_x': '0', 'sample_z': '0', 'rotation': str(p.rotation), 'projected_base_plate_y': '-30'})
        self.assertEqual(bad_sample['height_status'], 'sample_mismatch')
        self.assertEqual(bad_sample['height_error'], '')

if __name__ == '__main__':
    unittest.main()

"""File: test_tower_audit.py
Modification: 2026-10-13 — verify primary tower delta against saved bounding boxes.
"""
import tempfile
from pathlib import Path
import unittest

from tower_geometry import load_tower_blueprint
from geometry_audit import audit_tower_relation
from test_tower_geometry import make_jar


class TowerAuditTests(unittest.TestCase):
    def test_observed_saved_tower_vertical_box_agrees_with_blueprint(self):
        with tempfile.TemporaryDirectory() as t:
            jar = Path(t) / 'game.jar'
            make_jar(jar)
            blueprint = load_tower_blueprint(jar)
            base = {'BB': [0, -40, 0, 12, -38, 16]}
            tower = {'id': 'minecraft:jigsaw',
                     'pool_element': {'elements': [{'location': 'minecraft:pillager_outpost/watchtower'},
                                                  {'location': 'minecraft:pillager_outpost/watchtower_overgrown'}]},
                     'BB': [0, -37, 0, 14, -17, 14]}
            start = {'Children': [base, tower]}
            self.assertEqual(audit_tower_relation(start, base, blueprint)['tower_vertical_status'], 'match')
            tower['BB'][1] = -36
            self.assertEqual(audit_tower_relation(start, base, blueprint)['tower_vertical_status'], 'mismatch')

    def test_reject_missing_primary_tower_without_fake_success(self):
        with tempfile.TemporaryDirectory() as t:
            jar = Path(t) / 'game.jar'
            make_jar(jar)
            blueprint = load_tower_blueprint(jar)
            base = {'BB': [0, 60, 0, 12, 62, 16]}
            actual = audit_tower_relation({'Children': [base]}, base, blueprint)
            self.assertEqual(actual['tower_vertical_status'], 'missing')

if __name__ == '__main__':
    unittest.main()

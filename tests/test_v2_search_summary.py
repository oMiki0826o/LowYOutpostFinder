"""File: test_v2_search_summary.py
Modification: 2026-10-13 — sampled lowest-Y is not a region-wide proof.
"""
from __future__ import annotations
import csv
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from finder import base_row, main
from search_conditions import summarize_search

class VerifiedHeightOrderTests(unittest.TestCase):
    def test_region_minimum_requires_full_resolved_near_origin_coverage(self):
        rows=[{'status':'absent'},
              {'status':'verified_tower', 'base_plate_y':-52, 'watchtower_min_y':-52,
               'structure_center_y':-30},
              {'status':'verified_tower','base_plate_y':-54,'watchtower_min_y':-54,
               'structure_center_y':-32}]
        result=summarize_search(rows,center_below=0,max_y=0,total_candidates=3,priority='near-origin')
        self.assertEqual(result['lowest_status'],'lowest_verified_within_radius')
        result=summarize_search(rows[:2],center_below=0,max_y=0,total_candidates=3,priority='near-origin')
        self.assertEqual(result['lowest_status'],'not_proven')
        result=summarize_search([{'status':'timeout'},*rows[1:]],center_below=0,max_y=0,
                                total_candidates=3,priority='near-origin')
        self.assertEqual(result['lowest_status'],'not_proven')
        result=summarize_search(rows,center_below=0,max_y=0,total_candidates=3,priority='terrain')
        self.assertEqual(result['lowest_status'],'not_proven')

    def test_centered_distance_sort_uses_search_center_not_world_origin(self):
        from finder import candidates
        center_x, center_z = -1024, 512
        samples = list(candidates(123, 8192, center_x=center_x, center_z=center_z))
        expected = sorted(samples, key=lambda p: ((p['x']-center_x)**2+(p['z']-center_z)**2))[:3]
        rows = []
        for p in reversed(expected):
            r = base_row(123, p['chunk_x'], p['chunk_z'], status='verified_tower')
            r.update(base_plate_y=-50, watchtower_min_y=-50, watchtower_max_y=-30,
                     structure_center_y=-40, structure_min_y=-50, structure_max_y=-30)
            rows.append(r)
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'results.csv'
            with patch('finder.confirmed_world', return_value=({'DataVersion':4440},123)), \
                 patch('finder.detect_world_version', return_value=('1.21.8',4440)), \
                 patch('live.run_live', return_value=rows):
                self.assertEqual(main(['search-live','--world',td,'--radius','8192',
                   '--center-x',str(center_x),'--center-z',str(center_z),
                   '--out',str(out),'--limit','3']),0)
            with out.open(encoding='utf-8') as f: parsed=list(csv.DictReader(f))
            self.assertEqual([(int(row['x']),int(row['z'])) for row in parsed],
                             [(p['x'],p['z']) for p in expected])
            self.assertEqual(int(parsed[0]['search_distance_sq']),
                             (expected[0]['x']-center_x)**2+(expected[0]['z']-center_z)**2)
            self.assertEqual(int(parsed[0]['distance_sq']),
                             expected[0]['x']**2+expected[0]['z']**2)

    def test_highest_priority_sampled_tower_can_be_sorted_by_real_base_height(self):
        from finder import candidates
        pts=sorted(candidates(123,2048),key=lambda p:(p['x']**2+p['z']**2,p['chunk_x'],p['chunk_z']))
        self.assertGreaterEqual(len(pts),2)
        rows=[]
        for p,y in zip(pts[:2],[-10,-50]):
            row=base_row(123,p['chunk_x'],p['chunk_z'],status='verified_tower')
            row.update(base_plate_y=y,watchtower_min_y=y,watchtower_max_y=y+20,
                       structure_center_y=-60,structure_min_y=y,structure_max_y=y+20)
            rows.append(row)
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'hits.csv';audit=Path(td)/'audit.csv';summary=Path(td)/'summary.json'
            opts=['search-live','--version','auto','--world',td,'--radius','2048',
                  '--limit','2','--center-y-below','0','--sort-by','base-y',
                  '--audit',str(audit),'--out',str(out),'--summary',str(summary)]
            with patch('finder.confirmed_world',return_value=({'DataVersion':4440,'Version':{'Name':'1.21.8'}},123)),\
                 patch('finder.detect_world_version',return_value=('1.21.8',4440)),\
                 patch('live.run_live',return_value=rows):
                self.assertEqual(main(opts),0)
            with out.open(encoding='utf-8') as f: parsed=list(csv.DictReader(f))
            self.assertEqual([int(row['base_plate_y']) for row in parsed],[-50,-10])
            info=json.loads(summary.read_text())
            self.assertEqual(info['lowest_status'],'not_proven')
            self.assertGreater(info['unchecked'],0)
            self.assertEqual(info['sort_by'],'base-y')

if __name__=='__main__':unittest.main()

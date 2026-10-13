"""File: test_v2_seed_geometry.py
Modification: 2026-10-13 — seed-only exact start X/Z requires matching original JAR; Y remains unknown.
"""
import csv
from pathlib import Path
import tempfile
import unittest

from lowy_outpost_finder.cli import main, candidates
from test_start_geometry import sample_jar
from test_placement_assets import add_assets
from lowy_outpost_finder.start_geometry import projection, load_outpost_assets


class SeedGeometryTests(unittest.TestCase):
    def test_seed_only_projection_exact_coordinates_and_no_fabricated_y(self):
        with tempfile.TemporaryDirectory() as td:
            jar=Path(td)/'minecraft.jar'; sample_jar(jar);add_assets(jar)
            out=Path(td)/'plan.csv'
            self.assertEqual(main(['seed-geometry','--version','1.21.8','--seed','123',
                 '--game-jar',str(jar),'--radius','8192','--center-x','250',
                 '--center-z','-900','--out',str(out)]),0)
            with out.open(encoding='utf-8') as f:rows=list(csv.DictReader(f))
            self.assertTrue(rows)
            expected=list(candidates(123,8192,center_x=250,center_z=-900))
            self.assertEqual(len(rows),len(expected))
            size=load_outpost_assets(jar).size
            for row in rows:
                geo=projection(123,int(row['chunk_x']),int(row['chunk_z']),size)
                self.assertEqual(int(row['sample_x']),geo.sample_x)
                self.assertEqual(int(row['sample_z']),geo.sample_z)
                self.assertEqual(int(row['rotation']),geo.rotation)
                self.assertEqual(row['classification'],'seed_geometry_only')
                self.assertNotIn('base_plate_y',row)
                self.assertNotIn('watchtower_y',row)

    def test_gui_requires_jar_and_accepts_geometry_mode(self):
        from lowy_outpost_finder.gui_model import SearchRequest,build_arguments
        with self.assertRaises(ValueError):
            build_arguments(SearchRequest(mode='seed-geometry',out='geometry.csv'))
        args,_=build_arguments(SearchRequest(mode='seed-geometry',out='geometry.csv',
                                           game_jar='minecraft.jar',center_x='-40'))
        self.assertEqual(args[0],'seed-geometry')
        self.assertEqual(args[args.index('--center-x')+1],'-40')

if __name__=='__main__':unittest.main()

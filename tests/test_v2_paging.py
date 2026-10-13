"""File: test_v2_paging.py
Modification: 2026-10-13 — paged original-game validation cannot invent nearest-region proofs.
"""
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
from finder import candidates, main

class PagingTests(unittest.TestCase):
    def test_offset_creates_page_candidates_and_no_false_nearest_proof(self):
        import csv, json
        all_candidates=sorted(list(candidates(123,8192)),key=lambda r:(r['x']**2+r['z']**2,r['chunk_x'],r['chunk_z']))
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'hits.csv'; summary=Path(td)/'summary.json'
            def fake_live(args):
                with args.candidates.open() as f: rows=list(csv.DictReader(f))
                self.assertEqual([(int(r['chunk_x']),int(r['chunk_z'])) for r in rows],
                         [(r['chunk_x'],r['chunk_z']) for r in all_candidates[3:5]])
                return [{'status':'absent'}, {'status':'absent'}]
            with patch('finder.confirmed_world',return_value=({'DataVersion':4440},123)), \
                 patch('finder.detect_world_version',return_value=('1.21.8',4440)), \
                 patch('live.run_live',side_effect=fake_live):
                self.assertEqual(main(['search-live','--world',td,'--radius','8192','--offset','3',
                                      '--limit','2','--out',str(out),'--summary',str(summary)]),0)
            report=json.loads(summary.read_text())
            self.assertEqual(report['offset'],3)
            self.assertEqual(report['nearest_status'],'not_proven')
            self.assertEqual(report['lowest_status'],'not_proven')

if __name__=='__main__':unittest.main()

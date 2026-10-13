"""File: test_structure_contract.py
Modification: 2026-10-13 — proof of bounded pool/template dependency traversal.
"""
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lowy_outpost_finder.structure_contract import inspect_structure_contract
BASE='data/minecraft/worldgen/'


def fixture(path,*,missing=False):
    with zipfile.ZipFile(path,'w') as z:
        z.writestr('version.json',json.dumps({'id':'1.21.8'}))
        z.writestr(BASE+'structure/pillager_outpost.json',json.dumps({'type':'minecraft:jigsaw','start_pool':'minecraft:pillager_outpost/base_plates','size':7}))
        z.writestr(BASE+'template_pool/pillager_outpost/base_plates.json',json.dumps({
            'fallback':'minecraft:empty',
            'elements':[{'weight':1,'element':{'element_type': 'minecraft:empty_pool_element'}}] if not missing else
            [{'weight':1,'element':{'element_type':'minecraft:unsupported_pool_element'}}]}))
    return path

class StructureContracts(unittest.TestCase):
    def test_walks_known_pools_without_guessing_random_outcome(self):
        with tempfile.TemporaryDirectory() as d:
            report=inspect_structure_contract(fixture(Path(d)/'a.jar'),'1.21.8')
            self.assertEqual(report['template_pools_visited'],1)
            self.assertEqual(report['templates_visited'],0)
            self.assertEqual(report['size'],7)
            self.assertFalse(report['complete_jigsaw_simulation_proven'])

    def test_unsupported_pool_type_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,'Unsupported'):
                inspect_structure_contract(fixture(Path(d)/'a.jar',missing=True),'1.21.8')

    def test_jar_version_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,'mismatch'):
                inspect_structure_contract(fixture(Path(d)/'a.jar'),'26.3')

if __name__=='__main__':unittest.main()

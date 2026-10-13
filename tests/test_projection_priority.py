"""File: test_projection_priority.py
Modification: 2026-10-13 — seed-to-vanilla terrain priority uses template dimensions.
"""
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from test_start_geometry import sample_jar
from test_finder import generated_world
import lowy_outpost_finder.cli as finder

class ProjectionPriorityTests(unittest.TestCase):
    def test_priority_native_uses_supplied_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            generated_world(folder)
            jar=folder/'assets.jar';sample_jar(jar)
            candidate=next(finder.candidates(123,4096))
            opts=SimpleNamespace(world=folder,version='auto',priority='terrain',radius=4096,
                                 limit=1,core_archive=folder/'source.tar.gz',game_jar=jar,
                                 max_y=None,audit=folder/'audit.csv',out=folder/'result.csv')
            calls=[]
            def capture(cmd,check):
                calls.append(cmd)
                if '--csv' in cmd:
                    path=Path(cmd[cmd.index('--csv')+1])
                    path.write_text('version,seed,chunk_x,chunk_z,x,z,projected_surface_y,biome_id,classification\n'
                        f"1.21.8,123,{candidate['chunk_x']},{candidate['chunk_z']},{candidate['x']},{candidate['z']},64,1,estimated_only\n",encoding='utf-8')
            with patch('lowy_outpost_finder.cli.subprocess.run',side_effect=capture), patch('lowy_outpost_finder.live.run_live',return_value=[]):
                finder.run_search_live(opts)
            command=next(c for c in calls if '--csv' in c)
            self.assertEqual(command[command.index('--template-width')+1],'13')
            self.assertEqual(command[command.index('--template-depth')+1],'17')

if __name__=='__main__': unittest.main()

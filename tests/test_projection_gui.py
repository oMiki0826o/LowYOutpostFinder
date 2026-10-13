"""File: test_projection_gui.py
Modification: 2026-10-13 — bilingual UI supports optional exact Jigsaw geometry metadata.
"""
import unittest
from lowy_outpost_finder.gui_model import SearchRequest, build_arguments
from lowy_outpost_finder.i18n import tr

class ProjectionGuiTests(unittest.TestCase):
    def test_en_and_zh_label_exist(self):
        self.assertIn('JAR', tr('en-US', 'field_game_jar'))
        self.assertIn('JAR', tr('zh-TW', 'field_game_jar'))

    def test_estimate_forwards_jar(self):
        q=SearchRequest(mode='estimate', version='1.21.8', seed='123', max_y='64',
                        out='projected.csv', game_jar='client.jar')
        for lang in ('en-US', 'zh-TW'):
            argv,_=build_arguments(q, language=lang)
            self.assertEqual(argv[argv.index('--game-jar')+1], 'client.jar')

if __name__ == '__main__':
    unittest.main()

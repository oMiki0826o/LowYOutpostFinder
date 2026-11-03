"""Publish the bilingual README with the user-approved GitHub template layout."""
from __future__ import annotations

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ReadmeGovernanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = (ROOT / 'README.md').read_text(encoding='utf-8')

    def test_one_root_readme_with_parallel_language_sections(self):
        names = sorted(p.name for p in ROOT.iterdir()
                       if p.is_file() and p.name.lower().startswith('readme'))
        self.assertEqual(names, ['README.md'])
        self.assertIn('[中文](#中文) | [English](#english)', self.text)
        headings = [line for line in self.text.splitlines() if line.startswith('#')]
        self.assertEqual(headings, [
            '# LowYOutpostFinder', '## 中文', '### 目錄',
            '### 關於', '### 功能', '### 安裝', '### 使用方式',
            '### 授權', '## English', '### Table of Contents',
            '### About', '### Features', '### Installation',
            '### Usage', '### License',
        ])

    def test_verified_version_license_and_no_full_width_punctuation(self):
        version = (ROOT / 'VERSION').read_text(encoding='utf-8').strip()
        license_text = (ROOT / 'LICENSE').read_text(encoding='utf-8')
        self.assertTrue(license_text.startswith('MIT License'))
        self.assertIn(f'badge/version-{version}-blue', self.text)
        self.assertIn('badge/license-MIT-green', self.text)
        self.assertNotRegex(self.text, r'[，。；：！？（）「」]')

    def test_local_readme_links_exist(self):
        for target in re.findall(r'\]\(([^)]+)\)', self.text):
            if target.startswith('#') or target.startswith(('https://', 'http://')):
                continue
            self.assertTrue((ROOT / target).is_file(),
                            f'Broken relative README link: {target}')

    def test_both_languages_explain_unverified_y_and_native_prerequisites(self):
        zh, en = self.text.split('## English', maxsplit=1)
        for section in (zh, en):
            for term in ('estimated_only', 'verified_tower',
                         'CMake', 'Git', '1.21.8',
                         '--max-y -37', '30,000,000',
                         'docs/SIMPLE_HOME.md'):
                with self.subTest(term=term):
                    self.assertIn(term, section)


if __name__ == '__main__':
    unittest.main()

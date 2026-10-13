"""File: test_native_integrity.py
Modification: 2026-10-13 — reject incorrect or misleading external sampler data.
"""
import csv
import os
from pathlib import Path
import tempfile
import threading
import unittest

from explorer import Explorer
from finder import candidates, examine


class NativeIntegrityTests(unittest.TestCase):
    def _fake_binary(self, directory, row):
        path = Path(directory) / 'native.sh'
        # Keep the fixture self-contained; the native binary is not trusted by default.
        columns = ('version', 'seed', 'chunk_x', 'chunk_z', 'x', 'z',
                   'projected_surface_y', 'biome_id', 'classification')
        import io
        out = io.StringIO()
        writer = csv.DictWriter(out, fieldnames=columns)
        writer.writeheader()
        writer.writerow(row)
        import shlex
        path.write_text('#!/bin/sh\nprintf %s ' + shlex.quote(out.getvalue()) + '\n', encoding='utf-8')
        path.chmod(0o700)
        return path

    def _row(self):
        sample = next(candidates(123, 8192))
        return {'version': '1.21.8', **sample, 'projected_surface_y': '55',
                'biome_id': '1', 'classification': 'estimated_only'}

    def _scan(self, binary):
        explorer = Explorer('1.21.8', mode='estimate', radius=8192, binary=binary)
        pause = threading.Event()
        pause.set()
        return explorer._one(123, threading.Event(), pause)

    @unittest.skipIf(os.name == 'nt', 'POSIX shell fixture; Windows executable support tested separately')
    def test_valid_native_sample_preserves_provisional_status(self):
        with tempfile.TemporaryDirectory() as directory:
            rows = self._scan(self._fake_binary(directory, self._row()))
            self.assertEqual(rows[0]['classification'], 'estimated_only')

    @unittest.skipIf(os.name == 'nt', 'POSIX shell fixture; Windows executable support tested separately')
    def test_wrong_seed_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            row = self._row()
            row['seed'] = 456
            with self.assertRaisesRegex(RuntimeError, 'seed'):
                self._scan(self._fake_binary(directory, row))

    @unittest.skipIf(os.name == 'nt', 'POSIX shell fixture; Windows executable support tested separately')
    def test_wrong_version_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            row = self._row()
            row['version'] = '26.3'
            with self.assertRaisesRegex(RuntimeError, 'version'):
                self._scan(self._fake_binary(directory, row))

    @unittest.skipIf(os.name == 'nt', 'POSIX shell fixture; Windows executable support tested separately')
    def test_not_actual_candidate_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            row = self._row()
            row['chunk_x'] = int(row['chunk_x']) + 1
            row['x'] = int(row['chunk_x']) * 16
            with self.assertRaisesRegex(RuntimeError, 'candidate'):
                self._scan(self._fake_binary(directory, row))

    @unittest.skipIf(os.name == 'nt', 'POSIX shell fixture; Windows executable support tested separately')
    def test_invalid_sample_y_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            row = self._row()
            row['projected_surface_y'] = '9999'
            with self.assertRaisesRegex(RuntimeError, 'height'):
                self._scan(self._fake_binary(directory, row))

    def test_wrong_chunk_position_does_not_count_as_verified(self):
        original = {'DataVersion': 4440, 'Status': 'minecraft:full',
                    'xPos': 1, 'zPos': 2, 'structures': {'starts': {}}}
        result = examine(original, 123, 0, 2, data_version=4440)
        self.assertEqual(result['status'], 'invalid_nbt')


if __name__ == '__main__':
    unittest.main()

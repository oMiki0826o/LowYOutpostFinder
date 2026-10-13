"""File: test_certification.py
Modification: 2026-10-13 — verification manifest requires authentic input provenance.
"""
import argparse
import csv
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lowy_outpost_finder.certification import certify_samples
from lowy_outpost_finder.noise_witness import run_compare, run_witnesses, WITNESS_FIELDS


def witnesses(path, *, asset='abc', y=-30):
    record = dict.fromkeys(WITNESS_FIELDS, '')
    record.update(version='1.21.8', seed=123, chunk_x=10, chunk_z=-3, sample_x=160,
                  sample_z=-48, rotation=0, world_surface_wg=y+1, base_plate_y=y,
                  watchtower_min_y=y, watchtower_max_y=y+20, asset_sha256=asset,
                  evidence='derived_from_vanilla_saved_jigsaw')
    with path.open('w', newline='', encoding='utf-8') as fp:
        w=csv.DictWriter(fp,fieldnames=WITNESS_FIELDS);w.writeheader();w.writerow(record)
    return path


def estimates(path, *, y=-30):
    path.write_text('version,seed,chunk_x,chunk_z,sample_x,sample_z,rotation,projected_base_plate_y,classification\n'
                    f'1.21.8,123,10,-3,160,-48,0,{y},estimated_only\n', encoding='utf-8')
    return path


class CertificationTests(unittest.TestCase):
    def test_good_samples_remain_finite_not_global_claim(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            result=certify_samples(witnesses(p/'w.csv'), estimates(p/'e.csv'), expected_asset_sha256='abc')
            self.assertEqual(result['comparison']['maximum_absolute_error'],0)
            self.assertTrue(result['all_compared_samples_match'])
            self.assertFalse(result['global_exactness_proven'])
            self.assertEqual(result['witness_count'],1)
            self.assertEqual(len(result['input_sha256']['witnesses']),64)

    def test_nonzero_height_difference_is_not_certified(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            result=certify_samples(witnesses(p/'w.csv'), estimates(p/'e.csv',y=-25),expected_asset_sha256='abc')
            self.assertFalse(result['all_compared_samples_match'])
            self.assertEqual(result['comparison']['maximum_absolute_error'],5)

    def test_assets_must_match_expected_and_be_consistent(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            with self.assertRaisesRegex(ValueError, 'asset'):
                certify_samples(witnesses(p/'w.csv'), estimates(p/'e.csv'), expected_asset_sha256='def')

    def test_cli_rejects_mismatched_game_jar_without_overwriting_output(self):
        import zipfile
        from lowy_outpost_finder.certification import run_certification
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            witness=witnesses(root/'w.csv');pred=estimates(root/'e.csv')
            archive=root/'wrong.jar'
            with zipfile.ZipFile(archive, 'w') as z:
                z.writestr('version.json', '{"id":"26.3"}')
            saved=root/'certification.json';saved.write_text('original')
            args=argparse.Namespace(witnesses=witness, estimates=pred, game_jar=archive,
                                    out=saved, require_matches=True)
            with self.assertRaisesRegex(ValueError,'mismatch'):
                run_certification(args)
            self.assertEqual(saved.read_text(),'original')

    def test_zero_samples_never_count_as_pass(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            witnessed=witnesses(p/'w.csv');est=estimates(p/'e.csv')
            witnessed.write_text(','.join(WITNESS_FIELDS)+'\n',encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'No verified'):
                certify_samples(witnessed, est, expected_asset_sha256='abc')

    def test_failed_compare_guard_preserves_preexisting_files(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            witnessed=witnesses(p/'w.csv');est=estimates(p/'e.csv')
            est.write_text('version,seed,chunk_x,chunk_z,sample_x,sample_z,rotation,projected_base_plate_y,classification\n',encoding='utf-8')
            output=p/'keep.csv';summary=p/'keep.json'; output.write_text('pristine');summary.write_text('pristine')
            args=argparse.Namespace(witnesses=witnessed,estimates=est,out=output,summary=summary,require_samples=True)
            with self.assertRaisesRegex(ValueError, 'No comparable'):
                run_compare(args)
            self.assertEqual(output.read_text(),'pristine')
            self.assertEqual(summary.read_text(),'pristine')

    def test_failed_witness_guard_preserves_preexisting_files(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);out=p/'keep.csv';out.write_text('pristine')
            args=argparse.Namespace(world=p, candidates=p, game_jar=p, out=out, summary=None, require_samples=True)
            with patch('lowy_outpost_finder.noise_witness.audit_world', return_value=([{
                'version':'1.21.8', 'seed':123, 'chunk_x':0, 'chunk_z':0,
                'status':'not_full'}],{'version':'1.21.8','seed':123,'game_asset_sha256':'abc'})):
                with self.assertRaisesRegex(ValueError,'No verified'):
                    run_witnesses(args)
            self.assertEqual(out.read_text(),'pristine')


if __name__=='__main__':
    unittest.main()

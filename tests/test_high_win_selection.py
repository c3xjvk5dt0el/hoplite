import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from research.high_win.study import fallback, model_fingerprint, verified_lock, write_json
from research.high_win.replay_ticks import ReplayDataError, verify_final_request, _tick_epoch


class SelectionTests(unittest.TestCase):
    def make_lock(self, root):
        validation={'phase':'validate','model':model_fingerprint(),'locked_candidate_id':'sweep_24_stop1.25_rr1.00'}
        write_json(root/'validate.json',validation)
        lock={'model':validation['model'],'candidate_id':validation['locked_candidate_id'],
              'validation_sha256':hashlib.sha256((root/'validate.json').read_bytes()).hexdigest()}
        write_json(root/'lock.json',lock)
        return root/'lock.json'

    def test_fingerprint_covers_selection_and_imported_indicators(self):
        self.assertIn('research/high_win/study.py',model_fingerprint())
        self.assertIn('research/backtest_pullback.py',model_fingerprint())

    def test_completed_lock_and_exact_final_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=self.make_lock(Path(tmp))
            self.assertEqual(verified_lock(path)['candidate_id'],'sweep_24_stop1.25_rr1.00')
            verify_final_request(path,'sweep_24_stop1.25_rr1.00','2026-06-01','2026-09-01')
            for candidate,start,end in [('another','2026-06-01','2026-09-01'),
                                        ('sweep_24_stop1.25_rr1.00','2026-07-01','2026-09-01')]:
                with self.assertRaises(ReplayDataError):
                    verify_final_request(path,candidate,start,end)

    def test_modified_validation_or_model_cannot_reuse_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=self.make_lock(Path(tmp))
            with patch('research.high_win.study.model_fingerprint',return_value={}):
                with self.assertRaises(ValueError): verified_lock(path)
            (Path(tmp)/'validate.json').write_text('{}')
            with self.assertRaises(ValueError): verified_lock(path)

    def test_artifact_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'result.json';write_json(path,{'original':True})
            with self.assertRaises(FileExistsError): write_json(path,{'changed':True})
            self.assertEqual(json.loads(path.read_text()),{'original':True})

    def test_no_trade_candidate_cannot_win_fallback(self):
        def record(name,count,net):
            return {'candidate':{'id':name},'base':{'trades':count},
                    'stress':{'net_usd':net,'closed_trade_max_drawdown_usd':50,'profit_factor':.9}}
        self.assertEqual(fallback([record('idle',0,0),record('active',201,-50)])['candidate']['id'],'active')
        with self.assertRaises(ValueError): fallback([record('idle',0,0)])

    def test_tick_clock_matches_mql_whole_seconds(self):
        cache={}
        a=_tick_epoch('2026-06-01 07:00:30.001Z',cache)
        b=_tick_epoch('2026-06-01 07:00:30.999Z',cache)
        c=_tick_epoch('2026-06-01 07:00:31.000Z',cache)
        self.assertEqual(a,b)
        self.assertEqual(c,b+1)


if __name__=='__main__': unittest.main()

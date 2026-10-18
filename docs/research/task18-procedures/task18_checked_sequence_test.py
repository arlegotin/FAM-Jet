import json,tempfile,unittest
from pathlib import Path
from task18_checked_sequence import run_sequence
class SequenceTests(unittest.TestCase):
 def check_case(self, mode, failed_phase, expected_calls):
  with tempfile.TemporaryDirectory() as t:
   phases=[{'command':n,'summary':str(Path(t)/f'{n}.json'),'expected_status':'passed'} for n in ('endpoint','risk','bank')];calls=[]
   def run(command):
    calls.append(command);p=next(p for p in phases if p['command']==command)
    if command==failed_phase:
     if mode=='nonzero':return 1
     if mode=='missing':return 0
     if mode=='failed':Path(p['summary']).write_text(json.dumps({'status':'failed_original_tolerance'}));return 0
    Path(p['summary']).write_text(json.dumps({'status':'passed'}));return 0
   with self.assertRaises((RuntimeError,FileNotFoundError)):run_sequence(phases,run)
   self.assertEqual(calls,expected_calls)
 def test_endpoint_failure_blocks_risk_and_bank(self):self.check_case('nonzero','endpoint',['endpoint'])
 def test_endpoint_missing_blocks_risk_and_bank(self):self.check_case('missing','endpoint',['endpoint'])
 def test_endpoint_failed_summary_blocks_risk_and_bank(self):self.check_case('failed','endpoint',['endpoint'])
 def test_risk_failure_blocks_bank(self):self.check_case('nonzero','risk',['endpoint','risk'])
 def test_risk_missing_blocks_bank(self):self.check_case('missing','risk',['endpoint','risk'])
 def test_risk_failed_summary_blocks_bank(self):self.check_case('failed','risk',['endpoint','risk'])
 def test_success_sequence(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'summary.json';p.write_text('{"status":"passed"}');calls=[];run_sequence([{'command':x,'summary':str(p),'expected_status':'passed'} for x in ('endpoint','risk','bank')],lambda x:calls.append(x) or 0);self.assertEqual(calls,['endpoint','risk','bank'])
if __name__=='__main__':unittest.main()

"""Small controls only: never builds the scientific fixture allocation."""
from decimal import Decimal, localcontext
import importlib
import json
from pathlib import Path

import pytest


def module(name):
    return importlib.import_module('validation.kernel_stage_a.' + name)


def test_descriptor_bits_marker_ties_skips_and_execution_order():
    d = module('descriptors')
    rows = d.fixtures()
    assert len(rows) == 32
    assert rows[0].events == ()
    assert rows[10].events[0].age.hex() == '0x1.fffffffffffffp+0'
    assert rows[21].upper == 5224 + 2.**-20
    assert [e.values[0] for e in rows[29].events] == [1., 2.**500, -2.**500]
    writes = d.timeline(rows[29], 'I')
    assert [e['event_id'] for e in writes] == [0, 1, 2, 3]
    assert [e['values'][0] for e in writes] == [1., 2.**500, -2.**500, 0.]
    assert writes[-1]['observed'] is False and writes[-1]['time'] == 0
    slots = list(d.slots())
    assert len(slots) == 128
    assert [(s.row, s.transform) for s in slots[:2]] == [(1, 'I'), (2, 'I')]
    assert [s.row for s in slots[32:35]] == [32, 31, 30]
    assert [s.row for s in slots[96:100]] == [1, 3, 5, 7]
    assert [s.row for s in slots if not s.applicable] == [15, 13, 12, 11]
    assert len({s.history_id for s in slots}) == 128
    assert sum(s.applicable for s in slots) * 6 == 744
    assert d.candidates() == (('jet', 1e-10), ('bank', 1e-10), ('bank', 1e-6),
                              ('jet', 1e-6), ('jet', 1e-2), ('bank', 1e-2))
    for row in rows:
        for transform in ('I', 'U', 'R'):
            d.timeline(row, transform)
        if row.number not in (11, 12, 13, 15):
            d.timeline(row, 'O')


def test_decimal_closed_integrals_scaled_solve_and_exact_float_input():
    r = module('reference')
    with r.context(80):
        assert r.exact(.1) != Decimal('.1')
        assert r.integral(0, Decimal(2), Decimal(0), Decimal(1)) == (1-Decimal(-2).exp())/2
        assert abs(r.integral(1, Decimal(2), Decimal(0), Decimal(1)) -
                   (1-3*Decimal(-2).exp())/4) < Decimal('1e-78')
        assert r.solve([[Decimal(2), Decimal(1)], [Decimal(1), Decimal(3)]],
                       [Decimal(1), Decimal(2)]) == [Decimal('.2'), Decimal('.6')]
        assert r.ordered_sum([Decimal(1), Decimal(2)**500, -Decimal(2)**500]) == 1
        f = r.Factors('bank', [1.], 1., 5224., 1e-6)
        c, window, residual = f.coefficients(0., 1.)
        eta = r.exact(1.)/r.exact(5224.)
        g = eta/(2+eta)
        b = eta*(1-(-(1+eta)).exp())/(1+eta)
        assert abs(c[0]-b/(g*(1+r.exact(1e-6)))) < Decimal('1e-75')
        assert residual < Decimal('1e-50')


def test_reference_guards_finite_comparisons_and_three_way_policy():
    r = module('reference')
    with r.context(80):
        ok = r.decode([Decimal(1)], [[Decimal(2)]], [Decimal(1)], [0.])
        assert ok['code'] == 0
        assert abs(ok['prediction'][0]-Decimal(2)/(1+r.exact(1e-8))) < Decimal('1e-75')
        tiny = r.decode([Decimal(0)], [[Decimal(0)]], [Decimal(1)], [3.])
        assert tiny['code'] == 5 and tiny['prediction'] == [Decimal(3)]
        assert r.decode([Decimal(-1)], [[Decimal(2)]], [Decimal(1)], [0.])['code'] == 3
        assert r.decode([Decimal(1)], [[Decimal(2)]], [Decimal(1)], [0.], quarantined=True)['code'] == 1
    p = dict(code=0, prediction=[1.], mass=2., bound=0., raw=[2.])
    a = dict(p)
    b = dict(p, prediction=[2.])
    outcome = r.compare_three(p, a, b)
    assert outcome['reader_arithmetic'] == 'PASS'
    assert outcome['source_state_fidelity'] == 'FAILED'
    assert outcome['end_to_end_gate'] == 'FAILED'
    assert outcome['stop'] == 'continue'
    assert r.compare_three(b, a, a)['stop'] == 'candidate'
    assert r.compare(dict(p,coefficients=[[1.]]),dict(a,coefficients=[[2.]]))['status']=='FAILED'
    assert r.compare(dict(p,windows=[dict(p,mass=2.)]),dict(a,windows=[dict(a,mass=3.)]))['status']=='FAILED'
    assert r.compare(dict(code=5,prediction=None,mass=0.,raw=None),
                     dict(code=5,prediction=[3.,4.],mass=0.,raw=None))['status']=='PASS'
    with pytest.raises(r.ReferenceFailure, match='threshold'):
        r.stable_margin(Decimal(0), Decimal(0))
    with pytest.raises(r.ReferenceFailure, match='precision'):
        r.agree([Decimal(1)], [Decimal(2)])


def test_unit_metadata_transport_retains_original_and_changes_only_units():
    a = module('authority')
    original = {'fit_provenance': {'t_ref': 1., 'writer_hash': 'a'*64, 'split': 'training'},
                'target_statistics': {'tasks': {'mean': {'mean': [2.]}}}}
    derived, audit = a.unit_metadata(original, 'b'*64, [0.25], [0.03125])
    assert original['fit_provenance']['t_ref'] == 1.
    assert derived['fit_provenance'] == {'t_ref': 8., 'writer_hash': 'b'*64, 'split': 'training'}
    assert derived['target_statistics'] == original['target_statistics']
    assert audit['kind'] == 'DERIVED unit transport'
    assert audit['parent'] == original
    with pytest.raises(ValueError, match='dimensionless'):
        a.unit_metadata(original, 'b'*64, [.25], [.03])


def test_authority_refuses_null_unknown_mismatch_before_backend(tmp_path):
    a = module('authority')
    calls = []
    prospective = json.loads(Path('validation/kernel_stage_a/prospective-seal.json').read_text())
    with pytest.raises(a.AuthorityError, match='null'):
        a.verify(prospective, Path.cwd())
    with pytest.raises(a.AuthorityError):
        a.verify(dict(prospective, extra=True), Path.cwd())
    driver = module('driver')
    with pytest.raises(a.AuthorityError):
        driver.run(prospective, Path.cwd(), lambda *x: calls.append(x))
    assert calls == []


class ControlledBackend:
    """No production imports, factors, scientific fixtures or reference calls."""
    def __init__(self, fail='source'):
        self.fail = fail
        self.executed = 0

    def setup(self, candidate, ledger):
        ledger.call('factor', lambda: None)

    def slot(self, candidate, slot, ledger):
        self.executed += 1
        ledger.call('read', lambda: None)
        if self.fail == 'common':
            raise module('driver').CommonFailure('controlled common prerequisite')
        scope = 'source_state_fidelity' if self.fail == 'source' else 'reader_arithmetic'
        return {scope: 'FAILED', 'end_to_end_gate': 'FAILED',
                'stop': 'continue' if self.fail == 'source' else 'candidate'}


@pytest.mark.parametrize('failure, reads, status', [('source', 744, 'FAILED'),
                                                  ('reader', 6, 'FAILED'), ('common', 1, 'STOPPED')])
def test_bounded_sequential_orchestration_preserves_failure_attribution(failure, reads, status):
    driver = module('driver')
    b = ControlledBackend(failure)
    result = driver.execute(b, checkpoint=lambda: None)
    assert result['status'] == status
    assert result['counts']['read'] == reads
    assert result['counts']['factor'] <= 6
    assert b.executed == reads
    assert len(result['inventory']) == 768


def test_budget_cancellation_and_unexpected_engine_error_stop_all():
    d = module('driver')
    ledger = d.Ledger()
    ledger.counts['read'] = 768
    with pytest.raises(d.CommonFailure, match='read cap'):
        ledger.call('read', lambda: pytest.fail('must refuse before call'))
    with pytest.raises(KeyboardInterrupt):
        d.execute(ControlledBackend(), checkpoint=lambda: (_ for _ in ()).throw(KeyboardInterrupt()))
    class Broken(ControlledBackend):
        def slot(self, *args):
            raise RuntimeError('reference engine unexpectedly failed')
    result = d.execute(Broken(), checkpoint=lambda: None)
    assert result['status'] == 'STOPPED'
    assert 'RuntimeError' in result['failure']


def test_reference_event_sum_delay_contrast_and_stability_are_independent():
    r = module('reference')
    with r.context(80):
        f = r.Factors('jet', [0.5], 1., 5224., 1e-6)
        events = [dict(time=-2., values=[3.], key=0, observed=True)]
        n,u = r.event_state(f,events,0.,1.,1.)
        assert abs(n[0]-Decimal(-1).exp()) < Decimal('1e-78')
        assert n[0] == n[1]
        n2,u2 = r.advance(f,n,u,2.,1.)
        assert abs(n2[0]-Decimal(-2).exp()) < Decimal('1e-78')
        assert abs(n2[1]-2*Decimal(-2).exp()) < Decimal('1e-78')
        assert abs(u2[1][0]-3*n2[1]) < Decimal('1e-75')
        result = r.evaluate(f,n,u,0.,4.,'contrast',[0.],solve_call=lambda fn:fn())
        assert len(result['windows']) == 2
        if result['code'] == 0:
            assert result['prediction'] == [result['windows'][0]['prediction'][0]-result['windows'][1]['prediction'][0]]
        r.validate_pair(result,result)
    with pytest.raises(r.ReferenceFailure,match='residual'):
        r.validate_pair({'residuals':[Decimal('1e-40')]},{'residuals':[Decimal('1e-40')]})


def test_monitor_stops_whole_process_group_and_charges_temporary_outputs(tmp_path):
    m = module('monitor')
    import sys
    out = tmp_path/'out'
    result = m.supervise([sys.executable,'-c','import time; time.sleep(10)'],out,
                         outer_seconds=.1,output_bytes=8192,free_disk_bytes=0,sampler=lambda pid:{pid:10})
    assert result['status'] == 'STOPPED'
    assert result['reason'] == 'outer timeout'
    assert result['returncode'] is not None
    assert result['absolute_process_tree_peak_bytes'] >= 0
    out2=tmp_path/'out2'
    code='from pathlib import Path; import time; Path("temporary.bin").write_bytes(b"x"*8192); time.sleep(10)'
    result=m.supervise([sys.executable,'-c',code],out2,outer_seconds=2,output_bytes=8192,free_disk_bytes=0,sampler=lambda pid:{pid:10})
    assert result['reason'] == 'output cap'
    assert (out2/'temporary.bin').exists()


def test_transport_snapshot_keeps_poison_bits_and_canonical_metric(tmp_path):
    p=module('production')
    import torch
    from famjet.types import Snapshot
    from famjet.eval.state_io import snapshot_hash
    base=Snapshot({'z':torch.tensor([[[[[2.,1.]]]]],dtype=torch.float64),
                   'h':torch.tensor([[[[[.5,.25]]]]],dtype=torch.float64),
                   'history_hash':torch.zeros((1,32),dtype=torch.uint8),
                   'time_unit_hash':torch.zeros(32,dtype=torch.uint8)},
                  torch.tensor([0.],dtype=torch.float64),torch.tensor([True]),'a'*64,torch.tensor([2]))
    before=snapshot_hash(base)
    slot=next(s for s in module('descriptors').slots() if s.row==3 and s.transform=='R')
    changed=p.transport_snapshot(base,slot,'jet','a'*64)
    assert torch.equal(changed.payload['h'],base.payload['h'])
    assert snapshot_hash(base)==before
    poisoned=p.inject(base,scale=1.,poison=True)
    raw=poisoned.payload['z'][0,0,0,0,0].view(torch.int64).item()
    assert raw==0x7ff8000000000000
    assert not torch.isnan(base.payload['z']).any()
    scaled=p.inject(base,scale=2.**-20,poison=False)
    assert scaled.payload['z'][0,0,0,0,-1].item()==2.**-20


def test_reference_import_is_closed_to_production_and_numpy():
    import subprocess,sys
    code='''
import importlib.abc,sys
class Block(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,*args):
  if fullname.split('.')[0] in ('famjet','torch','numpy','scipy'):
   raise RuntimeError('forbidden reference import '+fullname)
sys.meta_path.insert(0,Block())
from validation.kernel_stage_a.reference import context,Factors
with context(80):
 assert len(Factors('bank',[1.],1.,5224.,1e-6).coefficients(0.,1.)[0])==1
'''
    result=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True)
    assert result.returncode==0,result.stderr


def test_exact_synthetic_authority_detects_identity_release_and_deadline_mutations(tmp_path,monkeypatch):
    a=module('authority'); import time
    from copy import deepcopy
    record=tmp_path/'record.json'; record.write_text('{}')
    record_ref=dict(path=str(record),sha256=a.file_hash(record))
    started=time.monotonic()
    setup=tmp_path/'setup.json'
    setup.write_text(json.dumps(dict(actual_factor_constructions=6,actual_reads=0,allocation_start_monotonic=started)))
    observed=dict(package_hash=a.PACKAGE,host_identity={'node':'synthetic'},source_full_git='synthetic')
    monkeypatch.setattr(a,'observe',lambda root:observed)
    monkeypatch.setattr(a,'git',lambda *args:'')
    for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS'):
        monkeypatch.setenv(key,'1')
    p=dict(implementation_review=dict(record_ref,approved=True),
           represented_rate_records={family:record_ref for family in ('jet','bank')},
           static_exports={f'{family}:{rho.hex()}':record_ref for family,rho in module('descriptors').candidates()},
           resource_measurement_boundary_seal=dict(baseline='post-import/pre-allocation per worker',absolute_rss=True,
                process_tree_rss=True,sequential_workers=True,outputs_include_temporaries=True,
                allocation_start_monotonic=started,deadline_monotonic=started+600,allocation_start_utc_epoch=time.time(),
                setup_ledger=dict(path=str(setup),sha256=a.file_hash(setup))),
           fresh_launch_snapshot=dict(utc_epoch=time.time(),free_disk_bytes=2**40,power_observation='synthetic only',host_identity=observed['host_identity']),
           output_directory=str(tmp_path/'output'))
    setupdir=tmp_path/'setup-outputs'; setupdir.mkdir()
    setup.write_text(json.dumps(dict(actual_factor_constructions=6,actual_reads=0,allocation_start_monotonic=started,
          package_hash=a.PACKAGE,source_full_git='synthetic',static_exports=p['static_exports'],
          represented_rate_records=p['represented_rate_records'],output_directory=str(setupdir),output_peak_bytes=100,
          incremental_worker_peak_bytes=100)))
    p['resource_measurement_boundary_seal']['setup_ledger']['sha256']=a.file_hash(setup)
    seal=dict(version=1,scope='Task18 kernel Stage A only',observed=observed,pending=p,limits=a.LIMITS)
    seal['root_stage_A_release']=dict(approved=True,scope='Stage A scientific execution',payload_sha256=a.digest(seal),
                                        ruling_path=str(record),ruling_sha256=a.file_hash(record))
    assert a.verify(seal,tmp_path)==p
    for mutate in (lambda x:x['observed'].update(package_hash='0'*64),
                   lambda x:x['root_stage_A_release'].update(payload_sha256='0'*64),
                   lambda x:x['pending']['resource_measurement_boundary_seal'].update(deadline_monotonic=0),
                   lambda x:x['pending']['static_exports'].clear()):
        broken=deepcopy(seal); mutate(broken)
        with pytest.raises(a.AuthorityError): a.verify(broken,tmp_path)


def test_monitor_memory_cap_requires_actual_post_import_baseline(tmp_path):
    m=module('monitor'); import sys
    code='''
import json,os,time
from pathlib import Path
Path('monitor-events.jsonl').write_text(json.dumps(dict(event='baseline',pid=os.getpid(),rss=10))+'\\n')
time.sleep(10)
'''
    result=m.supervise([sys.executable,'-c',code],tmp_path/'memory',outer_seconds=2,
                       incremental_bytes=50,free_disk_bytes=0,sampler=lambda pid:{pid:100})
    assert result['reason']=='incremental worker memory cap'
    assert result['incremental_worker_peak_bytes']==90
    assert result['workers'][next(iter(result['workers']))]['baseline_bytes']==10


def test_cli_refuses_prospective_seal_without_importing_backend(tmp_path):
    import subprocess,sys
    result=subprocess.run([sys.executable,'-m','validation.kernel_stage_a','--seal',
                           'validation/kernel_stage_a/prospective-seal.json'],capture_output=True,text=True)
    assert result.returncode==2
    assert 'null execution authority' in result.stderr


def test_read_worker_trace_counts_real_small_analytic_calls_without_factorization():
    import torch
    from famjet.readers.kernel_projection import KernelProjection
    trace=module('reader_worker').Trace()
    reader=KernelProjection(torch.tensor([1.],dtype=torch.float64),'bank',1.)
    import sys
    sys.setprofile(trace.profile)
    try:
        value,diagnostic=reader.window(torch.tensor([1.],dtype=torch.float64),
                                      torch.tensor([[2.]],dtype=torch.float64),0.,1.)
    finally: sys.setprofile(None)
    assert value is not None
    assert trace.counts['coefficients']==1
    assert trace.counts['window_vector']==2
    assert trace.counts['factor']==0
    assert trace.windows[0]['raw'][0]>0


def test_observed_schema_and_package_match_read_only_registered_interfaces():
    from famjet.eval.isolation import REGISTRY_VERSION,source_identity
    from famjet.eval.state_io import FORMAT_VERSION
    observed=module('authority').observe(Path.cwd())
    assert observed['snapshot_schema']['registry_version']==REGISTRY_VERSION
    assert observed['snapshot_schema']['format_version']==FORMAT_VERSION
    assert observed['package_hash']==source_identity()==module('authority').PACKAGE


def test_observer_helper_requires_exact_declared_pid_parent_executable_and_argv():
    m=module('monitor')
    entry=dict(pid=30,parent=20,executable=m.PS,argv=m.PS_ARGV)
    declared={30:entry}
    processes={10:dict(parent=1,executable='/python',argv=[]),
               20:dict(parent=10,executable='/python',argv=[]),30:entry}
    roles=m.classify(10,processes,{10:100,20:100},declared)
    assert roles=={10:'worker',20:'worker',30:'observer_helper'}
    assert m.classify(10,processes,{10:100},declared)[30]=='unaccounted'
    for change in (dict(parent=99),dict(executable='/tmp/ps'),dict(argv=[m.PS,'different'])):
        altered=dict(processes,**{})
        altered[30]=dict(entry,**change)
        assert m.classify(10,altered,{10:100,20:100},declared)[30]=='unaccounted'
    assert m.classify(10,processes,{10:100,20:100},{})[30]=='unaccounted'


def test_observed_helper_peak_is_charged_even_if_declaration_arrives_after_exit(tmp_path):
    m=module('monitor'); import sys
    code='''
import json,os,time
from pathlib import Path
p=Path('monitor-events.jsonl')
p.write_text(json.dumps(dict(event='baseline',pid=os.getpid(),rss=10))+'\\n')
time.sleep(.08)
with p.open('a') as f:
 f.write(json.dumps(dict(event='observer_helper',pid=os.getpid()+100000,parent=os.getpid(),executable='/bin/ps',argv=['/bin/ps','-axo','pid=,ppid=,rss=,comm=,args=']))+'\\n')
time.sleep(10)
'''
    polls=[0]
    def sample(pid):
        polls[0]+=1
        helper=dict(pid=pid+100000,parent=pid,executable=m.PS,argv=m.PS_ARGV)
        readings={pid:100}
        if polls[0]<3: readings[pid+100000]=20
        return m.ResidentTree(readings,{pid:dict(parent=1,executable='/python',argv=[]),pid+100000:helper})
    result=m.supervise([sys.executable,'-c',code],tmp_path/'helper',outer_seconds=.3,
                        free_disk_bytes=0,incremental_bytes=100,sampler=sample)
    assert result['reason']=='incremental worker memory cap'
    assert result['incremental_worker_peak_bytes']==110

"""Controlled completion-resource boundaries; no scientific or native launch."""
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from validation.kernel_stage_a import authority, driver, monitor
from validation.kernel_stage_a import __main__ as cli


def _seal(start, seconds=1200, limits=None):
    return dict(version=1, scope='Task18 kernel Stage A only', observed={},
                pending={name: 'controlled' for name in authority.PENDING},
                limits=limits if limits is not None else authority.LIMITS,
                root_stage_A_release={'approved': True}) | {
                    'pending': {**{name: 'controlled' for name in authority.PENDING},
                                'resource_measurement_boundary_seal': {
                                    'allocation_start_monotonic': start,
                                    'deadline_monotonic': start+seconds}}}


def test_shared_authority_deadline_accepts_exact_allocation_and_rejects_old_and_expired(monkeypatch):
    clock=SimpleNamespace(now=100.0)
    monkeypatch.setattr(authority.time, 'monotonic', lambda: clock.now)
    assert authority.entry(_seal(100.0)) == 1300.0
    for seal in (_seal(100.0, 600), _seal(100.0, limits=dict(authority.LIMITS, output_bytes=67108864))):
        with pytest.raises(authority.AuthorityError): authority.entry(seal)
    clock.now=1300.0
    with pytest.raises(authority.AuthorityError, match='deadline'):
        authority.entry(_seal(100.0))


@pytest.mark.parametrize(('candidate_start', 'elapsed', 'expected'),
                         [(0, 179.999, None), (0, 180.0, 'candidate timeout'),
                          (1100, 1199.999, None), (1100, 1200.0, 'outer timeout')])
def test_driver_uses_adopted_candidate_and_outer_edges(monkeypatch, candidate_start, elapsed, expected):
    # Controlled one-slot inventory keeps the real driver checks and ledger active.
    candidate=('jet', 1e-10)
    slot=SimpleNamespace(row=1, transform='I', applicable=True)
    monkeypatch.setattr(driver, 'candidates', lambda: (candidate,))
    monkeypatch.setattr(driver, 'slots', lambda: (slot,))
    ticks=iter((100.0, *(100.0+candidate_start for _ in range(4)),
                100.0+elapsed, 100.0+elapsed))
    monkeypatch.setattr(driver.time, 'monotonic', lambda: next(ticks, 100.0+elapsed))
    class Backend:
        def setup(self, candidate, ledger): pass
        def slot(self, candidate, slot, ledger):
            return {'stop': 'continue'}
    result=driver.execute(Backend(), checkpoint=lambda: None)
    assert (result['failure'] or '').endswith(expected or '') if expected else result['status']=='PASS'


def test_cli_passes_common_output_and_time_policy_to_supervisor(tmp_path, monkeypatch, capsys):
    setup=tmp_path/'setup.json'
    setup.write_text(json.dumps({'output_directory': str(tmp_path/'setup-output')}))
    seal=_seal(100.0)
    seal['pending']['resource_measurement_boundary_seal']['setup_ledger']={'path': str(setup)}
    seal['pending']['output_directory']=str(tmp_path/'output')
    path=tmp_path/'seal.json'; path.write_text(json.dumps(seal))
    seen=[]
    monkeypatch.setattr(authority.time, 'monotonic', lambda: 101.0)
    monkeypatch.setattr(monitor, 'supervise', lambda command, output, **kw: seen.append(kw) or {'status':'COMPLETED'})
    monkeypatch.setattr(cli.commands, 'stage_command', lambda root, seal: ['/controlled/worker'])
    monkeypatch.setattr(sys, 'argv', ['stage-a', '--seal', str(path)])
    assert cli.main()==0
    assert len(seen)==1
    assert seen[0]['output_bytes']==201326592
    assert seen[0]['outer_ceiling_seconds']==1200
    assert seen[0]['candidate_seconds']==180
    assert seen[0]['outer_seconds']==1199.0
    assert seen[0]['incremental_bytes']==402653184


def test_monitor_ceiling_uses_adopted_override_and_retains_generic_default(tmp_path, monkeypatch):
    # Fail before spawn, after the monitor computes its effective deadline.
    clock=SimpleNamespace(now=100.0)
    monkeypatch.setattr(monitor.time, 'monotonic', lambda: clock.now)
    class Owner:
        pid=570018
        returncode=None
        polls=0
        def poll(self):
            self.polls+=1
            if self.polls>1: self.returncode=0
            return self.returncode
        def wait(self, timeout):
            self.returncode=-9
            return self.returncode
    def controlled_owner(*args, **kwargs):
        clock.now=800.0
        return Owner()
    monkeypatch.setattr(monitor.subprocess, 'Popen', controlled_owner)
    monkeypatch.setattr(monitor.os, 'killpg', lambda *args: None)
    monkeypatch.setattr(monitor.time, 'sleep', lambda seconds: None)
    generic=monitor.supervise(['/controlled'], tmp_path/'generic', outer_seconds=1200,
                               free_disk_bytes=0, sampler=lambda pid: {})
    clock.now=100.0
    adapted=monitor.supervise(['/controlled'], tmp_path/'adapted', outer_seconds=1200,
                               outer_ceiling_seconds=1200, candidate_seconds=180,
                               free_disk_bytes=0, sampler=lambda pid: {})
    assert generic['reason']=='outer timeout'
    assert adapted['reason'] != 'outer timeout'


def test_prospective_seal_remains_null_blocking_at_adopted_limits():
    seal=json.loads(Path('validation/kernel_stage_a/prospective-seal.json').read_text())
    assert seal['limits']==authority.LIMITS
    assert seal['pending']['resource_measurement_boundary_seal'] is None
    assert seal['root_stage_A_release'] is None
    with pytest.raises(authority.AuthorityError, match='null'):
        authority.entry(seal)


def test_live_observation_includes_completion_amendment_without_helper_launch(monkeypatch):
    monkeypatch.setattr(authority,'git',lambda *args,**kwargs:'controlled-head')
    monkeypatch.setattr(authority,'runtime',lambda:{'controlled':True})
    root=Path.cwd()
    observed=authority.observe(root)
    path='docs/amendments/2026-10-19-kernel-stage-a-completion-resources.md'
    assert observed['files'][path]==hashlib.sha256((root/path).read_bytes()).hexdigest()


def test_completion_setup_template_keeps_worker_and_only_changes_resource_policy():
    old=ast.parse(Path('docs/research/task18-stage-a-setup-parent-384mib.py').read_text())
    new=ast.parse(Path('docs/research/task18-stage-a-setup-parent-completion.py').read_text())
    def worker(tree):
        return next(node.value.value for node in tree.body if isinstance(node,ast.Assign)
                    and any(isinstance(t,ast.Name) and t.id=='worker' for t in node.targets))
    assert hashlib.sha256(worker(new).encode()).hexdigest()=='f768a8f98577653e81779f080bac27edddd854b173a3c221e3499b5d21ccc1b0'
    assert worker(new)==worker(old)
    deadline=next(node for node in old.body if isinstance(node,ast.Assign)
                  and any(isinstance(t,ast.Name) and t.id=='deadline' for t in node.targets))
    assert deadline.value.right.value==600.0
    deadline.value.right.value=1200.0
    supervise=next(node for node in ast.walk(old) if isinstance(node,ast.Call)
                   and isinstance(node.func,ast.Name) and node.func.id=='supervise')
    output=next(k for k in supervise.keywords if k.arg=='output_bytes')
    assert output.value.left.value==67108864
    output.value.left.value=201326592
    supervise.keywords.extend([ast.keyword(arg='outer_ceiling_seconds',value=ast.Constant(1200)),
                               ast.keyword(arg='candidate_seconds',value=ast.Constant(180))])
    final_cap=next(node for node in ast.walk(old) if isinstance(node,ast.Compare)
                   and isinstance(node.ops[0],ast.LtE) and isinstance(node.comparators[0],ast.Constant)
                   and node.comparators[0].value==67108864)
    final_cap.comparators[0].value=201326592
    assert ast.dump(old,include_attributes=False)==ast.dump(new,include_attributes=False)


def _body_function(path, outer_name, name, globals_):
    """Execute the original nested boundary function without opening a process."""
    tree=ast.parse(Path(path).read_text())
    outer=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==outer_name)
    target=deepcopy(next(n for n in ast.walk(outer) if isinstance(n,ast.FunctionDef) and n.name==name))
    code=compile(ast.fix_missing_locations(ast.Module(body=[target],type_ignores=[])),path,'exec')
    exec(code,globals_)
    return globals_[name]


def test_monitor_candidate_check_and_reader_context_share_candidate_and_outer_deadline(tmp_path):
    clock=SimpleNamespace(now=279.999)
    state=dict(time=SimpleNamespace(monotonic=lambda:clock.now),_MonitorStop=monitor._MonitorStop,
               deadline=1200.0,work_deadline=1199.9,candidate_start=100.0,candidate_seconds=180,
               candidate_ranges=[(100.0,None)],authority_root=tmp_path,output=tmp_path)
    check=_body_function('validation/kernel_stage_a/monitor.py','supervise','check',state)
    reader_context=_body_function('validation/kernel_stage_a/monitor.py','supervise','reader_context',state)
    check()
    assert reader_context(150.0,151.0)['deadline']==280.0
    clock.now=280.0
    with pytest.raises(monitor._MonitorStop,match='candidate timeout'): check()
    check(final=True)
    assert reader_context(50.0,51.0) is None
    state['candidate_seconds']=90
    clock.now=190.0
    with pytest.raises(monitor._MonitorStop,match='candidate timeout'): check()
    assert reader_context(150.0,151.0)['deadline']==190.0
    state['candidate_start']=None
    clock.now=1199.9
    with pytest.raises(monitor._MonitorStop,match='outer timeout'): check()


def test_monitor_sampler_and_poll_wait_use_earliest_active_deadline():
    tree=ast.parse(Path('validation/kernel_stage_a/monitor.py').read_text())
    outer=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='supervise')
    assignments={n.targets[0].id:n.value for n in ast.walk(outer) if isinstance(n,ast.Assign)
                 and len(n.targets)==1 and isinstance(n.targets[0],ast.Name)
                 and n.targets[0].id in ('applicable','remaining')}
    assert set(assignments)=={'applicable','remaining'}
    state=dict(candidate_start=100.0,candidate_seconds=180,work_deadline=1000.0,
               time=SimpleNamespace(monotonic=lambda:150.0))
    for name in ('applicable','remaining'):
        expression=ast.Expression(body=deepcopy(assignments[name]))
        value=eval(compile(ast.fix_missing_locations(expression),'monitor-bound','eval'),state)
        assert value==(280.0 if name=='applicable' else 130.0)
    state['work_deadline']=250.0
    for name,want in (('applicable',250.0),('remaining',100.0)):
        expression=ast.Expression(body=deepcopy(assignments[name]))
        assert eval(compile(ast.fix_missing_locations(expression),'monitor-bound','eval'),state)==want


def test_production_candidate_deadline_is_minimum_of_candidate_and_shared_allocation():
    tree=ast.parse(Path('validation/kernel_stage_a/production.py').read_text())
    backend=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Backend')
    setup=next(n for n in backend.body if isinstance(n,ast.FunctionDef) and n.name=='setup')
    controlled=deepcopy(setup)
    controlled.body=controlled.body[:3]
    code=compile(ast.fix_missing_locations(ast.Module(body=[controlled],type_ignores=[])),
                 'validation/kernel_stage_a/production.py','exec')
    scope={'authority':authority}
    exec(code,scope)
    for outer,want in ((250.0,190.0),(150.0,150.0)):
        fake=SimpleNamespace(event=lambda kind:10.0,seal={'pending':{
            'resource_measurement_boundary_seal':{'deadline_monotonic':outer}}})
        scope['setup'](fake,('jet',1e-10),None)
        assert fake.candidate_deadline==want

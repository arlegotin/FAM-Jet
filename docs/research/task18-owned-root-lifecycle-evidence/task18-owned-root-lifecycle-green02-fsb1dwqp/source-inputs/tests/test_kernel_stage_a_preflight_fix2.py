"""Synthetic live-authority accounting only; no native helper or backend run."""
import json
import os
import sys

import pytest
from validation.kernel_stage_a import authority,monitor


@pytest.mark.parametrize('stop_for', ['cap','foreign'])
def test_live_authority_helper_is_charged_before_end_and_retained_on_stop(tmp_path,stop_for):
    out=tmp_path/stop_for
    command=[sys.executable,'-c','import time; time.sleep(10)']
    helpers=[]
    def sample(pid):
        helper=dict(pid=pid+100000,parent=pid,executable=authority.GIT,
                    argv=authority.git_commands(tmp_path)[0])
        if not helpers:
            authority.event(out/'monitor-events.jsonl','authority_start',pid=pid)
            authority.event(out/'monitor-events.jsonl','authority_helper',**helper)
            helpers.append(helper['pid'])
        readings={pid:60,helper['pid']:70}
        identities={pid:dict(pid=pid,parent=os.getpid(),executable=sys.executable,argv=command),helper['pid']:helper}
        if stop_for=='foreign':
            foreign=dict(pid=pid+200000,parent=pid,executable='/unowned',argv=['foreign'])
            identities[foreign['pid']]=foreign; readings[foreign['pid']]=7
        return monitor.ResidentTree(readings,identities)
    result=monitor.supervise(command,out,outer_seconds=.4,free_disk_bytes=0,
                              incremental_bytes=100 if stop_for=='cap' else 1000,
                              sampler=sample,authority_root=tmp_path)
    assert result['status']=='STOPPED'
    assert result['reason']==('incremental worker memory cap' if stop_for=='cap' else 'foreign process identity')
    assert result['outer_seconds']<.2
    assert result['authority_full_rss_peak_bytes']==130
    assert result['incremental_worker_peak_bytes']==130
    helper=result['workers'][str(helpers[0])]
    assert helper['sampled_authority_helper'] is True
    assert helper['absolute_peak_bytes']==70
    assert helper['baseline_bytes']==0 and helper['incremental_peak_bytes']==70
    assert result['authority_phase']['completed']==[]
    events=[json.loads(line) for line in (out/'monitor-events.jsonl').read_text().splitlines()]
    assert not any(event['event']=='authority_helper_end' for event in events)
    assert result['returncode']!=0
    # JSON object keys are strings, including the existing PID-keyed phase map.
    assert json.loads((out/'monitor.json').read_text())==json.loads(json.dumps(result))

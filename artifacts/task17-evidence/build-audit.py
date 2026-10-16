"""Task17 deterministic audit; no protected generation or model comparison."""
from pathlib import Path
import hashlib,json,subprocess
from dataclasses import replace
import numpy as np
from famjet.config import load_config
from famjet.data.synthetic import generate_episode
from famjet.eval.controls import kernel_nullspace_fixture,run_controls
from famjet.eval.isolation import source_identity
from famjet.eval.metrics import fit_target_statistics
from famjet.provenance import canonical_hash

base='1ef93681d9f9977e8c0aa5bd7d1c4ab9932c484c'
root=Path('artifacts/task17-evidence')
oldpath=Path('configs/manifests/synthetic_v1.json'); newpath=Path('configs/manifests/synthetic_v2_targets.json')
old=json.loads(oldpath.read_text()); new=json.loads(newpath.read_text())
files=[oldpath,Path('configs/manifests/beijing_v1.json')]+sorted(Path('configs/manifests/synthetic_v1.populations').glob('*.json'))
archive=[]
for path in files:
    previous=subprocess.check_output(['git','show',f'{base}:{path}'])
    current=path.read_bytes()
    assert previous==current,str(path)
    archive.append({'path':str(path),'sha256':hashlib.sha256(current).hexdigest(),'unchanged_from_base':True})
rows=[]
for population,record in new['populations'].items():
    a=json.loads((oldpath.parent/old['populations'][population]['path']).read_text())
    b=json.loads((newpath.parent/record['path']).read_text())
    for namespace,split in a['splits'].items():
        other=b['splits'][namespace]
        assert split['root']==other['root']
        assert len(split['episodes'])==len(other['episodes'])
        for x,y in zip(split['episodes'],other['episodes']):
            assert x['episode_id']==y['episode_id'] and x['regime']==y['regime']
            assert x['hashes']['events']==y['hashes']['events'] and x['hashes']['queries']==y['hashes']['queries']
            rows.append({'population':population,'namespace':namespace,'episode_id':x['episode_id'],
                         'events':x['hashes']['events'],'queries':x['hashes']['queries'],
                         'legacy_oracle_hash':x['hashes']['oracle'],'current_oracle_hash':y['hashes']['oracle']})
c=load_config(Path('configs/data.yaml')); episodes=[[],[]]; differences=[]
primary=json.loads((newpath.parent/new['populations']['primary']['path']).read_text())
for entry in primary['splits']['training']['episodes']:
    g=replace(c.data.generator,namespace='training',regime=entry['regime'])
    pair=[]
    for j,version in enumerate(('initial_spec_v1','initial_spec_v2_targets')):
        e=generate_episode(replace(c,data=replace(c.data,generator_version=version,generator=g)),primary['splits']['training']['root'],entry['episode_id'])
        episodes[j].append(e);pair.append(e.labels.numpy())
    differences.append({'episode_id':entry['episode_id'],'changed_finite_coordinates':int(np.count_nonzero(pair[0]!=pair[1])),
                        'maximum_absolute_difference':float(np.max(abs(pair[0]-pair[1])))})
stats=[fit_target_statistics(e) for e in episodes]
audit={'base_commit':base,'current_package_source_hash':source_identity(),
       'legacy_target_semantics':'observed_event_targets_v1','current_target_semantics':'observed_event_targets_v2',
       'stochastic_seed_namespace':'initial_spec_v1','old_root_seal':old['manifest_hash'],'new_root_seal':new['manifest_hash'],
       'unchanged_archives':archive,'draw_identity_mappings':rows,'primary_training_label_differences':differences,
       'training_statistics_mapping':{'legacy_hash':canonical_hash(stats[0]),'current_hash':canonical_hash(stats[1]),
                                      'legacy':stats[0],'current':stats[1]},
       'beijing':{'legacy_status':'checksum_verified_historical_known_affected_labels','current_preparation':'pending_task22','protected_outputs_opened':False},
       'protected_namespaces':{k:new['splits'][k] for k in ('pilot','confirmation','replication')}}
(root/'version-mapping.json').write_text(json.dumps(audit,indent=2,allow_nan=False)+'\n')
(root/'nullspace.json').write_text(json.dumps(kernel_nullspace_fixture(np.linspace(0,64,48)**1.03,np.geomspace(.02,1.28,4),np.geomspace(.02,1.28,8)),indent=2,allow_nan=False)+'\n')
(root/'controls.json').write_text(json.dumps(run_controls(load_config(Path('configs/smoke.yaml'))),indent=2,allow_nan=False)+'\n')
print(f'{len(archive)} old artifacts byte-identical; {len(rows)} exploratory draws invariant; no protected episodes generated')

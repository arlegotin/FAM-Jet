import hashlib,json,subprocess
from pathlib import Path
root=Path.cwd(); evidence=root/'docs/research/task18-terminal-lifecycle-file-control-evidence'
archive=evidence/'t18f-ot0owjzs'; native=archive/'native'; output=native/'empty-output'
records=[json.loads(line) for line in (output/'monitor-evidence.jsonl').read_text().splitlines()]
runtime=next(row['value'] for row in records if row['kind']=='runtime')
launch=next(row['value'] for row in records if row['kind']=='python_root_launch')
expected=' '.join([runtime['process_image']['path'],*launch['argv'][1:]])
root_rows=[dict(record_index=i,sample_id=row['sample_id'],**entry) for i,row in enumerate(records) if row['kind']=='sample' for entry in row['processes'] if entry['pid']==launch['pid']]
membership=next(dict(record_index=i,**row) for i,row in enumerate(records) if row['kind']=='cleanup_membership')
end=next(dict(record_index=i,**row['value']) for i,row in enumerate(records) if row['kind']=='python_root_end')
resolutions=[dict(record_index=i,**row) for i,row in enumerate(records) if row['kind']=='resolution']
assert len(root_rows)==2 and root_rows[0]['raw_args']==expected and root_rows[1]['raw_args']=='<defunct>'
assert end['returncode']==0 and end['record_index']<resolutions[-1]['record_index']
result=dict(scope='read-only retained evidence; no new OS/process/project imports',source_git='9550cf38f12915ff81a261ff5372febf26d294d4',expected_live_display=expected,live_display_matches_exact_vector=True,root_rows=root_rows,membership=membership,actual_root_end=end,resolutions=resolutions,signal_records=[row for row in records if row['kind']=='cleanup_signal'],stdout=(output/'stdout.log').read_text(),stderr=(output/'stderr.log').read_text(),diagnosis='Short file invocation fixes live argv proof. An actual later defunct row has lost argv and remains unaccounted under unchanged strict classifier despite truthful owning end. Root-only numeric membership is not an empty-group certificate.',survivor_case='NOT RUN',compatibility='NEEDS_CONTEXT')
(archive/'retained-evidence-diagnosis.json').write_text(json.dumps(result,indent=2)+'\n')
files={str(path.relative_to(archive)):dict(bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest()) for path in sorted(native.rglob('*')) if path.is_file()}
(archive/'native-file-inventory.json').write_text(json.dumps(files,indent=2)+'\n')
print(json.dumps(dict(live_raw_equals_expected=True,terminal_raw_args=root_rows[1]['raw_args'],root_returncode=end['returncode'],end_index=end['record_index'],terminal_resolution_index=resolutions[-1]['record_index'],numeric_query_complete=membership['value']['complete'],members=membership['value']['rows'],signals=result['signal_records'],output_bytes=sum(row['bytes'] for path,row in files.items() if path.startswith('native/empty-output/')),survivor_NOT_RUN=True),indent=2))

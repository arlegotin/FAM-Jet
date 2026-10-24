"""Stdlib-only inspection of saved evidence; no model execution or new data reads."""
import ast
from decimal import Decimal, localcontext
import hashlib
import json
from pathlib import Path
import struct
import sys
import time
import zipfile

start_epoch, start = time.time(), time.monotonic()
out = Path(__file__).resolve().parent
assert not (out/'summary.log').exists()
invocation = json.loads((out/'invocation.json').read_bytes())
for path, record in invocation['files'].items():
    raw = Path(path).read_bytes()
    assert len(raw) == record['bytes'] and hashlib.sha256(raw).hexdigest() == record['sha256']
result = json.loads((out/'result.json').read_bytes())
archive = zipfile.ZipFile(out/'first-failure-arrays.npz')


def array_at(name, index):
    raw = archive.read(name+'.npy')
    assert raw[:8] == b'\x93NUMPY\x01\x00'
    length = struct.unpack('<H', raw[8:10])[0]
    header = ast.literal_eval(raw[10:10+length].decode())
    assert header['descr'] == '<f8' and not header['fortran_order']
    offset = 0
    for i, size in zip(index, header['shape']):
        offset = offset*size+i
    return struct.unpack_from('<d', raw, 10+length+8*offset)[0]


with localcontext() as ctx:
    ctx.prec = 70
    rows = {}
    for value, label in ((3, 'numerator'), (8, 'mass')):
        index = (0, 0, 3, 3, value)
        numbers = {n: array_at(n, index) for n in ('direct_h', 'recovered_h', 'l0', 'l1')}
        exact = Decimal(result['first_failure']['queries'][0]['decimal70_terminal_key_ZH'][7][value])
        numbers['decimal70_h'] = str(exact)
        numbers['direct_h_absolute_error_to_decimal'] = str(abs(Decimal.from_float(numbers['direct_h'])-exact))
        numbers['recovered_h_absolute_error_to_decimal'] = str(abs(Decimal.from_float(numbers['recovered_h'])-exact))
        rows[label] = numbers
    summary = {'input_manifest_bytechecks': 'passed',
               'affected_anchor_index': 3, 'affected_key_index': 3,
               'affected_channel': 'raw index16 = H(anchor3,value3)/(H(anchor3,mass)+epsilon)',
               'values': rows,
               'direct_ratio_feature': array_at('direct_raw', (0, 1, 3, 16)),
               'laguerre_ratio_feature': array_at('laguerre_raw', (0, 1, 3, 16)),
               'epsilon_unchanged': result['reader']['epsilon']}
log = json.dumps(summary, indent=2, sort_keys=True)+'\n'
(out/'summary.log').write_text(log)
record = {'argv': [sys.executable, *sys.argv], 'cwd': str(Path.cwd()),
          'start_epoch_seconds': start_epoch, 'end_epoch_seconds': time.time(),
          'elapsed_seconds': time.monotonic()-start, 'exit_code': 0,
          'scope': 'stdlib-only saved-evidence analysis; no model or scientific-library execution',
          'log_bytes': len(log.encode()), 'log_sha256': hashlib.sha256(log.encode()).hexdigest(),
          'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(out/'summary-invocation.json').write_text(json.dumps(record, indent=2, sort_keys=True)+'\n')
print(log, end='')

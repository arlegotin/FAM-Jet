"""Clean worker instrumentation. Accepts ONLY existing closed numeric request."""
from collections import Counter
import json
import math
import sys
import time

import torch
from famjet.eval import isolation
from .monitor import record_baseline


class Trace:
    def __init__(self,emit=lambda kind:None):
        self.counts=Counter(); self.windows=[]; self.coefficients=[]; self.vectors=[]; self.latest_vector=[]; self.emit=emit

    def increment(self,kind):
        self.counts[kind]+=1; self.emit(kind)

    def profile(self,frame,event,arg):
        name=frame.f_code.co_name; path=frame.f_code.co_filename
        if event=='call' and '/famjet/' in path:
            if name in ('coefficients','window_vector','snapshot_record','snapshot_from_record','_advance_payload','_reconstruct','read'):
                self.increment(name)
        if event=='c_call' and getattr(arg,'__name__','')=='clone': self.increment('tensor_clone')
        if event=='c_call' and getattr(arg,'__name__','') in ('linalg_eigh','_linalg_eigh'):
            self.increment('factor'); raise RuntimeError('factorization forbidden in read worker')
        if event=='return' and path.endswith('/famjet/readers/kernel_projection.py'):
            if name=='window_vector' and arg is not None: self.latest_vector[:]=arg.tolist()
            if name=='window' and arg is not None:
                value,diagnostic=arg
                c=frame.f_locals.get('c')
                self.coefficients.append(c.tolist() if c is not None and bool(torch.isfinite(c).all()) else None)
                self.vectors.append(self.latest_vector[:])
                def finite_scalar(v): return v is not None and math.isfinite(v)
                raw=frame.f_locals.get('sums')
                reached=dict(coefficients=self.coefficients[-1] is not None,
                    mass=finite_scalar(diagnostic['mass']),bound=finite_scalar(diagnostic['cancellation_bound']),
                    raw=raw is not None and all(math.isfinite(v) for v in raw),prediction=value is not None)
                self.windows.append(dict(code=diagnostic['code'],prediction=value.tolist() if value is not None else None,
                    mass=diagnostic['mass'] if reached['mass'] else None,
                    bound=diagnostic['cancellation_bound'] if reached['bound'] else None,
                    raw=raw if reached['raw'] else None,reached=reached))
        return self.profile


def main():
    torch.set_num_threads(1); torch.set_num_interop_threads(1)
    record_baseline(sys.argv[1],deadline=float(sys.argv[2]))  # after imports, before numeric request allocation
    request=json.loads(sys.stdin.buffer.read())
    if set(request)!={'method','state','queries','operation','model_hash','source_hash'} or request['operation']!='read':
        raise ValueError('closed read-only worker request required')
    def emit(kind):
        sys.stdout.write(json.dumps(dict(counter=kind))+'\n'); sys.stdout.flush()
    trace=Trace(emit); start=time.monotonic()
    sys.setprofile(trace.profile)
    try: record=isolation._worker(request)
    finally: sys.setprofile(None)
    result=isolation._result_from_record(record)
    numeric=isolation.result_json(result)
    def finite(value):
        if isinstance(value,dict): return {k:finite(v) for k,v in value.items()}
        if isinstance(value,(list,tuple)): return [finite(v) for v in value]
        if type(value) is float and not math.isfinite(value): return None
        return value
    response=finite(dict(numeric=numeric,counts=dict(trace.counts),windows=trace.windows,coefficients=trace.coefficients,
                        window_vectors=trace.vectors,seconds=time.monotonic()-start))
    sys.stdout.write(json.dumps(response,allow_nan=False,separators=(',',':')))

"""Bounded sequential slot driver; scientific backend imported only after seal."""
from collections import Counter
import time
import traceback
from . import authority
from .descriptors import candidates,slots


class CommonFailure(RuntimeError): pass
class CandidateFailure(RuntimeError): pass


class Ledger:
    def __init__(self):
        self.counts=Counter(); self.seconds=Counter(); self.events=[]

    def call(self,kind,function,*args,**kwargs):
        cap={'factor':6,'read':768,'read_dispatch':768}.get(kind)
        if cap is not None and self.counts[kind]>=cap: raise CommonFailure(kind+' cap')
        self.counts[kind]+=1
        start=time.monotonic()
        try: return function(*args,**kwargs)
        finally: self.seconds[kind]+=time.monotonic()-start


def execute(backend,*,checkpoint):
    """Testable control loop. Backend owns no authority; run() supplies it."""
    ledger=Ledger(); inventory=[]; groups=[]; stage_start=time.monotonic(); failure=None
    for candidate in candidates():
        for slot in slots():
            inventory.append(dict(candidate=[candidate[0],candidate[1].hex()],row=slot.row,
                                  transform=slot.transform,status='PENDING' if slot.applicable else 'NONAPPLICABLE'))
    try:
        for ci,candidate in enumerate(candidates()):
            checkpoint(); candidate_start=time.monotonic(); stopped=False
            try: ledger.call('candidate_setup',backend.setup,candidate,ledger)
            except CandidateFailure as exc:
                for row in inventory[ci*128:(ci+1)*128]:
                    if row['status']=='PENDING': row.update(status='UNEXECUTED_FACTOR_FAILED',failure=str(exc))
                continue
            for transform in ('I','O','U','R'):
                group_start=time.monotonic()
                for index,slot in enumerate(slots()):
                    if slot.transform!=transform or not slot.applicable: continue
                    row=inventory[ci*128+index]
                    if stopped: row['status']='UNEXECUTED_CANDIDATE_STOP'; continue
                    checkpoint()
                    if time.monotonic()-candidate_start>=90: raise CommonFailure('candidate timeout')
                    if time.monotonic()-stage_start>=600: raise CommonFailure('outer timeout')
                    start=time.monotonic()
                    outcome=backend.slot(candidate,slot,ledger)
                    row.update(status='EXECUTED',outcome=outcome,seconds=time.monotonic()-start)
                    checkpoint()
                    stopped=outcome['stop']=='candidate'
                groups.append(dict(candidate=[candidate[0],candidate[1].hex()],transform=transform,
                                   seconds=time.monotonic()-group_start))
    except Exception as exc:
        # Engine/schema/resource exceptions NEVER become numerical fallback.
        failure=type(exc).__name__+': '+str(exc)
        ledger.events.append(dict(kind='whole_stage_stop',failure=failure,traceback=traceback.format_exc()))
    for row in inventory:
        if row['status']=='PENDING': row['status']='UNEXECUTED_STAGE_STOP'
    failed=any(row['status'] not in ('EXECUTED','NONAPPLICABLE') or any(
               value=='FAILED' for value in row.get('outcome',{}).values() if type(value) is str) for row in inventory)
    return dict(status='STOPPED' if failure else ('FAILED' if failed else 'PASS'),failure=failure,
                counts=dict(ledger.counts),seconds=dict(ledger.seconds),events=ledger.events,
                inventory=inventory,groups=groups,outer_seconds=time.monotonic()-stage_start)


def run(seal,root,backend_factory=None,*,checkpoint=lambda:None):
    pending=authority.verify(seal,root)
    if backend_factory is None:
        from .production import Backend
        backend_factory=Backend
    backend=backend_factory(seal,root)
    return execute(backend,checkpoint=checkpoint)

"""Pure source-owned launch vectors and exact expected native display checks."""
import hashlib
import json
import math
from pathlib import Path
import sys


def stage_command(root,seal_path):
    bootstrap='import sys; sys.path.insert(0,'+repr(str(Path(root).resolve()))+'); from validation.kernel_stage_a.__main__ import main; raise SystemExit(main())'
    return [sys.executable,'-I','-c',bootstrap,'--worker','--seal',str(Path(seal_path).resolve())]


def reader_command(root,event_path,deadline):
    bootstrap='import sys; sys.path.insert(0,'+repr(str(Path(root).resolve()))+'); from validation.kernel_stage_a.reader_worker import main; main()'
    return [sys.executable,'-I','-c',bootstrap,str(Path(event_path).resolve()),repr(float(deadline))]


def display(vector):
    """Expected ps display, not a parser/certificate of arbitrary argv bytes."""
    return ' '.join(vector)


def vector_hash(vector):
    return hashlib.sha256(json.dumps(vector,separators=(',',':')).encode()).hexdigest()


def matches(observed,expected):
    return expected is not None and (observed==expected or observed==[display(expected)])


def reader_from_display(value,*,root,event_path,deadline):
    fixed=reader_command(root,event_path,0.)[:-1]
    prefix=display(fixed)+' '
    if type(value) is not str or not value.startswith(prefix): return None
    tail=value[len(prefix):]
    try: represented=float(tail)
    except ValueError: return None
    if not math.isfinite(represented) or not 0<represented<=deadline or repr(represented)!=tail: return None
    expected=reader_command(root,event_path,represented)
    return expected if display(expected)==value else None


def reader_vector(observed,context):
    if context is None or type(observed) is not list or not all(type(v) is str for v in observed): return None
    value=observed[0] if len(observed)==1 else display(observed)
    expected=reader_from_display(value,**context)
    return expected if expected is not None and matches(observed,expected) else None

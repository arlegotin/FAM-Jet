"""Re-executable local diagnostics, not a universal stability certificate."""
import json
import platform
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
import numpy as np
import yaml
from famjet.memory.oracle import direct_moments
from famjet.eval.metrics import relative_error
from famjet.artifacts import atomic_json


def run_checks() -> dict:
    ordinary=yaml.safe_load((ROOT/'configs/numerics.yaml').read_text())['ordinary_fp64']
    rng=np.random.default_rng(20261013)
    gaps=rng.lognormal(mean=0.,sigma=1.,size=512)
    times=np.cumsum(gaps)
    keys=rng.uniform(.05,1.,size=(512,5))
    values=rng.normal(size=(512,3))
    gates=rng.uniform(0.,1.,size=512)
    writes=gates[:,None,None]*keys[:,:,None]*np.concatenate([values,np.ones((512,1))],axis=1)[:,None,:]
    rates=np.geomspace(.001,1.,4)
    T=times[-1]
    z,h=direct_moments(times,writes,rates,T)
    # Independent diagnostic loop only; production recurrence belongs to Task 4.
    rz=np.zeros_like(z); rh=np.zeros_like(h)
    l0=np.zeros_like(z); l1=np.zeros_like(z)
    previous=0.
    for t,x in zip(times,writes):
        d=(rates*(t-previous))[:,None,None]
        a=np.exp(-d)
        old_z=rz
        rh=a*rh+a*d*old_z
        rz=a*old_z+x
        old_l0=l0
        l1=a*l1-2*a*d*old_l0+x
        l0=a*old_l0+x
        previous=t
    eps=1e-8
    p=rng.uniform(.05,1.,size=5)
    def normalize(state):
        u=np.einsum('k,jkv->jv',p,state)
        return u[:,:3]/(u[:,3:]+eps)
    contracted_z=np.einsum('k,jkv->jv',p,z)
    contracted_h=np.einsum('k,jkv->jv',p,h)
    r=normalize(z)
    derivative=-contracted_h[:,:3]/(contracted_z[:,3:]+eps)+r*contracted_h[:,3:]/(contracted_z[:,3:]+eps)
    step=1e-5
    plus=direct_moments(times,writes,rates*np.exp(step),T)[0]
    minus=direct_moments(times,writes,rates*np.exp(-step),T)[0]
    derivative_error=relative_error((normalize(plus)-normalize(minus))/(2*step),derivative)
    differences=[]
    for delta in 10.**-np.arange(1,7):
        plus=direct_moments(times,writes,rates*(1+delta),T)[0]
        minus=direct_moments(times,writes,rates*(1-delta),T)[0]
        differences.append({'relative_rate_spacing':float(delta),'moment_relative_error':relative_error(-(plus-minus)/(2*delta),h)})
    # Cubic Hermite of exp(-lambda) as a function of log(lambda).
    x=np.linspace(0.,np.log(1000.),10001)
    u=x/np.log(1000.)
    width=np.log(1000.)
    interp=(2*u**3-3*u**2+1)*np.exp(-1)+(u**3-2*u**2+u)*width*(-np.exp(-1))+(-2*u**3+3*u**2)*np.exp(-1000)+(u**3-u**2)*width*(-1000*np.exp(-1000))
    i=int(np.argmin(interp))
    return {'schema_version':1,'platform':platform.platform(),'machine':platform.machine(),'python':platform.python_version(),
            'numpy':np.__version__,'precision':'float64','seed':20261013,'rng':'PCG64/default_rng',
            'fixture':{'events':512,'key_dim':5,'value_dim':3,'gap_lognormal_mean':0.,'gap_lognormal_sigma':1.,'T':float(T),'rates':rates.tolist(),'normalization_epsilon':eps,'query_features':p.tolist(),
                       'first_times':times[:3].tolist(),'first_write':writes[0].tolist()},
            'ordinary_fp64_allclose':{'recurrent_z':bool(np.allclose(rz,z,**ordinary)), 'recurrent_h':bool(np.allclose(rh,h,**ordinary)), 'equivalent_h':bool(np.allclose((l0-l1)/2,h,**ordinary))},
            'direct_recurrent':{'z':relative_error(rz,z),'h':relative_error(rh,h)},
            'equivalent_coordinates':{'z':relative_error(l0,z),'h':relative_error((l0-l1)/2,h)},
            'normalized_log_derivative_error':derivative_error,'finite_difference_spacings':differences,
            'hermite':{'minimum':float(interp[i]),'rate_at_minimum':float(np.exp(x[i])),'true_value':float(np.exp(-np.exp(x[i]))),'points':10001,'range':[1,1000]},
            'scope':'one seeded diagnostic fixture; no universal stability or FP32 claim'}


def main() -> int:
    result=run_checks()
    tolerances=yaml.safe_load((ROOT/'configs/numerics.yaml').read_text())
    # Also retain per-element ordinary checks, separate from norm diagnostics.
    checks=[all(result['ordinary_fp64_allclose'].values())]
    checks.append(result['normalized_log_derivative_error'] < tolerances['normalized_derivative']['relative_error_max'])
    checks.append(abs(result['hermite']['minimum']-tolerances['hermite']['expected_minimum']) < tolerances['hermite']['absolute_tolerance'])
    result['checks_passed']=all(checks)
    result['tolerances']=tolerances
    atomic_json(ROOT/'artifacts/numerical_checks.json',result)
    print(json.dumps(result,indent=2,allow_nan=False))
    return 0 if all(checks) else 1


if __name__ == '__main__':
    raise SystemExit(main())

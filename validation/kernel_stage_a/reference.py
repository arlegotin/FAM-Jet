"""Independent scalar defining-equation reference. Standard library ONLY.

No production imports, factorizations, integral branches or guard helpers.
Nothing here runs on import; the actual 32-row allocation remains sealed.
"""
from contextlib import contextmanager
from decimal import (Decimal, Context, localcontext, ROUND_HALF_EVEN,
                     InvalidOperation, DivisionByZero, Overflow, DecimalException)
import math


class ReferenceFailure(RuntimeError):
    pass


@contextmanager
def context(precision):
    if precision not in (80,160):
        raise ValueError('only the declared 80/160 passes are allowed')
    ctx = Context(prec=precision, rounding=ROUND_HALF_EVEN, Emin=-999999999, Emax=999999999,
                  traps=[InvalidOperation,DivisionByZero,Overflow])
    try:
        with localcontext(ctx): yield
    except DecimalException as exc:
        raise ReferenceFailure('Decimal engine failure: '+str(exc)) from exc


def exact(value):
    """Decode all binary64 bits; never use a shortened decimal string."""
    if isinstance(value,Decimal): return value
    if type(value) is int: return Decimal(value)
    if type(value) is not float or not math.isfinite(value):
        raise ReferenceFailure('nonfinite/non-binary64 reference input')
    return Decimal.from_float(value)


def ordered_sum(values):
    # Python's stable sort preserves fixed original event/channel tie order.
    return sum(sorted(values,key=lambda x:-abs(x)),Decimal(0))


def integral(order, rate, lower, upper):
    """Independent endpoint antiderivatives, deliberately no production series."""
    if order not in (0,1,2) or not rate>0 or not 0<=lower<upper:
        raise ReferenceFailure('integral domain')
    def endpoint(x):
        z=rate*x
        if order==0: poly=Decimal(1)
        elif order==1: poly=z+1
        else: poly=z*z+2*z+2
        return (-z).exp()*poly
    return (endpoint(lower)-endpoint(upper))/rate**(order+1)


def solve(matrix, vector):
    """Largest-absolute-column pivot; lowest original current row wins ties."""
    n=len(vector)
    if not n or len(matrix)!=n or any(len(row)!=n for row in matrix):
        raise ReferenceFailure('solve shape')
    a=[list(row)+[rhs] for row,rhs in zip(matrix,vector)]
    for k in range(n):
        pivot=max(range(k,n),key=lambda j:abs(a[j][k]))
        a[k],a[pivot]=a[pivot],a[k]
        if not a[k][k].is_finite() or not a[k][k]:
            raise ReferenceFailure('zero/nonfinite pivot')
        for j in range(k+1,n):
            multiplier=a[j][k]/a[k][k]
            a[j][k]=Decimal(0)
            for i in range(k+1,n+1): a[j][i]-=multiplier*a[k][i]
    result=[Decimal(0)]*n
    for j in range(n-1,-1,-1):
        result[j]=(a[j][n]-ordered_sum([a[j][i]*result[i] for i in range(j+1,n)]))/a[j][j]
    if not all(x.is_finite() for x in result): raise ReferenceFailure('nonfinite solve')
    return result


class Factors:
    def __init__(self,family,rates,t_ref,prior_scale,ridge):
        if family not in ('jet','bank') or not rates: raise ReferenceFailure('basis schema')
        self.alpha=[]; self.orders=[]
        for rate in rates:
            for order in ((0,1) if family=='jet' else (0,)):
                self.alpha.append(exact(rate)*exact(t_ref)); self.orders.append(order)
        self.eta=exact(t_ref)/exact(prior_scale); self.ridge=exact(ridge)
        if self.eta<=0 or self.ridge<=0 or any(x<=0 for x in self.alpha):
            raise ReferenceFailure('nonpositive scale/rate/ridge')
        self.gram=[[self.eta*x**q*y**p*Decimal(math.factorial(q+p))/
                    (x+y+self.eta)**(q+p+1) for y,p in zip(self.alpha,self.orders)]
                   for x,q in zip(self.alpha,self.orders)]
        self.diagonal=[self.gram[i][i].sqrt() for i in range(len(self.alpha))]
        self.scaled=[[g/self.diagonal[i]/self.diagonal[j] + (self.ridge if i==j else 0)
                      for j,g in enumerate(row)] for i,row in enumerate(self.gram)]

    def coefficients(self,lower,upper):
        b=[self.eta*x**q*integral(q,x+self.eta,exact(lower),exact(upper))
           for x,q in zip(self.alpha,self.orders)]
        rhs=[x/d for x,d in zip(b,self.diagonal)]
        theta=solve(self.scaled,rhs)
        residual=max(abs(ordered_sum([a*t for a,t in zip(row,theta)])-h)
                     for row,h in zip(self.scaled,rhs))/max(Decimal(1),max(map(abs,rhs)))
        if residual>=Decimal('1e-50'): raise ReferenceFailure('normalized solve residual')
        return [t/d for t,d in zip(theta,self.diagonal)],b,residual


def decode(normalizers,numerators,coefficients,fallback,*,quarantined=False,structural_zero=False):
    n=[exact(v) for v in normalizers]; u=[[exact(v) for v in row] for row in numerators]
    c=coefficients; margins={}
    result=dict(code=0,prediction=[exact(v) for v in fallback],mass=None,bound=None,raw=None,margins=margins)
    def failed(code):
        result['code']=code
        return result
    if quarantined: return failed(1)
    if not all(v.is_finite() for v in n for _ in (0,)) or not all(v.is_finite() for row in u for v in row):
        return failed(2)
    if any(v<0 for v in n): return failed(3)
    mass=ordered_sum([a*b for a,b in zip(c,n)]); result['mass']=mass
    if not mass.is_finite(): return failed(7)
    if any(n): margins['nonnegative_mass']=mass
    if mass<0: return failed(4)
    margins['floor']=mass-exact(1e-8)
    if not mass>exact(1e-8): return failed(5)
    bound=Decimal(64)*Decimal(2)**-53*ordered_sum([abs(a)*b for a,b in zip(c,n)])
    result['bound']=bound; margins['cancellation']=mass-bound
    if not bound.is_finite(): return failed(7)
    if not mass>bound: return failed(6)
    raw=[ordered_sum([a*row[j] for a,row in zip(c,u)]) for j in range(len(fallback))]
    result['raw']=raw
    prediction=[x/(mass+exact(1e-8)) for x in raw]
    if not all(v.is_finite() for v in prediction): return failed(7)
    result['prediction']=prediction
    return result


def agree(low,high):
    if isinstance(high,dict):
        if set(low)!=set(high): raise ReferenceFailure('precision schema')
        for k in high: agree(low[k],high[k])
    elif isinstance(high,(list,tuple)):
        if len(low)!=len(high): raise ReferenceFailure('precision shape')
        for a,b in zip(low,high): agree(a,b)
    elif isinstance(high,Decimal):
        if low is None or abs(low-high)>Decimal('1e-50')*(1+abs(high)):
            raise ReferenceFailure('precision agreement')
    elif low!=high: raise ReferenceFailure('precision decision')


def stable_margin(low,high):
    radius=max(abs(high-low),Decimal('1e-60')*(1+abs(high)))
    if high-radius<=0<=high+radius:
        raise ReferenceFailure('unresolved threshold applicability')


def compare(left,right):
    """Every mutually finite field remains mandatory even for equal decisions."""
    failed=[]
    if left['code']!=right['code']: failed.append('code')
    for field in ('prediction','mass','bound','raw'):
        a,b=left.get(field),right.get(field)
        if a is None or b is None: continue  # field was not reached in this scope
        aa=a if isinstance(a,(list,tuple)) else [a]
        bb=b if isinstance(b,(list,tuple)) else [b]
        if len(aa)!=len(bb): failed.append(field+'.shape'); continue
        for i,(x,y) in enumerate(zip(aa,bb)):
            if x is None or y is None: continue
            x,y=exact(x),exact(y)
            if x.is_finite() and y.is_finite() and abs(x-y)>exact(1e-12)*(1+abs(y)):
                failed.append(f'{field}[{i}]')
    for field in ('coefficients','window_vectors'):
        if field in left and field in right:
            for j,(a,b) in enumerate(zip(left[field],right[field])):
                nested=compare({'code':0,'prediction':a},{'code':0,'prediction':b})
                failed.extend(f'{field}[{j}].{key}' for key in nested['failed_fields'])
    if 'windows' in left and 'windows' in right:
        for j,(a,b) in enumerate(zip(left['windows'],right['windows'])):
            nested=compare(a,b)
            failed.extend(f'windows[{j}].{key}' for key in nested['failed_fields'])
    return dict(status='FAILED' if failed else 'PASS',failed_fields=failed)


def compare_three(production,supplied,events):
    pa,ab,pb=compare(production,supplied),compare(supplied,events),compare(production,events)
    return dict(reader_arithmetic=pa['status'],source_state_fidelity=ab['status'],
                strict_end_to_end=pb['status'],
                end_to_end_gate='PASS' if ab['status']==pb['status']=='PASS' else 'FAILED',
                comparisons=dict(P_A=pa,A_B=ab,P_B=pb),
                stop='candidate' if pa['status']=='FAILED' else 'continue')


def event_state(factors,events,snapshot_time,t_ref,scale):
    """Independent event kernels; fixed order is supplied by descriptor timeline."""
    n=[]; u=[]
    for alpha,order in zip(factors.alpha,factors.orders):
        terms=[]; columns=[[] for _ in events[0]['values']] if events else [[] for _ in range(8)]
        for event in events:
            if not event['observed'] or event['key']!=0: continue
            age=(exact(snapshot_time)-exact(event['time']))/exact(t_ref)
            if age<0: raise ReferenceFailure('future event')
            z=alpha*age
            weight=(z if order else Decimal(1))*(-z).exp()*exact(scale)
            terms.append(weight)
            for col,value in zip(columns,event['values']): col.append(weight*exact(value))
        n.append(ordered_sum(terms)); u.append([ordered_sum(col) for col in columns])
    return n,u


def advance(factors,n,u,delay,t_ref):
    delta=exact(delay)/exact(t_ref); nn=[]; uu=[]
    if delta<0: raise ReferenceFailure('reverse snapshot time')
    for i,(alpha,order) in enumerate(zip(factors.alpha,factors.orders)):
        z=alpha*delta; decay=(-z).exp()
        nn.append(decay*(n[i]+(z*n[i-1] if order else 0)))
        uu.append([decay*(v+(z*u[i-1][j] if order else 0)) for j,v in enumerate(u[i])])
    return nn,uu


def evaluate(factors,n,u,lower,upper,task,fallback,*,solve_call,invalid=False,quarantined=False):
    windows=[]; coefficients=[]; vectors=[]; residuals=[]
    prediction=[exact(v) for v in fallback]; code=0
    intervals=[(exact(lower),exact(upper))]
    if task=='contrast': intervals.append((exact(upper),2*exact(upper)-exact(lower)))
    elif task!='mean': raise ReferenceFailure('unknown task')
    for a,b in intervals:
        c,window,residual=solve_call(lambda:factors.coefficients(a,b))
        coefficients.append(c); vectors.append(window); residuals.append(residual)
        result=decode(n,u,c,fallback,quarantined=quarantined)
        if invalid: result.update(code=5,prediction=prediction,mass=None,bound=None,raw=None,margins={})
        windows.append(result)
        if result['code']:
            code=result['code']; break
    if not code:
        prediction=windows[0]['prediction'] if task=='mean' else [a-b for a,b in zip(windows[0]['prediction'],windows[1]['prediction'])]
    return dict(code=code,prediction=prediction,windows=windows,coefficients=coefficients,
                window_vectors=vectors,residuals=residuals)


def validate_pair(low,high):
    agree(low,high)
    for residual in high.get('residuals',[]):
        if residual>=Decimal('1e-50'): raise ReferenceFailure('normalized solve residual')
    for a,b in zip(low.get('windows',[]),high.get('windows',[])):
        for key,margin in b['margins'].items(): stable_margin(a['margins'][key],margin)

"""Exact prospective source definitions. No production or numerical imports."""
from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256

P = (1., 2., 3., 4., 5., 6., 7., 8.)
S = (1., -1., 2., -2., 4., -4., 8., -8.)
ZERO = (0.,)*8


@dataclass(frozen=True)
class Event:
    age: float
    values: tuple
    key: int = 0


@dataclass(frozen=True)
class Fixture:
    number: int
    events: tuple
    task: str = 'mean'
    lower: float = 0.
    upper: float = 4.
    T: float = 0.
    scale: float = 1.
    poison: bool = False


@dataclass(frozen=True)
class Slot:
    row: int
    transform: str
    applicable: bool
    history_id: str
    query_id: int


def fixtures():
    def E(age, value, key=0):
        return Event(float(age), tuple(float(x) for x in value), key)
    def times(v, multiplier):
        return tuple(multiplier*x for x in v)
    neg = times(S, -1)
    mix = (E(1,S), E(3,times(S,-2)), E(6,P))
    return (
        Fixture(1,()), Fixture(2,(E(1,P,1),)), Fixture(3,(E(3,S),)),
        Fixture(4,(E(2**24,P),),lower=float(2**24),upper=float(2**24+2)),
        Fixture(5,(E(7,P),E(2,P),E(0,P)),upper=8.),
        Fixture(6,(E(6,S),E(5,S),E(1,S)),task='contrast'),
        Fixture(7,(E(3,ZERO),E(1,ZERO))), Fixture(8,(E(1,P),),scale=2.**-40),
        Fixture(9,(E(0,S),),upper=1.),
        Fixture(10,(E(2,S),),lower=2.),
        Fixture(11,(E(float.fromhex('0x1.fffffffffffffp+0'),S),),lower=2.),
        Fixture(12,(E(float.fromhex('0x1.0000000000001p+1'),S),),lower=2.),
        Fixture(13,(E(float.fromhex('0x1.fffffffffffffp+1'),S),),lower=2.),
        Fixture(14,(E(4,S),),lower=2.),
        Fixture(15,(E(float.fromhex('0x1.0000000000001p+2'),S),),lower=2.),
        Fixture(16,(E(16,S),),lower=2.),
        Fixture(17,(E(7,ZERO),E(6,times(S,3)),E(5,neg),E(2,times(S,2)),E(1,S)),task='contrast'),
        Fixture(18,(E(4,S),E(1,P)),task='contrast'),
        Fixture(19,(E(5,S),),task='contrast'), Fixture(20,(E(1,S),),task='contrast'),
        Fixture(21,(E(5224,times(S,-2)),E(4096,neg),E(2048,ZERO),E(1024,S),E(0,times(S,2))),task='contrast',upper=2048.),
        Fixture(22,(E(5224,S),),lower=5224.,upper=5224.+2.**-20),
        Fixture(23,(E(20896,neg),E(10448,S)),lower=10448.,upper=10449.),
        Fixture(24,(E(8,S),E(0,P)),lower=52240.,upper=52249.,T=52240.),
        Fixture(25,mix), Fixture(26,mix,scale=2.**-20), Fixture(27,mix,scale=2.**20),
        Fixture(28,mix+mix), Fixture(29,(E(5,neg),E(3,S))),
        Fixture(30,(E(2,P),E(1,times(S,2.**500)),E(1,times(S,-2.**500)))),
        Fixture(31,(E(1,S),),lower=1.,upper=float.fromhex('0x1.0000000000001p+0')),
        Fixture(32,mix,poison=True))


def candidates():
    return (('jet',1e-10),('bank',1e-10),('bank',1e-6),
            ('jet',1e-6),('jet',1e-2),('bank',1e-2))


def slots():
    for transform, rows in (('I',range(1,33)),('O',range(32,0,-1)),
                            ('U',range(1,33)),('R',(*range(1,33,2),*range(2,33,2)))):
        for row in rows:
            digest = sha256(f'task18-kernel-v1/{row:02}/{transform}'.encode()).hexdigest()
            yield Slot(row, transform, not (transform=='O' and row in (11,12,13,15)),
                       digest, int(digest[:15],16))


def timeline(row, transform):
    """Serializable event descriptors only; rationally verify allowed shifts."""
    if transform not in ('I','O','U','R') or (transform=='O' and row.number in (11,12,13,15)):
        raise ValueError('nonapplicable/unknown transform')
    unit, shift = (8.,0.) if transform=='U' else (1.,16. if transform=='O' else 0.)
    writes = []
    for event in sorted(enumerate(row.events), key=lambda x:(-x[1].age,x[0])):
        e = event[1]
        t = -e.age*unit+shift
        if Fraction(t)-Fraction(shift) != -Fraction(e.age)*Fraction(unit):
            raise ValueError('represented transform lost exact age')
        writes.append(dict(event_id=len(writes),time=t,values=e.values,key=e.key,observed=True))
    if writes:
        writes.append(dict(event_id=len(writes),time=shift,values=ZERO,key=0,observed=False))
    return tuple(writes)


def manifest():
    """Hex-only floats preserve binary64 bits without producing snapshots."""
    from dataclasses import asdict
    def encode(x):
        if type(x) is float: return x.hex()
        if isinstance(x,(list,tuple)): return [encode(v) for v in x]
        if type(x) is dict: return {k:encode(v) for k,v in x.items()}
        return x
    return dict(version=1,fixtures=encode([asdict(r) for r in fixtures()]),
                slots=[asdict(s) for s in slots()], candidates=encode(candidates()),
                marker='one no-write O/key0 at time zero after every nonempty history',
                poison_bits='7ff8000000000000', policies=dict(epsilon=(1e-8).hex(),
                floor=(1e-8).hex(),cancellation=(64*2.**-53).hex(),prior_scale=(5224.).hex()))

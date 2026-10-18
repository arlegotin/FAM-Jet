"""Small analytic controls only: no Stage A fixture inventory or campaign."""
import importlib.util
import math
from dataclasses import replace
import pytest
import torch


def reader_class():
    assert importlib.util.find_spec('famjet.readers.kernel_projection'), 'projection reader missing'
    from famjet.readers.kernel_projection import KernelProjection
    return KernelProjection


def test_single_exponential_closed_solution_and_epsilon_shrinkage():
    # pi=e^-x and phi=e^-2x: G=1/5, b=(e^-3a-e^-3b)/3.
    r = reader_class()(torch.tensor([2.], dtype=torch.float64), 'bank', 1., prior_scale=1., ridge=1e-2)
    coefficient = 5*(math.exp(-.75)-math.exp(-3.))/3/1.01
    assert r.coefficients(.25, 1.).item() == pytest.approx(coefficient, abs=1e-14)
    n = torch.tensor([2.], dtype=torch.float64)
    u = n[:, None]*torch.tensor([3., -4.], dtype=torch.float64)
    value, diagnostic = r.window(n, u, .25, 1.)
    mass = coefficient*2
    assert diagnostic['code'] == 0
    torch.testing.assert_close(value, torch.tensor([3., -4.], dtype=torch.float64)*mass/(mass+1e-8), atol=1e-14, rtol=1e-14)


def test_jet_moment_gram_and_window_include_alpha_factor():
    r = reader_class()(torch.tensor([2.], dtype=torch.float64), 'jet', 1., prior_scale=1., ridge=1e-2)
    torch.testing.assert_close(r.gram, torch.tensor([[1/5, 2/25], [2/25, 8/125]], dtype=torch.float64), atol=1e-16, rtol=1e-16)
    b = r.window_vector(0., 1.)
    assert b[0].item() == pytest.approx(-math.expm1(-3)/3, abs=1e-16)
    assert b[1].item() == pytest.approx(2*(1-4*math.exp(-3))/9, abs=1e-16)


def test_adjacent_endpoint_integral_survives_cancellation():
    r = reader_class()(torch.tensor([2.], dtype=torch.float64), 'jet', 1., prior_scale=1., ridge=1e-2)
    a, b = 1., math.nextafter(1., math.inf)
    expected = math.exp(-3)*(b-a)
    torch.testing.assert_close(r.window_vector(a, b), torch.tensor([expected, 2*expected], dtype=torch.float64), atol=0., rtol=1e-14)


def test_tail_integrals_and_overflow_products_are_finite():
    r = reader_class()(torch.tensor([2.], dtype=torch.float64), 'jet', 1., prior_scale=1., ridge=1e-2)
    assert torch.equal(r.window_vector(1e300, 1.1e300), torch.zeros(2, dtype=torch.float64))


def test_guard_short_circuit_codes_and_no_clipping():
    r = reader_class()(torch.tensor([2.], dtype=torch.float64), 'bank', 1., prior_scale=1., ridge=1e-2)
    n = torch.tensor([1.], dtype=torch.float64); u = n[:, None]*7
    assert r.window(-n, u, 0., 1.)[1]['code'] == 3
    assert r.window(n*0, u, 0., 1.)[1]['code'] == 5
    assert r.window(n, u*float('inf'), 0., 1.)[1]['code'] == 2
    assert r.window(n, u, 0., 1., quarantined=True)[1]['code'] == 1
    # Reached cancellation guard: signed coefficients almost cancel positive N.
    m = reader_class()(torch.tensor([.1, 1.], dtype=torch.float64), 'bank', 1., prior_scale=1., ridge=1e-2)
    c = m.coefficients(3., 4.)
    assert c[0] > 0 > c[1]
    n = torch.tensor([1e12, -c[0].item()/c[1].item()*1e12], dtype=torch.float64)
    # Strict guard must reject even when rounded mass is positive and above floor.
    n[1] = math.nextafter(n[1].item(), 0.)
    assert m.window(n, torch.ones(2, 1, dtype=torch.float64), 3., 4.)[1]['code'] == 6


@pytest.mark.parametrize('a,b', [(-1., 2.), (1., 1.), (0., math.inf), (0., math.nan)])
def test_malformed_window_rejected(a,b):
    r = reader_class()(torch.tensor([2.], dtype=torch.float64), 'bank', 1., prior_scale=1., ridge=1e-2)
    with pytest.raises(ValueError): r.coefficients(a,b)


def test_two_channel_scaled_ridge_against_decimal_defining_solve():
    from decimal import Decimal, localcontext
    r = reader_class()(torch.tensor([2.],dtype=torch.float64),'jet',1.,prior_scale=1.,ridge=1e-2)
    with localcontext() as context:
        context.prec=80
        D=Decimal; rho=D.from_float(1e-2); a=D('.25'); b=D(1); s=D(3)
        g00=D(1)/5; g01=D(2)/25; g11=D(8)/125
        b0=((-s*a).exp()-(-s*b).exp())/s
        b1=D(2)*((a/s+1/s**2)*(-s*a).exp()-(b/s+1/s**2)*(-s*b).exp())
        # Equivalent canonical metric: (G + rho diag(G)) c = b.
        aa=g00*(1+rho); dd=g11*(1+rho); determinant=aa*dd-g01*g01
        expected=torch.tensor([float((dd*b0-g01*b1)/determinant),float((aa*b1-g01*b0)/determinant)],dtype=torch.float64)
    torch.testing.assert_close(r.coefficients(.25,1.),expected,atol=1e-12,rtol=1e-12)


def test_static_reconstruction_rejects_invalid_alpha_even_with_consistent_gram():
    r=reader_class()(torch.tensor([2.],dtype=torch.float64),'bank',1.,prior_scale=1.,ridge=1e-2)
    arrays={name:getattr(r,name).clone() for name in r.array_names}
    arrays['alpha'][0]=-0.1
    # A finite Gram can still be formed at this negative rate; domain must reject.
    with pytest.raises(ValueError):
        reader_class().from_statics({name:getattr(r,name) for name in r.config_names},arrays)


def test_mass_scaling_changes_shrinkage_and_floor_without_rescue():
    r=reader_class()(torch.tensor([2.],dtype=torch.float64),'bank',1.,prior_scale=1.,ridge=1e-2)
    n=torch.ones(1,dtype=torch.float64); u=n[:,None]*3
    a,da=r.window(n,u,0.,1.)
    b,db=r.window(n*2,u*2,0.,1.)
    assert b.item()>a.item()
    assert db['mass']==2*da['mass']
    assert r.window(n*2**-40,u*2**-40,0.,1.)[1]['code']==5


def test_static_factor_condition_and_residual_are_reported_without_cache():
    r=reader_class()(torch.tensor([2.],dtype=torch.float64),'bank',1.,prior_scale=1.,ridge=1e-2)
    before={name:value.clone() for name,value in r.state_dict().items()}
    diagnostic=r.factor_diagnostics()
    assert diagnostic['minimum_eigenvalue']==pytest.approx(1.)
    assert diagnostic['condition_estimate']==pytest.approx(1.)
    assert diagnostic['factor_residual']<=1e-15
    r.coefficients(.25,1.)
    for name,value in r.state_dict().items(): assert torch.equal(value,before[name])

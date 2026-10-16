import numpy as np
import pytest


def test_direct_moments_fixture():
    from famjet.memory.oracle import direct_moments
    z,h=direct_moments(np.array([0,1]),np.array([[[2.,1.]],[[6.,1.]]]),np.array([1.]),2.)
    np.testing.assert_allclose(z,[[[2*np.exp(-2)+6*np.exp(-1),np.exp(-2)+np.exp(-1)]]],rtol=1e-14)
    np.testing.assert_allclose(h,[[[4*np.exp(-2)+6*np.exp(-1),2*np.exp(-2)+np.exp(-1)]]],rtol=1e-14)
    assert z.dtype==h.dtype==np.float64


def test_direct_empty_and_invalid():
    from famjet.memory.oracle import direct_moments
    assert direct_moments(np.array([]),np.empty((0,2,3)),np.array([1.]),2)[0].shape==(1,2,3)
    for times,writes,rates,T in [([3],[[1]],[1],2),([0],[[np.nan]],[1],2),([0],[[1]],[0],2)]:
        with pytest.raises(ValueError):
            direct_moments(np.array(times),np.array(writes),np.array(rates),T)


def test_relative_error():
    from famjet.eval.metrics import relative_error
    assert relative_error(np.array([3.,4.]),np.array([0.,0.])) == float('inf')
    assert relative_error(np.zeros(2),np.zeros(2)) == 0
    assert relative_error(np.array([3.,4.]),np.array([0.,5.])) == pytest.approx(np.sqrt(10)/5)


def test_standalone_numerical_diagnostics():
    from validation.numerical_checks import run_checks
    r=run_checks()
    assert r['seed']==20261013
    assert r['direct_recurrent']['z'] < 1e-12
    assert r['direct_recurrent']['h'] < 1e-12
    assert r['equivalent_coordinates']['h'] < 1e-12
    assert r['normalized_log_derivative_error'] < 1e-8
    assert len(r['finite_difference_spacings'])==6
    assert r['hermite']['minimum']==pytest.approx(-.135026,abs=1e-5)

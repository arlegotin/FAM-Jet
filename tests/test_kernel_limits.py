import numpy as np
import pytest


def test_both_fixed_linear_nullspaces_have_small_erasure_and_large_other_response():
    from famjet.eval.controls import kernel_nullspace_fixture
    f=kernel_nullspace_fixture(np.linspace(0,64,48)**1.03,np.geomspace(.02,1.28,4),np.geomspace(.02,1.28,8))
    assert f['scope']=='fixed_linear_writers'
    for name in ['jet_erased','bank_erased']:
        r=f[name]
        assert r['rank']==8 and r['condition']<2000
        assert r['erasure_residual']<1e-12 and r['other_response']>.005
        assert r['normalization_difference']==0 and abs(r['window_mean_difference'])>.08
        assert max(abs(np.asarray(r['values'])))<=1.
        assert r['direct_sum_residual']<1e-12
    with pytest.raises(ValueError,match='condition|rank'):
        kernel_nullspace_fixture(np.ones(48),np.ones(4),np.ones(8))

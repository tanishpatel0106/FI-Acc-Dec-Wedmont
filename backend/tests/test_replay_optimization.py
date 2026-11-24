"""Analytical optimization checks for compiled replay numerical helpers."""
import numpy as np
from lifecycle.studies.historical_replay import proj_capped_simplex, mv_opt, erc


def test_capped_simplex_known_projection():
    actual=proj_capped_simplex(np.array([1.,.4,-.1]),np.full(3,.6))
    assert np.allclose(actual,[.6,.4,0],atol=1e-10)
    assert np.isclose(actual.sum(),1)


def test_mean_variance_matches_independent_quadratic_optimum():
    from scipy.optimize import minimize
    rng=np.random.default_rng(4837)
    for n in [3,7]:
        a=rng.normal(size=(n,n));cov=(a@a.T+np.eye(n))*.02
        mu=rng.normal(.05,.03,size=n);gamma=4.;cap=.6
        result=mv_opt(mu,cov,gamma,cap)
        objective=lambda w:gamma/2*w@cov@w-w@mu
        reference=minimize(objective,np.ones(n)/n,bounds=[(0,cap)]*n,
            constraints={'type':'eq','fun':lambda w:w.sum()-1},method='SLSQP',options={'ftol':1e-13,'maxiter':1000})
        assert reference.success
        assert np.isclose(result.sum(),1,atol=1e-8)
        assert np.all(result>=0) and np.all(result<=cap+1e-9)
        assert abs(objective(result)-objective(reference.x))<1e-9


def test_equal_risk_contribution_has_known_diagonal_solution():
    vol=np.array([.1,.2,.4])
    actual=erc(np.diag(vol**2))
    expected=(1/vol)/(1/vol).sum()
    assert np.allclose(actual,expected,atol=1e-10)

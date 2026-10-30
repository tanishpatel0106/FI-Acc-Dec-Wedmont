import numpy as np

from lifecycle.engine.lifecycle import kernel
from lifecycle.engine.lifecycle.policies import constant_mix


def run(R, w, w0=1_000_000.0, rate=0.0, retire_m=0, labor=None, pension=None, savings=0.0, rule="fixed_real",
        kappa=0.0, rebalance=1, gamma=0.5, c_min=1e-9, disc=None):
    N, T, A = R.shape
    labor = np.zeros((N, T)) if labor is None else labor
    pension = np.zeros((N, T)) if pension is None else pension
    pol = constant_mix(np.asarray(w, dtype=float), T)
    cfg = kernel.KernelConfig(
        w0=w0, retire_m=retire_m, spend_rule=kernel.SPEND_CODES[rule], rate=rate, savings_rate=savings,
        wmode=pol.wmode, sched=pol.sched, risky_w=pol.risky_w, safe_w=pol.safe_w, theta=pol.theta,
        bucket_years=0.0, start_age=65.0, risky_mask=np.zeros(A), rebalance_every=rebalance, kappa=kappa,
        disc=np.ones(T) if disc is None else disc, beq=np.zeros(T), gamma=gamma, eta=0.0, c_min=c_min,
        k_shift=1.0, scale=1000.0, w_ref=1.0, amort=np.zeros(T))
    return kernel.simulate(R, np.zeros((N, T), dtype=np.int64), labor, pension, cfg)

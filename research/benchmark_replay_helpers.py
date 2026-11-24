"""Compare compiled helpers with their identical interpreted algorithms."""
import ast
import json
from pathlib import Path
import time
import numpy as np
from numpy.typing import NDArray
from lifecycle.studies import historical_replay as replay

ROOT=Path(__file__).resolve().parents[1]
nodes=[node for node in ast.parse(Path(replay.__file__).read_text()).body if isinstance(node,ast.FunctionDef)
       and node.name in ['proj_capped_simplex','mv_opt','erc']]
for node in nodes:node.decorator_list=[]
reference={'np':np,'NDArray':NDArray}
exec(compile(ast.Module(body=nodes,type_ignores=[]),'interpreted_reference','exec'),reference)
rng=np.random.default_rng(7591)
a=rng.normal(size=(6,6));cov=(a@a.T+np.eye(6))*.02;mu=rng.normal(.05,.03,size=6)
for _ in range(5):
    x=rng.normal(size=6);cap=np.full(6,.4)
    assert np.allclose(replay.proj_capped_simplex(x,cap),reference['proj_capped_simplex'](x,cap),rtol=1e-12,atol=1e-12)
assert np.allclose(replay.mv_opt(mu,cov,4.,.6),reference['mv_opt'](mu,cov,4.,.6),rtol=1e-10,atol=1e-12)
assert np.allclose(replay.erc(cov),reference['erc'](cov),rtol=1e-10,atol=1e-12)
def elapsed(fn):
    timings=[]
    for _ in range(5):
        start=time.perf_counter();fn(mu,cov,4.,.6);timings.append(time.perf_counter()-start)
    return float(np.median(timings))
legacy=elapsed(reference['mv_opt']);compiled=elapsed(replay.mv_opt)
record=dict(legacy_median_seconds=legacy,compiled_median_seconds=compiled,microbenchmark_speedup=legacy/compiled,
    problem='Six-asset capped mean-variance helper; five warm timings; no claim of full application speedup',
    comparison='Same algorithm/iteration caps; outputs agree to rtol 1e-10 and atol 1e-12; independent SLSQP optimum tests pass')
(ROOT/'research/integrated_handoff_2026_11_20/replay_helper_benchmark.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
print('Compiled/interpreted helper agreement passed; warm microbenchmark recorded')

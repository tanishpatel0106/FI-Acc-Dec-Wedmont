"""Re-evaluate the complete archived demo with bounded numerical-library threading."""
import json
import os
from pathlib import Path
import time

if __name__=='__main__':
    os.environ['OPENBLAS_NUM_THREADS']='1'
    os.environ['NUMBA_NUM_THREADS']='4'

import numpy as np
from numba import set_num_threads

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'research/integrated_handoff_2026_11_20'


def main():
    os.environ.pop('LIFECYCLE_DATA_DIR',None)
    from lifecycle.data import panel
    from lifecycle.runs.jsonsafe import clean
    from lifecycle.studies.historical_replay import HistoricalReplaySpec,run_historical_replay
    panel.reload()
    prior=json.loads((ROOT/'research/followup_2026_11_19/main_runs.json').read_text())['historical_replay']
    spec=HistoricalReplaySpec.model_validate(prior['spec'])
    before=json.loads((ROOT/'research/followup_2026_11_19'/(prior['run_id']+'.json')).read_text())
    set_num_threads(4)
    start=time.time()
    def progress(stage,fraction):
        print(f'{time.time()-start:.1f}s | {stage} | {fraction:.1%}',flush=True)
    after=clean(run_historical_replay(spec,progress))
    (OUT/'engine24_historical_replay.json').write_text(json.dumps(after,indent=2),encoding='utf-8')
    differences=[]
    def compare(a,b,path):
        if isinstance(a,dict) and isinstance(b,dict):
            for key in a.keys()|b.keys():
                if key in {'meta','timings'}:continue
                compare(a.get(key),b.get(key),path+'/'+key)
        elif isinstance(a,list) and isinstance(b,list) and len(a)==len(b):
            for i,(x,y) in enumerate(zip(a,b)):compare(x,y,path+'/'+str(i))
        elif isinstance(a,(float,int)) and not isinstance(a,bool) and isinstance(b,(float,int)) and not isinstance(b,bool):
            if not np.isclose(a,b,rtol=1e-10,atol=1e-9,equal_nan=True):
                differences.append(dict(path=path,before=a,after=b,absolute_change=b-a))
        elif a!=b:
            differences.append(dict(path=path,before=a,after=b))
    compare(before,after,'')
    record=dict(original_run_id=prior['run_id'],engine_semantic_version='2.4',seconds=time.time()-start,
        spec=prior['spec'],comparison_tolerance='rtol 1e-10, atol 1e-9; excludes version metadata',
        numerical_library_threads='BLAS capped at 1 and Numba at 4; no research parameter changed',
        differences=differences,changed_count=len(differences),
        forward_summary={name:{key:value.get(key) for key in ['available','ce_consumption','p_no_shortfall','unmet_mean','terminal']} for name,value in after['forward'].items()})
    (OUT/'engine24_historical_replay_audit.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print('Complete historical replay re-evaluated; changed fields:',len(differences),flush=True)


if __name__=='__main__':main()

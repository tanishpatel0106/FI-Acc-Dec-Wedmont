"""Rerun the existing public SHED criterion analysis without changing dated outputs."""
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
PROJECT=Path(os.environ.get('FIXED_INCOME_SURVEY_ROOT',ROOT.parent))
sys.path.insert(0,str(PROJECT/'scripts'))
import capacity_validation as analysis

OUT=ROOT/'research/integrated_handoff_2026_11_20/evidence_shed'
OUT.mkdir(exist_ok=True)
analysis.OUT=OUT
analysis.run_shed()
records=[]
for year in [2018,2019,2024,2025]:
    name=f'SHED_public_use_data_{year}_(CSV).zip'
    path=PROJECT/'data/capacity_validation'/name
    records.append(dict(filename=name,relative_path='data/capacity_validation/'+name,
        url='https://www.federalreserve.gov/consumerscommunities/files/'+name,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),bytes=path.stat().st_size))
(OUT/'input_manifest.json').write_text(json.dumps(dict(sources=records,
    source_script_sha256=hashlib.sha256((PROJECT/'scripts/capacity_validation.py').read_bytes()).hexdigest(),
    status='Existing October analysis rerun November 20; not a new original finding',
    linkage='Official shedid and 2025 panel_weight for 2024-2025; older 2018-2019 retained panel is unweighted',
    uncertainty='HC3 model-based coefficient intervals; no full survey-design or CV-difference confidence interval'),indent=2),encoding='utf-8')
print('SHED criterion evidence rerun completed')

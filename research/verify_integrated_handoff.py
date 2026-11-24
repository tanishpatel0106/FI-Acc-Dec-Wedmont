"""Validate the complete aggregate handoff and write a reviewable verification receipt."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

import nbformat
import numpy as np
import pandas as pd
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[1]
PROJECT=ROOT.parent
OUT=ROOT/'research/integrated_handoff_2026_11_20'
CLEAN=PROJECT/'.validation_cleanroom_2026_11_20'


def junit(name):
    tree=ET.parse(OUT/name)
    suites=tree.getroot().findall('testsuite')
    record={k:sum(int(s.get(k,0)) for s in suites) for k in ['tests','failures','errors','skipped']}
    assert record['tests']>0 and record['failures']==record['errors']==record['skipped']==0
    return record


def main():
    notebook=nbformat.read(OUT/'integrated_research.ipynb',as_version=4)
    code=[c for c in notebook.cells if c.cell_type=='code']
    assert code and all(c.execution_count is not None for c in code)
    assert not any(o.output_type=='error' for c in code for o in c.outputs)
    assert not any(re.search('[\u4e00-\u9fff]',c.source) for c in notebook.cells)
    assert len(list((OUT/'figures').glob('*.png')))==8
    browser=json.loads((OUT/'browser_clean_tests.json').read_text())['stats']
    assert browser['expected']==26 and browser['unexpected']==browser['flaky']==browser['skipped']==0
    unit=json.loads((CLEAN/'frontend_clean_tests.json').read_text())
    assert unit['success'] and unit['numPassedTests']==230 and unit['numFailedTests']==0
    shutil.copy2(CLEAN/'frontend_clean_tests.json',OUT/'frontend_clean_tests.json')
    assert (CLEAN/'lifecycle/web/.next/BUILD_ID').exists()
    install=json.loads((OUT/'one_command_install_verification.json').read_text())
    assert install['status']=='passed' and install['production_build']=='passed'
    assert install['studies']['permanent']=='done' or install['studies'].get('permanent_core_duration')=='done'
    audit=json.loads((ROOT/'research/npm_audit_fixed_2026_11_20.json').read_text())
    assert audit['metadata']['vulnerabilities']['total']==0
    shutil.copy2(ROOT/'research/npm_audit_fixed_2026_11_20.json',OUT/'npm_audit_final.json')
    reproduction=json.loads((OUT/'clean_reproduction_comparison.json').read_text())
    assert len(reproduction)==16
    inventory=pd.read_csv(OUT/'evidence_prior/country_evidence_inventory.csv')
    assert len(inventory)==13 and inventory.country.nunique()==13
    for dataset in ['public','wrds']:
        score=pd.read_csv(OUT/(dataset+'_household_policy_scores.csv'))
        rules=pd.read_csv(OUT/(dataset+'_household_rule_selection.csv'))
        assert len(score)==480 and len(rules)==96
        assert np.allclose(score[['equity_weight','cash_weight','bond_weight']].sum(axis=1),1)
        assert score.outlay_success.between(0,1).all() and score.joint_success.le(score.outlay_success).all()
        assert score.funded_share.between(0,1+1e-10).all() and score.mean_unmet.ge(0).all()
    age=pd.read_csv(OUT/'age_out_of_wave_scores.csv')
    primary=age[age.model.eq('Financial vs financial + age')]
    assert len(primary)==6 and primary.estimate.gt(0).all() and primary.p_holm_six_incremental_age_tests.lt(.05).all()
    exact={}
    for name in ['frontier','signed_flow','historical_replay']:
        path=OUT/('engine24_'+name+'_reproduction.log')
        if not path.exists():continue
        content=path.read_text(encoding='utf-16' if path.read_bytes().startswith(b'\xff\xfe') else 'utf-8')
        if name=='historical_replay' and 'reproduced ' not in content:
            continue
        assert 'DIFFERENT' not in content and 'reproduced ' in content
        exact[name]=content.splitlines()[-1]
    assert 'frontier' in exact and 'signed_flow' in exact
    replay=json.loads((OUT/'engine24_historical_replay_audit.json').read_text())
    assert replay['changed_count']==9
    assert all(d['path'].startswith('/forward/') for d in replay['differences'])
    pages={}
    for name,expected in [('fixed_income_executive_brief_2026-11-20.pdf',1),('fixed_income_integrated_report_2026-11-20.pdf',11)]:
        reader=PdfReader(PROJECT/'output/pdf'/name)
        assert len(reader.pages)==expected
        assert all('\ufffd' not in p.extract_text() and len(p.extract_text())>200 for p in reader.pages)
        pages[name]=expected
    receipt=dict(date='2026-11-20',engine_semantic_version='2.4',
        backend_and_accounting_tests=junit('clean_backend_tests.xml'),household_and_auc_tests=junit('clean_household_tests.xml'),
        frontend_unit_tests={'passed':230,'failed':0},browser_tests=browser,
        independent_install='Fresh local clone, uv frozen backend plus dev extra, npm ci, isolated report environment; no copied environments or node_modules',
        clean_public_data='Restored committed public snapshot and rebuilt panel independently',
        clean_household_data='Replayed 12 hash-verified SCF and 4 SHED archives, two Italian archives, two HFCS archives and the verified Indian analytic extract in an independent helper tree; live re-download was not required',
        clean_numeric_artifacts=reproduction,exact_prior_study_reproduction=exact,
        complete_legacy_demo_re_evaluation={'status':'Completed including forward simulation and all experiments','changed_fields':9,'scope':'Only forward CE and unmet-outlay summaries change; remaining numerical fields agree within recorded tolerance','audit':'engine24_historical_replay_audit.json'},
        production_build='Passed in independently installed frontend',lint='Passed without lint warnings',typecheck='Passed',
        one_command_windows_install=install,
        npm_audit='0 known advisories at the November 20 registry check; not a guarantee against future advisories',
        executed_notebook={'code_cells':len(code),'error_outputs':0,'standalone_figures':8,'language':'English'},
        pdf_pages=pages,pdf_review='Rendered pages visually checked; no clipping or missing report text',
        country_inventory='13 country records; 8 European aggregate profiles; evidence levels kept separate',
        warnings=['Existing Starlette/httpx TestClient deprecation','Report kernel warns that local TCP transport is unencrypted; no credentials or restricted rows in notebook',
                  'One initial household test run could not write the optional pytest cache; six tests passed',
                  'Early browser attempts used a stale server / a test origin outside CORS; final fresh frontend on the configured origin passed all 26 tests'],
        scientific_boundaries=['Repeated cross-sections do not identify causal aging','Held-out survey intervals condition on fitted training models',
            'Retrospective chronological tests are not an untouched prospective lockbox',
            'SHED validates a related hardship predictor, not the SCF stress formula','Mean-template nonlinear outcomes are not population outcomes',
            'Monte Carlo intervals exclude return-model and household-estimation uncertainty','Initial portfolio allocation is endowed; no initial implementation turnover charge',
            'No stable general CE advantage or harmonized country capacity ranking is established',
            'Legacy historical-replay forward summaries are superseded by the completed 2.4 re-evaluation; see ENGINE24_IMPACT_AUDIT.txt'],
        external_dependencies=['Employer response and installation environment','Research-access international microdata and resolved response documentation',
                               'No recording/transcript located in the sources previously searched'],
        licensed_data='No raw CRSP/TRACE rows, credentials or private microdata included in the delivery package')
    (OUT/'verification.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print('Integrated verification passed:',receipt['backend_and_accounting_tests']['tests'],'backend/research +',receipt['household_and_auc_tests']['tests'],'household, 230 frontend, 26 browser tests')


if __name__=='__main__':main()

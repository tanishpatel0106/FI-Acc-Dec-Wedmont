"""Package complete versioned source, public helpers and aggregate employer evidence."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]
PROJECT=ROOT.parent
OUT=ROOT/'research/integrated_handoff_2026_11_20'
DELIVERY=PROJECT/'outputs/fixed_income_complete_handoff_2026-11-20.zip'


def main():
    status=subprocess.check_output(['git','status','--porcelain'],cwd=ROOT).decode()
    if status.strip():
        raise RuntimeError('Commit the reviewed source and aggregate artifacts before packaging')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip()
    archive=subprocess.check_output(['git','archive','--format=zip','HEAD'],cwd=ROOT)
    payload={}
    with zipfile.ZipFile(io.BytesIO(archive)) as source:
        for item in source.infolist():
            if not item.is_dir():payload['lifecycle/'+item.filename]=source.read(item)
    for name in ['scf_analysis.py','capacity_validation.py','age_expense_analysis.py','italy_age_extension.py',
                 'india_age_analysis.py','europe_age_inventory.py','research_stage2.py']:
        payload['household/scripts/'+name]=(PROJECT/'scripts'/name).read_bytes()
    payload['household/data/age_expense_extension/bls_health_transcription.json']=(PROJECT/'data/age_expense_extension/bls_health_transcription.json').read_bytes()
    payload['household/data/age_expense_extension/india_extract_manifest.json']=(PROJECT/'data/age_expense_extension/india_extract_manifest.json').read_bytes()
    for name in ['fixed_income_executive_brief_2026-11-20.pdf','fixed_income_integrated_report_2026-11-20.pdf']:
        payload['output/pdf/'+name]=(PROJECT/'output/pdf'/name).read_bytes()
    payload['START_HERE.txt']=(OUT/'REPRODUCE.txt').read_bytes()
    hashes={name:dict(sha256=hashlib.sha256(data).hexdigest(),bytes=len(data)) for name,data in sorted(payload.items())}
    for name in payload:
        parts=Path(name).parts
        assert not any(p in ['.git','.venv','node_modules','.next','__pycache__'] for p in parts),name
        assert not name.endswith('.env') and not name.startswith('lifecycle/data/wrds_') and '/data/runs/' not in name,name
        assert not (name.startswith('lifecycle/data/') or name.startswith('household/data/raw/') or name.startswith('household/data/capacity_validation/')),name
    licensed=json.loads((ROOT/'research/wrds_validation_2026_11_19/extraction_summary.json').read_text())
    forbidden_hashes={v['sha256'] for v in licensed['sources'].values()}
    assert not any(record['sha256'] in forbidden_hashes for record in hashes.values())
    manifest=dict(date='2026-11-20',source_commit=commit,engine_semantic_version='2.4',
        contents='Complete committed source; public snapshots; executed aggregate notebooks; public household helper source; final PDFs',
        raw_wrds_data_included=False,raw_household_data_included=False,credentials_included=False,
        manifest_scope='All archive entries except MANIFEST.json itself',files=hashes)
    payload['MANIFEST.json']=json.dumps(manifest,indent=2).encode('utf-8')
    with zipfile.ZipFile(DELIVERY,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for name,data in sorted(payload.items()):archive.writestr(name,data)
    with zipfile.ZipFile(DELIVERY) as archive:
        assert archive.testzip() is None
        for name,record in hashes.items():assert hashlib.sha256(archive.read(name)).hexdigest()==record['sha256']
    digest=hashlib.sha256(DELIVERY.read_bytes()).hexdigest()
    DELIVERY.with_suffix('.sha256').write_text(digest+'  '+DELIVERY.name+'\n',encoding='ascii')
    print(json.dumps(dict(package=DELIVERY.name,bytes=DELIVERY.stat().st_size,entries=len(payload),source_commit=commit,sha256=digest,crc='passed',entry_hashes='all passed'),indent=2))


if __name__=='__main__':main()

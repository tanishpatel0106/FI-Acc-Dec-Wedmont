"""Reproduce the Italian, Indian and European aggregate results from public inputs."""
import os
from pathlib import Path
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
PROJECT=Path(os.environ.get('FIXED_INCOME_SURVEY_ROOT',ROOT.parent))
sys.path.insert(0,str(PROJECT/'scripts'))
import age_expense_analysis as household

OUT=ROOT/'research/integrated_handoff_2026_11_20/evidence_international_rerun'
OUT.mkdir(exist_ok=True)
household.OUT=OUT
import italy_age_extension
import india_age_analysis
import europe_age_inventory


def main():
    italy_age_extension.run()
    data=PROJECT/'data/age_expense_extension'
    if not (data/'india_analysis_fields.csv.gz').exists() and not (data/'india_respondents.xlsx').exists():
        with zipfile.ZipFile(data/'sebi2025_respondents.zip') as archive:
            member=next(name for name in archive.namelist() if name.endswith('/Respondent Data.XLSX'))
            with archive.open(member) as source,(data/'india_respondents.xlsx').open('wb') as destination:
                import shutil
                shutil.copyfileobj(source,destination,1024*1024)
    india_age_analysis.run()
    india_age_analysis.estimate_age()
    europe_age_inventory.extract()
    print('Italian, Indian and eight-country European evidence reproduced',flush=True)


if __name__=='__main__':main()

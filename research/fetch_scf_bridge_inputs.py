"""Download and verify the frozen public SCF inputs needed for this handoff."""
import argparse
import hashlib
import json
from pathlib import Path
import requests

HERE=Path(__file__).resolve().parent/'integrated_handoff_2026_11_20'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--target',type=Path,required=True,help='Household helper root with scripts/ and data/')
    parser.add_argument('--include-shed',action='store_true',help='Also fetch the four public SHED files')
    parser.add_argument('--include-international',action='store_true',help='Also fetch Italian microdata, SEBI respondents and HFCS tables')
    args=parser.parse_args()
    records=json.loads((HERE/'household_input_manifest.json').read_text())['sources']
    if args.include_shed:
        records+=json.loads((HERE/'evidence_shed/input_manifest.json').read_text())['sources']
    if args.include_international:
        records+=json.loads((HERE/'international_input_manifest.json').read_text())['sources']
    for record in records:
        folder=args.target/Path(record['relative_path']).parent if 'relative_path' in record else args.target/'data'/('raw' if '2025' in record['filename'] else 'capacity_validation')
        folder.mkdir(exist_ok=True,parents=True)
        path=folder/record['filename']
        if path.exists():
            if hashlib.sha256(path.read_bytes()).hexdigest()!=record['sha256']:
                raise RuntimeError('Existing input hash differs from frozen vintage: '+path.name)
            print('Verified existing public input',path.name,flush=True)
            continue
        temp=path.with_suffix(path.suffix+'.download')
        digest=hashlib.sha256()
        try:
            with requests.get(record['url'],stream=True,timeout=(20,180)) as response:
                response.raise_for_status()
                with temp.open('wb') as stream:
                    for block in response.iter_content(1024*1024):
                        if block:stream.write(block);digest.update(block)
            if digest.hexdigest()!=record['sha256']:
                raise RuntimeError('Official input differs from frozen vintage: '+path.name+'; inspect the new release rather than mixing versions')
            temp.replace(path)
        finally:
            if temp.exists():temp.unlink()
        print('Downloaded and verified',path.name,flush=True)


if __name__=='__main__':main()

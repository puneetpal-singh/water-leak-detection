"""Fetch official CSVs and nominal topology, verifying Zenodo's MD5 checksums."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib
import json
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data' / 'raw'
RECORD = 'https://zenodo.org/api/records/4017659'

def download() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    response = requests.get(RECORD, timeout=60)
    response.raise_for_status()
    record = response.json()
    (RAW / 'zenodo_record.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    selected = [f for f in record['files'] if f['key'].endswith('.csv') or f['key'] in
                ['README.txt', 'L-TOWN.inp', 'dataset_configuration.yaml', '2018_Fixed_Leakages_Report.txt']]
    def fetch(item: dict) -> None:
        path = RAW / item['key']
        expected = item['checksum'].split(':')[1]
        if path.exists() and hashlib.md5(path.read_bytes()).hexdigest() == expected:
            return
        url = f"https://zenodo.org/records/4017659/files/{item['key']}?download=1"
        r = requests.get(url, timeout=180)
        r.raise_for_status()
        if hashlib.md5(r.content).hexdigest() != expected:
            raise ValueError(f"Checksum mismatch: {item['key']}")
        path.write_bytes(r.content)
        print(f"Verified {item['key']}: {len(r.content):,} bytes", flush=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(fetch, selected))

if __name__ == '__main__':
    download()

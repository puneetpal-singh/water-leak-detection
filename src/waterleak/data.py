"""Read the inspected BattLeDIM schema without mixing truth into telemetry."""
from pathlib import Path
import json
import hashlib
import numpy as np
import pandas as pd
import yaml

KINDS = {'Pressures': ('pressure', 'm'), 'Flows': ('flow', 'm3/h'),
         'Levels': ('level', 'm'), 'Demands': ('demand', 'L/h')}

def verify_sources(raw: Path) -> dict:
    """Reject changed source bytes before rebuilding derived data."""
    record = json.loads((raw / 'zenodo_record.json').read_text())
    verified = {}
    for entry in record['files']:
        path = raw / entry['key']
        if not path.exists():
            continue
        algorithm, expected = entry['checksum'].split(':', 1)
        if algorithm != 'md5':
            raise ValueError(f'Unsupported checksum: {algorithm}')
        with path.open('rb') as handle:
            actual = hashlib.file_digest(handle, 'md5').hexdigest()
        if actual != expected:
            raise ValueError(f'Source checksum mismatch: {path.name}; run download_data.py again')
        verified[path.name] = entry['checksum']
    return verified

def read_csv(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, sep=';', decimal=',')
    frame.index = pd.to_datetime(frame.pop('Timestamp'), format='%Y-%m-%d %H:%M:%S', errors='raise')
    frame.index.name = 'timestamp'
    return frame.apply(pd.to_numeric, errors='raise').sort_index()

def audit_and_clean(frame: pd.DataFrame, kind: str) -> tuple[pd.DataFrame, dict]:
    """Drop only identical timestamp duplicates; fill at most two past samples."""
    if frame.empty or not isinstance(frame.index, pd.DatetimeIndex) or frame.index.hasnans:
        raise ValueError('Measurements require a nonempty, valid DatetimeIndex')
    frame = frame.sort_index()
    if not frame.index.floor('5min').equals(frame.index):
        raise ValueError('Off-grid timestamps require explicit handling')
    duplicates = int(frame.index.duplicated().sum())
    if duplicates:
        for _, group in frame[frame.index.duplicated(keep=False)].groupby(level=0):
            same = group.eq(group.iloc[0]) | (group.isna() & group.iloc[0].isna())
            if not same.all().all():
                raise ValueError('Conflicting measurements at a duplicate timestamp')
    original = frame[~frame.index.duplicated(keep='first')]
    grid = pd.date_range(original.index.min(), original.index.max(), freq='5min', name='timestamp')
    if not original.index.isin(grid).all():
        raise ValueError('Off-grid timestamps require explicit handling')
    aligned = original.reindex(grid)
    numeric = aligned.replace([np.inf, -np.inf], np.nan)
    negatives = (numeric < 0).sum()
    # Signed flow and sub-atmospheric pressure can be meaningful. Retain and flag.
    if kind == 'demand':
        numeric = numeric.mask(numeric < 0)
    clean = numeric.ffill(limit=2)
    audit = {
        'rows': len(frame), 'sensors': len(frame.columns), 'start': str(grid.min()),
        'end': str(grid.max()), 'duplicate_timestamps': duplicates,
        'missing_timestamps': len(grid.difference(original.index)),
        'sampling_seconds': original.index.to_series().diff().dt.total_seconds().value_counts().to_dict(),
        'original_missing_cells': int(aligned.isna().sum().sum()),
        'nonfinite_cells': int(np.isinf(aligned.to_numpy()).sum()),
        'negative_cells': int(negatives.sum()),
        'missing_pct': (aligned.isna().mean() * 100).to_dict(),
        'filled_cells': int((numeric.isna() & clean.notna()).sum().sum()),
        'remaining_missing_cells': int(clean.isna().sum().sum())}
    return clean, audit

def read_events(raw: Path) -> pd.DataFrame:
    """Configuration is retrospective truth. Never pass this frame as features."""
    config = yaml.safe_load((raw / 'dataset_configuration.yaml').read_text())
    rows = [list(map(str.strip, row.split(','))) for row in config['leakages'] if row]
    events = pd.DataFrame(rows, columns=['pipe', 'start', 'end', 'diameter_m', 'type', 'peak'])
    for name in ['start', 'end', 'peak']:
        events[name] = pd.to_datetime(events[name], format='%Y-%m-%d %H:%M')
    events['diameter_m'] = events.diameter_m.astype(float)
    return events.sort_values('start').reset_index(drop=True)

def read_topology(path: Path) -> dict:
    """Parse nominal EPANET geometry; coordinates are schematic, not lat/lon."""
    nodes, edges, section = {}, [], ''
    for line in path.read_text().splitlines():
        line = line.split(';')[0].strip()
        if not line:
            continue
        if line.startswith('['):
            section = line
            continue
        fields = line.split()
        if section == '[COORDINATES]' and len(fields) >= 3:
            nodes[fields[0]] = [float(fields[1]), float(fields[2])]
        if section in ['[PIPES]', '[PUMPS]', '[VALVES]'] and len(fields) >= 3:
            edges.append({'id': fields[0], 'from': fields[1], 'to': fields[2]})
    return {'nodes': nodes, 'edges': edges}

def prepare(root: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    raw, results, processed = root / 'data/raw', root / 'results', root / 'data/processed'
    results.mkdir(exist_ok=True)
    processed.mkdir(parents=True, exist_ok=True)
    verified = verify_sources(raw)
    frames, truths, audits, dictionary = [], [], {}, []
    for year in [2018, 2019]:
        measurements = []
        for name, (kind, unit) in KINDS.items():
            filename = f'{year}_SCADA_{name}.csv'
            clean, audit = audit_and_clean(read_csv(raw / filename), kind)
            audits[filename] = audit
            for sensor in clean:
                dictionary.append({'year': year, 'file': filename, 'sensor': sensor,
                    'column': f'{kind}:{sensor}', 'kind': kind, 'unit': unit,
                    'network_entity': 'link' if kind == 'flow' else 'node',
                    'role': 'measurement', 'frequency': '5min'})
            measurements.append(clean.add_prefix(f'{kind}:'))
        joined = pd.concat(measurements, axis=1, join='outer')
        frames.append(joined)
        truth = read_csv(raw / f'{year}_Leakages.csv')
        truths.append(truth)
        audits[f'{year}_Leakages.csv'] = {'rows': len(truth), 'pipes': len(truth.columns),
            'any_leak_fraction': float(truth.gt(0).any(axis=1).mean()),
            'role': 'retrospective ground truth; excluded from inference'}
    telemetry = pd.concat(frames).sort_index()
    truth = pd.concat(truths).fillna(0).sort_index()
    events = read_events(raw)
    telemetry.to_parquet(processed / 'telemetry.parquet')
    (processed / 'source_checksums.json').write_text(json.dumps(verified, indent=2), encoding='utf-8')
    truth.to_parquet(processed / 'leak_truth.parquet')
    events.to_csv(results / 'events.csv', index=False)
    pd.DataFrame(dictionary).to_csv(results / 'data_dictionary.csv', index=False)
    (results / 'data_audit.json').write_text(json.dumps(audits, indent=2), encoding='utf-8')
    topology = read_topology(raw / 'L-TOWN.inp')
    (results / 'topology.json').write_text(json.dumps(topology), encoding='utf-8')
    manifest = json.loads((raw / 'zenodo_record.json').read_text())
    inventory = [{'file': f['key'], 'bytes': f['size'], 'checksum': f['checksum'],
                  'downloaded': (raw / f['key']).exists()} for f in manifest['files']]
    pd.DataFrame(inventory).to_csv(results / 'source_inventory.csv', index=False)
    return telemetry, truth, events, audits

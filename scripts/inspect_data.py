"""Stage 1: preserve source data, audit every CSV, export the data dictionary."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from waterleak.data import prepare

if __name__ == '__main__':
    x, truth, events, audits = prepare(Path(__file__).resolve().parents[1])
    print(f'{x.shape=}, {len(events)=}, {len(events[events.start.dt.year == 2019])=}')
    for name, a in audits.items():
        print(name, {k: v for k, v in a.items() if k not in ['missing_pct', 'sampling_seconds']})

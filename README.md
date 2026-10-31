# Water Network Leak Detection and Sensor Analytics using BattLeDIM

An engineering study of pressure, flow, demand and tank-level measurements from
the public [BattLeDIM dataset](https://zenodo.org/records/4017659).

The work proceeds in committed stages: inspect and audit the official files;
analyse operating patterns; build causal features; compare statistical and ML
alarms on chronological holdouts; present results in an interactive dashboard.

## Dataset and scope

The source CSVs use semicolons and decimal commas, with timezone-naive timestamps.
The network has 33 pressure sensors (m), 3 flow sensors (m3/h), 1 tank level (m),
and 82 demand meters (L/h). Historical measurements cover 2018; evaluation covers
2019. Leak flows and configuration are retrospective truth, never input features.

Persistent leaks make all of 2019 leak-positive. This study therefore evaluates
**new leak onset detection within 72 hours**, rather than claiming that ordinary
binary leak-presence classification is meaningful. Exact methodology and measured
results are added after the experiment runs.

## Reproduce the data audit

```powershell
python -m venv .venv
.venv/Scripts/Activate.ps1
python -m pip install -r requirements.txt
python scripts/download_data.py
python scripts/inspect_data.py
```

The downloader verifies official MD5 checksums. Raw files are ignored by Git;
`results/source_inventory.csv` records both downloaded and omitted source files.
The two Excel files duplicate CSV content. `L-TOWN_Real.inp` contains the hidden
generation parameters; only the nominal `L-TOWN.inp` is used for topology.

## Credits

BattLeDIM: Vrachimis et al., *Battle of the Leakage Detection and Isolation
Methods*, Journal of Water Resources Planning and Management 148(12), 04022068,
2022. Dataset DOI: 10.5281/zenodo.4017659, CC BY 4.0.

Dashboard design follows [/unslop by Damir Sokolovsky](https://github.com/heydamir/unslop),
CC BY 4.0. See `docs/design.md` for the direction and design review.

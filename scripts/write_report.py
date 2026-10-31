"""Generate README result rows and CV bullets from the measured experiment."""
from pathlib import Path
import pandas as pd
import json

ROOT = Path(__file__).resolve().parents[1]
metrics = pd.read_csv(ROOT / 'results/model_comparison.csv')
insights = json.loads((ROOT / 'results/insights.json').read_text())
experiment = json.loads((ROOT / 'results/experiment.json').read_text())
rows = []
for m in metrics.itertuples():
    delay = f'{m.mean_delay_hours:.1f}' if pd.notna(m.mean_delay_hours) else '—'
    rows.append(f'| {m.method} | {m.precision:.3f} | {m.recall:.3f} | {m.f1:.3f} | {m.pr_auc_ap:.3f} | {m.leaks_detected}/19 | {m.false_alarms} | {delay} |')
table = '\n'.join(rows)
pca = metrics[metrics.method == 'PCA reconstruction'].iloc[0]
readme = f'''# Water Network Leak Detection and Sensor Analytics using BattLeDIM

An engineering and data analytics project that investigates **25,018,560 sensor
measurements**, then asks whether interpretable anomaly detectors can identify
new leak onsets reliably. The emphasis is on operating patterns, causal features,
honest evaluation and engineering interpretation.

[Interactive dashboard](https://battledim-sensor-analytics-puneet.puneetsekhon07.chatgpt.site)
· [Methodology](docs/methodology.md) · [Step-by-step walkthrough](docs/walkthrough.md)
· [Measured results](results/model_comparison.csv) · [CV bullets](results/cv_bullets.md)

The Site and GitHub repository were initially created with private access.

![Web dashboard overview](results/screenshots/overview.jpg)

## Problem and scope

Water-network signals change with daily demand, pumps, seasons and leaks. An
anomaly score is useful only if it leads to timely alarms with tolerable false
alarms. This project studies that distinction, rather than maximizing accuracy
on an imbalanced label.

**The main result is a limitation:** high event recall is largely explained by
frequent alarms. These detectors need improvement before use in operations.
The project demonstrates how to expose that failure, not conceal it.

## Dataset

Official source: [BattLeDIM, Zenodo record 4017659](https://zenodo.org/records/4017659).
This is realistic **simulated** telemetry from L-Town, not a deployed utility trial.

| Measurement | Channels | Source units | Network reference |
|---|---:|---|---|
| Pressure | 33 | m | Node ID |
| Flow | 3 | m³/h | Link ID: p227, p235, PUMP_1 |
| Tank level | 1 | m | T1 |
| AMR demand | 82 | L/h | Node ID |

2018 and 2019 each contain 105,120 five-minute rows. The CSVs have semicolon
separators, decimal commas and timezone-naive timestamps. The inspected files
have **zero missing values, duplicate timestamps or irregular intervals**.
No imputation was needed. The pipeline still tests missing-grid and duplicate handling.

Leak histories give pipe-level simulated leak flow; configuration provides
33 onsets (14 in 2018 and 19 in 2019), types, peaks and reported ends. They are
ground truth only. The nominal EPANET file supplies actual schematic geometry.
Hidden generating parameters in `L-TOWN_Real.inp` are deliberately not used.

See the [sensor data dictionary](results/data_dictionary.csv),
[complete source inventory](results/source_inventory.csv) and
[data quality audit](results/data_audit.json). Excel files duplicate the CSVs;
the large real-parameter INP file is omitted. Downloaded CSVs remain separate
from derived Parquet files and are ignored by Git.

## Workflow

```mermaid
flowchart LR
    A[Official CSVs + checksums] --> B[Audit and aligned telemetry]
    B --> C[EDA and engineering comparisons]
    B --> D[Causal 15-minute features]
    D --> E[2018 fit and validation]
    E --> F[Frozen models and thresholds]
    F --> G[2019 scores and streaming alarms]
    H[Retrospective event truth] --> I[Strict onset evaluation]
    G --> I
    C --> J[Web and Streamlit dashboards]
    I --> J
```

## Engineering Insights

- Both DMA flow series peak around 19:00 and have their minimum hourly mean
  around 04:00 across the whole record. The p235 hourly mean spans
  {insights['strongest_hourly_flow_swing_m3h']:.1f} m³/h, so a fixed raw-flow threshold would mix the demand cycle with anomalies.
- Pressure n1 and flow p227 have Pearson correlation
  {insights['pressure_flow_correlation_n1_p227']:.2f}. Pressure-flow association helps interpret anomalies, but is not a causal diagnosis.
- Existing leaks occupy {insights['2018_leak_presence_fraction']:.1%} of 2018 and all of 2019.
  Binary “any leak present” evaluation on 2019 has no negative class.
- Trailing daily references suppress operating cycles but can absorb gradual
  leaks. Near-constant and switching sensors can also create extreme MAD scores.
- Overlapping leaks and changes in demand confound local before/after comparisons.
  Sensor departures do not establish which pipe caused them.

EDA exports include distributions, percentiles, rolling and rate-of-change
inspection, hourly and weekday profiles, weekly/monthly trends, a focused
correlation matrix, selected pressure-flow pairs and local pre-onset/onset/recovery
comparisons. Recovery is unavailable for events censored at the record end.

## Features and methods

The first detector uses 33 pressures, 3 flows and 1 level. Demand channels remain
available for analysis. Completed 15-minute bins are right-labeled at availability
time. Features include same-quarter-hour trailing daily residuals, one-hour
rolling mean/std/range, one-hour differences, lagged residuals, weekly changes,
a pressure contrast and a guarded flow-ratio change: **{experiment['feature_count']} features**.

The daily reference uses only the preceding seven days, with at least five daily
observations. No centered windows, future filling or event labels enter features.
Scaling, feature selection and model fits use training rows only. The trailing
reference updates causally during test, while fitted models and thresholds stay fixed.

Five methods are compared: a sensor residual MAD baseline, IQR fences, Isolation
Forest, PCA reconstruction error and novelty Local Outlier Factor. The robust
baseline uses residuals; the other four use the full shared feature matrix.
All methods share the sensor gate and alarm policy. PCA retains
{experiment['pca_explained_variance']:.1%} of training variance using {experiment['pca_components']} components. There is no deep-learning component.

## Evaluation design

Fit on January–September 2018 after warmup and exclusions around historical
transitions: {experiment['training_rows']:,} eligible rows, with a seeded sample of {experiment['sample_rows']:,} for ML fitting.
These are **stable operating states with background leaks**, not certified leak-free
examples. Validation covers October–December 2018; 2019 is held out for testing.

Choose among five predeclared training-score percentiles using validation event
F1. Validation has only two new onsets, making calibration uncertain. Require
four consecutive 15-minute exceedances and at least two abnormal sensors;
clear after four non-exceedances. Confirmation is not backdated.

The task is **new onset within 72 hours**, not continuing leak presence. Match
new alarm starts one-to-one to events; pre-existing alarms receive no credit.
Unmatched alarms are false relative to this task, even if they reflect another
real hydraulic change. Point F1 uses active alarms; AP uses raw scores. No-skill
test AP is {pca.positive_fraction:.3f}. Mean delays include detections only, so read them with misses.
The pipeline also exports 24/72/168-hour sensitivity and a 200-shift timing control.

## Measured 2019 results

| Method | Precision | Recall | F1 | AP | Events detected | False alarms | Mean delay (h) |
|---|---:|---:|---:|---:|---:|---:|---:|
{table}

PCA matches {int(pca.leaks_detected)}/19 events, but its timing-shift control averages
{pca.shift_control_mean_recall:.1%} recall. Its {int(pca.false_alarms)} unmatched alarms ({pca.false_alarms_per_week:.2f}/week) make
event recall insufficient evidence of useful detection. Point AP is
{pca.pr_auc_ap:.3f} against {pca.positive_fraction:.3f} prevalence: modest separation, not a deployment result.

[Per-event delays and sensor attributions](results/event_detections.csv) ·
[Validation candidates](results/validation_calibration.csv) ·
[Horizon sensitivity](results/horizon_sensitivity.csv) ·
[All alarm episodes](results/alarm_episodes.csv)

## Visualizations and dashboard

The [web dashboard](https://battledim-sensor-analytics-puneet.puneetsekhon07.chatgpt.site)
has seven views: overview, operating patterns, sensor explorer, event explorer,
model comparison, nominal network/correlations and methodology. It lazy-loads
hourly sensor histories and completed 15-minute event windows. Plotly is bundled
locally. The Streamlit workbench adds original five-minute traces, trailing
standard deviations, rates of change and full evaluation tables.

![Event investigation with sensor residual attribution](results/screenshots/event.jpg)

Six self-contained interactive figures are in [results/figures](results/figures):
hourly flow, sensor correlations, model comparison, delay distributions, a
three-panel p523 event investigation, and a selected pressure-flow relationship.
Open the HTML files locally. Browser charts can export PNGs.

## Installation and usage

Python 3.11+ is required; the implementation was tested on Python 3.14.

```powershell
git clone https://github.com/puneetpal-singh/water-leak-detection.git
cd water-leak-detection
python -m venv .venv
.venv/Scripts/Activate.ps1
python -m pip install -r requirements.txt
python scripts/download_data.py
python scripts/inspect_data.py
python scripts/run_pipeline.py
python scripts/export_dashboard.py
python scripts/write_report.py
python -m pytest -q
python -m streamlit run dashboard/app.py
```

On macOS/Linux use `source .venv/bin/activate` instead. Downloading needs network
access and roughly 205 MB for the selected source files. Allow about 1 GB free
space for sources, derived data, exports and a virtual environment. The pipeline
runs on a CPU; runtime varies by machine. Important parameters and random seed
are in [config.json](config.json). Run scripts from the repository root.

The committed web export works without downloading raw data:

```powershell
python -m http.server 8765 --directory dashboard/web/dist
```

Open [localhost:8765](http://localhost:8765). Serve over HTTP; do not open index.html
with a file URL because the browser fetches JSON assets.

## Repository structure

```text
data/raw/                  Original verified downloads (Git-ignored)
data/processed/            Aligned telemetry, features and scores (Git-ignored)
notebooks/                 Four ordered, executable analysis entry points
src/waterleak/             Data, features, EDA, models and event evaluation
scripts/                   Download, audit, experiment, export and checks
dashboard/app.py           Full-resolution Streamlit workbench
dashboard/web/dist/        Buildless Plotly web dashboard and measured data
tests/                     Preprocessing, causality, model and event tests
results/                   Tables, experiment metadata, figures and screenshots
docs/                      Methodology, walkthrough and /unslop design review
```

The notebooks use reusable modules and saved results; they are not the pipeline.
Open them after running the scripts above. They contain analysis entry points,
not fabricated precomputed cell outputs.

## Validation and limitations

Nine tests check bounded forward fill, missing-grid handling, conflicting
duplicates, signed values, complete-bin availability, future-invariant features,
training-label boundaries, future-invariant model fitting and strict event matching.
`python scripts/check_dashboard.py` exercises all six Streamlit views against
the generated experiment. Browser checks cover web navigation and sensor/date/event
controls; the source includes responsive layouts and keyboard focus states.

There is one simulated network and one test year. Seasonal drift and continuing
leaks affect transferability. The short validation period limits calibration.
Model score clipping and robust scaling can suppress or exaggerate certain regimes.
The 72-hour onset task differs from the official BattLeDIM economic evaluation.
Attributions are sensor residual departures, not causal localization or ML feature
importance. The circular-shift control is descriptive and does not model annual drift.

## Future work

Compare pump-state and demand-conditioned baselines, calibrate per sensor group,
and measure false alarms under explicit operational budgets. Add more networks
and validation years before tuning complex models. Treat hydraulic localization
and the official economic scoring system as separate, explicitly evaluated tasks.

## Credits and licenses

BattLeDIM: Vrachimis et al., *Battle of the Leakage Detection and Isolation Methods*,
Journal of Water Resources Planning and Management 148(12), 04022068 (2022).
Dataset DOI: 10.5281/zenodo.4017659, CC BY 4.0. Use the official record for full authorship.

Dashboard design follows [/unslop by Damir Sokolovsky](https://github.com/heydamir/unslop),
CC BY 4.0. See [design direction and review](docs/design.md).
Bundled Plotly.js is MIT-licensed; its license header is retained in the vendor file.
'''
(ROOT / 'README.md').write_text(readme, encoding='utf-8')
bullets = '''# CV bullets

- Analysed 25 million simulated water-network measurements across 119 channels using Python, Pandas and NumPy; audited data quality and investigated daily patterns, sensor correlations and leak-related changes.
- Engineered 261 causal time-series features and compared five statistical and ML anomaly detectors using chronological holdouts, event matching, detection delays and false-alarm controls.
- Built interactive Plotly web and Streamlit dashboards for sensor exploration, 19 test-year leak investigations, model comparison and EPANET network visualization; documented reproducible results and detector limitations.
'''
(ROOT / 'results/cv_bullets.md').write_text(bullets, encoding='utf-8')
print('Generated README and three evidence-based CV bullets')

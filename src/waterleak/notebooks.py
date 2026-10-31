"""Generate guided notebooks that analyse real saved pipeline artifacts."""
from pathlib import Path
import nbformat as nbf

BOOTSTRAP = """from pathlib import Path
import sys, json
import pandas as pd
import plotly.express as px
import plotly.io as pio
pio.renderers.default = 'plotly_mimetype'
ROOT = Path.cwd() if (Path.cwd()/'results').exists() else Path.cwd().parent
sys.path.insert(0, str(ROOT/'src'))
experiment = json.loads((ROOT/'results/experiment.json').read_text())
assert experiment['protocol_version'] == 2
"""

def write_notebooks(root: Path) -> None:
    notebooks = [
        ('01_data_understanding', 'Understand the dataset before modeling', [
            ('Which files and measurements are actually present?',
             "inventory = pd.read_csv(ROOT/'results/source_inventory.csv')\ndictionary = pd.read_csv(ROOT/'results/data_dictionary.csv')\ndisplay(inventory)\ndictionary.drop_duplicates('column').groupby(['kind','unit']).size().to_frame('channels')"),
            ('Are the timestamp grid and values complete?',
             "audit = json.loads((ROOT/'results/data_audit.json').read_text())\nquality = pd.DataFrame({k:v for k,v in audit.items() if '_SCADA_' in k}).T\nquality[['rows','sensors','duplicate_timestamps','missing_timestamps','original_missing_cells','filled_cells']]"),
            ('Why is ordinary binary leak-presence classification unsuitable?',
             "presence = {year: audit[f'{year}_Leakages.csv']['any_leak_fraction'] for year in [2018,2019]}\nevents = pd.read_csv(ROOT/'results/events.csv', parse_dates=['start','end'])\ndisplay(pd.Series(presence, name='fraction_with_any_leak'))\nevents.assign(year=events.start.dt.year).groupby(['year','type']).size().unstack(fill_value=0)"),
            ('Check nominal topology without hidden generation parameters',
             "topology = json.loads((ROOT/'results/topology.json').read_text())\nprint(f\"Nominal coordinates: {len(topology['nodes'])}; links: {len(topology['edges'])}\")\nprint('Unspecified source timezone: retain naive wall-clock timestamps')"),
        ], 'The inspected SCADA files require no imputation. Persistent leaks make every 2019 timestamp leak-positive. The detector therefore targets new onsets, and configuration/pipe leak flows remain retrospective truth.'),
        ('02_exploratory_analysis', 'Operating patterns and leak-related sensor changes', [
            ('What daily operating pattern must a detector distinguish from leaks?',
             "profiles = pd.read_csv(ROOT/'results/hourly_profiles.csv')\npx.line(profiles, x='hour', y=['flow:p227','flow:p235','flow:PUMP_1'], labels={'value':'Flow (m³/h)'})"),
            ('Does the weekday pattern differ, and do weekly averages drift?',
             "weekday = pd.read_csv(ROOT/'results/weekday_profiles.csv')\ndisplay(weekday[['weekday','flow:p227','flow:p235']])\nweekly = pd.read_csv(ROOT/'results/weekly_means.csv')\npx.line(weekly, x='timestamp', y=['flow:p227','flow:p235'], labels={'value':'Weekly mean flow (m³/h)'})"),
            ('Which pressure and flow sensors move together?',
             "correlation = pd.read_csv(ROOT/'results/correlations.csv', index_col=0)\npx.imshow(correlation, zmin=-1, zmax=1, color_continuous_scale='BrBG')"),
            ('Inspect a focused distribution and pressure-flow relationship',
             "statistics = pd.read_csv(ROOT/'results/sensor_statistics.csv')\ndisplay(statistics[statistics.sensor.isin(['pressure:n1','flow:p227','flow:p235'])])\nx = pd.read_parquet(ROOT/'data/processed/telemetry.parquet', columns=['pressure:n1','flow:p227'])\npx.scatter(x.loc['2019'].iloc[::48], x='flow:p227', y='pressure:n1', opacity=.4, labels={'flow:p227':'Flow (m³/h)','pressure:n1':'Pressure (m)'})"),
            ('How do local before/onset/recovery summaries change around p523?',
             "changes = pd.read_csv(ROOT/'results/event_sensor_changes.csv')\nlocal = changes[changes['pipe'].eq('p523')].copy()\nlocal['magnitude'] = local.change_in_pre_std.abs()\nlocal.sort_values('magnitude', ascending=False).head(10).drop(columns='magnitude')"),
        ], 'Daily demand is a major confounder. Correlation does not imply hydraulic adjacency or causation. The local comparison is descriptive: concurrent leaks, seasonality and unequal window coverage can change the summaries. A record-end event has no observed recovery.'),
        ('03_feature_engineering', 'Causal feature construction and calibration boundaries', [
            ('Inspect the measured feature distributions',
             "features = pd.read_parquet(ROOT/'data/processed/features.parquet')\ndisplay(features[['pressure:n1|residual','flow:p227|residual','flow:p235|difference_1h']].describe())\npd.read_csv(ROOT/'results/feature_distributions.csv')"),
            ('Prove future measurements cannot change earlier features',
             "from waterleak.features import causal_features\nmeasurements = pd.read_parquet(ROOT/'data/processed/model_measurements.parquet').iloc[:1000]\nbefore, _ = causal_features(measurements)\naltered = measurements.copy()\naltered.iloc[850:] = 10000\nafter, _ = causal_features(altered)\npd.testing.assert_frame_equal(before.iloc[:850], after.iloc[:850])\nprint('PASS: future changes leave all earlier features unchanged')"),
            ('Prove estimator fitting and threshold reference are separated in time',
             "fit = features.index[experiment['estimator_fit_row_positions']]\nreference = features.index[experiment['threshold_reference_row_positions']]\nassert fit.intersection(reference).empty and fit.max() < reference.min()\nassert reference.max() < pd.Timestamp('2018-10-01')\npd.DataFrame({'start':[fit.min(),reference.min()], 'end':[fit.max(),reference.max()], 'rows':[len(fit),len(reference)]}, index=['Estimator fitting','Threshold reference'])"),
            ('Check an unseen-reference threshold against its saved percentile',
             "scores = pd.read_parquet(ROOT/'data/processed/scores.parquet')\nmethod = 'Local Outlier Factor'\nsetting = experiment['thresholds'][method]\ncalculated = scores.loc[reference, method].quantile(setting['quantile'])\nassert abs(calculated - setting['threshold']) < 1e-10\nprint('LOF threshold:', calculated, '; reference rows:', len(reference))"),
        ], 'The trailing reference uses past measurements and can absorb slow leaks. All fitted transforms use the estimator subset only. LOF novelty scores for fitted rows must not calibrate thresholds. Fitting-pool states may already contain background leaks.'),
        ('04_model_experiments', 'Evaluate score separation, event recall and alarm burden', [
            ('Compare every frozen method on the chronological benchmark',
             "comparison = pd.read_csv(ROOT/'results/model_comparison.csv')\ncomparison[['method','precision','recall','f1','pr_auc_ap','leaks_detected','false_alarms','mean_delay_hours']]"),
            ('Does the score retain precision as recall grows?',
             "curves = pd.read_csv(ROOT/'results/precision_recall_curves.csv')\npx.line(curves, x='recall', y='precision', color='method', range_x=[0,1], range_y=[0,1])"),
            ('Could frequent alarms explain the apparent event recall?',
             "comparison[['method','event_recall','shift_control_mean_recall','shift_control_p05_recall','shift_control_p95_recall','false_alarms_per_week']]"),
            ('Inspect each PCA event, including misses and contributing sensors',
             "detections = pd.read_csv(ROOT/'results/event_detections.csv')\ndetections[detections.method.eq('PCA reconstruction')][['pipe','start','detected_at','delay_hours','contributing_sensors','signed_residual_z']]"),
            ('How much does the detection window change conclusions?',
             "sensitivity = pd.read_csv(ROOT/'results/horizon_sensitivity.csv')\nsensitivity[['method','horizon_hours','leaks_detected','false_alarms','mean_delay_hours']]"),
            ('Inspect validation evidence rather than tune against the test year',
             "validation = pd.read_csv(ROOT/'results/validation_calibration.csv')\nvalidation[['method','quantile','event_f1','leaks_detected','false_alarms']]"),
        ], 'This is protocol v2 after a correctness review, with no 2019-based threshold search. The benchmark has already been inspected, so it is not an untouched external test. There are only two validation onsets. Mean delay excludes misses; the timing-shift control is descriptive, not a significance test. These detectors are not ready for operational deployment.'),
    ]
    destination = root / 'notebooks'
    destination.mkdir(exist_ok=True)
    for name, title, sections, interpretation in notebooks:
        cells = [nbf.v4.new_markdown_cell(f'# {title}\n\nRun the pipeline and dashboard export first. See [methodology](../docs/methodology.md) for protocol v2.'),
                 nbf.v4.new_code_cell(BOOTSTRAP)]
        for heading, source in sections:
            cells += [nbf.v4.new_markdown_cell(f'## {heading}'), nbf.v4.new_code_cell(source)]
        cells.append(nbf.v4.new_markdown_cell('## Interpretation and limits\n\n' + interpretation))
        notebook = nbf.v4.new_notebook(cells=cells)
        notebook.metadata['kernelspec'] = {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'}
        nbf.write(notebook, destination / f'{name}.ipynb')

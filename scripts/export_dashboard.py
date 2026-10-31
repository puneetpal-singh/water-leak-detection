"""Export real-data browser assets, standalone Plotly figures and research notebooks."""
from pathlib import Path
import json
import sys
import shutil
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from plotly.offline import get_plotlyjs
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from waterleak.data import read_events

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / 'dashboard/web/dist'
RESULTS = ROOT / 'results'

def serial(value):
    if isinstance(value, dict):
        return {str(k): serial(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [serial(v) for v in value]
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        return str(value)
    if value is pd.NaT or value is pd.NA:
        return None
    if isinstance(value, (float, np.floating)):
        return round(float(value), 5) if np.isfinite(value) else None
    if isinstance(value, np.integer):
        return int(value)
    return value

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(serial(value), allow_nan=False, separators=(',', ':')), encoding='utf-8')

def style(fig, title, ytitle=None):
    fig.update_layout(title=title, template='plotly_white', font={'family': 'Segoe UI, sans-serif', 'size': 13},
        paper_bgcolor='#fafafa', plot_bgcolor='#ffffff', margin={'l': 64, 'r': 24, 't': 64, 'b': 48},
        colorway=['#087f8c', '#bb791e', '#596575', '#bf5343'], height=460,
        legend={'orientation': 'h', 'y': 1.15})
    if ytitle:
        fig.update_yaxes(title=ytitle)
    return fig

def export():
    DIST.mkdir(parents=True, exist_ok=True)
    (DIST / 'plotly.min.js').write_text(get_plotlyjs(), encoding='utf-8')
    telemetry = pd.read_parquet(ROOT / 'data/processed/telemetry.parquet')
    model_x = pd.read_parquet(ROOT / 'data/processed/model_measurements.parquet')
    scores = pd.read_parquet(ROOT / 'data/processed/scores.parquet')
    active = pd.read_parquet(ROOT / 'data/processed/activity.parquet')
    sensor_z = pd.read_parquet(ROOT / 'data/processed/sensor_z.parquet')
    events = read_events(ROOT / 'data/raw')
    detections = pd.read_csv(RESULTS / 'event_detections.csv')
    metrics = pd.read_csv(RESULTS / 'model_comparison.csv')
    experiment = json.loads((RESULTS / 'experiment.json').read_text())
    insights = json.loads((RESULTS / 'insights.json').read_text())
    stats = pd.read_csv(RESULTS / 'sensor_statistics.csv')
    dictionary = pd.read_csv(RESULTS / 'data_dictionary.csv').drop_duplicates('column')
    correlations = pd.read_csv(RESULTS / 'correlations.csv', index_col=0)
    units = dictionary.set_index('column').unit.to_dict()
    sensors = []
    hourly = telemetry.resample('1h').mean()
    times = hourly.index.strftime('%Y-%m-%dT%H:%M:%S').tolist()
    for i, sensor in enumerate(telemetry):
        sensor_stats = stats[stats.sensor == sensor].iloc[0].to_dict()
        sensors.append({'id': sensor, 'file': f'sensors/{i}.json', 'unit': units[sensor], 'stats': sensor_stats})
        abnormal = sensor_z[sensor].abs().resample('1h').max().reindex(hourly.index).gt(2.5).tolist() if sensor in sensor_z else None
        save(DIST / f'sensors/{i}.json', {'x': times, 'y': hourly[sensor].round(3).tolist(), 'abnormal': abnormal})
    event_records = []
    for event in events.itertuples():
        selection = (model_x.index >= event.start - pd.Timedelta(hours=24)) & (model_x.index <= event.start + pd.Timedelta(hours=96))
        window = model_x.loc[selection]
        aligned_scores = scores.reindex(window.index)
        event_metrics = detections[detections['pipe'] == event.pipe].to_dict('records')
        record = {'pipe': event.pipe, 'start': str(event.start), 'end': str(event.end), 'type': event.type,
                  'peak': str(event.peak), 'year': event.start.year, 'detections': event_metrics,
                  'file': f'events/{event.pipe}.json'}
        event_records.append(record)
        save(DIST / record['file'], {'x': window.index.strftime('%Y-%m-%dT%H:%M:%S').tolist(),
             'measurements': {c: window[c].round(3).tolist() for c in window if c.startswith(('pressure:', 'flow:', 'level:'))},
             'scores': {c: aligned_scores[c].round(5).tolist() for c in aligned_scores},
             'sensor_z': {c: sensor_z[c].reindex(window.index).round(3).tolist() for c in sensor_z}})
    daily = telemetry.filter(regex=r'^(flow:|pressure:)').resample('D').mean()
    profiles = pd.read_csv(RESULTS / 'hourly_profiles.csv')
    weekday_profiles = pd.read_csv(RESULTS / 'weekday_profiles.csv')
    weekly = telemetry.filter(regex=r'^(flow:|pressure:)').resample('W').mean()
    save(DIST / 'data.json', {'insights': insights, 'sensors': sensors, 'events': event_records,
         'metrics': metrics.to_dict('records'), 'thresholds': experiment['thresholds'],
         'experiment': {k: v for k, v in experiment.items() if k != 'training_feature_medians'},
         'topology': json.loads((RESULTS / 'topology.json').read_text()),
         'correlation': {'labels': correlations.columns.tolist(), 'z': correlations.values.tolist()},
         'daily': {'x': daily.index.strftime('%Y-%m-%d').tolist(), 'series': daily.round(3).to_dict('list')},
         'profiles': profiles.round(3).to_dict('list'),
         'weekday_profiles': weekday_profiles.round(3).to_dict('list'),
         'weekly': {'x': weekly.index.strftime('%Y-%m-%d').tolist(), 'series': weekly.round(3).to_dict('list')}})
    figure_dir = RESULTS / 'figures'
    figure_dir.mkdir(exist_ok=True)
    def html(fig, filename):
        fig.write_html(figure_dir / filename, include_plotlyjs=True, full_html=True)
    # A few informative plots, not a plot for every possible sensor pair.
    fig = go.Figure()
    for sensor in ['flow:p227', 'flow:p235', 'flow:PUMP_1']:
        fig.add_trace(go.Scatter(x=profiles.hour, y=profiles[sensor], name=sensor, mode='lines'))
    html(style(fig, 'How does metered flow change through the day?', 'Flow (m3/h)'), 'hourly_flow.html')
    fig = go.Figure(go.Heatmap(z=correlations, x=correlations.columns, y=correlations.index,
                             colorscale='RdBu', zmin=-1, zmax=1, reversescale=True))
    html(style(fig, 'Which pressure and flow sensors move together?'), 'correlations.html')
    fig = go.Figure()
    for method in metrics.method:
        row = metrics[metrics.method == method].iloc[0]
        fig.add_trace(go.Bar(name=method, x=['Point F1', 'Event recall'], y=[row.f1, row.event_recall]))
    html(style(fig, 'New-onset detection on the untouched 2019 test year'), 'model_comparison.html')
    fig = go.Figure()
    for method, group in detections.groupby('method'):
        fig.add_trace(go.Box(y=group.delay_hours.dropna(), name=method, boxpoints='all'))
    html(style(fig, 'How long did detected events take to confirm?', 'Delay (hours); detected events only'), 'detection_delays.html')
    selected = events[events['pipe'] == 'p523'].iloc[0]
    window = model_x.loc[selected.start - pd.Timedelta(hours=24):selected.start + pd.Timedelta(hours=96)]
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=.08)
    fig.add_trace(go.Scatter(x=window.index, y=window['pressure:n1'], name='Pressure n1'), row=1, col=1)
    fig.add_trace(go.Scatter(x=window.index, y=window['flow:p227'], name='Flow p227'), row=2, col=1)
    for method in ['Robust baseline', 'PCA reconstruction']:
        fig.add_trace(go.Scatter(x=window.index, y=scores[method].reindex(window.index), name=method), row=3, col=1)
    # Different score scales are intentionally separate in the interactive dashboard.
    fig.data = fig.data[:3]
    fig.add_hline(y=experiment['thresholds']['Robust baseline']['threshold'], line_dash='dash', row=3, col=1)
    fig.add_vline(x=selected.start.timestamp() * 1000, line_color='#bb791e', line_dash='dot')
    style(fig, 'p523: measurements and robust-baseline score around an abrupt onset')
    fig.update_layout(height=800)
    fig.update_yaxes(title_text='Pressure (m)', row=1, col=1)
    fig.update_yaxes(title_text='Flow (m3/h)', row=2, col=1)
    fig.update_yaxes(title_text='Anomaly score', row=3, col=1)
    html(fig, 'event_p523.html')
    # Selected pairwise relationship and monthly trends are also exported.
    sample = telemetry.loc['2019'].iloc[::48]
    fig = go.Figure(go.Scattergl(x=sample['flow:p227'], y=sample['pressure:n1'], mode='markers',
                 marker={'size': 4, 'opacity': .35}, name='Every fourth hour, 2019'))
    style(fig, 'Pressure n1 versus flow p227', 'Pressure (m)')
    fig.update_xaxes(title='Flow (m3/h)')
    html(fig, 'pressure_flow.html')
    # Notebooks are executable analysis entry points, backed by reusable modules.
    import nbformat as nbf
    notebook_specs = [
        ('01_data_understanding', 'Inspect the official files and data dictionary',
         "audit = json.loads((ROOT/'results/data_audit.json').read_text())\npd.DataFrame(audit).T",
         "pd.read_csv(ROOT/'results/data_dictionary.csv').head(12)"),
        ('02_exploratory_analysis', 'Operating patterns, correlation and event comparisons',
         "profiles = pd.read_csv(ROOT/'results/hourly_profiles.csv')\npx.line(profiles, x='hour', y=['flow:p227','flow:p235','flow:PUMP_1'])",
         "correlation = pd.read_csv(ROOT/'results/correlations.csv', index_col=0)\npx.imshow(correlation, zmin=-1, zmax=1, color_continuous_scale='RdBu_r')"),
        ('03_feature_engineering', 'Inspect causal features and training masks',
         "from waterleak.features import aggregate, causal_features\nx = pd.read_parquet(ROOT/'data/processed/telemetry.parquet')\nf, residual = causal_features(aggregate(x))\nf[['pressure:n1|residual','flow:p227|residual']].describe()",
         "pd.read_csv(ROOT/'results/feature_distributions.csv')"),
        ('04_model_experiments', 'Compare frozen models on the 2019 holdout',
         "pd.read_csv(ROOT/'results/model_comparison.csv')",
         "pd.read_csv(ROOT/'results/event_detections.csv').query('method == \"Robust baseline\"')")]
    for name, title, cell1, cell2 in notebook_specs:
        nb = nbf.v4.new_notebook(cells=[nbf.v4.new_markdown_cell(f'# {title}\n\nRun `scripts/run_pipeline.py` first. Read `docs/methodology.md` for the onset task, contaminated stable-operation baseline and chronological split.'),
            nbf.v4.new_code_cell("from pathlib import Path\nimport sys, json\nimport pandas as pd\nimport plotly.express as px\nROOT = Path.cwd() if (Path.cwd()/'results').exists() else Path.cwd().parent\nsys.path.insert(0, str(ROOT/'src'))"),
            nbf.v4.new_code_cell(cell1), nbf.v4.new_code_cell(cell2)])
        nb.metadata['kernelspec'] = {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'}
        (ROOT / 'notebooks').mkdir(exist_ok=True)
        nbf.write(nb, ROOT / f'notebooks/{name}.ipynb')
    print(f'Exported {len(sensors)} sensor histories, {len(events)} event windows and {len(list(figure_dir.glob("*.html")))} figures')

if __name__ == '__main__':
    export()

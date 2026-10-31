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
from sklearn.metrics import precision_recall_curve
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from waterleak.data import read_events
from waterleak.evaluation import onset_labels

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
    features = pd.read_parquet(ROOT / 'data/processed/features.parquet')
    events = read_events(ROOT / 'data/raw')
    detections = pd.read_csv(RESULTS / 'event_detections.csv')
    metrics = pd.read_csv(RESULTS / 'model_comparison.csv')
    experiment = json.loads((RESULTS / 'experiment.json').read_text())
    pr_curves, pr_rows = {}, []
    test = scores.loc['2019']
    labels = onset_labels(test.index, events, experiment['config']['onset_horizon_hours'])
    for method in test:
        valid = test[method].notna()
        precision, recall, _ = precision_recall_curve(labels[valid], test.loc[valid, method])
        selected_points = np.unique(np.linspace(0, len(recall) - 1, min(500, len(recall))).astype(int))
        pr_curves[method] = {'precision': precision[selected_points].tolist(), 'recall': recall[selected_points].tolist()}
        pr_rows.extend({'method': method, 'precision': float(precision[j]), 'recall': float(recall[j])} for j in selected_points)
    pd.DataFrame(pr_rows).to_csv(RESULTS / 'precision_recall_curves.csv', index=False)
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
         'experiment': {k: v for k, v in experiment.items() if k not in ['training_feature_medians', 'estimator_fit_row_positions', 'threshold_reference_row_positions']},
         'pr_curves': pr_curves,
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
    html(style(fig, 'New-onset detection on the chronological 2019 benchmark'), 'model_comparison.html')
    fig = go.Figure()
    for method, curve in pr_curves.items():
        fig.add_trace(go.Scatter(x=curve['recall'], y=curve['precision'], mode='lines', name=method))
    fig.add_hline(y=float(labels.mean()), line_dash='dash', line_color='#69737b')
    style(fig, 'How much precision is retained as recall increases?', 'Precision')
    fig.update_xaxes(title='Recall', range=[0, 1])
    fig.update_yaxes(range=[0, 1])
    html(fig, 'precision_recall.html')
    fig = go.Figure()
    for method, group in detections.groupby('method', sort=False):
        matched = group.dropna(subset=['detected_at'])
        fig.add_trace(go.Scatter(x=matched.detected_at, y=matched['pipe'], name=method,
                                mode='markers', marker={'size': 7}))
    test_events = events[events.start.dt.year.eq(2019)]
    fig.add_trace(go.Scatter(x=test_events.start, y=test_events['pipe'], mode='markers', name='Known onset',
                            marker={'symbol': 'line-ns', 'size': 14, 'color': '#303a40'}))
    style(fig, 'When are new onsets and matched alarm confirmations observed?')
    fig.update_layout(height=640)
    html(fig, 'event_timeline.html')
    fig = make_subplots(rows=2, cols=1, subplot_titles=['Pressure n1 daily residual (m)', 'Flow p227 daily residual (m³/h)'])
    fitting = features.iloc[experiment['estimator_fit_row_positions']]
    for row, column in enumerate(['pressure:n1|residual', 'flow:p227|residual'], start=1):
        for split, frame, colour in [('Estimator fit', fitting, '#69737b'), ('2019 benchmark', features.loc['2019'], '#087782')]:
            fig.add_trace(go.Histogram(x=frame[column].dropna(), name=split, legendgroup=split, showlegend=row == 1,
                histnorm='probability density', nbinsx=80, opacity=.55, marker_color=colour), row=row, col=1)
    style(fig, 'How do feature distributions shift between fitting and 2019?')
    fig.update_layout(barmode='overlay', height=680)
    html(fig, 'feature_distributions.html')
    fig = go.Figure()
    for method, group in detections.groupby('method'):
        fig.add_trace(go.Box(y=group.delay_hours.dropna(), name=method, boxpoints='all'))
    html(style(fig, 'How long did detected events take to confirm?', 'Delay (hours); detected events only'), 'detection_delays.html')
    selected = events[events['pipe'] == 'p523'].iloc[0]
    window = model_x.loc[selected.start - pd.Timedelta(hours=24):selected.start + pd.Timedelta(hours=96)]
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=.08)
    fig.add_trace(go.Scatter(x=window.index, y=window['pressure:n1'], name='Pressure n1'), row=1, col=1)
    fig.add_trace(go.Scatter(x=window.index, y=window['flow:p227'], name='Flow p227'), row=2, col=1)
    fig.add_trace(go.Scatter(x=window.index, y=scores['Robust baseline'].reindex(window.index), name='Robust baseline'), row=3, col=1)
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
    from waterleak.notebooks import write_notebooks
    write_notebooks(ROOT)
    print(f'Exported {len(sensors)} sensor histories, {len(events)} event windows and {len(list(figure_dir.glob("*.html")))} figures')

if __name__ == '__main__':
    export()

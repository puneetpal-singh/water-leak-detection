"""Check source provenance, evaluation consistency and every browser sensor export."""
from pathlib import Path
import json
import sys
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from waterleak.data import verify_sources, read_events
from waterleak.evaluation import evaluate

ROOT = Path(__file__).resolve().parents[1]

def verify() -> None:
    results, processed, web = ROOT / 'results', ROOT / 'data/processed', ROOT / 'dashboard/web/dist'
    source = verify_sources(ROOT / 'data/raw')
    assert source == json.loads((processed / 'source_checksums.json').read_text()), 'Derived source manifest is stale'
    x = pd.read_parquet(processed / 'telemetry.parquet')
    assert x.shape == (210240, 119) and x.index.is_unique
    assert x.index.to_series().diff().dropna().eq(pd.Timedelta('5min')).all()
    scores = pd.read_parquet(processed / 'scores.parquet')
    activity = pd.read_parquet(processed / 'activity.parquet')
    experiment = json.loads((results / 'experiment.json').read_text())
    fit = scores.index[experiment['estimator_fit_row_positions']]
    reference = scores.index[experiment['threshold_reference_row_positions']]
    assert fit.intersection(reference).empty and fit.max() < reference.min()
    assert reference.max() < pd.Timestamp(experiment['config']['train_end'])
    calibration = pd.read_csv(results / 'validation_calibration.csv')
    for row in calibration.itertuples():
        np.testing.assert_allclose(row.threshold, scores.loc[reference, row.method].quantile(row.quantile), rtol=1e-10)
    metrics = pd.read_csv(results / 'model_comparison.csv')
    episodes = pd.read_csv(results / 'alarm_episodes.csv', parse_dates=['start', 'end'])
    detections = pd.read_csv(results / 'event_detections.csv', parse_dates=['start', 'end', 'detected_at'])
    events = read_events(ROOT / 'data/raw')
    for row in metrics.itertuples():
        alarms = episodes[episodes.method.eq(row.method)]
        calculated, matched = evaluate(scores[row.method], activity[row.method], alarms, events,
                                      '2019-01-01', '2020-01-01', experiment['config']['onset_horizon_hours'])
        for name, value in calculated.items():
            if value is not None:
                np.testing.assert_allclose(getattr(row, name), value, rtol=1e-10, err_msg=f'{row.method}: {name}')
        exported = detections[detections.method.eq(row.method)].sort_values('start')
        assert len(exported) == len(matched) == 19
        pd.testing.assert_series_equal(exported.detected_at.reset_index(drop=True), matched.detected_at.reset_index(drop=True), check_names=False)
        confirmed = exported.detected_at.dropna()
        assert confirmed.is_unique and confirmed.isin(alarms.start).all()
        candidates = calibration[calibration.method.eq(row.method)]
        selected = candidates.sort_values(['event_f1', 'false_alarms', 'quantile'], ascending=[False, True, False]).iloc[0]
        np.testing.assert_allclose(row.threshold, selected.threshold)
    payload = json.loads((web / 'data.json').read_text())
    assert len(payload['sensors']) == 119 and len(payload['events']) == 33
    assert payload['experiment']['protocol_version'] == 2
    assert payload['insights']['measurement_cells'] == x.size
    for method, threshold in experiment['thresholds'].items():
        np.testing.assert_allclose(payload['thresholds'][method]['threshold'], threshold['threshold'], atol=0.0000051, rtol=0)
    hourly = x.resample('1h').mean()
    for sensor in payload['sensors']:
        exported = json.loads((web / sensor['file']).read_text())
        assert exported['x'] == hourly.index.strftime('%Y-%m-%dT%H:%M:%S').tolist()
        np.testing.assert_allclose(np.array(exported['y'], dtype=float), hourly[sensor['id']].to_numpy(),
                                   atol=0.000501, rtol=0, equal_nan=True)
    for event in payload['events']:
        window = json.loads((web / event['file']).read_text())
        assert len(window['x']) == len(next(iter(window['scores'].values())))
        assert set(window['scores']) == set(scores.columns)
        if event['year'] == 2019:
            assert len(event['detections']) == len(metrics)
    (results / 'verification.json').write_text(json.dumps({
        'protocol_version': 2, 'verified_sources': len(source), 'source_shape': list(x.shape),
        'estimator_fit_rows': len(fit), 'unseen_reference_rows': len(reference),
        'model_metric_rows_verified': len(metrics), 'event_detection_rows_verified': len(detections),
        'sensor_exports_verified': len(payload['sensors']), 'event_windows_verified': len(payload['events']),
        'status': 'passed'}, indent=2), encoding='utf-8')
    print('PASS: source checksums, fit/reference separation, calibration, metrics, event matching, 119 sensor histories and 33 event exports')

if __name__ == '__main__':
    verify()

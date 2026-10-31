"""Check source provenance, evaluation consistency and every browser sensor export."""
from pathlib import Path
import json
import sys
import gzip
import base64
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
    manifest = json.loads((web / 'manifest.json').read_text())
    def asset(name):
        return json.loads(gzip.decompress((web/name).read_bytes()))
    def decode_clock(value):
        clock = value['time']
        return pd.date_range(clock['start'],periods=clock['count'],freq=pd.Timedelta(seconds=clock['step_seconds']))
    payload = asset(manifest['bootstrap'])
    assert len(payload['sensors']) == 119 and len(payload['events']) == 33
    assert payload['experiment']['protocol_version'] == 2
    assert payload['insights']['measurement_cells'] == x.size
    for method, threshold in experiment['thresholds'].items():
        np.testing.assert_allclose(payload['thresholds'][method]['threshold'], threshold['threshold'], atol=0.0000051, rtol=0)
    hourly = x.resample('1h').mean()
    for sensor in payload['sensors']:
        exported = asset(sensor['file'])
        pd.testing.assert_index_equal(decode_clock(exported),hourly.index,check_names=False)
        np.testing.assert_allclose(np.array(exported['y'], dtype=float), hourly[sensor['id']].to_numpy(),
                                   atol=0.000501, rtol=0, equal_nan=True)
        if exported['abnormal_bits'] is not None:
            packed = np.frombuffer(base64.b64decode(exported['abnormal_bits']),dtype=np.uint8)
            flags = np.unpackbits(packed,bitorder='little')[:len(hourly)].astype(bool)
            z = pd.read_parquet(processed/'sensor_z.parquet',columns=[sensor['id']])
            expected = z[sensor['id']].abs().resample('1h').max().reindex(hourly.index).gt(2.5)
            np.testing.assert_array_equal(flags,expected)
    model_x = pd.read_parquet(processed/'model_measurements.parquet')
    for event in payload['events']:
        window = asset(event['file'])
        index = decode_clock(window)
        assert len(index) == len(next(iter(window['scores'].values())))
        assert set(window['scores']) == set(scores.columns)
        for sensor,values in window['measurements'].items():
            np.testing.assert_allclose(np.array(values,dtype=float),model_x[sensor].reindex(index),atol=.000501,rtol=0,equal_nan=True)
        for method,values in window['scores'].items():
            np.testing.assert_allclose(np.array(values,dtype=float),scores[method].reindex(index),atol=.00000501,rtol=0,equal_nan=True)
        if event['year'] == 2019:
            assert len(event['detections']) == len(metrics)
    (results / 'verification.json').write_text(json.dumps({
        'protocol_version': 2, 'verified_sources': len(source), 'source_shape': list(x.shape),
        'estimator_fit_rows': len(fit), 'unseen_reference_rows': len(reference),
        'model_metric_rows_verified': len(metrics), 'event_detection_rows_verified': len(detections),
        'sensor_exports_verified': len(payload['sensors']), 'event_windows_verified': len(payload['events']),
        'asset_encoding': 'gzip JSON, regular time grids, packed anomaly flags',
        'status': 'passed'}, indent=2), encoding='utf-8')
    print('PASS: source checksums, fit/reference separation, calibration, metrics, event matching, 119 sensor histories and 33 event exports')

if __name__ == '__main__':
    verify()

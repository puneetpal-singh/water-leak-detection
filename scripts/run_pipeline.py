"""Run the chronological experiment and export reviewable tables and dashboards."""
from pathlib import Path
import json
import logging
import sys
import time
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from waterleak.data import read_events, prepare
from waterleak.features import aggregate, causal_features, stable_training_mask
from waterleak.models import fit_and_score
from waterleak.evaluation import alarm_episodes, evaluate, circular_alarm_control
from waterleak.analysis import analyse

ROOT = Path(__file__).resolve().parents[1]
log = logging.getLogger(__name__)

def run() -> None:
    started = time.monotonic()
    config = json.loads((ROOT / 'config.json').read_text())
    results, processed = ROOT / 'results', ROOT / 'data/processed'
    if not (processed / 'telemetry.parquet').exists():
        prepare(ROOT)
    telemetry = pd.read_parquet(processed / 'telemetry.parquet')
    truth = pd.read_parquet(processed / 'leak_truth.parquet')
    events = read_events(ROOT / 'data/raw')
    log.info('Analysing %s measurement rows', len(telemetry))
    insights = analyse(telemetry, truth, events, results)
    x = aggregate(telemetry, config['model_frequency'])
    features, residuals = causal_features(x)
    # Last partial bin remains available for plots, but not the 2019 score table.
    features = features.loc[features.index < '2020-01-01']
    fit_mask = stable_training_mask(features.index, events, config['train_end'],
                                    config['transition_exclusion_hours']) & features.notna().all(axis=1)
    if fit_mask.sum() < 100:
        raise ValueError('Too few training observations')
    log.info('Fitting 5 methods on %s stable-operation rows, %s features', fit_mask.sum(), features.shape[1])
    scores, sensor_z, metadata = fit_and_score(features, fit_mask, config['seed'], config['fit_sample_limit'])
    sensor_gate = sensor_z.abs().gt(config['sensor_z_threshold']).sum(axis=1).ge(config['minimum_sensors'])
    metrics, event_tables, alarm_tables, calibration, sensitivity = [], [], [], [], []
    activity = pd.DataFrame(index=scores.index)
    chosen = {}
    for method in scores:
        candidates = []
        for quantile in config['threshold_quantiles']:
            threshold = float(scores.loc[fit_mask, method].quantile(quantile))
            active, episodes = alarm_episodes(scores[method].gt(threshold) & sensor_gate,
                                               config['alarm_persistence'])
            validation, _ = evaluate(scores[method], active, episodes, events,
                                      config['train_end'], config['validation_end'], config['onset_horizon_hours'])
            row = {'method': method, 'quantile': quantile, 'threshold': threshold, **validation}
            calibration.append(row)
            candidates.append((validation['event_f1'], -validation['false_alarms'], quantile, threshold))
        # Validation event F1 is predeclared. Tie-break fewer alarms, then higher quantile.
        _, _, quantile, threshold = max(candidates)
        active, episodes = alarm_episodes(scores[method].gt(threshold) & sensor_gate,
                                           config['alarm_persistence'])
        test, event_table = evaluate(scores[method], active, episodes, events,
                                    '2019-01-01', '2020-01-01', config['onset_horizon_hours'])
        test.update(circular_alarm_control(episodes, events, config['seed'], hours=config['onset_horizon_hours']))
        metrics.append({'method': method, 'threshold': threshold, 'quantile': quantile, **test})
        for horizon in [24, 72, 168]:
            horizon_metrics, _ = evaluate(scores[method], active, episodes, events,
                '2019-01-01', '2020-01-01', horizon)
            sensitivity.append({'method': method, 'horizon_hours': horizon, **horizon_metrics})
        chosen[method] = {'threshold': threshold, 'quantile': quantile}
        event_table['method'] = method
        # Attributions use measurements available at alarm confirmation.
        contributors, signed = [], []
        for e in event_table.itertuples():
            if pd.isna(e.detected_at):
                contributors.append('')
                signed.append('')
            else:
                z = sensor_z.loc[e.detected_at]
                top = z.abs().nlargest(4).index
                contributors.append(', '.join(top))
                signed.append(', '.join(f'{c}={z[c]:+.2f}' for c in top))
        event_table['contributing_sensors'] = contributors
        event_table['signed_residual_z'] = signed
        event_tables.append(event_table)
        episodes['method'] = method
        alarm_tables.append(episodes)
        activity[method] = active
        log.info('%s: %s/%s events, %s false onset alarms, mean delay %s h', method,
                 test['leaks_detected'], test['leaks_total'], test['false_alarms'], test['mean_delay_hours'])
    comparison = pd.DataFrame(metrics)
    comparison.to_csv(results / 'model_comparison.csv', index=False)
    pd.DataFrame(sensitivity).to_csv(results / 'horizon_sensitivity.csv', index=False)
    pd.DataFrame(calibration).to_csv(results / 'validation_calibration.csv', index=False)
    pd.concat(event_tables).to_csv(results / 'event_detections.csv', index=False)
    pd.concat([a for a in alarm_tables if len(a)]).to_csv(results / 'alarm_episodes.csv', index=False)
    scores.to_parquet(processed / 'scores.parquet')
    activity.to_parquet(processed / 'activity.parquet')
    sensor_z.to_parquet(processed / 'sensor_z.parquet')
    x.to_parquet(processed / 'model_measurements.parquet')
    features.to_parquet(processed / 'features.parquet')
    # Distributions compare the frozen training and test feature sets.
    selected = ['pressure:n1|residual', 'flow:p227|residual', 'pressure:n1|std_1h', 'flow:p235|difference_1h']
    feature_stats = []
    for split, mask in [('train', fit_mask), ('test', features.index >= pd.Timestamp('2019-01-01'))]:
        table = features.loc[mask, selected].describe(percentiles=[.05, .5, .95]).T.reset_index(names='feature')
        table['split'] = split
        feature_stats.append(table)
    pd.concat(feature_stats).to_csv(results / 'feature_distributions.csv', index=False)
    metadata.update({'config': config, 'thresholds': chosen, 'duration_seconds': time.monotonic() - started,
                     'training_start': str(features.loc[fit_mask].index.min()),
                     'training_last': str(features.loc[fit_mask].index.max()),
                     'training_state': 'stable operation; may contain ongoing background leaks'})
    (results / 'experiment.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    (results / 'insights.json').write_text(json.dumps(insights, indent=2), encoding='utf-8')
    log.info('Experiment complete in %.1f seconds', time.monotonic() - started)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    run()
